# Copyright (C) 2015-2025 East Asian Observatory
# All Rights Reserved.
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful,but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,51 Franklin
# Street, Fifth Floor, Boston, MA  02110-1301, USA

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from collections import defaultdict, namedtuple, OrderedDict
from datetime import datetime, timedelta
from itertools import chain
import re
import warnings

from astropy.time import Time
from astropy.coordinates import AltAz, ICRS, SkyCoord
from astropy import units
from astropy.utils.exceptions import AstropyWarning
from numpy import arange, newaxis, nonzero

from ...admin.proposal import finalize_call_review
from ...astro.coord import get_earth_location
from ...email.format import render_email_template
from ...error import DatabaseIntegrityError, NoSuchRecord, NoSuchValue, \
    UserError
from ...file.csv import CSVWriter
from ...file.pdf import pdf_to_svg
from ...stats.table import table_mean_stdev
from ...view import auth
from ...view.util import int_or_none, float_or_none, \
    with_proposal, with_call_review, with_review
from ...web.util import ErrorPage, \
    HTTPError, HTTPForbidden, HTTPNotFound, HTTPRedirect, \
    flash, format_datetime, parse_datetime, url_for
from ...type.collection import AffiliationCollection, MemberCollection, \
    ReviewerCollection, ReviewDeadlineCollection
from ...type.enum import Assessment, \
    FigureType, FormatType, GroupType, \
    MessageThreadType, PermissionType, PersonTitle, \
    ProposalState, ProposalType, ReviewState
from ...type.simple import Affiliation, DateAndTime, Link, MemberPIInfo, \
    Note, \
    ProposalWithCode, Reviewer, ReviewerAcceptance, \
    ReviewFigureInfo, ReviewDeadline
from ...type.util import null_tuple, \
    with_can_edit, with_can_view, with_can_view_edit, \
    with_can_view_edit_rating, with_proposals
from ...util import lower_except_abbr


ProposalWithExtraPermissions = namedtuple(
    'ProposalWithExtraPermissions',
    ProposalWithCode._fields + (
        'can_view_review', 'can_edit_decision'))

ProposalWithInviteRoles = namedtuple(
    'ProposalWithInviteRoles',
    ProposalWithExtraPermissions._fields + ('invite_roles', 'add_roles'))

ProposalWithReviewerPersons = namedtuple(
    'ProposalWithReviewerPersons',
    ProposalWithCode._fields + (
        'reviewer_person_ids',))

ProposalWithTargets = namedtuple(
    'ProposalWithTargets',
    ProposalWithCode._fields + (
        'targets',))

ProposalWithViewReviewLinks = namedtuple(
    'ProposalWithViewReviewLinks',
    ProposalWithCode._fields + (
        'target_proposal', 'target_review'))

ReviewerWithCalcFig = namedtuple(
    'ReviewerWithCalcFig', Reviewer._fields + (
        'calculations', 'figures', 'can_view', 'can_edit', 'can_view_rating'))

RoleClosingInfo = namedtuple(
    'RoleClosingInfo', ('role_name', 'deadline', 'future'))


