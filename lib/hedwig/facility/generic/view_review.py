# Copyright (C) 2015 East Asian Observatory
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
from itertools import izip
import re

from ...email.format import render_email_template
from ...error import DatabaseIntegrityError, NoSuchRecord, UserError
from ...file.csv import CSVWriter
from ...util import get_countries
from ...view import auth
from ...view.util import with_proposal, with_call_review, with_review
from ...web.util import ErrorPage, \
    HTTPError, HTTPForbidden, HTTPNotFound, HTTPRedirect, \
    flash, session, url_for
from ...type import Affiliation, Assessment, \
    FileTypeInfo, FormatType, GroupType, Link, MemberPIInfo, \
    ProposalState, ProposalWithCode, \
    Reviewer, ReviewerCollection, ReviewerRole, TextRole, \
    null_tuple

ProposalWithReviewerPersons = namedtuple(
    'ProposalWithReviewerPersons',
    ProposalWithCode._fields + ('person_ids_primary', 'person_ids_secondary'))


class GenericReview(object):
    @with_call_review(permission='view')
    def view_review_call(self, db, call, can):
        proposals = db.search_proposal(
            call_id=call.id, state=ProposalState.submitted_states(),
            person_pi=True, with_reviewers=True,
            with_reviewer_role=ReviewerRole.CTTEE_PRIMARY,
            with_decision=True)

        return {
            'title': 'Review Process: {} {}'.format(call.semester_name,
                                                    call.queue_name),
            'can_edit': can.edit,
            'call_id': call.id,
            'proposals': [
                ProposalWithCode(*x, code=self.make_proposal_code(db, x),
                                 facility_code=None)
                for x in proposals.values()],
        }

    @with_call_review(permission='view')
    def view_review_call_tabulation(self, db, call, can):
        ctx = {
            'title': 'Proposal Tabulation: {} {}'.format(call.semester_name,
                                                         call.queue_name),
            'call': call,
        }

        ctx.update(self._get_proposal_tabulation(db, call))

        return ctx

    @with_call_review(permission='view')
    def view_review_call_tabulation_download(self, db, call, can,
                                             with_cois=True):
        tabulation = self._get_proposal_tabulation(db, call)

        writer = CSVWriter()

        titles = self._get_proposal_tabulation_titles(tabulation)
        if with_cois:
            titles.append('Co-Investigators')
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
            FileTypeInfo(name='CSV', mime='text/csv', preview=None),
            'proposals-{}-{}.csv'.format(
                re.sub('[^-_a-z0-9]', '_', call.semester_name.lower()),
                re.sub('[^-_a-z0-9]', '_', call.queue_name.lower())))

    def _get_proposal_tabulation(self, db, call):
        proposals = db.search_proposal(
            call_id=call.id, state=ProposalState.submitted_states(),
            with_members=True, with_reviewers=True, with_review_info=True,
            with_decision=True)

        affiliations = db.search_affiliation(
            queue_id=call.queue_id, hidden=False, with_weight_call_id=call.id)

        cs = get_countries()
        person_id = session['person']['id']

        proposal_list = []
        for proposal in proposals.values():
            try:
                member_pi = proposal.members.get_pi()
            except KeyError:
                member_pi = None

            try:
                proposal.members.get_person(person_id)
                can_view_review = False
            except KeyError:
                can_view_review = True

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
                'members': [
                    x._replace(
                        institution_country=cs.get(x.institution_country))
                    for x in proposal.members.values()],
                'code': self.make_proposal_code(db, proposal),
                'affiliations': self.calculate_affiliation_assignment(
                    db, proposal.members, affiliations),
            })

            if can_view_review:
                updated_proposal['rating'] = \
                    self.calculate_overall_rating(proposal.reviewers)

            else:
                # Remove 'reviewers' from dictionary for safety, so that
                # we don't have to rely on the template hiding reviews
                # which the user can't see.
                updated_proposal.update({
                    'reviewers': ReviewerCollection(),
                    'rating': None,
                })

            proposal_list.append(updated_proposal)

        return {
            'proposals': proposal_list,
            'affiliations': [
                x for x in affiliations.values() if not x.exclude] +
                [null_tuple(Affiliation)._replace(id=0, name='Unknown')],
            'affiliation_total': {},
            'affiliation_accepted': {},
        }

    def _get_proposal_tabulation_titles(self, tabulation):
        return (
            [
                'Proposal', 'PI name', 'PI affiliation', 'Title',
                'State', 'Decision', 'Exempt', 'Rating',
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
                    proposal['title'],
                    ProposalState.get_name(proposal['state']),
                    (None if decision_accept is None
                     else ('Accept' if decision_accept else 'Reject')),
                    ('Exempt' if proposal['decision_exempt'] else None),
                    proposal['rating'],
                ] +
                [proposal['affiliations'].get(x.id) for x in affiliations]
            )

    @with_call_review(permission='edit')
    def view_review_affiliation_weight(self, db, call, can, form):
        message = None

        affiliations = db.search_affiliation(
            queue_id=call.queue_id, hidden=False, exclude=False,
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

    @with_call_review(permission='edit')
    def view_review_call_reviewers(self, db, call, can):
        proposals = db.search_proposal(
            call_id=call.id, state=ProposalState.REVIEW,
            person_pi=True, with_reviewers=True, with_review_info=True)

        return {
            'title': 'Reviewers: {} {}'.format(call.semester_name,
                                               call.queue_name),
            'call': call,
            'proposals': [
                ProposalWithCode(*x, code=self.make_proposal_code(db, x),
                                 facility_code=None)
                for x in proposals.values()],
            'targets': [
                Link('Assign technical assessors',
                     url_for('.review_call_technical', call_id=call.id)),
                Link('Assign committee members',
                     url_for('.review_call_committee', call_id=call.id))],
        }

    @with_call_review(permission='edit')
    def view_reviewer_grid(self, db, call, can, primary_role, form):
        try:
            call = db.get_call(facility_id=self.id_, call_id=call.id)
        except NoSuchRecord:
            raise HTTPNotFound('Call or semester not found')

        if primary_role == ReviewerRole.TECH:
            group_type = GroupType.TECH
            secondary_role = None
            target = url_for('.review_call_technical', call_id=call.id)

        elif primary_role == ReviewerRole.CTTEE_PRIMARY:
            group_type = GroupType.CTTEE
            secondary_role = ReviewerRole.CTTEE_SECONDARY
            target = url_for('.review_call_committee', call_id=call.id)

        else:
            raise ErrorPage('Unexpected reviewer role')

        primary_role_info = ReviewerRole.get_info(primary_role)
        secondary_role_info = (None if secondary_role is None else
                               ReviewerRole.get_info(secondary_role))

        group_info = GroupType.get_info(group_type)

        group_members = db.search_group_member(queue_id=call.queue_id,
                                               group_type=group_type,
                                               with_person=True)

        group_person_ids = [x.person_id for x in group_members.values()]

        # Set of proposals and person identifiers to use to avoid allocating
        # someone the review of their own proposal.
        proposal_members = set()

        proposals = []
        for proposal in db.search_proposal(
                call_id=call.id, state=ProposalState.REVIEW,
                with_members=True, with_reviewers=True).values():

            for member in proposal.members.values():
                proposal_members.add((proposal.id, member.person_id))

            try:
                proposal_pi = proposal.members.get_pi()
            except KeyError:
                proposal_pi = null_tuple(MemberPIInfo)

            # Emulate search_proposal(person_pi=True) behaviour by setting
            # the "members" attribute to just the PI.
            proposal = proposal._replace(members=proposal_pi)

            proposals.append(ProposalWithReviewerPersons(
                *proposal, code=self.make_proposal_code(db, proposal),
                facility_code=None,
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
                                if ((proposal.id, person_id)
                                        in proposal_members):
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
            'target': target,
            'group_members': list(group_members.values()),
            'primary_unique': primary_role_info.unique,
            'secondary_unique': (None if secondary_role_info is None else
                                 secondary_role_info.unique),
            'message': message,
            'proposal_members': proposal_members,
        }

    @with_proposal(permission='none')
    def view_reviewer_add(self, db, proposal, role, form):
        try:
            role_info = ReviewerRole.get_info(role)
        except KeyError:
            raise HTTPError('Unknown reviewer role')

        if proposal.state != ProposalState.REVIEW:
            raise ErrorPage('This proposal is not under review.')

        try:
            call = db.get_call(facility_id=self.id_, call_id=proposal.call_id)
        except NoSuchRecord:
            raise HTTPError('The corresponding call was not found')

        if not auth.for_call_review(db, call).edit:
            raise HTTPForbidden('Edit permission denied for this call.')

        proposal_code = self.make_proposal_code(db, proposal)

        proposal_person_ids = [
            x.person_id for x in proposal.members.values()
        ]

        existing_person_ids = [
            x.person_id for x in db.search_reviewer(
                proposal_id=proposal.id, role=role).values()
        ]

        message_link = None
        message_invite = None

        member = dict(person_id=None, name='', email='')

        if form is not None:
            if 'person_id' in form:
                member['person_id'] = int(form['person_id'])
            member['name'] = form.get('name', '')
            member['email'] = form.get('email', '')

            email_ctx = {
                'proposal': proposal,
                'proposal_code': proposal_code,
                'role_info': role_info,
                'inviter_name': session['person']['name'],
                'target_proposal': url_for(
                    '.proposal_view', proposal_id=proposal.id, _external=True),
                'target_guideline': self.make_review_guidelines_url(role=role),
            }

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
                        proposal_id=proposal.id,
                        person_id=person.id, role=role)

                    email_ctx.update({
                        'recipient_name': person.name,
                        'target_review': url_for(
                            '.review_edit',
                            reviewer_id=reviewer_id, _external=True),
                    })

                    db.add_message(
                        'Proposal {} review'.format(proposal_code),
                        render_email_template('review_invitation.txt',
                                              email_ctx, facility=self),
                        [person.id])

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

                    person_id = db.add_person(member['name'])
                    db.add_email(person_id, member['email'], primary=True)
                    reviewer_id = db.add_reviewer(
                        proposal_id=proposal.id,
                        person_id=person_id, role=role)
                    (token, expiry) = db.add_invitation(person_id)

                    email_ctx.update({
                        'token': token,
                        'expiry': expiry,
                        'recipient_name': member['name'],
                        'target_review': url_for(
                            '.review_edit',
                            reviewer_id=reviewer_id, _external=True),
                        'target_url': url_for(
                            'people.invitation_token_enter',
                            token=token, _external=True),
                        'target_plain': url_for(
                            'people.invitation_token_enter',
                            _external=True),
                    })

                    db.add_message(
                        'Proposal {} review'.format(proposal_code),
                        render_email_template('review_invitation.txt',
                                              email_ctx, facility=self),
                        [person_id])

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
        cs = get_countries()
        exclude_person_ids = proposal_person_ids + existing_person_ids
        persons = [
            p._replace(institution_country=cs.get(p.institution_country))
            for p in db.search_person(registered=True, public=True,
                                      with_institution=True).values()
            if p.id not in exclude_person_ids]

        if role == ReviewerRole.EXTERNAL:
            target = url_for('.review_external_add', proposal_id=proposal.id)
        else:
            raise HTTPError('Unexpected reviewer role.')

        try:
            abstract = db.get_proposal_text(proposal.id, TextRole.ABSTRACT)
        except NoSuchRecord:
            abstract = None

        # Extract the PI before calling the template so that we can handle
        # the exception.
        person_pi = None
        try:
            person_pi = proposal.members.get_pi()
        except KeyError:
            pass

        return {
            'title': '{}: Add {} Reviewer'.format(
                proposal_code, role_info.name.title()),
            'persons': persons,
            'member': member,
            'message_link': message_link,
            'message_invite': message_invite,
            'target': target,
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
            'person_pi': person_pi,
        }

    @with_proposal(permission='none')
    def view_reviewer_remove(self, db, proposal, role, reviewer_id, form):
        try:
            role_info = ReviewerRole.get_info(role)
        except KeyError:
            raise HTTPError('Unknown reviewer role')

        if proposal.state != ProposalState.REVIEW:
            raise ErrorPage('This proposal is not under review.')

        try:
            call = db.get_call(facility_id=self.id_, call_id=proposal.call_id)
        except NoSuchRecord:
            raise HTTPError('The corresponding call was not found')

        if not auth.for_call_review(db, call).edit:
            raise HTTPForbidden('Edit permission denied for this call.')

        try:
            reviewer = db.search_reviewer(
                proposal_id=proposal.id, role=role, reviewer_id=reviewer_id,
                with_review=True).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Reviewer record not found.')

        if reviewer.review_present:
            raise ErrorPage('This reviewer already submitted a review.')

        proposal_code = self.make_proposal_code(db, proposal)

        if form is not None:
            if 'submit_confirm' in form:
                db.delete_reviewer(reviewer_id=reviewer_id)

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
        }

    @with_proposal(permission='none')
    def view_review_new(self, db, proposal, reviewer_role,
                        form, referrer=None):
        if proposal.state != ProposalState.REVIEW:
            raise HTTPForbidden(
                'This proposal is not currently under review.')

        try:
            role_info = ReviewerRole.get_info(reviewer_role)
        except KeyError:
            raise HTTPError('Unknown reviewer role')

        if (role_info.unique and
                proposal.reviewers.person_id_by_role(reviewer_role)):
            raise ErrorPage(
                'There is already a "{}" reviewer for this proposal.',
                role_info.name)

        can_add_roles = auth.can_add_review_roles(db, proposal)

        if reviewer_role not in can_add_roles:
            raise HTTPForbidden(
                'You can not add a review in the "{}" role.'.format(
                    role_info.name))

        return self._view_review_new_or_edit(
            db, None, proposal, form, referrer, reviewer_role=reviewer_role)

    @with_review(permission='edit')
    def view_review_info(self, db, reviewer, proposal, can):
        proposal_code = self.make_proposal_code(db, proposal)

        return {
            'title': '{}: Review Information'.format(proposal_code),
            'reviewer': reviewer,
            'proposal_code': proposal_code,
        }

    @with_review(permission='edit')
    def view_review_edit(self, db, reviewer, proposal, can, form,
                         referrer=None):
        return self._view_review_new_or_edit(
            db, reviewer, proposal, form, referrer)

    def _view_review_new_or_edit(self, db, reviewer, proposal, form, referrer,
                                 reviewer_role=None):
        if reviewer is None:
            is_new_reviewer = True
            target = url_for('.proposal_review_new', proposal_id=proposal.id,
                             reviewer_role=reviewer_role)
            reviewer = null_tuple(Reviewer)
        else:
            is_new_reviewer = False
            target = url_for('.review_edit', reviewer_id=reviewer.id)
            reviewer_role = reviewer.role

        try:
            role_info = ReviewerRole.get_info(reviewer_role)
        except KeyError:
            raise HTTPError('Unknown reviewer role')

        message = None

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
                    reviewer_id = db.add_reviewer(
                        proposal_id=proposal.id,
                        person_id=session['person']['id'],
                        role=reviewer_role)

                    # Change target in case of a UserError occurring while
                    # setting the review.
                    target = url_for('.review_edit', reviewer_id=reviewer_id)

                else:
                    reviewer_id = reviewer.id

                db.set_review(
                    reviewer_id=reviewer_id,
                    text=reviewer.review_text,
                    format_=reviewer.review_format,
                    assessment=reviewer.review_assessment,
                    rating=reviewer.review_rating,
                    weight=reviewer.review_weight,
                    is_update=reviewer.review_present)

                flash('The review has been saved.')

                raise HTTPRedirect(referrer if referrer
                                   else url_for('person_reviews'))

            except UserError as e:
                message = e.message

        proposal_code = self.make_proposal_code(db, proposal)

        title_description = role_info.name
        if role_info.name_review:
            title_description += ' Review'

        return {
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
        }

    @with_proposal(permission='none')
    def view_proposal_reviews(self, db, proposal):
        can = auth.for_review(db, reviewer=None, proposal=proposal)

        if not can.view:
            raise HTTPForbidden(
                'Permission denied for this proposal\'s reviews.')

        proposal_code = self.make_proposal_code(db, proposal)

        try:
            abstract = db.get_proposal_text(proposal.id, TextRole.ABSTRACT)
        except NoSuchRecord:
            abstract = None

        reviews = db.search_reviewer(proposal_id=proposal.id, with_review=True,
                                     with_review_text=True)

        # Extract the PI before calling the template so that we can handle
        # the exception.
        person_pi = None
        try:
            person_pi = proposal.members.get_pi()
        except KeyError:
            pass

        return {
            'title': '{}: Reviews'.format(proposal_code),
            'proposal': proposal,
            'proposal_code': proposal_code,
            'person_pi': person_pi,
            'abstract': abstract,
            'categories': db.search_proposal_category(
                proposal_id=proposal.id).values(),
            'reviews': reviews.values(),
            'overall_rating': self.calculate_overall_rating(reviews),
            'can_edit': can.edit,
            'can_add_roles': auth.can_add_review_roles(db, proposal),
        }
