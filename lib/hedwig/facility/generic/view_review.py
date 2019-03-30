# Copyright (C) 2015-2019 East Asian Observatory
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
from datetime import datetime
from itertools import chain
import re

from ...admin.proposal import finalize_call_review
from ...email.format import render_email_template
from ...error import DatabaseIntegrityError, NoSuchRecord, UserError
from ...file.csv import CSVWriter
from ...view import auth
from ...view.util import int_or_none, \
    with_proposal, with_call_review, with_review
from ...web.util import ErrorPage, \
    HTTPError, HTTPForbidden, HTTPNotFound, HTTPRedirect, \
    flash, format_datetime, parse_datetime, session, url_for
from ...type.collection import ReviewerCollection, ReviewDeadlineCollection
from ...type.enum import AffiliationType, Assessment, \
    FormatType, GroupType, \
    MessageThreadType, PermissionType, PersonTitle, ProposalState, ReviewState
from ...type.simple import Affiliation, DateAndTime, Link, MemberPIInfo, \
    ProposalWithCode, Reviewer, ReviewFigureInfo, ReviewDeadline
from ...type.util import null_tuple, \
    with_can_edit, with_can_view, with_can_view_edit


ProposalWithInviteRoles = namedtuple(
    'ProposalWithInviteRoles',
    ProposalWithCode._fields + ('invite_roles',))

ProposalWithReviewers = namedtuple(
    'ProposalWithReviewers',
    ProposalWithCode._fields + (
        'reviewers_primary', 'reviewers_secondary',
        'can_view_review', 'can_edit_decision'))

ProposalWithReviewerPersons = namedtuple(
    'ProposalWithReviewerPersons',
    ProposalWithCode._fields + (
        'reviewer_person_ids',))

ReviewerWithCalcFig = namedtuple(
    'ReviewerWithCalcFig', Reviewer._fields + (
        'calculations', 'figures', 'can_view', 'can_edit'))