class GenericReview(object):
    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call(self, current_user, db, call, can):
        role_class = self.get_reviewer_roles()
        type_class = self.get_call_types()

        # Which reviewer roles do we wish to show in the list of proposals?
        reviewer_roles = [
            x for x in [role_class.CTTEE_PRIMARY, role_class.CTTEE_SECONDARY]
            if type_class.has_reviewer_role(call.type, x)]

        proposals = []

        for proposal in db.search_proposal(
                call_id=call.id, state=ProposalState.submitted_states(),
                with_members=True, with_reviewers=bool(reviewer_roles),
                with_reviewer_role=reviewer_roles,
                with_decision=True, with_categories=True).values():
            member_pi = proposal.members.get_pi(default=None)
            if member_pi is not None:
                member_pi = with_can_view(
                    member_pi, auth.for_person_member(
                        current_user, db, member_pi,
                        auth_cache=can.cache).view)

            review_can = auth.for_review(
                role_class, current_user, db, reviewer=None, proposal=proposal,
                auth_cache=can.cache)

            decision_can = auth.for_proposal_decision(
                current_user, db, proposal, call=call, auth_cache=can.cache)

            reviewers = None
            if proposal.reviewers is not None:
                reviewers = proposal.reviewers.map_values(
                    lambda x: with_can_view(x, auth.for_person_reviewer(
                        current_user, db, x, auth_cache=can.cache).view))

            proposals.append(ProposalWithExtraPermissions(
                *proposal._replace(member=member_pi, reviewers=reviewers),
                code=self.make_proposal_code(db, proposal),
                can_view_review=review_can.view,
                can_edit_decision=decision_can.edit))

        return {
            'title': 'Review Process: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'can_edit': can.edit,
            'call_id': call.id,
            'proposals': proposals,
            'reviewer_roles': reviewer_roles,
        }

    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call_tabulation(self, current_user, db, call, can):
        type_class = self.get_call_types()

        ctx = {
            'title': 'Proposal Tabulation: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
        }

        tabulation = self._get_proposal_tabulation(current_user, db, call, can)

        n_accept = defaultdict(int)
        for proposal in tabulation['proposals']:
            n_accept[proposal['decision_accept']] += 1

        ctx['n_decision_accept'] = OrderedDict(
            (k, n_accept[k]) for k in (None, True, False)
            if k in n_accept)

        ctx.update(tabulation)

        return ctx

    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call_tabulation_download(
            self, current_user, db, call, can, with_cois=True):
        type_class = self.get_call_types()
        tabulation = self._get_proposal_tabulation(
            current_user, db, call, can, with_extra=True)

        writer = CSVWriter()

        titles = self._get_proposal_tabulation_titles(tabulation)
        if with_cois:
            titles = chain(titles, ['Co-Investigator names'])
        writer.add_row(titles)

        for (row, proposal) in zip(
                self._get_proposal_tabulation_rows(tabulation),
                tabulation['proposals']):
            if with_cois:
                row = chain(row, (
                    '{} ({})'.format(x.person_name, x.affiliation_name)
                    for x in proposal['members'].values()
                    if not x.pi))
            writer.add_row(row)

        return (
            writer.get_csv(),
            'text/csv',
            'proposals-{}-{}-{}.csv'.format(
                re.sub('[^-_a-z0-9]', '_', call.semester_name.lower()),
                re.sub('[^-_a-z0-9]', '_', call.queue_name.lower()),
                re.sub('[^-_a-z0-9]', '_', type_class.url_path(call.type))))

    def _get_proposal_tabulation(
            self, current_user, db, call, can, with_extra=False):
        """Prepare information for the detailed tabulation of proposals.

        This is used to prepare the information both for the online
        version and the downloadable CSV file.  For the CSV file, the
        `with_extra` option is enabled and additional information,
        beyond that which can be displayed on the online version,
        is retrieved.
        """

        affiliation_type_class = self.get_affiliation_types()
        role_class = self.get_reviewer_roles()

        proposals = db.search_proposal(
            call_id=call.id, state=ProposalState.submitted_states(),
            with_members=True, with_reviewers=True, with_review_info=True,
            with_decision=True, with_categories=with_extra)

        self.attach_review_extra(db, proposals)

        affiliations = db.search_affiliation(
            queue_id=call.queue_id, hidden=False, with_weight_call_id=call.id)

        proposal_list = []
        for proposal in proposals.values():
            can_view_review = auth.for_review(
                role_class, current_user, db, reviewer=None, proposal=proposal,
                auth_cache=can.cache).view

            members = proposal.members.map_values(lambda x: with_can_view(
                x, auth.for_person_member(
                    current_user, db, x, auth_cache=can.cache).view))

            member_pi = members.get_pi(default=None)

            n_other = 0
            for member in proposal.members.values():
                if (member_pi is None) or (member_pi.id != member.id):
                    n_other += 1

            # Use dictionary rather than namedtuple here so that subclasses
            # can easily add extra entries to the proposal records.
            updated_proposal = proposal._asdict()
            updated_proposal.update({
                'can_view_review': can_view_review,
                'member_pi': member_pi,
                'members_other': n_other,
                'members': members,
                'code': self.make_proposal_code(db, proposal),
                'affiliations': self.calculate_affiliation_assignment(
                    db, proposal.members, affiliations),
                'can_edit_decision': auth.for_proposal_decision(
                    current_user, db, proposal, call=call,
                    auth_cache=can.cache).edit,
            })

            if can_view_review:
                # Determine authorization for each review.  Hide ratings
                # which cannot be viewed.
                reviewers = ReviewerCollection()

                for reviewer_id, reviewer in proposal.reviewers.items():
                    reviewer_can = auth.for_review(
                        role_class, current_user, db,
                        reviewer=reviewer, proposal=proposal,
                        auth_cache=can.cache, allow_unaccepted=False)

                    reviewers[reviewer_id] = with_can_view_edit_rating(
                        reviewer,
                        auth.for_person_reviewer(
                            current_user, db, reviewer,
                            auth_cache=can.cache).view,
                        reviewer_can.edit, reviewer_can.view_rating)

                (overall_rating, std_dev) = self.calculate_overall_rating(
                    reviewers.map_values(
                        filter_value=lambda x: x.can_view_rating),
                    with_std_dev=True)

                updated_proposal.update({
                    'reviewers': reviewers,
                    'rating': overall_rating,
                    'rating_std_dev': std_dev,
                })

            else:
                # Remove 'reviewers' from dictionary for safety, so that
                # we don't have to rely on the template hiding reviews
                # which the user can't see.
                updated_proposal.update({
                    'reviewers': ReviewerCollection(),
                    'rating': None,
                    'rating_std_dev': None,
                })

            proposal_list.append(updated_proposal)

        return {
            'proposals': proposal_list,
            'affiliations':
                [x for x in affiliations.values_in_type_order(
                    affiliation_type_class)
                 if affiliation_type_class.is_tabulated(x.type)] +
                [null_tuple(Affiliation)._replace(id=0, name='Unknown')],
            'affiliation_total': {},
            'affiliation_accepted': {},
            'affiliation_available': {},
            'affiliation_original': {},
        }

    def _get_proposal_tabulation_titles(self, tabulation):
        return chain(
            [
                'Proposal', 'Type',
                'PI name', 'PI affiliation', 'PI institution',
                'Co-Investigators',
                'Title', 'State',
                'Decision', 'Exempt', 'Rating', 'Rating std. dev.',
                'Categories',
            ],
            (x.name for x in tabulation['affiliations']))

    def _get_proposal_tabulation_rows(self, tabulation):
        affiliations = tabulation['affiliations']

        for proposal in tabulation['proposals']:
            decision_accept = proposal['decision_accept']

            yield chain(
                [
                    proposal['code'],
                    ProposalType.get_short_name(proposal['type']),
                    (None if proposal['member_pi'] is None
                     else proposal['member_pi'].person_name),
                    (None if proposal['member_pi'] is None
                     else proposal['member_pi'].affiliation_name),
                    (None if proposal['member_pi'] is None
                     else proposal['member_pi'].institution_name),
                    proposal['members_other'],
                    proposal['title'],
                    ProposalState.get_name(proposal['state']),
                    (None if decision_accept is None
                     else ('Accept' if decision_accept else 'Reject')),
                    ('Exempt' if proposal['decision_exempt'] else None),
                    proposal['rating'],
                    proposal['rating_std_dev'],
                    ', '.join(x.category_name
                              for x in proposal['categories'].values()),
                ],
                [proposal['affiliations'].get(x.id) for x in affiliations])

    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call_allocation(self, current_user, db, call, can):
        type_class = self.get_call_types()

        ctx = {
            'title': 'Allocation Details: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
        }

        ctx.update(self._get_review_call_allocation(db, call, can))

        return ctx

    def _get_review_call_allocation(self, db, call, can):
        affiliation_type_class = self.get_affiliation_types()

        proposals = db.search_proposal(
            call_id=call.id, state=ProposalState.submitted_states(),
            with_members=True, with_decision=True)

        affiliations = db.search_affiliation(
            queue_id=call.queue_id, hidden=False,
            with_weight_call_id=call.id)

        affiliation_names = [
            ('{}'.format(x.id), x.name) for x in affiliations.values()
            if affiliation_type_class.is_tabulated(x.type)]

        affiliation_names.append(('0', 'Unknown'))

        proposal_list = []
        ra_bins = list(range(0, 24))
        for proposal in self._attach_proposal_targets(db, proposals).values():
            # Determine the fractional time spent in each RA bin, so that this
            # can be scaled by the proposal's allocation, which may change
            # later.  (At this level of detail we can't know whether an altered
            # allocation corresponds to excluding particular targets.)
            ra_fraction = defaultdict(float)
            for target in proposal.targets.to_frac_time_list():
                ra = int(round(target.coord.icrs.ra.hour))
                if ra > 23:
                    ra -= 24

                ra_fraction[ra] += target.frac_time

            info = {
                'id': '{}'.format(proposal.id),
                'code': proposal.code,
                'ra': [ra_fraction[x] for x in ra_bins],
                'category': {
                    'affiliation': self.calculate_affiliation_assignment(
                        db, proposal.members, affiliations),
                },
            }

            proposal_list.append(info)

        if call.multi_semester:
            ra_inaccessible = None

        else:
            semester = db.get_semester(self.id_, semester_id=call.semester_id)
            ra_inaccessible = self._get_ra_inaccessible(
                semester.date_start, semester.date_end)

        return {
            'proposals': proposal_list,
            'categories': [
                {
                    'code': 'decision',
                    'name': 'Decision',
                    'values': [
                        ('e', 'Exempt'),
                        ('a', 'Accept'),
                        ('u', 'Undecided'),
                        ('r', 'Reject'),
                    ],
                    'default': ['e', 'a'],
                },
                {
                    'code': 'affiliation',
                    'name': 'Affiliation',
                    'values': affiliation_names},
            ],
            'dynamic': self._get_review_call_allocation_dynamic(
                db, call, can, proposals),
            'ra_bins': ra_bins,
            'ra_inaccessible': ra_inaccessible,
        }

    def _get_ra_inaccessible(self, date_start, date_end):
        """
        Estimate which RAs are inaccessible in the middle of the shift
        during a semester between the given dates by considering a
        target with declination equal to the observatory's latitude.
        """

        obs_info = self.get_observing_info()
        if any(getattr(obs_info, x) is None for x in (
                'geo_x', 'geo_y', 'geo_z',
                'time_start', 'time_duration', 'el_min')):
            return None

        else:
            location = get_earth_location(obs_info)
            ras = list(range(0, 24))
            targets = SkyCoord(
                ras, [location.lat.degree] * len(ras),
                unit=(units.hourangle, units.degree), frame=ICRS)

            # Construct time in middle of shift by adding half of duration.
            datetime_start = datetime.combine(date_start, obs_info.time_start) \
                + timedelta(seconds=(obs_info.time_duration.total_seconds() / 2))

            date_range = (Time(date_end) - Time(date_start)).sec / 86400

            dates = Time(datetime_start) \
                + arange(0, date_range + 1,  15) * units.day

            frame = AltAz(location=location, obstime=dates[:, newaxis])

            with warnings.catch_warnings():
                # Ignore warning about not having the latest IERS data.
                warnings.simplefilter('ignore', AstropyWarning)

                targets = targets[newaxis, :].transform_to(frame)

            all_available = (targets.alt > (obs_info.el_min * units.deg))
            ra_available = [False] * len(ras)
            for date_available in all_available:
                for i in range(len(ras)):
                    if date_available[i]:
                        ra_available[i] = True

            ra_inaccessible = []
            inaccessible_start = None
            ra_previous = None
            for (i, ra) in enumerate(ras):
                if not ra_available[i]:
                    if inaccessible_start is None:
                        inaccessible_start = ra

                elif inaccessible_start is not None:
                    ra_inaccessible.append([inaccessible_start, ra_previous])
                    inaccessible_start = None

                ra_previous = ra

            if inaccessible_start is not None:
                ra_inaccessible.append([inaccessible_start, ra_previous])

            return ra_inaccessible

    def _attach_proposal_targets(self, db, proposals):
        """
        Attach targets (and construct codes) for the given proposals.
        """

        (proposal_ids, previous_proposal_ids) = db.get_original_proposal_ids(
            proposals)

        # Do a combined query for CRs and all the standard proposals.
        targets = db.search_target(proposal_id=proposal_ids)

        return proposals.map_values(lambda x: ProposalWithTargets(
            *x, code=self.make_proposal_code(db, x),
            targets=targets.subset_by_proposal(
                previous_proposal_ids.get(x.id, x.id))))

    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call_allocation_query(self, current_user, db, call, can):
        proposals = db.search_proposal(
            call_id=call.id, state=ProposalState.submitted_states(),
            with_decision=True)

        return self._get_review_call_allocation_dynamic(
            db, call, can, proposals)

    def _get_review_call_allocation_dynamic(self, db, call, can, proposals):
        """
        Get dynamic information, including total time (hours) for each
        proposal.

        This method should be overridden by subclasses to return the most
        suitable representative total time for each proposal.  For example
        this could be the total allocation, falling back to the total
        request if no allocation has yet been assigned.
        """

        return {
            x.id: {
                'decision': (
                    ('e' if x.decision_exempt else 'a')
                    if x.decision_accept else
                    ('u' if x.decision_accept is None else 'r')),
                'category': {},
            } for x in proposals.values()}

    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call_stats(self, current_user, db, call, can):
        type_class = self.get_call_types()

        ctx = {
            'title': 'Review Statistics: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
        }

        ctx.update(self._get_review_statistics(current_user, db, call, can))

        # Compute mean and standard deviation.
        ctx.update(zip(
            ('rating_proposal_mean', 'rating_proposal_stdev',
             'rating_person_mean', 'rating_person_stdev'),
            table_mean_stdev(
                ctx['ratings'], ctx['proposals'], ctx['persons'])))

        ctx.update(zip(
            ('weight_proposal_mean', 'weight_proposal_stdev',
             'weight_person_mean', 'weight_person_stdev'),
            table_mean_stdev(
                ctx['weights'], ctx['proposals'], ctx['persons'],
                scale_factor=100.0)))

        return ctx

    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call_stats_download(self, current_user, db, call, can):
        type_class = self.get_call_types()
        stats = self._get_review_statistics(current_user, db, call, can)

        writer = CSVWriter()

        writer.add_row(chain(
            ['Proposal'], *([
                x['name'], 'Weight'
            ] for x in stats['persons'].values())))

        for proposal in stats['proposals'].values():
            if proposal.id not in stats['ratings']:
                continue
            writer.add_row(chain(
                [proposal.code], *([
                    stats['ratings'].get(proposal.id, {}).get(x),
                    stats['weights'].get(proposal.id, {}).get(x),
                ] for x in stats['persons'].keys())))

        return (
            writer.get_csv(),
            'text/csv',
            'review-stats-{}-{}-{}.csv'.format(
                re.sub('[^-_a-z0-9]', '_', call.semester_name.lower()),
                re.sub('[^-_a-z0-9]', '_', call.queue_name.lower()),
                re.sub('[^-_a-z0-9]', '_', type_class.url_path(call.type))))

    def _get_review_statistics(self, current_user, db, call, can):
        role_class = self.get_reviewer_roles()

        proposals = db.search_proposal(
            call_id=call.id, state=ProposalState.submitted_states(),
            with_members=True, with_reviewers=True, with_review_info=True
        ).map_values(lambda x: ProposalWithCode(
            *x, code=self.make_proposal_code(db, x)))

        self.attach_review_extra(db, proposals)

        # Create dictionary of proposals by peer reviewer person IDs.
        peer_reviewer_proposals = defaultdict(list)
        for proposal in proposals.values():
            member = proposal.members.get_reviewer(default=None)
            if member is not None:
                peer_reviewer_proposals[member.person_id].append({
                    'id': proposal.id,
                    'code': proposal.code,
                })

        persons = {}
        ratings = defaultdict(dict)
        weights = defaultdict(dict)

        rating_weight = self.get_review_rating_weight_function()

        for proposal in proposals.values():
            if not auth.for_review(
                    role_class, current_user, db,
                    reviewer=None, proposal=proposal,
                    auth_cache=can.cache).view:
                continue

            for reviewer in proposal.reviewers.values():
                if not auth.for_review(
                        role_class, current_user, db,
                        reviewer=reviewer, proposal=proposal,
                        auth_cache=can.cache,
                        allow_unaccepted=False).view_rating:
                    continue

                (rating, weight) = rating_weight(reviewer)
                if (rating is None) or (weight is None):
                    continue

                person_id = reviewer.person_id
                if person_id not in persons:
                    persons[person_id] = {
                        'id': reviewer.person_id,
                        'name': reviewer.person_name,
                        'can_view': auth.for_person_reviewer(
                            current_user, db, reviewer,
                            auth_cache=can.cache).view,
                    }

                ratings[proposal.id][person_id] = rating
                weights[proposal.id][person_id] = weight

        return {
            'proposals': proposals,
            'persons': OrderedDict(sorted(
                persons.items(), key=(lambda x: x[1]['name']))),
            'peer_reviewer_proposals': peer_reviewer_proposals,
            'ratings': ratings,
            'weights': weights,
        }

    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call_clash(self, current_user, db, call, can, args, form):
        type_class = self.get_call_types()

        # Currently we use the "Clash Tool" target tool to perform the
        # clash search, so locate this tool.  However this is not necessary
        # and the relevant functionality could be extracted if it is
        # required to perform this search in a facility without this tool.
        for tool_info in self.target_tools.values():
            if tool_info.code == 'clash':
                tool = tool_info.tool
                break
        else:
            raise ErrorPage('Clash tool not available.')

        proposals = None
        if form is not None:
            proposals = db.search_proposal(
                call_id=call.id, state=ProposalState.submitted_states())

            proposals = self._attach_proposal_targets(db, proposals)

        ctx = {
            'title': 'Clash Search: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
        }

        ctx.update(tool.search_between_proposals(
            current_user, db, proposals, args, form))

        return ctx

    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call_clash_pair(
            self, current_user, db, call, can,
            proposal_a_id, proposal_b_id, args):
        type_class = self.get_call_types()

        for tool_info in self.target_tools.values():
            if tool_info.code == 'clash':
                tool = tool_info.tool
                break
        else:
            raise ErrorPage('Clash tool not available.')

        proposals = db.search_proposal(
            call_id=call.id, proposal_id=(proposal_a_id, proposal_b_id))

        if len(proposals) != 2:
            raise ErrorPage('The selected proposals could not be found.')

        proposals = self._attach_proposal_targets(db, proposals)

        ctx = {
            'title': 'Target Clash: {} and {}'.format(
                *(x.code for x in proposals.values())),
            'call': call,
        }

        ctx.update(tool.search_proposal_pair(
            current_user, db, proposals, args))

        return ctx

    @with_call_review(permission=PermissionType.EDIT)
    def view_review_affiliation_weight(
            self, current_user, db, call, can, form):
        affiliation_type_class = self.get_affiliation_types()
        type_class = self.get_call_types()
        message = None

        affiliations = db.search_affiliation(
            queue_id=call.queue_id,
            with_weight_call_id=call.id, with_weight_separate=True)

        try:
            note = db.get_affiliation_weight_note(call_id=call.id)
            note_exists = True
        except NoSuchRecord:
            note = Note(text='', format=FormatType.PLAIN)
            note_exists = False

        if form is not None:
            try:
                for (id_, affiliation) in list(affiliations.items()):
                    assert id_ == affiliation.id
                    hidden_field = 'hidden_{}'.format(id_)
                    affiliations[id_] = affiliation._replace(
                        weight=null_tuple(Affiliation)._replace(
                            id=id_,
                            name=affiliation.name,
                            weight=float_or_none(form['weight_{}'.format(id_)]),
                            hidden=((
                                None if form[hidden_field] == 'indeterminate'
                                else True
                            ) if hidden_field in form else False),
                            type=int_or_none(form['type_{}'.format(id_)]),
                        ))

                note = Note(
                    text=form['note'],
                    format=int(form['note_format']))

                updated_affiliations = AffiliationCollection()
                for affiliation in affiliations.values():
                    weight = affiliation.weight

                    hidden = (
                        affiliation.hidden
                        if weight.hidden is None else weight.hidden)
                    tabulated = affiliation_type_class.is_tabulated(
                        affiliation.type
                        if weight.type is None else weight.type)

                    if tabulated and (weight.weight is None) and not hidden:
                        raise UserError(
                            'Affiliation "{}" has no weight.',
                            affiliation.name)
                    elif (hidden or not tabulated) and (weight.weight is not None):
                        raise UserError(
                            'Affiliation "{}" should not have a weight.',
                            affiliation.name)

                    if not ((weight.weight is not None)
                            or (weight.hidden is not None)
                            or (weight.type is not None)):
                        continue

                    updated_affiliations[affiliation.id] = weight

                updates = db.sync_affiliation_weight(
                    affiliation_type_class,
                    call_id=call.id, records=updated_affiliations)

                if note.text:
                    db.set_affiliation_weight_note(
                        call_id=call.id, note=note.text, format_=note.format)
                elif note_exists:
                    db.delete_affiliation_weight_note(call_id=call.id)

                if any(updates):
                    flash('The affiliation weights have been updated.')
                raise HTTPRedirect(url_for('.review_call', call_id=call.id))

            except UserError as e:
                message = e.message

        return {
            'title': 'Affiliation Weight: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
            'message': message,
            'affiliations': affiliations,
            'affiliation_types': affiliation_type_class.get_options(),
            'note': note,
        }

    @with_call_review(permission=PermissionType.EDIT)
    def view_review_call_available(self, current_user, db, call, can, form):
        type_class = self.get_call_types()

        extra_info = None
        message = None

        try:
            note = db.get_available_note(call_id=call.id)
            note_exists = True
        except NoSuchRecord:
            note = Note(text='', format=FormatType.PLAIN)
            note_exists = False

        if form is not None:
            try:
                extra_info = self._view_review_call_available_get(
                    db, call, form)

                note = Note(
                    text=form['note'],
                    format=int(form['note_format']))

                self._view_review_call_available_save(
                    db, call, extra_info)

                if note.text:
                    db.set_available_note(
                        call_id=call.id, note=note.text, format_=note.format)
                elif note_exists:
                    db.delete_available_note(call_id=call.id)

                raise HTTPRedirect(url_for('.review_call', call_id=call.id))

            except UserError as e:
                message = e.message

        ctx = {
            'title': 'Time Available: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
            'note': note,
            'message': message,
        }

        ctx.update(self._view_review_call_available_extra(
            db, call, extra_info))

        return ctx

    def _view_review_call_available_get(self, db, call, form):
        return None

    def _view_review_call_available_save(self, db, call, info):
        pass

    def _view_review_call_available_extra(self, db, call, info):
        return {}

    @with_call_review(permission=PermissionType.EDIT)
    def view_review_call_deadline(self, current_user, db, call, can, form):
        type_class = self.get_call_types()
        role_class = self.get_reviewer_roles()
        message = None

        deadlines = db.search_review_deadline(call_id=call.id).map_values(
            lambda x: x._replace(date=format_datetime(x.date)))

        if form is not None:
            try:
                updated_records = {}
                added_records = {}

                for role_id in role_class.get_options():
                    date = DateAndTime(
                        form.get('date_date_{}'.format(role_id), ''),
                        form.get('date_time_{}'.format(role_id), ''))

                    if date.date == '' and date.time == '':
                        continue

                    record = deadlines.get_role(role_id, default=None)

                    if record is None:
                        added_records[role_id] = null_tuple(
                            ReviewDeadline)._replace(role=role_id, date=date)
                    else:
                        updated_records[record.id] = record._replace(date=date)

                deadlines = ReviewDeadlineCollection.organize_collection(
                    updated_records, added_records)

                parsed = deadlines.map_values(
                    lambda x: x._replace(date=parse_datetime(x.date)))

                db.sync_call_review_deadline(role_class, call.id, parsed)

                flash('The review deadlines have been saved.')
                raise HTTPRedirect(url_for('.review_call', call_id=call.id))

            except UserError as e:
                message = e.message

        return {
            'title': 'Review Deadlines: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
            'message': message,
            'deadlines': deadlines,
        }

    @with_call_review(permission=PermissionType.EDIT)
    def view_review_call_reviewers(self, current_user, db, call, can, args):
        role_class = self.get_reviewer_roles()
        type_class = self.get_call_types()

        role = args.get('role', None)
        if not role:
            role = None
        else:
            role = int(role)

        state = args.get('state', None)
        if not state:
            state = None
        else:
            state = int(state)

        proposal_type = args.get('type', None)
        if not proposal_type:
            proposal_type = None
        else:
            proposal_type = int(proposal_type)

        proposals = []
        invite_roles = [x for x in role_class.get_invited_roles()
                        if type_class.has_reviewer_role(call.type, x)]
        thanked_roles = [x for x in role_class.get_thanked_roles()
                         if type_class.has_reviewer_role(call.type, x)]
        assigned_roles = OrderedDict((
            (role_num, group)
            for (role_num, group) in role_class.get_assigned_roles().items()
            if type_class.has_reviewer_role(call.type, role_num)))
        unnotified_roles = defaultdict(int)
        unthanked_roles = defaultdict(int)
        state_editable_roles = {}
        type_excluded_roles = {}

        for proposal in db.search_proposal(
                call_id=call.id, state=ProposalState.submitted_states(),
                type_=proposal_type,
                with_members=True, with_reviewers=True,
                with_review_info=True, with_reviewer_note=True,
                with_reviewer_role=role, with_review_state=state).values():
            roles = state_editable_roles.get(proposal.state)
            if roles is None:
                roles = role_class.get_editable_roles(proposal.state)
                state_editable_roles[proposal.state] = roles
            excluded_roles = type_excluded_roles.get(proposal.type)
            if excluded_roles is None:
                excluded_roles = ProposalType.get_excluded_roles(
                    proposal.type)
                type_excluded_roles[proposal.type] = excluded_roles

            member_pi = proposal.members.get_pi(default=None)
            if member_pi is not None:
                member_pi = with_can_view(member_pi, auth.for_person_member(
                    current_user, db, member_pi, auth_cache=can.cache).view)

            proposals.append(ProposalWithInviteRoles(
                *proposal._replace(
                    member=member_pi,
                    reviewers=proposal.reviewers.map_values(
                        lambda x: with_can_view_edit(
                            x,
                            can_view=auth.for_person_reviewer(
                                current_user, db, x,
                                auth_cache=can.cache).view,
                            can_edit=(x.role in roles)))),
                invite_roles=[
                    x for x in invite_roles
                    if x in roles and x not in excluded_roles],
                add_roles=auth.can_add_review_roles(
                    type_class, role_class, current_user, db, proposal,
                    auth_cache=can.cache),
                code=self.make_proposal_code(db, proposal),
                can_view_review=auth.for_review(
                    role_class, current_user, db, None, proposal,
                    auth_cache=can.cache).view,
                can_edit_decision=None))

            for reviewer in proposal.reviewers.values():
                if ((reviewer.role in assigned_roles)
                        and (reviewer.role in roles)
                        and (not reviewer.notified)):
                    unnotified_roles[reviewer.role] += 1

                if ((reviewer.role in thanked_roles)
                        and (reviewer.review_state == ReviewState.DONE)
                        and (reviewer.thanked is False)):
                    unthanked_roles[reviewer.role] += 1

        return {
            'title': 'Reviewers: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
            'proposals': proposals,
            'types': ProposalType.get_options(),
            'roles': role_class.get_options(),
            'states': ReviewState.get_options(),
            'current_type': proposal_type,
            'current_role': role,
            'current_state': state,
            'assigned_roles': assigned_roles,
            'unnotified_roles': unnotified_roles,
            'unthanked_roles': unthanked_roles,
            'all_invite_roles': invite_roles,
        }

    @with_call_review(permission=PermissionType.EDIT)
    def view_reviewer_grid(
            self, current_user, db, call, can, primary_role, form):
        role_class = self.get_reviewer_roles()
        type_class = self.get_call_types()

        # Dictionaries of roles which we are processing and roles which
        # conflict with them.
        roles = OrderedDict((
            (primary_role, role_class.get_info(primary_role)),))
        roles_conflict = {}

        if not type_class.has_reviewer_role(call.type, primary_role):
            raise ErrorPage('Reviewer role is not expected for this call.')

        group_type = role_class.get_review_group(primary_role)

        if group_type is None:
            raise ErrorPage('Reviewer role is not assigned.')

        # Special case for the committee primary role: also assign secondary.
        if primary_role == role_class.CTTEE_PRIMARY:
            roles[role_class.CTTEE_SECONDARY] = role_class.get_info(
                role_class.CTTEE_SECONDARY)
            roles_conflict[role_class.CTTEE_OTHER] = role_class.get_info(
                role_class.CTTEE_OTHER)

        # All roles to consider: those we are processing plus those
        # which may conflict with them.
        all_roles = set(roles.keys())
        all_roles.update(roles_conflict.keys())

        # Retrieve proposals.
        def augment_proposal(proposal):
            # Emulate search_proposal(with_member_pi=True) behaviour by setting
            # the "member" attribute to just the PI.
            member_pi = proposal.members.get_pi(default=None)
            if member_pi is not None:
                proposal = proposal._replace(member=with_can_view(
                    member_pi, auth.for_person_member(
                        current_user, db, member_pi,
                        auth_cache=can.cache).view))

            return ProposalWithReviewerPersons(
                *proposal, code=self.make_proposal_code(db, proposal),
                reviewer_person_ids={role_id: {
                    x.person_id: ReviewState.is_present(x.review_state)
                    for x in proposal.reviewers.values_by_role(role_id)}
                    for role_id in all_roles})

        type_excluded_roles = {}
        def filter_proposal(proposal):
            excluded_roles = type_excluded_roles.get(proposal.type)
            if excluded_roles is None:
                excluded_roles = ProposalType.get_excluded_roles(
                    proposal.type)
                type_excluded_roles[proposal.type] = excluded_roles

            return primary_role not in excluded_roles

        proposals = db.search_proposal(
            call_id=call.id,
            state=role_class.get_editable_states(primary_role),
            with_members=True, with_reviewers=True,
            with_review_info=True, with_reviewer_role=all_roles,
            with_categories=(group_type == GroupType.PEER),
        ).map_values(augment_proposal, filter_value=filter_proposal)

        # Determine group membership.
        if group_type == GroupType.PEER:
            group_members = MemberCollection()
            for proposal in proposals.values():
                member_reviewer = proposal.members.get_reviewer(default=None)
                if member_reviewer is not None:
                    # Ensure we didn't already add this person to the review
                    # group.  (This could happen if the same person is the
                    # designated reviewer for multiple proposals.)
                    if not group_members.has_person(member_reviewer.person_id):
                        group_members[member_reviewer.id] = with_proposals(
                            member_reviewer, proposal)
                    else:
                        # This person is already in group -- add proposal.
                        group_members.get_person(
                            member_reviewer.person_id
                        ).proposals.append(proposal)

        else:
            group_members = db.search_group_member(
                queue_id=call.queue_id, group_type=group_type,
                with_person=True)

        group_name = GroupType.get_name(group_type)
        group_person_ids = [x.person_id for x in group_members.values()]

        # Get any relevant acceptance records.
        acceptance = db.search_reviewer_acceptance(
            proposal_id=list(proposals.keys()),
            role=list(roles.keys()))

        message = None

        if form is not None:
            # Read the form inputs into the review list.  Do this first
            # so that we can return the whole updated grid to the user
            # in case of an error performing the update.
            reviewers_orig = {}
            for proposal in proposals.values():
                orig = reviewers_orig[proposal.id] = \
                    proposal.reviewer_person_ids.copy()

                for (role_id, role) in roles.items():
                    if role.unique:
                        # Read the radio button setting.
                        person_ids = []
                        id_ = 'rev_{}_{}'.format(role_id, proposal.id)
                        if id_ in form:
                            person_id = int_or_none(form[id_])
                            if ((person_id is not None) and
                                    (person_id in group_person_ids)):
                                person_ids = [person_id]

                    else:
                        # See which checkbox inputs are present.
                        person_ids = [
                            x for x in group_person_ids
                            if 'rev_{}_{}_{}'.format(role_id, proposal.id, x)
                            in form]

                    proposal.reviewer_person_ids[role_id] = {
                        x: orig[role_id].get(x, False) for x in person_ids}

            try:
                reviewer_remove = []
                reviewer_add = []

                for proposal in proposals.values():
                    proposal_reviewers_orig = reviewers_orig[proposal.id]
                    proposal_reviewers_updated = proposal.reviewer_person_ids

                    for (role_id, role) in roles.items():
                        orig = proposal_reviewers_orig[role_id]
                        updated = proposal_reviewers_updated[role_id]

                        # Apply uniqueness constraint.
                        if role.unique and (len(updated) > 1):
                            raise UserError(
                                'Multiple {} assignments selected for '
                                'proposal {}.',
                                lower_except_abbr(role.name), proposal.code)

                        # Check for multiple or conflicting assignments.
                        for person_id in updated:
                            for (role_other_id, role_other) in roles.items():
                                if role_other_id == role_id:
                                    continue
                                if person_id in proposal_reviewers_updated[
                                        role_other_id]:
                                    raise UserError(
                                        'A reviewer has been selected for '
                                        'multiple roles for proposal {}.',
                                        proposal.code)
                            for (role_other_id, role_other) in \
                                    roles_conflict.items():
                                if person_id in proposal_reviewers_updated[
                                        role_other_id]:
                                    raise UserError(
                                        'A reviewer selected for proposal {} '
                                        'already has a {}{}.',
                                        proposal.code,
                                        lower_except_abbr(role_other.name),
                                        (' review' if role_other.name_review
                                         else ''))

                        # Copy the original reviewer list before removing
                        # entries from it.
                        orig = orig.copy()

                        for person_id in updated:
                            if person_id in orig:
                                del orig[person_id]
                            else:
                                if proposal.members.has_person(person_id):
                                    raise UserError(
                                        'A proposal member has been selected '
                                        'as a reviewer for proposal {}.',
                                        proposal.code)

                                reviewer_add.append({
                                    'proposal_id': proposal.id,
                                    'person_id': person_id,
                                    'role': role_id,
                                })

                        for (person_id, present) in orig.items():
                            if present:
                                raise UserError(
                                    'This page can not be used to remove '
                                    'a reviewer who already started '
                                    'their review.')

                            reviewer_remove.append({
                                'proposal_id': proposal.id,
                                'person_id': person_id,
                                'role': role_id,
                            })

                try:
                    db.multiple_reviewer_update(
                        role_class=role_class,
                        remove=reviewer_remove, add=reviewer_add)
                except DatabaseIntegrityError:
                    raise UserError(
                        'Could not update reviewer assignments.')

                flash('The {} assignments have been updated.',
                      group_name.lower())
                raise HTTPRedirect(url_for('.review_call_reviewers',
                                           call_id=call.id))

            except UserError as e:
                message = e.message

        return {
            'title': '{}: {} {} {}'.format(
                group_name.title(),
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
            'proposals': proposals,
            'target': url_for('.review_call_grid', call_id=call.id,
                              reviewer_role=primary_role),
            'group_members': group_members,
            'roles': roles,
            'conflict_person_ids': {
                proposal.id: set(chain.from_iterable(
                    proposal.reviewer_person_ids[role].keys()
                    for role in roles_conflict))
                for proposal in proposals.values()},
            'message': message,
            'is_peer_review': (group_type == GroupType.PEER),
            'acceptance': acceptance,
        }

    @with_review(permission=PermissionType.NONE, with_note=True)
    def view_reviewer_note(self, current_user, db, reviewer, proposal, form):
        auth_cache = {}
        role_class = self.get_reviewer_roles()

        try:
            call = db.get_call(facility_id=self.id_, call_id=proposal.call_id)
        except NoSuchRecord:
            raise HTTPError('The corresponding call was not found')

        if not auth.for_call_review(
                current_user, db, call, auth_cache=auth_cache).edit:
            raise HTTPForbidden('Edit permission denied for this call.')

        try:
            role_info = role_class.get_info(reviewer.role)
        except KeyError:
            raise HTTPError('Unknown reviewer role')

        if not role_info.invite:
            raise ErrorPage('Reviewer role is not invited.')

        note_exists = (reviewer.note is not None)
        proposal_code = self.make_proposal_code(db, proposal)
        message = None

        if form:
            try:
                reviewer = reviewer._replace(
                    note=form['note'],
                    note_format=int(form['note_format']))

                if not reviewer.note:
                    if note_exists:
                        db.delete_reviewer_note(reviewer_id=reviewer.id)

                        flash(
                            'The note for proposal {} has been deleted.',
                            proposal_code)

                else:
                    db.set_reviewer_note(
                        reviewer_id=reviewer.id,
                        note=reviewer.note,
                        format_=reviewer.note_format)

                    flash(
                        'The note for proposal {} has been saved.',
                        proposal_code)

                raise HTTPRedirect(url_for(
                    '.review_call_reviewers', call_id=call.id))

            except UserError as e:
                message = e.message

        elif not note_exists:
            reviewer = reviewer._replace(
                note='',
                note_format=FormatType.PLAIN)

        return {
            'title': '{}: {} Reviewer Note'.format(
                proposal_code, role_info.name.title()),
            'reviewer': with_can_view(reviewer, auth.for_person_reviewer(
                current_user, db, reviewer, auth_cache=auth_cache).view),
            'proposal': proposal,
            'proposal_code': proposal_code,
            'role_info': role_info,
            'call': call,
            'message': message,
        }

    @with_call_review(permission=PermissionType.EDIT)
    def view_reviewer_notify(self, current_user, db, call, can, role, form):
        role_class = self.get_reviewer_roles()
        type_class = self.get_call_types()

        if not type_class.has_reviewer_role(call.type, role):
            raise ErrorPage('Reviewer role is not expected for this call.')

        group_type = role_class.get_review_group(role)

        if group_type is None:
            raise ErrorPage('Reviewer role is not assigned.')

        group_name = GroupType.get_name(group_type)

        # Prepare the list of reviewers and proposal reviews.  (This is needed
        # both to display the confirmation page and to send the notifications.)
        reviewers = OrderedDict()

        for proposal in db.search_proposal(
                call_id=call.id, state=role_class.get_editable_states(role),
                with_reviewers=True, with_reviewer_role=role,
                with_reviewer_notified=False).values():
            proposal = ProposalWithCode(
                *proposal, code=self.make_proposal_code(db, proposal))

            for reviewer in proposal.reviewers.values():
                person_id = reviewer.person_id
                if person_id not in reviewers:
                    reviewers[person_id] = []

                reviewers[person_id].append(proposal._replace(
                    reviewers=None, reviewer=with_can_view(
                        reviewer, auth.for_person_reviewer(
                            current_user, db, reviewer,
                            auth_cache=can.cache).view)))

        # Get the deadline for this review role.
        deadline = db.search_review_deadline(
            call_id=call.id, role=role).get_single(None)

        if form is not None:
            if 'submit_confirm' in form:
                try:
                    n_notifications = 0

                    for (person_id, proposals_all) in reviewers.items():
                        # Include only reviews present in the form parameters.
                        proposals = [
                            x for x in proposals_all
                            if 'reviewer_{}'.format(x.reviewer.id) in form]
                        if not proposals:
                            continue

                        self._message_review_notification(
                            current_user, db,
                            role, person_id, proposals, deadline)

                        n_notifications += 1

                    if n_notifications:
                        flash(
                            'Notifications have been sent to {} reviewer(s).',
                            n_notifications)

                except UserError as e:
                    raise ErrorPage(e.message)

            raise HTTPRedirect(url_for(
                '.review_call_reviewers', call_id=call.id))

        return {
            'title': '{}: {} {} {}: Notify'.format(
                group_name.title(),
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
            'role': role,
            'reviewers': reviewers,
            'deadline': deadline,
        }

    def _message_review_notification(
            self, current_user, db, role, person_id, proposals, deadline):
        """
        Send a message to a an assigned reviewer informing them of their
        review assignments and update the notified flag for the
        corresponding entries in the reviewers table.

        This method takes a list of proposals, each of which should have a
        `reviewer` attribute corresponding to the review for which the
        notification is being sent.
        """

        assert proposals
        for proposal in proposals:
            assert proposal.reviewer.role == role
            assert proposal.reviewer.person_id == person_id
            assert not proposal.reviewer.notified

        type_class = self.get_call_types()
        role_class = self.get_reviewer_roles()

        role_name = role_class.get_name(role)

        # Use the reviewer information from the first proposal to get
        # the (presumably) common information for the notification email.
        reviewer = proposals[0].reviewer

        email_ctx = {
            'recipient_name': reviewer.person_name,
            'inviter_name': current_user.person.name,
            'queue_name': proposals[0].queue_name,
            'semester_name': proposals[0].semester_name,
            'call_type': type_class.get_name(proposals[0].call_type),
            'role_name': role_name,
            'role_is_peer': (role == role_class.PEER),
            'role_is_accepted': role_class.is_accepted_review(role),
            'target_guideline': self.make_review_guidelines_url(role=role),
            'review_deadline': deadline,
            'proposals': [
                ProposalWithViewReviewLinks(
                    *x, target_proposal=url_for(
                        '.proposal_view',
                        proposal_id=x.id, _external=True),
                    target_review=url_for(
                        '.review_edit',
                        reviewer_id=x.reviewer.id, _external=True))
                for x in proposals],
        }

        if not reviewer.person_registered:
            (token, expiry) = db.issue_invitation(person_id)

            email_ctx.update({
                'token': token,
                'expiry': expiry,
                'target_url': url_for(
                    'people.invitation_token_enter',
                    token=token, _external=True),
                'target_plain': url_for(
                    'people.invitation_token_enter',
                    _external=True),
            })

        email_subject = 'Assignment of {} {}'.format(
            lower_except_abbr(role_name),
            ('reviews' if (len(proposals) > 1) else 'review'))

        db.add_message(
            email_subject,
            render_email_template(
                'review_notification.txt',
                email_ctx, facility=self),
            [person_id])

        for proposal in proposals:
            db.update_reviewer(role_class, proposal.reviewer.id, notified=True)

    @with_call_review(permission=PermissionType.EDIT)
    def view_reviewer_thank(self, current_user, db, call, can, role, form):
        role_class = self.get_reviewer_roles()
        type_class = self.get_call_types()

        if not type_class.has_reviewer_role(call.type, role):
            raise ErrorPage('Reviewer role is not expected for this call.')

        if not role_class.is_thanked_review(role):
            raise ErrorPage('Thanks not enabled for this reviewer role.')

        # Prepare the list of reviewers and proposal reviews.  (This is needed
        # both to display the confirmation page and to send the messages.)
        reviewers = OrderedDict()

        for proposal in db.search_proposal(
                call_id=call.id, with_review_state=ReviewState.DONE,
                with_reviewers=True, with_reviewer_role=role,
                with_reviewer_thanked=False).values():
            proposal = ProposalWithCode(
                *proposal, code=self.make_proposal_code(db, proposal))

            for reviewer in proposal.reviewers.values():
                person_id = reviewer.person_id
                if person_id not in reviewers:
                    reviewers[person_id] = []

                reviewers[person_id].append(proposal._replace(
                    reviewers=None, reviewer=with_can_view(
                        reviewer, auth.for_person_reviewer(
                            current_user, db, reviewer,
                            auth_cache=can.cache).view)))

        if form is not None:
            if 'submit_confirm' in form:
                try:
                    n_notifications = 0

                    for (person_id, proposals_all) in reviewers.items():
                        # Include only reviews present in the form parameters.
                        proposals = [
                            x for x in proposals_all
                            if 'reviewer_{}'.format(x.reviewer.id) in form]
                        if not proposals:
                            continue

                        self._message_review_thank(
                            current_user, db, role, person_id, proposals)

                        n_notifications += 1

                    if n_notifications:
                        flash(
                            'Messages have been sent to {} reviewer(s).',
                            n_notifications)

                except UserError as e:
                    raise ErrorPage(e.message)

            raise HTTPRedirect(url_for(
                '.review_call_reviewers', call_id=call.id))

        return {
            'title': '{}: {} {} {}: Thank'.format(
                role_class.get_name_with_review(role),
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
            'role': role,
            'reviewers': reviewers,
        }

    def _message_review_thank(
            self, current_user, db, role, person_id, proposals):
        """
        Send a message to a reviewer thanking
        them for their contribution.

        This method takes a list of proposals, each of which should have a
        `reviewer` attribute corresponding to the review for which the
        message is being sent.
        """

        assert proposals
        for proposal in proposals:
            assert proposal.reviewer.role == role
            assert proposal.reviewer.person_id == person_id
            assert not proposal.reviewer.thanked

        type_class = self.get_call_types()
        role_class = self.get_reviewer_roles()

        role_name = role_class.get_name(role)

        reviewer = proposals[0].reviewer

        email_ctx = {
            'recipient_name': reviewer.person_name,
            'sender_name': current_user.person.name,
            'queue_name': proposals[0].queue_name,
            'semester_name': proposals[0].semester_name,
            'call_type': type_class.get_name(proposals[0].call_type),
            'role_name': role_name,
            'proposals': proposals,
        }

        email_subject = 'Thank you for your {}'.format(
            ('reviews' if (len(proposals) > 1) else 'review'))

        db.add_message(
            email_subject,
            render_email_template(
                'review_thank_you.txt',
                email_ctx, facility=self),
            [person_id])

        for proposal in proposals:
            db.update_reviewer(role_class, proposal.reviewer.id, thanked=True)

    @with_proposal(permission=PermissionType.NONE, with_categories=True)
    def view_reviewer_add(self, current_user, db, proposal, role, form):
        role_class = self.get_reviewer_roles()
        type_class = self.get_call_types()
        text_role_class = self.get_text_roles()

        try:
            role_info = role_class.get_info(role)
        except KeyError:
            raise HTTPError('Unknown reviewer role')

        if not type_class.has_reviewer_role(proposal.call_type, role):
            raise ErrorPage('Reviewer role is not expected for this call.')

        if not role_info.invite:
            raise ErrorPage('Reviewer role is not invited.')

        if proposal.state not in role_class.get_editable_states(role):
            raise ErrorPage(
                'This proposal is not in a suitable state '
                'for this type of review.')

        if role in ProposalType.get_excluded_roles(proposal.type):
            raise ErrorPage(
                'Reviewer role is not expected for this proposal type.')

        try:
            call = db.get_call(facility_id=self.id_, call_id=proposal.call_id)
        except NoSuchRecord:
            raise HTTPError('The corresponding call was not found')

        auth_cache = {}

        if not auth.for_call_review(
                current_user, db, call, auth_cache=auth_cache).edit:
            raise HTTPForbidden('Edit permission denied for this call.')

        proposal_person_ids = [
            x.person_id for x in proposal.members.values()
        ]

        existing_person_ids = [
            x.person_id for x in db.search_reviewer(
                proposal_id=proposal.id, role=role).values()
        ]

        message_link = None
        message_invite = None

        member_info = self._read_member_form(form)

        with member_info.release() as member:
            if member['is_link'] is None:
                member_info.raise_()

            elif member['is_link']:
                try:
                    member_info.raise_()

                    try:
                        person = db.get_person(person_id=member['person_id'])
                    except NoSuchRecord:
                        raise UserError('Could not find the person profile.')

                    if person.id in proposal_person_ids:
                        raise UserError(
                            'This person is a member of the proposal.')

                    if person.id in existing_person_ids:
                        raise UserError(
                            'This person already has this role.')

                    reviewer_id = db.add_reviewer(
                        role_class=role_class,
                        proposal_id=proposal.id,
                        person_id=person.id, role=role)

                    self._message_review_invite(
                        current_user, db,
                        proposal=proposal,
                        role=role,
                        person_id=person.id,
                        person_name=person.name,
                        person_registered=True,
                        reviewer_id=reviewer_id,
                        is_reminder=False)

                    flash('{} has been added as a reviewer.', person.name)

                    raise HTTPRedirect(url_for(
                        '.review_call_reviewers', call_id=proposal.call_id))

                except UserError as e:
                    message_link = e.message

            else:
                try:
                    member_info.raise_()

                    person_id = db.add_person(
                        member['name'], title=member['title'],
                        primary_email=member['email'])
                    reviewer_id = db.add_reviewer(
                        role_class=role_class,
                        proposal_id=proposal.id,
                        person_id=person_id, role=role)

                    self._message_review_invite(
                        current_user, db,
                        proposal=proposal,
                        role=role,
                        person_id=person_id,
                        person_name=member['name'],
                        person_registered=False,
                        reviewer_id=reviewer_id,
                        is_reminder=False)

                    flash('{} has been invited to register.', member['name'])

                    # Return to the call reviewers page after editing the new
                    # reviewer's institution.
                    raise HTTPRedirect(url_for(
                        'people.person_edit_institution',
                        person_id=person_id, next_page=url_for(
                            '.review_call_reviewers',
                            call_id=proposal.call_id)))

                except UserError as e:
                    message_invite = e.message

        # Prepare list of people to exclude from the member directory.
        exclude_person_ids = proposal_person_ids + existing_person_ids

        try:
            abstract = db.get_proposal_text(proposal.id,
                                            text_role_class.ABSTRACT)
        except NoSuchRecord:
            abstract = None

        # Get the PI of the proposal (as for a with_member_pi search).
        member_pi = proposal.members.get_pi(default=None)
        if member_pi is not None:
            member_pi = with_can_view(member_pi, auth.for_person_member(
                current_user, db, member_pi, auth_cache=auth_cache).view)

        proposal_code = self.make_proposal_code(db, proposal)

        # Get the review deadline, if specified.
        deadline = db.search_review_deadline(
            call_id=proposal.call_id,
            role=role).get_single(default=None)

        return {
            'title': '{}: Add {} Reviewer'.format(
                proposal_code, role_info.name.title()),
            'person_list_url': url_for('query.person_list_all'),
            'persons_exclude': exclude_person_ids,
            'member': member_info.data,
            'message_link': message_link,
            'message_invite': message_invite,
            'target': url_for('.proposal_reviewer_add',
                              proposal_id=proposal.id, reviewer_role=role),
            'title_link': 'Select Reviewer from the Directory',
            'title_invite': 'Invite a Reviewer to Register',
            'submit_link': 'Select reviewer',
            'submit_invite': 'Invite to register',
            'label_link': 'Reviewer',
            'proposal': proposal._replace(member=member_pi),
            'proposal_code': proposal_code,
            'call': call,
            'abstract': abstract,
            'titles': PersonTitle.get_options(),
            'review_deadline': deadline,
        }

    def _message_review_invite(self, current_user, db, proposal, role,
                               person_id, person_name, person_registered,
                               reviewer_id, is_reminder=False,
                               reminder_token=None, reminder_expiry=None):
        """
        Send a review invitation or reminder email message.
        """

        # Prepare basic email context.
        type_class = self.get_call_types()
        role_class = self.get_reviewer_roles()
        role_info = role_class.get_info(role)
        proposal_code = self.make_proposal_code(db, proposal)

        deadline = db.search_review_deadline(
            call_id=proposal.call_id,
            role=role).get_single(default=None)

        email_ctx = {
            'recipient_name': person_name,
            'proposal': proposal,
            'proposal_code': proposal_code,
            'call_type': type_class.get_name(proposal.call_type),
            'role_info': role_info,
            'inviter_name': current_user.person.name,
            'target_proposal': url_for(
                '.proposal_view', proposal_id=proposal.id, _external=True),
            'target_review': url_for(
                '.review_edit',
                reviewer_id=reviewer_id, _external=True),
            'target_guideline': self.make_review_guidelines_url(role=role),
            'is_reminder': is_reminder,
            'review_deadline': deadline,
        }

        # If the person is not registered, generate a new token if this is
        # not a reminder, or if the previous token expired.
        if not person_registered:
            if (is_reminder
                    and (reminder_token is not None)
                    and (reminder_expiry is not None)
                    and (reminder_expiry > datetime.utcnow())):
                token = reminder_token
                expiry = reminder_expiry

            else:
                (token, expiry) = db.issue_invitation(person_id)

            email_ctx.update({
                'token': token,
                'expiry': expiry,
                'target_url': url_for(
                    'people.invitation_token_enter',
                    token=token, _external=True),
                'target_plain': url_for(
                    'people.invitation_token_enter',
                    _external=True),
            })

        # Prepare the message appropriately for either an invitation or
        # reminder.
        email_subject = 'Proposal {} review'.format(proposal_code)

        if is_reminder:
            email_subject = 'Re: ' + email_subject

        # Generate and store the message.
        db.add_message(
            email_subject,
            render_email_template('review_invitation.txt',
                                  email_ctx, facility=self),
            [person_id],
            thread_type=MessageThreadType.REVIEW_INVITATION,
            thread_id=reviewer_id)

    @with_review(permission=PermissionType.NONE)
    def view_reviewer_remove(self, current_user, db, reviewer, proposal, form):
        role_class = self.get_reviewer_roles()

        if proposal.state not in role_class.get_editable_states(reviewer.role):
            raise ErrorPage(
                'This proposal is not in a suitable state '
                'for this type of review.')

        if not auth.for_call_review_proposal(current_user, db, proposal).edit:
            raise HTTPForbidden('Edit permission denied for this call.')

        if ReviewState.is_present(reviewer.review_state):
            raise ErrorPage('This reviewer already started a review.')

        try:
            role_info = role_class.get_info(reviewer.role)
        except KeyError:
            raise HTTPError('Unknown reviewer role')

        if not role_info.invite:
            raise HTTPError('Unexpected reviewer role.')

        proposal_code = self.make_proposal_code(db, proposal)

        if form is not None:
            if 'submit_confirm' in form:
                db.delete_reviewer(reviewer_id=reviewer.id)

                flash('{} has been removed as a reviewer of proposal {}.',
                      reviewer.person_name, proposal_code)

            raise HTTPRedirect(url_for('.review_call_reviewers',
                                       call_id=proposal.call_id))

        return {
            'title': '{}: Remove {} Reviewer'.format(
                proposal_code, role_info.name.title()),
            'message': 'Are you sure you wish to remove {} '
                       'as a reviewer of this proposal?'.format(
                           reviewer.person_name),
            'target': url_for('.proposal_reviewer_remove',
                              reviewer_id=reviewer.id),
        }

    @with_review(permission=PermissionType.NONE)
    def view_reviewer_reinvite(
            self, current_user, db, reviewer, proposal, form):
        return self._view_reviewer_reinvite_remind(
            current_user, db, reviewer, proposal, form)

    @with_review(permission=PermissionType.NONE, with_invitation=True)
    def view_reviewer_remind(
            self, current_user, db, reviewer, proposal, form):
        return self._view_reviewer_reinvite_remind(
            current_user, db, reviewer, proposal, form, is_reminder=True)

    @with_review(permission=PermissionType.NONE, with_invitation=True)
    def view_reviewer_notify_again(
            self, current_user, db, reviewer, proposal, form):
        return self._view_reviewer_reinvite_remind(
            current_user, db, reviewer, proposal, form,
            is_repeat_notification=True)

    def _view_reviewer_reinvite_remind(
            self, current_user, db, reviewer, proposal, form,
            is_reminder=False, is_repeat_notification=False):
        role_class = self.get_reviewer_roles()

        if proposal.state not in role_class.get_editable_states(reviewer.role):
            raise ErrorPage(
                'This proposal is not in a suitable state '
                'for this type of review.')

        if not auth.for_call_review_proposal(current_user, db, proposal).edit:
            raise HTTPForbidden('Edit permission denied for this call.')

        try:
            role_info = role_class.get_info(reviewer.role)
        except KeyError:
            raise HTTPError('Unknown reviewer role')

        if not role_info.invite:
            raise HTTPError('Unexpected reviewer role.')

        if is_reminder:
            if is_repeat_notification:
                raise Exception('both reminder and notification specified')

            endpoint_suffix = 'remind'
            description = 'sent a reminder message'
            title = 'Remind'

        elif is_repeat_notification:
            if not reviewer.person_registered:
                raise ErrorPage('This reviewer is not registered.')

            endpoint_suffix = 'notify_again'
            description = 'sent another notification message'
            title = 'Notify'

        else:
            if reviewer.person_registered:
                raise ErrorPage('This reviewer is already registered.')

            endpoint_suffix = 'reinvite'
            description = 're-invited to register'
            title = 'Re-invite'

        if form is not None:
            if 'submit_confirm' in form:
                self._message_review_invite(
                    current_user, db,
                    proposal=proposal,
                    role=reviewer.role,
                    person_id=reviewer.person_id,
                    person_name=reviewer.person_name,
                    person_registered=reviewer.person_registered,
                    reviewer_id=reviewer.id,
                    is_reminder=is_reminder,
                    reminder_token=reviewer.invitation_token,
                    reminder_expiry=reviewer.invitation_expiry)

                flash(
                    '{} has been {}.',
                    reviewer.person_name, description)

            raise HTTPRedirect(url_for('.review_call_reviewers',
                                       call_id=proposal.call_id))

        proposal_code = self.make_proposal_code(db, proposal)

        return {
            'title': '{}: {} {} Reviewer'.format(
                proposal_code, title, role_info.name.title()),
            'message':
                'Would you like to re-send an invitation to {} '
                'to review proposal {}?'.format(
                    reviewer.person_name, proposal_code),
            'target': url_for(
                '.proposal_reviewer_{}'.format(endpoint_suffix),
                reviewer_id=reviewer.id),
            'is_reminder': is_reminder,
            'is_repeat_notification': is_repeat_notification,
            'proposal_id': proposal.id,
            'reviewer_id': reviewer.id,
            'person_registered': reviewer.person_registered,
        }

    @with_proposal(permission=PermissionType.NONE,
                   with_decision=True, with_decision_note=True)
    def view_review_new(
            self, current_user, db, proposal, reviewer_role, args, form):
        role_class = self.get_reviewer_roles()
        type_class = self.get_call_types()

        try:
            role_info = role_class.get_info(reviewer_role)
        except KeyError:
            raise HTTPError('Unknown reviewer role')

        if (role_info.unique and proposal.reviewers.has_role(reviewer_role)):
            raise ErrorPage(
                'There is already a "{}" reviewer for this proposal.',
                role_info.name)

        auth_cache = {}

        can_add_roles = auth.can_add_review_roles(
            type_class, role_class, current_user, db, proposal,
            auth_cache=auth_cache)

        if reviewer_role not in can_add_roles:
            raise HTTPForbidden(
                'You can not add a review in the "{}" role.'.format(
                    role_info.name))

        return self._view_review_new_or_edit(
            current_user, db, None, proposal, args, form,
            reviewer_role=reviewer_role, auth_cache=auth_cache)

    @with_review(
        permission=PermissionType.EDIT, allow_unaccepted=True,
        with_categories=True)
    def view_review_accept(
            self, current_user, db, reviewer, proposal, can, args, form):
        role_class = self.get_reviewer_roles()
        if not role_class.is_accepted_review(reviewer.role):
            raise ErrorPage('This review does not require acceptance.')

        if reviewer.person_id != current_user.person.id:
            raise HTTPForbidden(
                'Accept permission denied for this review.')

        proposal_code = self.make_proposal_code(db, proposal)

        if reviewer.accepted is not None:
            if reviewer.accepted:
                description = 'accepted'
                message = (
                    'You indicated that you do not have a significant '
                    'conflict of interest, so you may now proceed to '
                    'view the proposal and enter your review.')
                links = [
                    Link(
                        'View proposal {}'.format(proposal_code),
                        url_for('.proposal_view', proposal_id=proposal.id)),
                    Link(
                        '{} your review'.format(
                            'Edit' if ReviewState.is_present(
                                reviewer.review_state) else 'Write'),
                        url_for('.review_edit', reviewer_id=reviewer.id)),
                ]
            else:
                description = 'rejected'
                message = (
                    'You indicated that you have a significant conflict of '
                    'interest, so this review should have been removed from '
                    'your review list.')
                links = [
                    Link(
                        'Back to your review list',
                        url_for('people.person_reviews')),
                ]
            raise ErrorPage(
                'You have already entered a conflict of interest declaration '
                'for this review. ' + message,
                title='{}: {} already {}'.format(
                    proposal_code,
                    role_class.get_name_with_review(reviewer.role),
                    description),
                links=links)

        try:
            acceptance = db.search_reviewer_acceptance(
                proposal_id=reviewer.proposal_id,
                person_id=reviewer.person_id,
                role=reviewer.role,
                with_text=True).get_single()

        except NoSuchRecord:
            acceptance = null_tuple(ReviewerAcceptance)

        referrer = args.get('referrer')
        message = None

        if form is not None:
            try:
                reviewer = reviewer._replace(
                    accepted=int_or_none(form.get('accepted', '')))
                acceptance = acceptance._replace(
                    text=form['explanation'])
                referrer = form.get('referrer')

                if reviewer.accepted is None:
                    raise UserError(
                        'Please select a declaration.')

                elif (not reviewer.accepted) and (not acceptance.text):
                    raise UserError(
                        'Please enter an explanation.')

                if acceptance.id is not None:
                    db.update_reviewer_acceptance(
                        reviewer_acceptance_id=acceptance.id,
                        accepted=reviewer.accepted,
                        text=acceptance.text, format_=FormatType.PLAIN)

                else:
                    db.add_reviewer_acceptance(
                        role_class, proposal_id=reviewer.proposal_id,
                        person_id=reviewer.person_id, role=reviewer.role,
                        accepted=reviewer.accepted,
                        text=acceptance.text, format_=FormatType.PLAIN)

                db.update_reviewer(
                    role_class, reviewer.id, accepted=reviewer.accepted)

                if reviewer.accepted:
                    flash('The review has been accepted.')
                    target = (
                        referrer if referrer else
                        url_for('.review_info', reviewer_id=reviewer.id))
                else:
                    flash('The review has been rejected.')
                    target = url_for('people.person_reviews')

                raise HTTPRedirect(target)

            except UserError as e:
                message = e.message

        try:
            text_role_class = self.get_text_roles()
            abstract = db.get_proposal_text(
                proposal.id, text_role_class.ABSTRACT)
        except NoSuchRecord:
            abstract = None

        return {
            'title': '{}: Accept {}'.format(
                proposal_code,
                role_class.get_name_with_review(reviewer.role)),
            'reviewer': reviewer,
            'proposal': proposal._replace(members=proposal.members.map_values(
                lambda x: with_can_view(x, auth.for_person_member(
                    current_user, db, x, auth_cache=can.cache).view))),
            'proposal_code': proposal_code,
            'abstract': abstract,
            'explanation': acceptance.text,
            'message': message,
            'referrer': referrer,
            'target_guideline': self.make_review_guidelines_url(
                role=reviewer.role),
            'role_is_peer': (reviewer.role == role_class.PEER),
        }

    @with_review(permission=PermissionType.NONE)
    def view_review_clear_accept(
            self, current_user, db, reviewer, proposal, form):
        auth_cache = {}
        role_class = self.get_reviewer_roles()
        if not role_class.is_accepted_review(reviewer.role):
            raise ErrorPage('This review does not require acceptance.')

        if not (reviewer.accepted is not None and not reviewer.accepted):
            raise ErrorPage('This review has not been rejected.')

        if not auth.for_call_review_proposal(
                current_user, db, proposal, auth_cache=auth_cache).edit:
            raise HTTPForbidden('Edit permission denied for this call.')

        if form is not None:
            if 'submit_confirm' in form:
                db.update_reviewer(
                    role_class, reviewer.id, accepted=None)

                flash('The review rejection has been cleared.')

            raise HTTPRedirect(url_for(
                '.review_edit', reviewer_id=reviewer.id))

        proposal_code = self.make_proposal_code(db, proposal)

        return {
            'title': '{}: Clear Rejection of {}'.format(
                proposal_code,
                role_class.get_name_with_review(reviewer.role)),
            'message':
                'Are you sure you wish to clear the review '
                'rejection by {}?'.format(reviewer.person_name),
        }

    @with_review(permission=PermissionType.EDIT)
    def view_review_info(self, current_user, db, reviewer, proposal, can):
        proposal_code = self.make_proposal_code(db, proposal)

        return {
            'title': '{}: Review Information'.format(proposal_code),
            'reviewer': reviewer,
            'proposal_code': proposal_code,
        }

    @with_review(permission=PermissionType.EDIT,
                 with_decision=True, with_decision_note=True,
                 with_acceptance=True)
    def view_review_edit(
            self, current_user, db, reviewer, proposal, can, args, form):
        return self._view_review_new_or_edit(
            current_user, db, reviewer, proposal, args, form,
            auth_cache=can.cache)

    def _view_review_new_or_edit(
            self, current_user, db, reviewer, proposal, args, form,
            reviewer_role=None, auth_cache=None):
        role_class = self.get_reviewer_roles()

        if reviewer is None:
            is_new_reviewer = True
            is_own_review = True
            target = url_for('.proposal_review_new', proposal_id=proposal.id,
                             reviewer_role=reviewer_role)
            reviewer = null_tuple(Reviewer)._replace(role=reviewer_role)

        else:
            is_new_reviewer = False
            is_own_review = (reviewer.person_id == current_user.person.id)
            target = url_for('.review_edit', reviewer_id=reviewer.id)

        referrer = args.get('referrer')

        try:
            role_info = role_class.get_info(reviewer.role)
        except KeyError:
            raise HTTPError('Unknown reviewer role')

        message = None
        extra_info = None

        if form is not None:
            # Read form inputs first.
            is_done = 'done' in form
            referrer = form.get('referrer', None)

            try:
                if role_info.assessment:
                    reviewer = reviewer._replace(
                        review_assessment=int_or_none(form['assessment']))

                if role_info.rating:
                    reviewer = reviewer._replace(
                        review_rating=int_or_none(form['rating']))

                if role_info.weight:
                    reviewer = reviewer._replace(
                        review_weight=int_or_none(form['weight']))

            except:
                raise HTTPError('Form value not understood.')

            if role_info.text:
                reviewer = reviewer._replace(
                    review_text=form['text'],
                    review_format=FormatType.PLAIN)

            if role_info.note:
                # If this is our own review, the browser should have
                # sent the note text field.  Otherwise we preserve the
                # note field, only setting it if it is currently undefined,
                # as not to do so would trigger an error.
                if is_own_review:
                    reviewer = reviewer._replace(
                        review_note=form['note'],
                        review_note_format=FormatType.PLAIN,
                        review_note_public=('note_public' in form))
                elif reviewer.review_note is None:
                    reviewer = reviewer._replace(
                        review_note='',
                        review_note_format=FormatType.PLAIN,
                        review_note_public=False)

            try:
                extra_info = self._view_review_edit_get(
                    db, reviewer, proposal, form)

                # Validate the form inputs, but leave checking of enum values
                # to the db.set_review method.
                if role_info.assessment:
                    if (is_done and (reviewer.review_assessment is None)):
                        raise UserError('Please select an assessment value.')

                if role_info.rating:
                    if (is_done if (reviewer.review_rating is None)
                            else not (0 <= reviewer.review_rating <= 100)):
                        raise UserError('Please give a rating between '
                                        '0 and 100.')

                if role_info.weight:
                    if (is_done if (reviewer.review_weight is None)
                            else not (0 <= reviewer.review_weight <= 100)):
                        raise UserError('Please give a self-assessment '
                                        'weighting between 0 and 100.')

                if is_new_reviewer:
                    reviewer = reviewer._replace(id=db.add_reviewer(
                        role_class=role_class,
                        proposal_id=proposal.id,
                        person_id=current_user.person.id,
                        role=reviewer.role))

                    # Change target in case of a UserError occurring while
                    # setting the review.
                    target = url_for('.review_edit', reviewer_id=reviewer.id)

                reviewer = reviewer._replace(review_state=(
                    ReviewState.DONE if is_done else ReviewState.PREPARATION))

                self._view_review_edit_save(db, reviewer, proposal, extra_info)

                db.set_review(
                    role_class=role_class,
                    reviewer_id=reviewer.id,
                    text=reviewer.review_text,
                    format_=reviewer.review_format,
                    assessment=reviewer.review_assessment,
                    rating=reviewer.review_rating,
                    weight=reviewer.review_weight,
                    note=reviewer.review_note,
                    note_format=reviewer.review_note_format,
                    note_public=reviewer.review_note_public,
                    state=reviewer.review_state)

                flash('The review has been saved and marked as {}.',
                      ReviewState.get_name(reviewer.review_state).lower())

                # Determine where to redirect the user.  Look for a
                # "referrer" value identifying a suitable page.
                if referrer == 'pr':
                    target_redir = url_for('.proposal_reviews',
                                           proposal_id=proposal.id)

                elif referrer == 'cr':
                    target_redir = url_for('.review_call_reviewers',
                                           call_id=proposal.call_id)

                elif referrer == 'tab':
                    target_redir = url_for('.review_call_tabulation',
                                           call_id=proposal.call_id)

                else:
                    # Otherwise, by default redirect back to the person's
                    # "your reviews" page.
                    target_redir = url_for('people.person_reviews')

                raise HTTPRedirect(target_redir)

            except UserError as e:
                message = e.message

        proposal_code = self.make_proposal_code(db, proposal)

        title_description = role_info.name
        if role_info.name_review:
            title_description += ' Review'

        # If this is not the person's own review, hide the private note and
        # adjust the role info to exclude it.
        if role_info.note and not is_own_review:
            role_info = role_info._replace(note=False)
            reviewer = reviewer._replace(review_note=None)

        # If this is not the feedback review, hide the decision note.
        if reviewer.role != role_class.FEEDBACK:
            proposal = proposal._replace(decision_note=None)

        # If this role allows calculations, retrieve any which are present.
        if role_info.calc and (reviewer.id is not None):
            calculations = self._prepare_calculations(
                db.search_review_calculation(reviewer_id=reviewer.id))
        else:
            calculations = None

        # If this role allows figures, retrieve any which are present.
        if role_info.figure and (reviewer.id is not None):
            figures = db.search_review_figure(
                reviewer_id=reviewer.id,
                with_caption=True, with_has_preview=True)
        else:
            figures = None

        # Get the review deadline, if specified.
        deadline = db.search_review_deadline(
            call_id=proposal.call_id,
            role=reviewer.role).get_single(default=None)

        ctx = {
            'title': '{}: {} {}'.format(
                proposal_code,
                ('Add' if is_new_reviewer else 'Edit'),
                title_description),
            'target': target,
            'proposal_code': proposal_code,
            'proposal': proposal,
            'reviewer': with_can_view(reviewer, auth.for_person_reviewer(
                current_user, db, reviewer, auth_cache=auth_cache).view),
            'role_info': role_info,
            'assessment_options': Assessment.get_options(),
            'message': message,
            'referrer': referrer,
            'target_guideline': self.make_review_guidelines_url(
                role=reviewer.role),
            'calculators': (self.calculators if role_info.calc else None),
            'calculations': calculations,
            'figures': figures,
            'review_deadline': deadline,
            'show_review_acceptance': (
                role_info.accept and auth.for_call_review_proposal(
                    current_user, db, proposal, auth_cache=auth_cache).edit),
        }

        ctx.update(self._view_review_edit_extra(
            db, reviewer, proposal, extra_info))

        return ctx

    def _view_review_edit_get(self, db, reviewer, proposal, form):
        """
        Placeholder for facility-specific method to read form values
        containing extra information for the review.

        Parsing errors should be left for later.

        :return: an object containing any additional information which
            the facility class requires.

        :raises HTTPError: if a serious parsing error occurs.
            (Current input can not be shown again in the form at this point.)
        """

        return None

    def _view_review_edit_save(self, db, reviewer, proposal, info):
        """
        Placeholder for facility-specific method to parse previously-read
        form inputs and store them in the database.

        :raises UserError: in the event of a problem with the input.
            (Current input will be shown again in the form for correction.)
        """

        pass

    def _view_review_edit_extra(self, db, reviewer, proposal, info):
        """
        Placeholder for facility-specific method to generate extra
        information to show in the proposal edit page.

        `info` will be the object returned by _view_review_edit_get
        if a POST is being handled, or None otherwise.
        """

        return {}

    @with_review(permission=PermissionType.VIEW)
    def view_review_calculation_manage(
            self, current_user, db, reviewer, proposal, can, form):
        role_class = self.get_reviewer_roles()

        return self._view_calculation_manage(
            db, proposal, reviewer, can, form,
            title='{}:  Calculations'.format(
                role_class.get_name_with_review(reviewer.role)),
            target_redirect=url_for(
                '.review_edit', reviewer_id=reviewer.id,
                _anchor='calculations'))

    @with_review(permission=PermissionType.VIEW)
    def view_review_calculation_view(
            self, current_user, db, reviewer, proposal, can,
            review_calculation_id):
        # Retrieve the calculation to identify the calculator and mode.
        try:
            calculation = db.search_review_calculation(
                review_calculation_id=review_calculation_id,
                reviewer_id=reviewer.id).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Review calculation not found.')

        calculator_info = self.calculators.get(calculation.calculator_id)
        if calculator_info is None:
            raise HTTPNotFound('Calculator not found.')

        # Find the view function associated with this mode and call it.
        view_func = calculator_info.view_functions.get(calculation.mode)
        if view_func is None:
            raise HTTPNotFound('Calculator mode not found.')

        return view_func(
            review_calculation=calculation, can=can,
            parent_proposal=proposal, parent_reviewer=reviewer)

    @with_review(permission=PermissionType.EDIT)
    def view_review_edit_figure(
            self, current_user, db, reviewer, proposal, can,
            fig_id, form, file_):
        role_class = self.get_reviewer_roles()
        role_info = role_class.get_info(reviewer.role)
        name = role_class.get_name_with_review(reviewer.role)

        if fig_id is None:
            # We are trying to add a new figure -- check whether this is
            # permitted.
            if not role_info.figure:
                raise ErrorPage(
                    'The {} can not have figures attached.', name.lower())

            figure = null_tuple(ReviewFigureInfo)._replace(caption='')

            target = url_for('.review_new_figure', reviewer_id=reviewer.id)

        else:
            try:
                figure = db.search_review_figure(
                    reviewer_id=reviewer.id, link_id=fig_id,
                    with_caption=True).get_single()
            except NoSuchRecord:
                raise HTTPNotFound('Figure not found.')

            target = url_for(
                '.review_edit_figure', reviewer_id=reviewer.id, fig_id=fig_id)

        return self._view_edit_figure(
            current_user, db, form, file_, figure, proposal, reviewer,
            title=name,
            target_edit=target,
            target_redirect=url_for(
                '.review_edit', reviewer_id=reviewer.id))

    @with_review(permission=PermissionType.VIEW)
    def view_review_view_figure(
            self, current_user, db, reviewer, proposal, can,
            fig_id, md5sum, type_=None):
        if (type_ is None) or (type_ == 'svg'):
            try:
                figure = db.get_review_figure(
                    reviewer.id, fig_id, md5sum=md5sum)
            except NoSuchRecord:
                raise HTTPNotFound('Figure not found.')

            if type_ is None:
                return figure

            elif type_ == 'svg':
                if figure.type == FigureType.PDF:
                    return pdf_to_svg(figure.data, 1)

                else:
                    raise HTTPError('Figure type cannot be converted to SVG.')

            else:
                raise HTTPError('Figure view type unexpectedly didn\'t match.')

        elif type_ == 'thumbnail':
            try:
                return db.get_review_figure_thumbnail(
                    reviewer.id, fig_id, md5sum=md5sum)
            except NoSuchRecord:
                raise HTTPNotFound('Figure thumbnail not found.')

        elif type_ == 'preview':
            try:
                return db.get_review_figure_preview(
                    reviewer.id, fig_id, md5sum=md5sum)
            except NoSuchRecord:
                raise HTTPNotFound('Figure preview not found.')

        else:
            raise HTTPError('Unknown figure view type.')

    @with_review(permission=PermissionType.EDIT)
    def view_review_manage_figure(
            self, current_user, db, reviewer, proposal, can, form):
        role_class = self.get_reviewer_roles()
        role_info = role_class.get_info(reviewer.role)
        name = role_class.get_name_with_review(reviewer.role)

        return self._view_manage_figure(
            db, form, proposal=proposal, reviewer=reviewer, role=None,
            title=name,
            target_edit=url_for(
                '.review_manage_figure', reviewer_id=reviewer.id),
            target_redirect=url_for(
                '.review_edit', reviewer_id=reviewer.id, _anchor='figures'))

    @with_proposal(
        permission=PermissionType.NONE,
        with_decision=True, with_categories=True)
    def view_proposal_reviews(self, current_user, db, proposal):
        type_class = self.get_call_types()
        role_class = self.get_reviewer_roles()
        text_role_class = self.get_text_roles()

        auth_cache = {}
        if not auth.for_review(
                role_class, current_user, db,
                reviewer=None, proposal=proposal,
                auth_cache=auth_cache).view:
            raise HTTPForbidden(
                'Permission denied for this proposal\'s reviews.')

        proposal_code = self.make_proposal_code(db, proposal)

        try:
            abstract = db.get_proposal_text(proposal.id,
                                            text_role_class.ABSTRACT)
        except NoSuchRecord:
            abstract = None

        # Attach the PI to the proposal (as for a with_member_pi search).
        # Also attach a reviewer collection.
        reviewers = ReviewerCollection()
        member_pi = proposal.members.get_pi(default=None)
        if member_pi is not None:
            member_pi = with_can_view(
                member_pi, auth.for_person_member(
                    current_user, db, member_pi, auth_cache=auth_cache).view)
        proposal = proposal._replace(member=member_pi, reviewers=reviewers)

        # Add permission fields and hide non-public notes so that we don't
        # have to rely on the template to do this.
        for (reviewer_id, reviewer) in db.search_reviewer(
                proposal_id=proposal.id, with_review=True,
                with_review_text=True, with_review_note=True,
                with_acceptance=True).items():
            role_info = role_class.get_info(reviewer.role)
            reviewer_can = auth.for_review(
                role_class, current_user, db,
                reviewer=reviewer, proposal=proposal,
                auth_cache=auth_cache, allow_unaccepted=False)

            if not reviewer.review_note_public:
                reviewer = reviewer._replace(review_note=None)

            if role_info.calc:
                calculations = self._prepare_calculations(
                    db.search_review_calculation(reviewer_id=reviewer.id))
            else:
                calculations = None

            if role_info.figure:
                figures = db.search_review_figure(
                    reviewer_id=reviewer.id,
                    with_caption=True, with_has_preview=True)
            else:
                figures = None

            reviewers[reviewer_id] = ReviewerWithCalcFig(
                *reviewer,
                calculations=calculations, figures=figures,
                can_view=auth.for_person_reviewer(
                    current_user, db, reviewer, auth_cache=auth_cache).view,
                can_edit=reviewer_can.edit,
                can_view_rating=reviewer_can.view_rating)

        self.attach_review_extra(db, {None: proposal})

        return {
            'title': '{}: Reviews'.format(proposal_code),
            'proposal': proposal,
            'proposal_code': proposal_code,
            'abstract': abstract,
            'reviews': reviewers,
            'overall_rating': self.calculate_overall_rating(
                reviewers.map_values(
                    filter_value=lambda x: x.can_view_rating)),
            'can_add_roles': auth.can_add_review_roles(
                type_class, role_class, current_user, db,
                proposal, auth_cache=auth_cache),
            'can_edit_decision': auth.for_proposal_decision(
                current_user, db, proposal, auth_cache=auth_cache).edit,
        }

    @with_proposal(permission=PermissionType.NONE,
                   with_decision=True, with_decision_note=True)
    def view_proposal_decision(self, current_user, db, proposal, args, form):
        auth_cache = {}

        if not auth.for_proposal_decision(
                current_user, db, proposal, auth_cache=auth_cache).edit:
            raise HTTPForbidden(
                'Decision edit permission denied for this proposal.')

        referrer = args.get('referrer')

        message = None
        extra_info = None
        proposal_code = self.make_proposal_code(db, proposal)

        if form is not None:
            try:
                # Read form inputs.
                referrer = form.get('referrer', None)

                decision = form['decision_accept']
                proposal = proposal._replace(
                    decision_accept=(None if (decision == '')
                                     else bool(int(decision))),
                    decision_exempt=('decision_exempt' in form),
                    decision_note=form['decision_note'],
                    decision_note_format=FormatType.PLAIN)
                extra_info = self._view_proposal_decision_get(db, proposal,
                                                              form)

                # Parse and store new values.
                if proposal.decision_exempt and (not proposal.decision_accept):
                    raise UserError('Proposal should not be marked "exempt" '
                                    'when rejected.')

                self._view_proposal_decision_save(db, proposal, extra_info)

                db.set_decision(
                    proposal_id=proposal.id,
                    accept=proposal.decision_accept,
                    exempt=proposal.decision_exempt,
                    note=proposal.decision_note,
                    note_format=proposal.decision_note_format)

                flash('The decision for proposal {} has been saved.',
                      proposal_code)

                # Determine where to redirect the user.
                if referrer == 'rp':
                    target_redir = url_for('.review_call',
                                           call_id=proposal.call_id)

                elif referrer == 'pr':
                    target_redir = url_for('.proposal_reviews',
                                           proposal_id=proposal.id)

                else:
                    # By default redirect to the detailed tabulation.
                    target_redir = url_for('.review_call_tabulation',
                                           call_id=proposal.call_id)

                raise HTTPRedirect(target_redir)

            except UserError as e:
                message = e.message

        # Emulate search_proposal(with_member_pi=True) behavior.
        member_pi = proposal.members.get_pi(default=None)
        if member_pi is not None:
            member_pi = with_can_view(
                member_pi, auth.for_person_member(
                    current_user, db, member_pi, auth_cache=auth_cache).view)

        ctx = {
            'title': '{}: Decision'.format(proposal_code),
            'proposal': proposal._replace(member=member_pi),
            'proposal_code': proposal_code,
            'message': message,
            'referrer': referrer,
        }

        ctx.update(self._view_proposal_decision_extra(db, proposal,
                                                      extra_info))

        return ctx

    def _view_proposal_decision_get(self, db, proposal, form):
        """
        Placeholder for a method where a facility-specific subclass could
        read a set of form values representing its additional information
        from the decision page.  The method should return an object containing
        anything the class needs to know from the form.  Parsing errors should
        be left for later.
        """

        return None

    def _view_proposal_decision_save(self, db, proposal, info):
        """
        Placeholder for a method where a facility-specific subclass could
        parse the (previously read) form inputs and store them in the
        database.

        Can raise UserError in the case of a problem with the inputs.

        The "proposal" object will have been updated to include the
        decision_accept and decision_exempt values as currently
        being entered.
        """

    def _view_proposal_decision_extra(self, db, proposal, info):
        """
        Placeholder for a method where a facility-specific subclass could
        generate extra information to show in the decision page.  The
        "info" will be None if a POST is not being handled, otherwise it
        will be the object returned  by _view_proposal_decision_get.
        """

        return {}

    @with_call_review(permission=PermissionType.EDIT)
    def view_review_advance_final(self, current_user, db, call, can, form):
        type_class = self.get_call_types()

        # For "immediate review" calls, allow the user to select
        # which proposals to advance.
        call_proposals = None
        if type_class.has_immediate_review(call.type):
            call_proposals = db.search_proposal(
                call_id=call.id, state=ProposalState.REVIEW,
                with_member_pi=True)

            if not call_proposals:
                raise ErrorPage(
                    'There are no proposals still in '
                    'the initial review state.')

        if form is not None:
            if 'submit_confirm' in form:
                selected_proposals = None
                if call_proposals is not None:
                    selected_proposals = []
                    for proposal in call_proposals.values():
                        if 'proposal_{}'.format(proposal.id) in form:
                            selected_proposals.append(proposal)

                    if not selected_proposals:
                        raise ErrorPage('No proposals selected to advance.')

                (n_update, n_error) = finalize_call_review(
                    db, call_id=call.id, proposals=selected_proposals)

                if n_update:
                    flash('{} {} advanced to the final review state.',
                          n_update,
                          ('proposals' if n_update > 1 else 'proposal'))

                if n_error:
                    raise ErrorPage(
                        'Errors encountered advancing {} {} '
                        'to the final review state.',
                        n_error,
                        ('proposals' if n_error > 1 else 'proposal'))

            raise HTTPRedirect(url_for('.review_call', call_id=call.id))

        if call_proposals is not None:
            call_proposals = call_proposals.map_values(
                lambda x: ProposalWithCode(
                    *x, code=self.make_proposal_code(db, x)
                )._replace(member=with_can_view(
                    x.member, auth.for_person_member(
                        current_user, db, x.member,
                        auth_cache=can.cache).view)))

        # For information, determine which review roles are closing and what
        # their deadlines are.
        role_class = self.get_reviewer_roles()
        deadlines = db.search_review_deadline(call_id=call.id)
        now = datetime.utcnow()
        roles_closing = []
        for role_id in role_class.get_options():
            role_info = role_class.get_info(role_id)
            if role_info.edit_fr or not role_info.edit_rev:
                continue

            deadline_future = False
            role_deadline = deadlines.get_role(role_id, default=None)
            if role_deadline is not None:
                if role_deadline.date > now:
                    deadline_future = True

            roles_closing.append(RoleClosingInfo(
                role_info.name, role_deadline, deadline_future))

        return {
            'title': 'Final Review: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'message':
                'Are you sure you wish to advance to the final review phase?',
            'target': url_for('.review_call_advance_final', call_id=call.id),
            'call': call,
            'proposals': call_proposals,
            'roles_closing': roles_closing,
        }

    @with_call_review(permission=PermissionType.EDIT)
    def view_review_confirm_feedback(self, current_user, db, call, can, form):
        role_class = self.get_reviewer_roles()
        type_class = self.get_call_types()

        # Get proposals for this call, including their feedback review
        # and decision.  Note: "with_decision" means include it in the
        # results, decision_accept_defined that the proposal must have one.
        proposals = db.search_proposal(
            call_id=call.id, state=ProposalState.FINAL_REVIEW,
            with_reviewers=True, with_review_info=True, with_review_text=True,
            with_review_state=ReviewState.DONE,
            with_reviewer_role=role_class.FEEDBACK,
            with_decision=True, decision_accept_defined=True)

        # Ignore proposals without reviews.
        for id_ in list(proposals.keys()):
            proposal = proposals[id_]
            if not proposal.reviewers:
                del proposals[id_]

        message = None

        if form is not None:
            try:
                if not proposals:
                    raise ErrorPage(
                        'No proposals have feedback awaiting approval.')

                ready_updates = {}

                for id_ in list(proposals.keys()):
                    proposal = proposals[id_]
                    ready = ('ready_{}'.format(id_) in form)

                    # If the status changed, place the proposal in our
                    # updates dictionary.
                    if ready != proposal.decision_ready:
                        ready_updates[id_] = ready

                    # Also update the proposal in the result collection
                    # in case we have to display the form again.
                    proposals[id_] = proposal._replace(decision_ready=ready)

                if ready_updates:
                    for (id_, ready) in ready_updates.items():
                        db.set_decision(proposal_id=id_, ready=ready)

                    flash('The feedback approval status has been updated.')

                raise HTTPRedirect(url_for('.review_call', call_id=call.id))

            except UserError as e:
                message = e.message

        return {
            'title': 'Feedback: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
            'proposals': proposals.map_values(
                lambda x: ProposalWithCode(
                    *x, code=self.make_proposal_code(db, x)
                )._replace(reviewers=x.reviewers.map_values(
                    lambda y: with_can_view(y, auth.for_person_reviewer(
                        current_user, db, y, auth_cache=can.cache).view)))),
            'message': message,
        }
