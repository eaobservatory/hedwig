# Copyright (C) 2015-2016 East Asian Observatory
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

from collections import namedtuple, OrderedDict
from datetime import datetime
from itertools import izip
import re

from ...admin.proposal import finalize_call_review
from ...email.format import render_email_template
from ...error import DatabaseIntegrityError, NoSuchRecord, UserError
from ...file.csv import CSVWriter
from ...view import auth
from ...view.util import with_proposal, with_call_review, with_review
from ...web.util import ErrorPage, \
    HTTPError, HTTPForbidden, HTTPNotFound, HTTPRedirect, \
    flash, session, url_for
from ...type.collection import ReviewerCollection
from ...type.enum import AffiliationType, Assessment, \
    FileTypeInfo, FormatType, GroupType, \
    MessageThreadType, PermissionType, PersonTitle, ProposalState, ReviewState
from ...type.simple import Affiliation, Link, MemberPIInfo, \
    ProposalWithCode, Reviewer
from ...type.util import null_tuple, with_can_edit


ProposalWithInviteRoles = namedtuple(
    'ProposalWithInviteRoles',
    ProposalWithCode._fields + ('invite_roles',))

ProposalWithReviewers = namedtuple(
    'ProposalWithReviewers',
    ProposalWithCode._fields + (
        'reviewers_primary', 'reviewers_secondary', 'can_view_review'))

ProposalWithReviewerPersons = namedtuple(
    'ProposalWithReviewerPersons',
    ProposalWithCode._fields + ('person_ids_primary', 'person_ids_secondary'))