class GenericReview(object):
    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call(self, db, call, can):
        role_class = self.get_reviewer_roles()
        type_class = self.get_call_types()

        is_admin = session.get('is_admin', False)

        proposals = []

        for proposal in db.search_proposal(
                call_id=call.id, state=ProposalState.submitted_states(),
                with_members=True, with_reviewers=True,
                with_reviewer_role=(role_class.CTTEE_PRIMARY,
                                    role_class.CTTEE_SECONDARY),
                with_decision=True, with_categories=True).values():
            member_pi = proposal.members.get_pi(default=None)
            if member_pi is not None:
                member_pi = with_can_view(
                    member_pi, (is_admin or member_pi.person_public))

            review_can = auth.for_review(
                role_class, db, reviewer=None, proposal=proposal,
                auth_cache=can.cache)

            decision_can = auth.for_proposal_decision(
                db, proposal, call=call, auth_cache=can.cache)

            proposals.append(ProposalWithReviewers(
                *proposal._replace(member=member_pi),
                code=self.make_proposal_code(db, proposal),
                reviewers_primary=[
                    with_can_view(x, (is_admin or x.person_public))
                    for x in proposal.reviewers.values_by_role(
                        role_class.CTTEE_PRIMARY)],
                reviewers_secondary=[
                    with_can_view(x, (is_admin or x.person_public))
                    for x in proposal.reviewers.values_by_role(
                        role_class.CTTEE_SECONDARY)],
                can_view_review=review_can.view,
                can_edit_decision=decision_can.edit))

        return {
            'title': 'Review Process: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'can_edit': can.edit,
            'call_id': call.id,
            'proposals': proposals,
        }

    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call_tabulation(self, db, call, can):
        type_class = self.get_call_types()

        ctx = {
            'title': 'Proposal Tabulation: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
        }

        ctx.update(self._get_proposal_tabulation(db, call, can))

        return ctx

    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call_tabulation_download(self, db, call, can,
                                             with_cois=True):
        type_class = self.get_call_types()
        tabulation = self._get_proposal_tabulation(
            db, call, can, with_extra=True)

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

    def _get_proposal_tabulation(self, db, call, can, with_extra=False):
        """Prepare information for the detailed tabulation of proposals.

        This is used to prepare the information both for the online
        version and the downloadable CSV file.  For the CSV file, the
        `with_extra` option is enabled and additional information,
        beyond that which can be displayed on the online version,
        is retrieved.
        """

        is_admin = session.get('is_admin', False)

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
            member_pi = proposal.members.get_pi(default=None)

            can_view_review = auth.for_review(
                role_class, db, reviewer=None, proposal=proposal,
                auth_cache=can.cache).view

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
                'members': proposal.members.map_values(
                    lambda x: with_can_view(x, (is_admin or x.person_public))),
                'code': self.make_proposal_code(db, proposal),
                'affiliations': self.calculate_affiliation_assignment(
                    db, proposal.members, affiliations),
                'can_edit_decision': auth.for_proposal_decision(
                    db, proposal, call=call, auth_cache=can.cache).edit,
            })

            if can_view_review:
                # Determine authorization for each review.  Hide ratings
                # which cannot be viewed.
                reviewers = ReviewerCollection()

                for reviewer_id, reviewer in proposal.reviewers.items():
                    reviewer_can = auth.for_review(
                        role_class, db, reviewer=reviewer, proposal=proposal,
                        auth_cache=can.cache)

                    if not reviewer_can.view_rating:
                        reviewer = reviewer._replace(
                            review_rating=None, review_weight=None)

                    reviewers[reviewer_id] = with_can_view_edit(
                        reviewer,
                        (is_admin or reviewer.person_public),
                        reviewer_can.edit)

                (overall_rating, std_dev) = self.calculate_overall_rating(
                    reviewers, with_std_dev=True)

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
                [x for x in affiliations.values()
                 if x.type == AffiliationType.STANDARD] +
                [null_tuple(Affiliation)._replace(id=0, name='Unknown')],
            'affiliation_total': {},
            'affiliation_accepted': {},
            'affiliation_available': {},
            'affiliation_original': {},
        }

    def _get_proposal_tabulation_titles(self, tabulation):
        return chain(
            [
                'Proposal', 'PI name', 'PI affiliation', 'Co-Investigators',
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
                    (None if proposal['member_pi'] is None
                     else proposal['member_pi'].person_name),
                    (None if proposal['member_pi'] is None
                     else proposal['member_pi'].affiliation_name),
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

    @with_call_review(permission=PermissionType.EDIT)
    def view_review_affiliation_weight(self, db, call, can, form):
        type_class = self.get_call_types()
        message = None

        affiliations = db.search_affiliation(
            queue_id=call.queue_id, hidden=False,
            type_=AffiliationType.STANDARD,
            with_weight_call_id=call.id)

        if form is not None:
            try:
                updated_affiliations = OrderedDict()
                for affiliation in affiliations.values():
                    id_ = affiliation.id
                    updated_affiliations[id_] = affiliation._replace(
                        weight=float(form['weight_{}'.format(id_)]))

                updates = db.sync_affiliation_weight(
                    call_id=call.id, records=updated_affiliations)

                if any(updates):
                    flash('The affiliation weights have been updated.')
                raise HTTPRedirect(url_for('.review_call', call_id=call.id))

            except UserError as e:
                message = e.message
                affiliations = updated_affiliations

        return {
            'title': 'Affiliation Weight: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
            'message': message,
            'affiliations': affiliations,
        }

    @with_call_review(permission=PermissionType.EDIT)
    def view_review_call_available(self, db, call, can, form):
        raise ErrorPage('Time available not implemented for this facility.')

    @with_call_review(permission=PermissionType.EDIT)
    def view_review_call_deadline(self, db, call, can,form):
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
                        form['date_date_{}'.format(role_id)],
                        form['date_time_{}'.format(role_id)])

                    if date.date == '' and date.time == '':
                        continue

                    record = deadlines.get_role(role_id, None)

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
    def view_review_call_reviewers(self, db, call, can, args):
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

        proposals = []
        invite_roles = role_class.get_invited_roles()
        state_editable_roles = {}

        for proposal in db.search_proposal(
                call_id=call.id, state=ProposalState.review_states(),
                with_member_pi=True, with_reviewers=True,
                with_review_info=True,
                with_reviewer_role=role, with_review_state=state).values():
            roles = state_editable_roles.get(proposal.state)
            if roles is None:
                roles = role_class.get_editable_roles(proposal.state)
                state_editable_roles[proposal.state] = roles

            proposals.append(ProposalWithInviteRoles(
                *proposal,
                invite_roles=[x for x in invite_roles if x in roles],
                code=self.make_proposal_code(db, proposal)))

        return {
            'title': 'Reviewers: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
            'proposals': proposals,
            'targets': [
                Link('Assign technical assessors',
                     url_for('.review_call_grid', call_id=call.id,
                             reviewer_role=role_class.TECH)),
                Link('Assign committee members',
                     url_for('.review_call_grid', call_id=call.id,
                             reviewer_role=role_class.CTTEE_PRIMARY))],
            'roles': role_class.get_options(),
            'states': ReviewState.get_options(),
            'current_role': role,
            'current_state': state,
        }

    @with_call_review(permission=PermissionType.EDIT)
    def view_reviewer_grid(self, db, call, can,
                           primary_role, form):
        role_class = self.get_reviewer_roles()
        type_class = self.get_call_types()

        # Dictionaries of roles which we are processing and roles which
        # conflict with them.
        roles = OrderedDict((
            (primary_role, role_class.get_info(primary_role)),))
        roles_conflict = {}

        if primary_role == role_class.TECH:
            group_type = GroupType.TECH

        elif primary_role == role_class.CTTEE_PRIMARY:
            group_type = GroupType.CTTEE
            roles[role_class.CTTEE_SECONDARY] = role_class.get_info(
                role_class.CTTEE_SECONDARY)
            roles_conflict[role_class.CTTEE_OTHER] = role_class.get_info(
                role_class.CTTEE_OTHER)

        else:
            raise ErrorPage('Unexpected reviewer role')

        # All roles to consider: those we are processing plus those
        # which may conflict with them.
        all_roles = set(roles.keys())
        all_roles.update(roles_conflict.keys())

        group_info = GroupType.get_info(group_type)

        group_members = db.search_group_member(queue_id=call.queue_id,
                                               group_type=group_type,
                                               with_person=True)

        group_person_ids = [x.person_id for x in group_members.values()]

        proposals = []
        for proposal in db.search_proposal(
                call_id=call.id,
                state=role_class.get_editable_states(primary_role),
                with_members=True, with_reviewers=True,
                with_review_info=True, with_reviewer_role=all_roles).values():
            # Emulate search_proposal(with_member_pi=True) behaviour by setting
            # the "member" attribute to just the PI.
            member_pi = proposal.members.get_pi(default=None)
            if member_pi is not None:
                proposal = proposal._replace(member=with_can_view(
                    member_pi, (session.get('is_admin', False)
                                or member_pi.person_public)))

            proposals.append(ProposalWithReviewerPersons(
                *proposal, code=self.make_proposal_code(db, proposal),
                reviewer_person_ids={role_id: {
                    x.person_id: ReviewState.is_present(x.review_state)
                    for x in proposal.reviewers.values_by_role(role_id)}
                    for role_id in all_roles}))

        message = None

        if form is not None:
            # Read the form inputs into the review list.  Do this first
            # so that we can return the whole updated grid to the user
            # in case of an error performing the update.
            reviewers_orig = {}
            for proposal in proposals:
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

                for proposal in proposals:
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
                                role.name.lower(), proposal.code)

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
                                        proposal.code, role_other.name.lower(),
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
                      group_info.name.lower())
                raise HTTPRedirect(url_for('.review_call_reviewers',
                                           call_id=call.id))

            except UserError as e:
                message = e.message

        return {
            'title': '{}: {} {} {}'.format(
                group_info.name.title(),
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
                for proposal in proposals},
            'message': message,
        }

    @with_proposal(permission=PermissionType.NONE)
    def view_reviewer_add(self, db, proposal, role, form):
        role_class = self.get_reviewer_roles()
        text_role_class = self.get_text_roles()

        try:
            role_info = role_class.get_info(role)
        except KeyError:
            raise HTTPError('Unknown reviewer role')

        if not role_info.invite:
            raise HTTPError('Unexpected reviewer role.')

        if proposal.state not in role_class.get_editable_states(role):
            raise ErrorPage(
                'This proposal is not in a suitable state '
                'for this type of review.')

        try:
            call = db.get_call(facility_id=self.id_, call_id=proposal.call_id)
        except NoSuchRecord:
            raise HTTPError('The corresponding call was not found')

        if not auth.for_call_review(db, call).edit:
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

        member = dict(person_id=None, name='', title=None, email='')

        if form is not None:
            if 'person_id' in form:
                member['person_id'] = int(form['person_id'])
            member['name'] = form.get('name', '')
            if 'person_title' in form:
                member['title'] = int_or_none(form['person_title'])
            member['email'] = form.get('email', '')

            if 'submit_link' in form:
                try:
                    if member['person_id'] is None:
                        raise UserError(
                            'No-one was selected from the directory.')
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
                        db,
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

            elif 'submit_invite' in form:
                try:
                    if not member['name']:
                        raise UserError('Please enter the person\'s name.')
                    if not member['email']:
                        raise UserError('Please enter an email address.')

                    member['name'] = member['name'].strip()
                    member['email'] = member['email'].strip()

                    person_id = db.add_person(
                        member['name'], title=member['title'],
                        primary_email=member['email'])
                    reviewer_id = db.add_reviewer(
                        role_class=role_class,
                        proposal_id=proposal.id,
                        person_id=person_id, role=role)

                    self._message_review_invite(
                        db,
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

            else:
                raise ErrorPage('Unknown action.')

        # Prepare list of people to display as the registered member directory.
        # Note that this includes people without public profiles as this page
        # is restricted to privileged users administering a review process.
        exclude_person_ids = proposal_person_ids + existing_person_ids
        persons = [
            p for p in db.search_person(registered=True,
                                        with_institution=True).values()
            if p.id not in exclude_person_ids]

        try:
            abstract = db.get_proposal_text(proposal.id,
                                            text_role_class.ABSTRACT)
        except NoSuchRecord:
            abstract = None

        # Get the PI of the proposal (as for a with_member_pi search).
        member_pi = proposal.members.get_pi(default=None)
        if member_pi is not None:
            member_pi = with_can_view(
                member_pi,
                (session.get('is_admin', False) or member_pi.person_public))

        proposal_code = self.make_proposal_code(db, proposal)

        return {
            'title': '{}: Add {} Reviewer'.format(
                proposal_code, role_info.name.title()),
            'persons': persons,
            'member': member,
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
            'categories': db.search_proposal_category(
                proposal_id=proposal.id),
            'titles': PersonTitle.get_options(),
        }

    def _message_review_invite(self, db, proposal, role,
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

        email_ctx = {
            'recipient_name': person_name,
            'proposal': proposal,
            'proposal_code': proposal_code,
            'call_type': type_class.get_name(proposal.call_type),
            'role_info': role_info,
            'inviter_name': session['person']['name'],
            'target_proposal': url_for(
                '.proposal_view', proposal_id=proposal.id, _external=True),
            'target_review': url_for(
                '.review_edit',
                reviewer_id=reviewer_id, _external=True),
            'target_guideline': self.make_review_guidelines_url(role=role),
            'is_reminder': is_reminder,
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
    def view_reviewer_remove(self, db, reviewer, proposal, form):
        role_class = self.get_reviewer_roles()

        if proposal.state not in role_class.get_editable_states(reviewer.role):
            raise ErrorPage(
                'This proposal is not in a suitable state '
                'for this type of review.')

        try:
            call = db.get_call(facility_id=self.id_, call_id=proposal.call_id)
        except NoSuchRecord:
            raise HTTPError('The corresponding call was not found')

        if not auth.for_call_review(db, call).edit:
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
                                       call_id=call.id))

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
    def view_reviewer_reinvite(self, db, reviewer, proposal, form):
        return self._view_reviewer_reinvite_remind(
            db, reviewer, proposal, form, is_reminder=False)

    @with_review(permission=PermissionType.NONE, with_invitation=True)
    def view_reviewer_remind(self, db, reviewer, proposal, form):
        return self._view_reviewer_reinvite_remind(
            db, reviewer, proposal, form, is_reminder=True)

    def _view_reviewer_reinvite_remind(self, db, reviewer, proposal,
                                       form, is_reminder):
        role_class = self.get_reviewer_roles()

        if proposal.state not in role_class.get_editable_states(reviewer.role):
            raise ErrorPage(
                'This proposal is not in a suitable state '
                'for this type of review.')

        try:
            call = db.get_call(facility_id=self.id_, call_id=proposal.call_id)
        except NoSuchRecord:
            raise HTTPError('The corresponding call was not found')

        if not auth.for_call_review(db, call).edit:
            raise HTTPForbidden('Edit permission denied for this call.')

        if reviewer.person_registered and not is_reminder:
            raise ErrorPage('This reviewer is already registered.')

        try:
            role_info = role_class.get_info(reviewer.role)
        except KeyError:
            raise HTTPError('Unknown reviewer role')

        if not role_info.invite:
            raise HTTPError('Unexpected reviewer role.')

        if form is not None:
            if 'submit_confirm' in form:
                self._message_review_invite(
                    db,
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
                    reviewer.person_name,
                    ('sent a reminder message' if is_reminder
                     else 're-invited to register'))

            raise HTTPRedirect(url_for('.review_call_reviewers',
                                       call_id=call.id))

        proposal_code = self.make_proposal_code(db, proposal)

        return {
            'title': '{}: {} {} Reviewer'.format(
                proposal_code,
                ('Remind' if is_reminder else 'Re-invite'),
                role_info.name.title()),
            'message':
                'Would you like to re-send an invitation to {} '
                'to review proposal {}?'.format(
                    reviewer.person_name, proposal_code),
            'target': url_for(
                '.proposal_reviewer_{}'.format(
                    'remind' if is_reminder else 'reinvite'),
                reviewer_id=reviewer.id),
            'is_reminder': is_reminder,
            'proposal_id': proposal.id,
            'reviewer_id': reviewer.id,
            'person_registered': reviewer.person_registered,
        }

    @with_proposal(permission=PermissionType.NONE,
                   with_decision=True, with_decision_note=True)
    def view_review_new(self, db, proposal, reviewer_role, args, form):
        role_class = self.get_reviewer_roles()

        try:
            role_info = role_class.get_info(reviewer_role)
        except KeyError:
            raise HTTPError('Unknown reviewer role')

        if (role_info.unique and proposal.reviewers.has_role(reviewer_role)):
            raise ErrorPage(
                'There is already a "{}" reviewer for this proposal.',
                role_info.name)

        can_add_roles = auth.can_add_review_roles(role_class, db, proposal)

        if reviewer_role not in can_add_roles:
            raise HTTPForbidden(
                'You can not add a review in the "{}" role.'.format(
                    role_info.name))

        return self._view_review_new_or_edit(
            db, None, proposal, args, form, reviewer_role=reviewer_role)

    @with_review(permission=PermissionType.EDIT)
    def view_review_info(self, db, reviewer, proposal, can):
        proposal_code = self.make_proposal_code(db, proposal)

        return {
            'title': '{}: Review Information'.format(proposal_code),
            'reviewer': reviewer,
            'proposal_code': proposal_code,
        }

    @with_review(permission=PermissionType.EDIT,
                 with_decision=True, with_decision_note=True)
    def view_review_edit(self, db, reviewer, proposal, can, args, form):
        return self._view_review_new_or_edit(
            db, reviewer, proposal, args, form)

    def _view_review_new_or_edit(self, db, reviewer, proposal, args, form,
                                 reviewer_role=None):
        role_class = self.get_reviewer_roles()

        if reviewer is None:
            is_new_reviewer = True
            is_own_review = True
            target = url_for('.proposal_review_new', proposal_id=proposal.id,
                             reviewer_role=reviewer_role)
            reviewer = null_tuple(Reviewer)._replace(role=reviewer_role)

        else:
            is_new_reviewer = False
            is_own_review = (reviewer.person_id == session['person']['id'])
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
                        person_id=session['person']['id'],
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

        ctx = {
            'title': '{}: {} {}'.format(
                proposal_code,
                ('Add' if is_new_reviewer else 'Edit'),
                title_description),
            'target': target,
            'proposal_code': proposal_code,
            'proposal': proposal,
            'reviewer': with_can_view(
                reviewer,
                (session.get('is_admin', False) or reviewer.person_public)),
            'role_info': role_info,
            'assessment_options': Assessment.get_options(),
            'message': message,
            'referrer': referrer,
            'target_guideline': self.make_review_guidelines_url(
                role=reviewer.role),
            'calculators': (self.calculators if role_info.calc else None),
            'calculations': calculations,
            'figures': figures,
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
            self, db, reviewer, proposal, can, form):
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
            self, db, reviewer, proposal, can, review_calculation_id):
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

        return view_func(review_calculation=calculation, can=can)

    @with_review(permission=PermissionType.EDIT)
    def view_review_edit_figure(
            self, db, reviewer, proposal, can, fig_id, form, file_):
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
                    reviewer_id=reviewer.id, fig_id=fig_id,
                    with_caption=True).get_single()
            except NoSuchRecord:
                raise HTTPNotFound('Figure not found.')

            target = url_for(
                '.review_edit_figure', reviewer_id=reviewer.id, fig_id=fig_id)

        return self._view_edit_figure(
            db, form, file_, figure, proposal, reviewer, title=name,
            target_edit=target,
            target_redirect=url_for(
                '.review_edit', reviewer_id=reviewer.id))

    @with_review(permission=PermissionType.VIEW)
    def view_review_view_figure(
            self, db, reviewer, proposal, can, fig_id, md5sum, type_=None):
        if type_ is None:
            try:
                return db.get_review_figure(
                    reviewer.id, fig_id, md5sum=md5sum)
            except NoSuchRecord:
                raise HTTPNotFound('Figure not found.')

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
    def view_review_manage_figure(self, db, reviewer, proposal, can, form):
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

    @with_proposal(permission=PermissionType.NONE, with_decision=True)
    def view_proposal_reviews(self, db, proposal):
        role_class = self.get_reviewer_roles()
        text_role_class = self.get_text_roles()

        is_admin = session.get('is_admin', False)

        auth_cache = {}
        if not auth.for_review(role_class, db,
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
                member_pi, (is_admin or member_pi.person_public))
        proposal = proposal._replace(member=member_pi, reviewers=reviewers)

        # Add "can_edit" fields and hide non-public notes so that we don't
        # have to rely on the template to do this.  Also hide the rating
        # if not viewable.
        for (reviewer_id, reviewer) in db.search_reviewer(
                proposal_id=proposal.id, with_review=True,
                with_review_text=True, with_review_note=True).items():
            role_info = role_class.get_info(reviewer.role)
            reviewer_can = auth.for_review(
                role_class, db, reviewer=reviewer, proposal=proposal,
                auth_cache=auth_cache)

            if not reviewer.review_note_public:
                reviewer = reviewer._replace(review_note=None)

            if not reviewer_can.view_rating:
                reviewer = reviewer._replace(
                    review_rating=None, review_weight=None)

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
                can_view=(is_admin or reviewer.person_public),
                can_edit=reviewer_can.edit)

        self.attach_review_extra(db, {None: proposal})

        return {
            'title': '{}: Reviews'.format(proposal_code),
            'proposal': proposal,
            'proposal_code': proposal_code,
            'abstract': abstract,
            'categories': db.search_proposal_category(
                proposal_id=proposal.id),
            'reviews': reviewers,
            'overall_rating': self.calculate_overall_rating(reviewers),
            'can_add_roles': auth.can_add_review_roles(
                role_class, db, proposal, auth_cache=auth_cache),
            'can_edit_decision': auth.for_proposal_decision(
                db, proposal, auth_cache=auth_cache).edit,
        }

    @with_proposal(permission=PermissionType.NONE,
                   with_decision=True, with_decision_note=True)
    def view_proposal_decision(self, db, proposal, args, form):
        if not auth.for_proposal_decision(db, proposal).edit:
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
                member_pi,
                session.get('is_admin', False) or member_pi.person_public)

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
    def view_review_advance_final(self, db, call, can, form):
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
            is_admin = session.get('is_admin', False)

            call_proposals = call_proposals.map_values(
                lambda x: ProposalWithCode(
                    *x, code=self.make_proposal_code(db, x)
                )._replace(member=with_can_view(
                    x.member, (is_admin or x.member.person_public))))

        return {
            'title': 'Final Review: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'message':
                'Are you sure you wish to advance to the final review phase?',
            'target': url_for('.review_call_advance_final', call_id=call.id),
            'call': call,
            'proposals': call_proposals,
        }

    @with_call_review(permission=PermissionType.EDIT)
    def view_review_confirm_feedback(self, db, call, can, form):
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

        is_admin = session.get('is_admin', False)

        return {
            'title': 'Feedback: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
            'proposals': proposals.map_values(
                lambda x: ProposalWithCode(
                    *x, code=self.make_proposal_code(db, x)
                )._replace(reviewers=x.reviewers.map_values(
                    lambda y: with_can_view(
                        y, (is_admin or y.person_public))))),
            'message': message,
        }