class GenericReview(object):
    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call(self, db, call, can):
        role_class = self.get_reviewer_roles()

        proposals = []

        for proposal in db.search_proposal(
                call_id=call.id, state=ProposalState.submitted_states(),
                with_members=True, with_reviewers=True,
                with_reviewer_role=(role_class.CTTEE_PRIMARY,
                                    role_class.CTTEE_SECONDARY),
                with_decision=True, with_categories=True).values():
            member_pi = proposal.members.get_pi(default=None)

            review_can = auth.for_review(
                role_class, db, reviewer=None, proposal=proposal,
                auth_cache=can.cache)

            proposals.append(ProposalWithReviewers(
                *proposal._replace(member=member_pi),
                code=self.make_proposal_code(db, proposal),
                reviewers_primary=proposal.reviewers.values_by_role(
                    role_class.CTTEE_PRIMARY),
                reviewers_secondary=proposal.reviewers.values_by_role(
                    role_class.CTTEE_SECONDARY),
                can_view_review=review_can.view))

        return {
            'title': 'Review Process: {} {}'.format(call.semester_name,
                                                    call.queue_name),
            'can_edit': can.edit,
            'call_id': call.id,
            'proposals': proposals,
        }

    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call_tabulation(self, db, call, can):
        ctx = {
            'title': 'Proposal Tabulation: {} {}'.format(call.semester_name,
                                                         call.queue_name),
            'call': call,
        }

        ctx.update(self._get_proposal_tabulation(db, call, can))

        return ctx

    @with_call_review(permission=PermissionType.VIEW)
    def view_review_call_tabulation_download(self, db, call, can,
                                             with_cois=True):
        tabulation = self._get_proposal_tabulation(
            db, call, can, with_extra=True)

        writer = CSVWriter()

        titles = self._get_proposal_tabulation_titles(tabulation)
        if with_cois:
            titles.append('Co-Investigator names')
        writer.add_row(titles)

        for (row, proposal) in izip(
                self._get_proposal_tabulation_rows(tabulation),
                tabulation['proposals']):
            if with_cois:
                row.extend([
                    '{} ({})'.format(x.person_name, x.affiliation_name)
                    for x in proposal['members']
                    if not x.pi])
            writer.add_row(row)

        return (
            writer.get_csv(),
            null_tuple(FileTypeInfo)._replace(mime='text/csv'),
            'proposals-{}-{}.csv'.format(
                re.sub('[^-_a-z0-9]', '_', call.semester_name.lower()),
                re.sub('[^-_a-z0-9]', '_', call.queue_name.lower())))

    def _get_proposal_tabulation(self, db, call, can, with_extra=False):
        """Prepare information for the detailed tabulation of proposals.

        This is used to prepare the information both for the online
        version and the downloadable CSV file.  For the CSV file, the
        `with_extra` option is enabled and additional information,
        beyond that which can be displayed on the online version,
        is retrieved.
        """

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
                'members': list(proposal.members.values()),
                'code': self.make_proposal_code(db, proposal),
                'affiliations': self.calculate_affiliation_assignment(
                    db, proposal.members, affiliations),
                'can_edit_decision': (
                    can.edit and proposal.state == ProposalState.FINAL_REVIEW),
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

                    reviewers[reviewer_id] = with_can_edit(
                        reviewer, reviewer_can.edit)

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
        return (
            [
                'Proposal', 'PI name', 'PI affiliation', 'Co-Investigators',
                'Title', 'State',
                'Decision', 'Exempt', 'Rating', 'Rating std. dev.',
                'Categories',
            ] +
            [x.name for x in tabulation['affiliations']]
        )

    def _get_proposal_tabulation_rows(self, tabulation):
        affiliations = tabulation['affiliations']

        for proposal in tabulation['proposals']:
            decision_accept = proposal['decision_accept']

            yield (
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
                ] +
                [proposal['affiliations'].get(x.id) for x in affiliations]
            )

    @with_call_review(permission=PermissionType.EDIT)
    def view_review_affiliation_weight(self, db, call, can, form):
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
            'title': 'Affiliation Weight: {} {}'.format(call.semester_name,
                                                        call.queue_name),
            'call': call,
            'message': message,
            'affiliations': affiliations.values(),
        }

    @with_call_review(permission=PermissionType.EDIT)
    def view_review_call_available(self, db, call, can, form):
        raise ErrorPage('Time available not implemented for this facility.')

    @with_call_review(permission=PermissionType.EDIT)
    def view_review_call_reviewers(self, db, call, can, args):
        role_class = self.get_reviewer_roles()

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
            'title': 'Reviewers: {} {}'.format(call.semester_name,
                                               call.queue_name),
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

        try:
            call = db.get_call(facility_id=self.id_, call_id=call.id)
        except NoSuchRecord:
            raise HTTPNotFound('Call or semester not found')

        if primary_role == role_class.TECH:
            group_type = GroupType.TECH
            secondary_role = None

        elif primary_role == role_class.CTTEE_PRIMARY:
            group_type = GroupType.CTTEE
            secondary_role = role_class.CTTEE_SECONDARY

        else:
            raise ErrorPage('Unexpected reviewer role')

        primary_role_info = role_class.get_info(primary_role)
        secondary_role_info = (None if secondary_role is None else
                               role_class.get_info(secondary_role))

        group_info = GroupType.get_info(group_type)

        group_members = db.search_group_member(queue_id=call.queue_id,
                                               group_type=group_type,
                                               with_person=True)

        group_person_ids = [x.person_id for x in group_members.values()]

        proposals = []
        for proposal in db.search_proposal(
                call_id=call.id,
                state=role_class.get_editable_states(primary_role),
                with_members=True, with_reviewers=True).values():
            # Emulate search_proposal(with_member_pi=True) behaviour by setting
            # the "member" attribute to just the PI.
            proposal = proposal._replace(
                member=proposal.members.get_pi(default=None))

            proposals.append(ProposalWithReviewerPersons(
                *proposal, code=self.make_proposal_code(db, proposal),
                person_ids_primary=(
                    proposal.reviewers.person_id_by_role(primary_role)),
                person_ids_secondary=(
                    None if secondary_role is None else
                    proposal.reviewers.person_id_by_role(secondary_role))))

        role_list = zip([primary_role, secondary_role],
                        [primary_role_info, secondary_role_info],
                        ['primary', 'secondary'])

        message = None

        if form is not None:
            # Read the form inputs into an updated proposal list.  Do this
            # first so that we can return the whole updated grid to the user
            # in case of an error performing the update.
            proposals_updated = []
            for proposal in proposals:
                for (role, role_info, prefix) in role_list:
                    if role is None:
                        continue

                    if role_info.unique:
                        # Read the radio button setting.
                        person_ids = []
                        id_ = '{}_{}'.format(prefix, proposal.id)
                        if id_ in form:
                            person_id = int(form[id_])
                            if person_id in group_person_ids:
                                person_ids = [person_id]

                    else:
                        # See which checkbox inputs are present.
                        person_ids = [
                            x for x in group_person_ids
                            if '{}_{}_{}'.format(prefix, proposal.id, x)
                            in form]

                    proposal = proposal._replace(
                        **{'person_ids_{}'.format(prefix): person_ids})

                proposals_updated.append(proposal)

            try:
                reviewer_remove = []
                reviewer_add = []

                for (proposal, proposal_updated) in zip(
                        proposals, proposals_updated):
                    for (role, role_info, prefix) in role_list:
                        if role is None:
                            continue
                        if proposal.id != proposal_updated.id:
                            raise HTTPError('Proposals got out of sync.')

                        id_ = 'person_ids_{}'.format(prefix)
                        orig = getattr(proposal, id_)
                        updated = getattr(proposal_updated, id_)

                        # Apply uniqueness constraint.
                        if role_info.unique and (len(updated) > 1):
                            raise UserError(
                                'Multiple {} reviewers selected for '
                                'proposal {}.',
                                prefix, proposal.code)

                        for person_id in updated:
                            if person_id in orig:
                                orig.remove(person_id)
                            else:
                                if proposal.members.has_person(person_id):
                                    raise UserError(
                                        'A proposal member has been selected '
                                        'as a reviewer for proposal {}.',
                                        proposal.code)

                                reviewer_add.append({
                                    'proposal_id': proposal.id,
                                    'person_id': person_id,
                                    'role': role,
                                })

                        for person_id in orig:
                            reviewer_remove.append({
                                'proposal_id': proposal.id,
                                'person_id': person_id,
                                'role': role,
                            })

                try:
                    db.multiple_reviewer_update(
                        role_class=role_class,
                        remove=reviewer_remove, add=reviewer_add)
                except DatabaseIntegrityError:
                    raise UserError(
                        'Could not update reviewer assignments. '
                        'Perhaps you are trying to remove a reviewer '
                        'who already provided a review?')

                flash('The {} assignments have been updated.',
                      group_info.name.lower())
                raise HTTPRedirect(url_for('.review_call_reviewers',
                                           call_id=call.id))

            except UserError as e:
                message = e.message
                proposals = proposals_updated

        return {
            'title': '{}: {} {}'.format(group_info.name.title(),
                                        call.semester_name, call.queue_name),
            'call': call,
            'proposals': proposals,
            'target': url_for('.review_call_grid', call_id=call.id,
                              reviewer_role=primary_role),
            'group_members': list(group_members.values()),
            'primary_unique': primary_role_info.unique,
            'secondary_unique': (None if secondary_role_info is None else
                                 secondary_role_info.unique),
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
                member['title'] = (None if (form['person_title'] == '')
                                   else int(form['person_title']))
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

                    person_id = db.add_person(member['name'],
                                              title=member['title'])
                    db.add_email(person_id, member['email'], primary=True)
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
                    session['next_page'] = url_for(
                        '.review_call_reviewers', call_id=proposal.call_id)

                    raise HTTPRedirect(url_for(
                        'people.person_edit_institution', person_id=person_id))

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

        # Attach the PI to the proposal (as for a with_member_pi search).
        proposal = proposal._replace(
            member=proposal.members.get_pi(default=None))

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
            'proposal': proposal,
            'proposal_code': proposal_code,
            'call': call,
            'abstract': abstract,
            'categories': db.search_proposal_category(
                proposal_id=proposal.id).values(),
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
                (token, expiry) = db.add_invitation(person_id)

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

        if reviewer.review_state != ReviewState.NOT_DONE:
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

    @with_review(permission=PermissionType.NONE)
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

    @with_proposal(permission=PermissionType.NONE)
    def view_review_new(self, db, proposal, reviewer_role, form):
        role_class = self.get_reviewer_roles()

        try:
            role_info = role_class.get_info(reviewer_role)
        except KeyError:
            raise HTTPError('Unknown reviewer role')

        if (role_info.unique and
                proposal.reviewers.person_id_by_role(reviewer_role)):
            raise ErrorPage(
                'There is already a "{}" reviewer for this proposal.',
                role_info.name)

        can_add_roles = auth.can_add_review_roles(role_class, db, proposal)

        if reviewer_role not in can_add_roles:
            raise HTTPForbidden(
                'You can not add a review in the "{}" role.'.format(
                    role_info.name))

        return self._view_review_new_or_edit(
            db, None, proposal, None, form, reviewer_role=reviewer_role)

    @with_review(permission=PermissionType.EDIT)
    def view_review_info(self, db, reviewer, proposal, can):
        proposal_code = self.make_proposal_code(db, proposal)

        return {
            'title': '{}: Review Information'.format(proposal_code),
            'reviewer': reviewer,
            'proposal_code': proposal_code,
        }

    @with_review(permission=PermissionType.EDIT)
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
            referrer = 'pr'
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
            try:
                # Read form inputs first.
                referrer = form.get('referrer', None)

                if role_info.text:
                    reviewer = reviewer._replace(
                        review_text=form['text'],
                        review_format=FormatType.PLAIN)

                if role_info.assessment:
                    try:
                        reviewer = reviewer._replace(
                            review_assessment=int(form['assessment']))
                    except:
                        raise UserError('Please select an assessment.')

                if role_info.rating:
                    try:
                        reviewer = reviewer._replace(
                            review_rating=int(form['rating']))
                    except:
                        raise UserError('Please provide an integer rating.')

                if role_info.weight:
                    try:
                        reviewer = reviewer._replace(
                            review_weight=int(form['weight']))
                    except:
                        raise UserError('Please provide an integer '
                                        'self-assessment weighting.')

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

                extra_info = self._view_review_edit_get(
                    db, reviewer, proposal, form)

                # Validate the form inputs.
                if role_info.assessment:
                    if not Assessment.is_valid(reviewer.review_assessment):
                        raise UserError('Selected assessment not recognized.')

                if role_info.rating:
                    if not (0 <= reviewer.review_rating <= 100):
                        raise UserError('Please give a rating between '
                                        '0 and 100.')

                if role_info.weight:
                    if not (0 <= reviewer.review_weight <= 100):
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
                    is_update=(not (
                        is_new_reviewer
                        or (reviewer.review_state == ReviewState.NOT_DONE))))

                flash('The review has been saved.')

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

        ctx = {
            'title': '{}: {} {}'.format(
                proposal_code,
                ('Add' if is_new_reviewer else 'Edit'),
                title_description),
            'target': target,
            'proposal_code': proposal_code,
            'proposal': proposal,
            'reviewer': reviewer,
            'role_info': role_info,
            'assessment_options': Assessment.get_options(),
            'message': message,
            'referrer': referrer,
            'target_guideline': self.make_review_guidelines_url(
                role=reviewer.role),
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
        """

        return None

    def _view_review_edit_save(self, db, reviewer, proposal, info):
        """
        Placeholder for facility-specific method to parse previously-read
        form inputs and store them in the database.

        :raises UserError: in  the event of a problem with the input
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

    @with_proposal(permission=PermissionType.NONE)
    def view_proposal_reviews(self, db, proposal):
        role_class = self.get_reviewer_roles()
        text_role_class = self.get_text_roles()

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
        proposal = proposal._replace(
            member=proposal.members.get_pi(default=None),
            reviewers=reviewers)

        # Add "can_edit" fields and hide non-public notes so that we don't
        # have to rely on the template to do this.  Also hide the rating
        # if not viewable.
        for (reviewer_id, reviewer) in db.search_reviewer(
                proposal_id=proposal.id, with_review=True,
                with_review_text=True, with_review_note=True).items():
            reviewer_can = auth.for_review(
                role_class, db, reviewer=reviewer, proposal=proposal,
                auth_cache=auth_cache)

            if not reviewer.review_note_public:
                reviewer = reviewer._replace(review_note=None)

            if not reviewer_can.view_rating:
                reviewer = reviewer._replace(
                    review_rating=None, review_weight=None)

            reviewers[reviewer_id] = with_can_edit(reviewer, reviewer_can.edit)

        self.attach_review_extra(db, {None: proposal})

        return {
            'title': '{}: Reviews'.format(proposal_code),
            'proposal': proposal,
            'proposal_code': proposal_code,
            'abstract': abstract,
            'categories': db.search_proposal_category(
                proposal_id=proposal.id).values(),
            'reviews': list(reviewers.values()),
            'overall_rating': self.calculate_overall_rating(reviewers),
            'can_add_roles': auth.can_add_review_roles(
                role_class, db, proposal, auth_cache=auth_cache),
        }

    def view_proposal_decision(self, db, proposal_id, form):
        try:
            proposal = db.search_proposal(
                facility_id=self.id_, proposal_id=proposal_id,
                with_member_pi=True,
                with_decision=True, with_decision_note=True).get_single()
        except NoSuchRecord:
            raise HTTPError('The proposal was not found.')

        if proposal.state != ProposalState.FINAL_REVIEW:
            raise ErrorPage('This proposal is not under final review.')

        try:
            call = db.get_call(facility_id=self.id_, call_id=proposal.call_id)
        except NoSuchRecord:
            raise HTTPError('The corresponding call was not found.')

        if not auth.for_call_review(db, call).edit:
            raise HTTPForbidden('Edit permission denied for this call.')

        message = None
        extra_info = None
        proposal_code = self.make_proposal_code(db, proposal)

        if form is not None:
            try:
                # Read form inputs.
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
                    note_format=proposal.decision_note_format,
                    is_update=proposal.has_decision)

                flash('The decision for proposal {} has been saved.',
                      proposal_code)

                # Redirect back to tabulation page.
                raise HTTPRedirect(url_for('.review_call_tabulation',
                                           call_id=call.id))

            except UserError as e:
                message = e.message

        ctx = {
            'title': '{}: Decision'.format(proposal_code),
            'proposal': proposal,
            'proposal_code': proposal_code,
            'message': message,
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
        if form is not None:
            if 'submit_confirm' in form:
                (n_update, n_error) = finalize_call_review(db, call_id=call.id)

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

        return {
            'title': 'Final Review: {} {}'.format(call.semester_name,
                                                  call.queue_name),
            'message':
                'Are you sure you wish to advance to the final review phase?',
            'target': url_for('.review_call_advance_final', call_id=call.id),
            'call': call,
        }

    @with_call_review(permission=PermissionType.EDIT)
    def view_review_confirm_feedback(self, db, call, can, form):
        role_class = self.get_reviewer_roles()

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
                        db.set_decision(
                            proposal_id=id_, ready=ready, is_update=True)

                    flash('The feedback approval status has been updated.')

                raise HTTPRedirect(url_for('.review_call', call_id=call.id))

            except UserError as e:
                message = e.message

        return {
            'title': 'Feedback: {} {}'.format(call.semester_name,
                                              call.queue_name),
            'call': call,
            'proposals': [
                ProposalWithCode(*x, code=self.make_proposal_code(db, x))
                for x in proposals.values()],
            'message': message,
        }
