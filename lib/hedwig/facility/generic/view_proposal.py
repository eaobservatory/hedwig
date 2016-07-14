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

from collections import namedtuple

from ...astro.coord import CoordSystem
from ...astro.catalog import parse_source_list
from ...email.format import render_email_template
from ...config import get_config
from ...error import ConsistencyError, NoSuchRecord, UserError
from ...file.info import determine_figure_type, determine_pdf_page_count
from ...publication.url import make_publication_url
from ...type.collection import PrevProposalCollection, ResultCollection, \
    TargetCollection
from ...type.enum import AffiliationType, AttachmentState, \
    CallState, FigureType, FormatType, MessageThreadType, \
    PermissionType, ProposalState, PublicationType
from ...type.simple import Affiliation, \
    Calculation, CalculatorInfo, CalculatorMode, CalculatorValue, Call, \
    PrevProposal, PrevProposalPub, \
    ProposalCategory, ProposalFigureInfo, ProposalText, \
    Queue, ProposalText, Semester, Target, \
    TargetToolInfo, ValidationMessage
from ...type.util import null_tuple
from ...view import auth
from ...web.util import ErrorPage, HTTPError, HTTPForbidden, \
    HTTPNotFound, HTTPRedirect, \
    flash, session, url_for
from ...view.util import count_words, organise_collection, with_proposal

CalculationExtra = namedtuple(
    'CalculationExtra',
    Calculation._fields + ('calculator_name',
                           'inputs', 'outputs', 'mode_info', 'target_view'))

PrevProposalExtra = namedtuple(
    'PrevProposalExtra',
    PrevProposal._fields + ('links',))

PrevProposalPubExtra = namedtuple(
    'PrevProposalPubExtra',
    PrevProposalPub._fields + ('url',))


class GenericProposal(object):
    def view_proposal_new(self, db, call_id, form):
        try:
            call = db.search_call(
                facility_id=self.id_, call_id=call_id, state=CallState.OPEN
            ).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Call not found')
        except MultipleRecords:
            raise HTTPError('Multiple calls found')

        affiliations = db.search_affiliation(
            queue_id=call.queue_id, hidden=False)
        if not affiliations:
            raise HTTPError('No affiliations appear to be available.')

        message = None

        proposal_title = ''
        affiliation_id = None

        if form is not None:
            proposal_title = form['proposal_title']

            affiliation_id = int(form['affiliation_id'])
            if affiliation_id not in affiliations:
                raise ErrorPage('Invalid affiliation selected.')

            try:
                proposal_id = db.add_proposal(
                    call_id=call_id, person_id=session['person']['id'],
                    affiliation_id=affiliation_id,
                    title=proposal_title)
                flash('Your new proposal has been created.')
                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal_id,
                                           first_view='true'))

            except UserError as e:
                message = e.message

        return {
            'title': 'New Proposal',
            'call': call,
            'message': message,
            'proposal_title': proposal_title,
            'affiliations': affiliations.values(),
            'affiliation_id': affiliation_id
        }

    @with_proposal(permission=PermissionType.VIEW)
    def view_proposal_view(self, db, proposal, can, args):
        review_can = auth.for_review(self.get_reviewer_roles(),
                                     db, reviewer=None, proposal=proposal)

        ctx = {
            'title': proposal.title,
            'can_edit': can.edit,
            'can_remove_self': (ProposalState.can_edit(proposal.state) and
                                any(x.person_id == session['person']['id']
                                    for x in proposal.members.values())),
            'can_view_review': review_can.view,
            'can_edit_review': review_can.edit,
            'can_view_feedback': auth.for_proposal_feedback(
                self.get_reviewer_roles(),
                db, proposal=proposal).view,
            'is_submitted': ProposalState.is_submitted(proposal.state),
            'proposal': proposal._replace(
                members=list(proposal.members.values())),
            'students': proposal.members.get_students(),
            'proposal_code': self.make_proposal_code(db, proposal),
            'show_person_proposals_callout': ('first_view' in args),
        }

        ctx.update(self._view_proposal_extra(db, proposal))

        return ctx

    def _view_proposal_extra(self, db, proposal, extra_text_roles={}):
        """
        Method to gather additional information for the proposal view page.

        Sub-classes can override this method to add additional information
        to the proposal.
        """

        role_class = self.get_text_roles()

        proposal_text = db.get_all_proposal_text(proposal.id)
        proposal_pdf = db.search_proposal_pdf(proposal.id)

        proposal_fig = db.search_proposal_figure(proposal.id,
                                                 with_caption=True,
                                                 with_has_preview=True)

        targets = db.search_target(proposal_id=proposal.id)
        target_total_time = targets.total_time()

        targets = [
            x._replace(system=CoordSystem.get_name(x.system)) for x in
            targets.to_formatted_collection().values()]

        calculations = db.search_calculation(proposal_id=proposal.id)

        prev_proposals = [
            PrevProposalExtra(
                *x._replace(publications=[
                    PrevProposalPubExtra(
                        *p, url=make_publication_url(p.type, p.description))
                    for p in x.publications]),
                links=self.make_proposal_info_urls(x.proposal_code))
            for x in db.search_prev_proposal(proposal_id=proposal.id).values()]

        extra = {
            'abstract': proposal_text.get(role_class.ABSTRACT, None),
            'targets': targets,
            'target_total_time': target_total_time,
            'calculators': self.calculators.values(),
            'calculations': self._prepare_calculations(calculations),
            'target_tools': self.target_tools.values(),
            'tool_note': proposal_text.get(role_class.TOOL_NOTE, None),
            'categories': db.search_proposal_category(
                proposal_id=proposal.id).values(),
            'prev_proposals': prev_proposals,
        }

        for role in (role_class.TECHNICAL_CASE, role_class.SCIENCE_CASE):
            extra['{}_case'.format(role_class.short_name(role))] = {
                'role': role,
                'text': proposal_text.get(role, None),
                'pdf': proposal_pdf.get_role(role, None),
                'fig': proposal_fig.values_by_role(role),
            }

        for (role_attr, role) in extra_text_roles.items():
            extra[role_attr] = proposal_text.get(role, None)

        return extra

    def _validate_proposal(self, db, proposal):
        messages = []

        # Check the title.
        if not proposal.title:
            messages.append(ValidationMessage(
                True,
                'The proposal does not have a title.',
                'Edit the proposal title',
                url_for('.title_edit', proposal_id=proposal.id)))

        # Check the members list.
        try:
            proposal.members.validate(editor_person_id=None)
        except UserError as e:
            messages.append(ValidationMessage(
                True, e.message,
                'Edit the proposal members',
                url_for('.member_edit', proposal_id=proposal.id)))

        # Now validate the "extra" parts of the proposal.
        extra = self._view_proposal_extra(db, proposal)

        messages.extend(self._validate_proposal_extra(db, proposal, extra))

        # Return the list of messages.
        return messages

    def _validate_proposal_extra(self, db, proposal, extra,
                                 skip_missing_targets=False,
                                 check_excluded_pi=False):
        role_class = self.get_text_roles()
        messages = []

        if check_excluded_pi:
            member_pi = proposal.members.get_pi(default=None)

            # Ignore if there's no PI: the previous members.validate test
            # should have generated an error for that.
            if member_pi is not None:
                exclude = db.search_affiliation(queue_id=proposal.queue_id,
                                                type_=AffiliationType.EXCLUDED)

                if member_pi.affiliation_id in exclude:
                    exclude_names = [
                        x.name for x in exclude.values()
                        if ((not x.hidden) or
                            (x.id == member_pi.affiliation_id))]

                    messages.append(ValidationMessage(
                        False,
                        'The principal investigator (PI) has an ineligible '
                        'affiliation.  The PI should not be someone with ' +
                        ('one of the following affiliations: '
                         if len(exclude_names) > 1 else
                         'the following affiliation: ') +
                        ', '.join(exclude_names) +
                        '.',
                        'Select a different proposal member as the PI',
                        url_for('.member_edit', proposal_id=proposal.id)))

        if extra['abstract'] is None:
            messages.append(ValidationMessage(
                True,
                'The proposal does not have an abstract.',
                'Edit the proposal abstract',
                url_for('.abstract_edit', proposal_id=proposal.id)))

        if not extra['prev_proposals']:
            messages.append(ValidationMessage(
                False,
                'No previous proposals have been listed.  If you do not have '
                'any previously accepted proposals you should ignore this '
                'warning.',
                'Edit previous proposals and publications',
                url_for('.previous_edit', proposal_id=proposal.id)))

        if (not skip_missing_targets) and (not extra['targets']):
            messages.append(ValidationMessage(
                False,
                'No target objects have been specified.',
                'Edit target list',
                url_for('.target_edit', proposal_id=proposal.id)))

        elif extra['targets'] and (extra['tool_note'] is None):
            messages.append(ValidationMessage(
                False,
                'A note on the target tool results has not been added.',
                'Check targets with tools and edit note',
                url_for('.tool_note_edit', proposal_id=proposal.id)))

        if not extra['calculations']:
            messages.append(ValidationMessage(
                False,
                'The proposal does not have any calculation results attached.',
                'See available calculators',
                url_for('.facility_home', _anchor='calc')))

        for role in (role_class.TECHNICAL_CASE, role_class.SCIENCE_CASE):
            role_name = role_class.get_name(role)
            case = extra['{}_case'.format(role_class.short_name(role))]

            if case['text'] is not None:
                for fig in case['fig']:
                    if fig.state == AttachmentState.ERROR:
                        messages.append(ValidationMessage(
                            False,
                            'A figure in the {} could not be processed. '
                            'Please check the file is valid and contact us '
                            'for help in the event that this error '
                            'persists.'.format(role_name.lower()),
                            'Edit {}'.format(role_name.lower()),
                            url_for('.case_edit',
                                    proposal_id=proposal.id, role=role)))
                        break

            elif case['pdf'] is not None:
                if (case['pdf'].state ==
                        AttachmentState.ERROR):
                    messages.append(ValidationMessage(
                        False,
                        'The {} PDF file could not be processed. '
                        'Please check the file is valid and contact us '
                        'for help in the event that this error '
                        'persists.'.format(role_name.lower()),
                        'Edit {}'.format(role_name.lower()),
                        url_for('.case_edit',
                                proposal_id=proposal.id, role=role)))

            else:
                messages.append(ValidationMessage(
                    True,
                    'The proposal does not have a {}.'.format(
                        role_name.lower()),
                    'Edit {}'.format(role_name.lower()),
                    url_for('.case_edit',
                            proposal_id=proposal.id, role=role)))

        return messages

    @with_proposal(permission=PermissionType.EDIT)
    def view_proposal_submit(self, db, proposal, can, form):
        if ProposalState.is_submitted(proposal.state):
            raise ErrorPage('The proposal has already been submitted.')

        messages = self._validate_proposal(db, proposal)
        has_error = any(x.is_error for x in messages)

        if form is not None:
            if 'submit_confirm' in form:
                if has_error:
                    raise ErrorPage(
                        'The proposal can not be submitted while there are '
                        'errors in validation.')

                db.update_proposal(proposal.id, state=ProposalState.SUBMITTED)

                self._message_proposal_submit(db, proposal)

                flash('The proposal has been submitted.')

            else:
                flash('The submission process has been cancelled.')

            raise HTTPRedirect(url_for('.proposal_view',
                                       proposal_id=proposal.id))

        return {
            'title': 'Submit Proposal',
            'proposal': proposal,
            'proposal_code': self.make_proposal_code(db, proposal),
            'validation_messages': messages,
            'can_submit': (not has_error),
            'can_edit': True,
            'is_submit_page': True,
        }

    def _message_proposal_submit(self, db, proposal):
        proposal_code = self.make_proposal_code(db, proposal)

        db.add_message(
            'Proposal {} submitted'.format(proposal_code),
            render_email_template(
                'proposal_submitted.txt', {
                    'proposal': proposal,
                    'proposal_code': proposal_code,
                    'target_url': url_for(
                        '.proposal_view',
                        proposal_id=proposal.id, _external=True),
                    'submitter_name': session['person']['name'],
                },
                facility=self),
            [x.person_id for x in proposal.members.values()],
            thread_type=MessageThreadType.PROPOSAL_STATUS,
            thread_id=proposal.id)

    @with_proposal(permission=PermissionType.VIEW)
    def view_proposal_validate(self, db, proposal, can):
        messages = self._validate_proposal(db, proposal)

        return {
            'title': 'Proposal Validation',
            'proposal': proposal,
            'proposal_code': self.make_proposal_code(db, proposal),
            'validation_messages': messages,
            'can_edit': can.edit,
            'is_submit_page': False,
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_proposal_withdraw(self, db, proposal, can, form):
        if not ProposalState.is_submitted(proposal.state):
            raise ErrorPage('The proposal has not been submitted.')

        if form is not None:
            if 'submit_confirm' in form:
                db.update_proposal(proposal.id, state=ProposalState.WITHDRAWN)

                self._message_proposal_withdraw(db, proposal)

                flash('The proposal has been withdrawn.')

            else:
                flash('The withdrawl process has been cancelled.')

            raise HTTPRedirect(url_for('.proposal_view',
                                       proposal_id=proposal.id))

        return {
            'title': 'Withdraw Proposal',
            'proposal': proposal,
            'proposal_code': self.make_proposal_code(db, proposal),
        }

    def _message_proposal_withdraw(self, db, proposal):
        proposal_code = self.make_proposal_code(db, proposal)

        db.add_message(
            'Proposal {} withdrawn'.format(proposal_code),
            render_email_template(
                'proposal_withdrawn.txt', {
                    'proposal': proposal,
                    'proposal_code': proposal_code,
                    'withdrawer_name': session['person']['name'],
                },
                facility=self),
            [x.person_id for x in proposal.members.values()],
            thread_type=MessageThreadType.PROPOSAL_STATUS,
            thread_id=proposal.id)

    @with_proposal(permission=PermissionType.EDIT)
    def view_title_edit(self, db, proposal, can, form):
        message = None

        if form is not None:
            try:
                proposal = proposal._replace(title=form['proposal_title'])
                db.update_proposal(proposal.id, title=proposal.title)
                flash('The proposal title has been changed.')
                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Title',
            'message': message,
            'proposal': proposal,
            'proposal_code': self.make_proposal_code(db, proposal),
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_abstract_edit(self, db, proposal, can, form):
        role_class = self.get_text_roles()
        return self._edit_text(
            db, proposal, role_class.ABSTRACT, proposal.abst_word_lim,
            url_for('.abstract_edit', proposal_id=proposal.id), form, 10,
            extra_initialization=self._view_abstract_edit_init,
            extra_form_read=self._view_abstract_edit_read,
            extra_form_proc=self._view_abstract_edit_proc,
            target_redir=url_for('.proposal_view', proposal_id=proposal.id,
                                 _anchor='abstract'))

    def _view_abstract_edit_init(self, db, proposal, role):
        proposal_categories = db.search_proposal_category(
            proposal_id=proposal.id)

        return {
            'categories': db.search_category(facility_id=self.id_,
                                             hidden=False),
            'categories_selected': set(x.category_id
                                       for x in proposal_categories.values()),
            '_proposal_categories': proposal_categories,
        }

    def _view_abstract_edit_read(self, db, proposal, role, form, ctx):
        categories_selected = set()

        for category_id in ctx['categories']:
            if 'category_{}'.format(category_id) in form:
                categories_selected.add(category_id)

        ctx.update({'categories_selected': categories_selected})

        return ctx

    def _view_abstract_edit_proc(self, db, proposal, role, ctx):
        categories = ctx['categories']
        categories_selected = ctx['categories_selected'].copy()
        proposal_categories = ctx.pop('_proposal_categories')
        if proposal_categories:
            max_id = max(x.id for x in proposal_categories.values())
        else:
            max_id = 0

        for prop_cat_id, prop_cat in list(proposal_categories.items()):
            if prop_cat.category_id in categories_selected:
                categories_selected.discard(prop_cat.category_id)
            else:
                del proposal_categories[prop_cat_id]

        for cat_id in categories_selected:
            if cat_id in categories:
                max_id += 1
                proposal_categories[max_id] = ProposalCategory(
                    max_id, proposal.id, cat_id, None)

        db.sync_proposal_category(proposal.id, proposal_categories)

        return ctx

    @with_proposal(permission=PermissionType.EDIT)
    def view_member_edit(self, db, proposal, can, form):
        message = None
        records = proposal.members

        affiliations = db.search_affiliation(
            queue_id=proposal.queue_id, hidden=False)
        if not affiliations:
            raise HTTPError('No affiliations appear to be available.')

        if form is not None:
            if 'pi' in form:
                pi = int(form['pi'])
            else:
                pi = None

            try:
                # Create a new list from the items so that it is safe
                # to update and/or delete from records (for Python-3).
                for (id_, record) in list(records.items()):

                    # The affiliation_id should always be present, so use it
                    # to detect members who have been deleted from the form.
                    affiliation_str = form.get('affiliation_{}'.format(id_))
                    if affiliation_str is None:
                        del records[id_]
                        continue

                    records[id_] = record._replace(
                        pi=(id_ == pi),
                        editor=('editor_{}'.format(id_) in form),
                        observer=('observer_{}'.format(id_) in form),
                        affiliation_id=int(affiliation_str))

                db.sync_proposal_member(
                    proposal.id, records,
                    editor_person_id=session['person']['id'])

                flash('The proposal member list has been updated.')
                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id,
                                           _anchor='members'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Members',
            'message': message,
            'proposal_id': proposal.id,
            'semester_id': proposal.semester_id,
            'members': records.values(),
            'affiliations': affiliations.values(),
            'proposal_code': self.make_proposal_code(db, proposal),
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_member_add(self, db, proposal, can, form):
        message_link = message_invite = None
        member = dict(editor=None, observer=None, person_id=None,
                      name='', email='')

        affiliations = db.search_affiliation(
            queue_id=proposal.queue_id, hidden=False)
        if not affiliations:
            raise HTTPError('No affiliations appear to be available.')

        if form is not None:
            member['editor'] = 'editor' in form
            member['observer'] = 'observer' in form
            if 'person_id' in form:
                member['person_id'] = int(form['person_id'])
            member['name'] = form.get('name', '')
            member['email'] = form.get('email', '')
            member['affiliation_id'] = int(form['affiliation_id'])

            affiliation = affiliations.get(member['affiliation_id'])
            if affiliation is None:
                raise ErrorPage('Selected affiliation not found.')

            if 'submit_link' in form:
                try:
                    if member['person_id'] is None:
                        raise UserError(
                            'No-one was selected from the directory.')

                    try:
                        person = db.get_person(person_id=member['person_id'])
                    except NoSuchRecord:
                        raise ErrorPage('This person\'s record was not found')

                    assert person.id == member['person_id']

                    if not person.public:
                        raise ErrorPage('This person\'s record is private.')

                    db.add_member(proposal.id, person.id,
                                  member['affiliation_id'],
                                  editor=member['editor'],
                                  observer=member['observer'])

                    self._message_proposal_invite(
                        db, proposal=proposal,
                        person_id=person.id,
                        person_name=person.name,
                        is_editor=member['editor'],
                        affiliation_name=affiliation.name,
                        send_token=False)

                    flash('{} has been added to the proposal.', person.name)
                    raise HTTPRedirect(url_for('.proposal_view',
                                       proposal_id=proposal.id,
                                       _anchor='members'))

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
                    db.add_member(proposal.id, person_id,
                                  member['affiliation_id'],
                                  editor=member['editor'],
                                  observer=member['observer'])

                    self._message_proposal_invite(
                        db, proposal=proposal,
                        person_id=person_id,
                        person_name=member['name'],
                        is_editor=member['editor'],
                        affiliation_name=affiliation.name,
                        send_token=True)

                    flash('{} has been added to the proposal.',
                          member['name'])

                    # Return to the proposal page after editing the new
                    # member's institution.
                    session['next_page'] = url_for('.proposal_view',
                                                   proposal_id=proposal.id,
                                                   _anchor='members')

                    raise HTTPRedirect(url_for(
                        'people.person_edit_institution', person_id=person_id))

                except UserError as e:
                    message_invite = e.message

            else:
                raise ErrorPage('Unknown action.')

        # Prepare list of people to display as the registered member
        # directory, filtering out current proposal members.
        current_persons = [m.person_id for m in proposal.members.values()]
        persons = [
            p for p in db.search_person(registered=True, public=True,
                                        with_institution=True).values()
            if p.id not in current_persons
        ]

        return {
            'title': 'Add Member',
            'message_link': message_link,
            'message_invite': message_invite,
            'proposal_id': proposal.id,
            'semester_id': proposal.semester_id,
            'persons': persons,
            'affiliations': affiliations.values(),
            'member': member,
            'proposal_code': self.make_proposal_code(db, proposal),
            'target': url_for('.member_add', proposal_id=proposal.id),
            'title_link': 'Add a Member from the Directory',
            'title_invite': 'Invite a New Member to the Proposal',
            'submit_link': 'Add to proposal',
            'submit_invite': 'Invite to register',
            'label_link': 'Member',
        }

    def _message_proposal_invite(
            self, db, proposal, person_id, person_name,
            is_editor, affiliation_name, send_token):
        proposal_code = self.make_proposal_code(db, proposal)

        email_ctx = {
            'recipient_name': person_name,
            'proposal': proposal,
            'inviter_name': session['person']['name'],
            'affiliation': affiliation_name,
            'is_editor': is_editor,
            'target_semester': url_for(
                '.semester_calls', semester_id=proposal.semester_id,
                _external=True),
        }

        if send_token:
            (token, expiry) = db.add_invitation(person_id)

            email_ctx.update({
                'token': token,
                'expiry': expiry,
                'target_url': url_for(
                    'people.invitation_token_enter', token=token,
                    _external=True),
                'target_plain': url_for(
                    'people.invitation_token_enter',
                    _external=True),
            })

        else:
            email_ctx.update({
                'target_url': url_for(
                    '.proposal_view',
                    proposal_id=proposal.id, _external=True),
            })

        db.add_message(
            'Proposal {} invitation'.format(proposal_code),
            render_email_template('proposal_invitation.txt',
                                  email_ctx, facility=self),
            [person_id])

    @with_proposal(permission=PermissionType.EDIT)
    def view_member_reinvite(self, db, proposal, can, member_id, form):
        member = proposal.members.get(member_id)
        if member is None:
            raise HTTPNotFound('Proposal member not found.')

        if member.person_registered:
            raise ErrorPage('This proposal member has already registered.')

        proposal_code = self.make_proposal_code(db, proposal)

        if form:
            if 'submit_confirm' in form:
                self._message_proposal_invite(
                    db, proposal=proposal,
                    person_id=member.person_id,
                    person_name=member.person_name,
                    is_editor=member.editor,
                    affiliation_name=member.affiliation_name,
                    send_token=True)

                flash('{} has been re-invited to the proposal.',
                      member.person_name)

            raise HTTPRedirect(url_for('.proposal_view',
                                       proposal_id=proposal.id,
                                       _anchor='members'))

        return {
            'title': 'Re-send Proposal Invitation',
            'message':
                'Would you like to re-send an invitation '
                'to proposal {} to {}?'.format(proposal_code,
                                               member.person_name),
        }

    @with_proposal(permission=PermissionType.VIEW)
    def view_member_remove_self(self, db, proposal, can, form):
        if not ProposalState.can_edit(proposal.state):
            raise ErrorPage('This proposal is not in an editable state.')

        proposal_code = self.make_proposal_code(db, proposal)

        if form:
            if 'submit_cancel' in form:
                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id,
                                           _anchor='members'))

            elif 'submit_confirm' in form:
                try:
                    db.delete_member_person(
                        proposal_id=proposal.id,
                        person_id=session['person']['id'])
                except ConsistencyError:
                    raise ErrorPage(
                        'It was not possible to remove you from the proposal. '
                        'If you are the only editor of the proposal, you '
                        'must make someone else an editor '
                        'before removing yourself.')

                flash('You have been removed from proposal {}.', proposal_code)
                raise HTTPRedirect(url_for('home.home_page'))

        return {
            'title': 'Remove Yourself from Proposal',
            'message':
                'Are you sure you wish to remove yourself from '
                'proposal {}?'.format(proposal_code),
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_student_edit(self, db, proposal, can, form):
        message = None
        records = proposal.members

        if form:
            for member_id in records:
                records[member_id] = records[member_id]._replace(
                    student=('student_{}'.format(member_id) in form))

            try:
                (n_insert, n_update, n_delete) = \
                    db.sync_proposal_member_student(proposal.id, records)

                if n_update:
                    flash('The list of students has been updated.')

                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id,
                                           _anchor='members'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Students',
            'message': message,
            'proposal_id': proposal.id,
            'members': records.values(),
            'proposal_code': self.make_proposal_code(db, proposal),
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_previous_edit(self, db, proposal, can, form):
        message = None

        records = db.search_prev_proposal(proposal_id=proposal.id)

        if form is not None:
            # Temporary dictionaries for new records.
            updated_records = {}
            added_records = {}

            for param in form:
                if not param.startswith('code_'):
                    continue

                id_ = param[5:]

                prev_proposal_code = form[param]
                prev_proposal_id = None

                if id_.startswith('new_'):
                    target_id = int(id_[4:])
                    destination = added_records
                else:
                    target_id = int(id_)
                    destination = updated_records

                    if target_id in records:
                        prev_record = records[target_id]
                        if prev_record.proposal_code == prev_proposal_code:
                            prev_proposal_id = prev_record.proposal_id

                if prev_proposal_id is None:
                    try:
                        prev_proposal_id = self.parse_proposal_code(
                            db, prev_proposal_code)
                    except NoSuchRecord:
                        pass

                publications = []

                for i in range(6):
                    pub_desc = form['publication_{}_{}'.format(i, id_)].strip()
                    if not pub_desc:
                        continue
                    pub_type = int(form['pub_type_{}_{}'.format(i, id_)])

                    # Remove leading "doi:" from DOI references.
                    if (pub_type == PublicationType.DOI and
                            pub_desc.startswith('doi:')):
                        pub_desc = pub_desc[4:]

                    publications.append(
                        null_tuple(PrevProposalPub)._replace(
                            description=pub_desc, type=pub_type))

                destination[target_id] = null_tuple(PrevProposal)._replace(
                    id=target_id,
                    proposal_id=prev_proposal_id,
                    proposal_code=prev_proposal_code,
                    continuation=(('continuation_' + id_) in form),
                    publications=publications
                )

                records = organise_collection(
                    PrevProposalCollection, updated_records, added_records)

            try:
                updates = db.sync_proposal_prev_proposal(proposal.id, records)

                if any(updates):
                    flash('The previous proposals list has been saved.')

                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id,
                                           _anchor='prev_proposals'))

            except UserError as e:
                message = e.message

        call = db.get_call(facility_id=None, call_id=proposal.call_id)

        accepted_proposals = db.search_proposal(
            facility_id=self.id_, person_id=session['person']['id'],
            state=ProposalState.ACCEPTED)

        accepted_proposal_codes = [
            self.make_proposal_code(db, x)
            for x in accepted_proposals.values()]

        return {
            'title': 'Previous Proposals and Publications',
            'proposal_id': proposal.id,
            'message': message,
            'proposal_code': self.make_proposal_code(db, proposal),
            'accepted_proposals': accepted_proposal_codes,
            'prev_proposals': records.values(),
            'publication_types': PublicationType.get_options(),
            'note': call.prev_prop_note,
            'note_format': call.note_format,
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_target_edit(self, db, proposal, can, form):
        message = None

        records = db.search_target(
            proposal_id=proposal.id).to_formatted_collection()

        if form is not None:
            # Temporary dictionaries for new records.
            updated_records = {}
            added_records = {}

            for param in form:
                if not param.startswith('name_'):
                    continue
                id_ = param[5:]

                if id_.startswith('new_'):
                    target_id = int(id_[4:])
                    destination = added_records
                else:
                    target_id = int(id_)
                    destination = updated_records

                destination[target_id] = Target(
                    target_id, proposal.id, None, form[param],
                    int(form['system_' + id_]),
                    form['x_' + id_],
                    form['y_' + id_],
                    form['time_' + id_],
                    form['priority_' + id_])

            records = organise_collection(TargetCollection, updated_records,
                                          added_records)

            try:
                db.sync_proposal_target(
                    proposal.id,
                    TargetCollection.from_formatted_collection(records))

                flash('The target object list has been saved.')

                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id,
                                           _anchor='targets'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Targets',
            'proposal_id': proposal.id,
            'message': message,
            'systems': CoordSystem.get_options(),
            'targets': records.values(),
            'proposal_code': self.make_proposal_code(db, proposal),
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_target_upload(self, db, proposal, can, form, file_):
        message = None

        records = db.search_target(proposal_id=proposal.id)

        if form:
            try:
                if file_:
                    try:
                        buff = file_.read(64 * 1024)
                        if len(file_.read(1)):
                            raise UserError('The uploaded file was too large.')
                    finally:
                        file_.close()
                else:
                    raise UserError('No target list file was received.')

                overwrite = ('overwrite' in form)

                max_record = (max(records.keys()) if records else 0)

                new_records = parse_source_list(buff,
                                                number_from=max_record + 1)

                # TODO: would be more efficient to have a store-only
                # version of the sync method.
                if not overwrite:
                    new_records = TargetCollection(records.items() +
                                                   new_records.items())

                db.sync_proposal_target(proposal.id, new_records)

                flash('The target object list has been {}.',
                      ('overwritten' if overwrite else 'updated'))

                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id,
                                           _anchor='targets'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Upload Target List',
            'message': message,
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'mime_types': ['text/plain', 'text/csv'],
            'has_targets': bool(records),
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_tool_note_edit(self, db, proposal, can, form):
        role_class = self.get_text_roles()
        return self._edit_text(
            db, proposal, role_class.TOOL_NOTE, proposal.expl_word_lim,
            url_for('.tool_note_edit', proposal_id=proposal.id), form, 10,
            extra_initialization=self._view_tool_note_edit_init,
            target_redir=url_for('.proposal_view', proposal_id=proposal.id,
                                 _anchor='targets'))

    def _view_tool_note_edit_init(self, db, proposal, role):
        return {
            'help_link': url_for('help.user_page', page_name='target',
                                 _anchor='clash-tool'),
            'target_tools': self.target_tools.values(),
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_request_edit(self, db, proposal, can, form):
        raise ErrorPage('Observing request not implemented for this facility.')

    @with_proposal(permission=PermissionType.EDIT)
    def view_case_edit(self, db, proposal, can, role):
        role_class = self.get_text_roles()
        code = role_class.short_name(role)
        call = db.get_call(facility_id=None, call_id=proposal.call_id)

        text_info = db.search_proposal_text(proposal_id=proposal.id, role=role)

        pdf_info = db.search_proposal_pdf(
            proposal_id=proposal.id, role=role,
            with_uploader_name=True).get_single(None)

        figures = db.search_proposal_figure(
            proposal_id=proposal.id, role=role,
            with_caption=True, with_uploader_name=True).values()

        return {
            'title': 'Edit {}'.format(role_class.get_name(role).title()),
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'role_code': code,
            'role': role,
            'note': getattr(call, code + '_note'),
            'note_format': call.note_format,
            'word_limit': getattr(proposal, code + '_word_lim'),
            'fig_limit': getattr(proposal, code + '_fig_lim'),
            'page_limit': getattr(proposal, code + '_page_lim'),
            'text': text_info.get_single(None),
            'figures': figures,
            'pdf': pdf_info,
            'help_link': url_for('help.user_page',
                                 page_name=role_class.url_path(role)),
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_case_edit_text(self, db, proposal, can, role, form):
        role_class = self.get_text_roles()
        code = role_class.short_name(role)

        figures = db.search_proposal_figure(
            proposal_id=proposal.id, role=role).values()

        if role == role_class.TECHNICAL_CASE:
            calculations = self._prepare_calculations(
                db.search_calculation(proposal_id=proposal.id))
        else:
            calculations = None

        return self._edit_text(
            db, proposal, role,
            getattr(proposal, code + '_word_lim'),
            url_for('.case_edit_text', proposal_id=proposal.id, role=role),
            form, 30, figures, calculations,
            url_for('.case_edit', proposal_id=proposal.id, role=role))

    @with_proposal(permission=PermissionType.EDIT)
    def view_case_edit_figure(self, db, proposal, can, fig_id, role,
                              form, file):
        role_class = self.get_text_roles()
        code = role_class.short_name(role)
        name = role_class.get_name(role)
        max_size = int(get_config().get('upload', 'max_fig_size'))
        fig_limit = getattr(proposal, code + '_fig_lim')
        word_limit = proposal.capt_word_lim
        message = None

        if fig_id is None:
            # We are trying to add a new figure -- check whether this is
            # permitted.
            if not fig_limit:
                raise ErrorPage(
                    'The {} can not have figures attached.',
                    name.lower())

            elif len(db.search_proposal_figure(proposal_id=proposal.id,
                                               role=role)) >= fig_limit:
                raise ErrorPage(
                    'The {} already has the maximum number of figures.',
                    name.lower())

            figure = null_tuple(ProposalFigureInfo)._replace(caption='')

            target = url_for('.case_new_figure',
                             proposal_id=proposal.id, role=role)

        else:
            figure = db.search_proposal_figure(
                proposal_id=proposal.id, role=role,
                fig_id=fig_id, with_caption=True).get_single()

            target = url_for('.case_edit_figure',
                             proposal_id=proposal.id, role=role,
                             fig_id=fig_id)

        if form is not None:
            try:
                # Put the caption text into the figure object first in case
                # of errors later.
                figure = figure._replace(caption=form['text'])

                word_count = count_words(figure.caption)
                if word_count > word_limit:
                    raise UserError(
                        'Caption is too long: {} / {} words',
                        word_count, word_limit)

                if file:
                    try:
                        filename = file.filename
                        buff = file.read(max_size * 1024 * 1024)

                        # Did we get all of the file within the size limit?
                        if len(file.read(1)):
                            raise UserError(
                                'The uploaded figure was too large.')

                    finally:
                        file.close()

                    type_ = determine_figure_type(buff)
                    if type_ == FigureType.PDF:
                        page_count = determine_pdf_page_count(buff)
                        if page_count != 1:
                            raise UserError(
                                'The uploaded PDF has multiple pages.')

                    figure_args = {
                        'figure': buff,
                        'type_': type_,
                        'filename': filename,
                        'uploader_person_id': session['person']['id'],
                        'caption': figure.caption,
                    }

                    if figure.id is None:
                        # Add new figure.
                        db.add_proposal_figure(
                            role_class, proposal.id, role, **figure_args)

                        flash('The new figure has been uploaded.')

                    else:
                        # Update existing figure.
                        db.update_proposal_figure(
                            proposal.id, role, figure.id, **figure_args)

                        flash('The replacement figure has been uploaded.')

                elif figure.id is None:
                    # We weren't updating an existing figure, so the lack
                    # of a file upload is an error.
                    raise UserError('No new figure file was received.')

                else:
                    # No file uploaded for an existing figure: just edit the
                    # caption.
                    db.update_proposal_figure(proposal.id, role, figure.id,
                                              caption=figure.caption)

                    flash('The figure caption has been updated.')

                raise HTTPRedirect(url_for(
                    '.case_edit', proposal_id=proposal.id, role=role))

            except UserError as e:
                message = e.message

        return {
            'title': '{} {} Figure'.format(
                ('New' if figure.id is None else 'Edit'), name.title()),
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'figure': figure,
            'word_limit': word_limit,
            'message': message,
            'max_size': max_size,
            'mime_types': FigureType.allowed_mime_types(),
            'mime_type_names': FigureType.allowed_type_names(),
            'target': target,
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_case_manage_figure(self, db, proposal, can, role, form):
        role_class = self.get_text_roles()
        code = role_class.short_name(role)
        name = role_class.get_name(role)
        message = None

        figures = db.search_proposal_figure(proposal_id=proposal.id, role=role,
                                            with_uploader_name=True)

        if form is not None:
            try:
                figures_present = [int(param[7:])
                                   for param in form
                                   if param.startswith('figure_')]

                for fig_id in list(figures.keys()):
                    if fig_id not in figures_present:
                        del figures[fig_id]

                (n_insert, n_update, n_delete) = \
                    db.sync_proposal_figure(proposal.id, role, figures)

                if n_delete:
                    flash('{} {} been removed.', n_delete,
                          ('figure has' if n_delete == 1 else 'figures have'))

                raise HTTPRedirect(url_for(
                    '.case_edit', proposal_id=proposal.id, role=role))

            except UserError as e:
                message = e.message

        return {
            'title': 'Manage {} Figures'.format(name.title()),
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'role': role,
            'message': message,
            'target': url_for('.case_manage_figure',
                              proposal_id=proposal.id, role=role),
            'figures': figures.values(),
        }

    @with_proposal(permission=PermissionType.VIEW)
    def view_case_view_figure(self, db, proposal, can, fig_id, role, md5sum,
                              type_=None):
        if type_ is None:
            try:
                return db.get_proposal_figure(
                    proposal.id, role, fig_id, md5sum=md5sum)
            except NoSuchRecord:
                raise HTTPNotFound('Figure not found.')

        elif type_ == 'thumbnail':
            try:
                return db.get_proposal_figure_thumbnail(
                    proposal.id, role, fig_id, md5sum=md5sum)
            except NoSuchRecord:
                raise HTTPNotFound('Figure thumbnail not found.')

        elif type_ == 'preview':
            try:
                return db.get_proposal_figure_preview(
                    proposal.id, role, fig_id, md5sum=md5sum)
            except NoSuchRecord:
                raise HTTPNotFound('Figure preview not found.')

        else:
            raise HTTPError('Unknown figure view type.')

    @with_proposal(permission=PermissionType.EDIT)
    def view_case_edit_pdf(self, db, proposal, can, role, file):
        role_class = self.get_text_roles()
        code = role_class.short_name(role)
        name = role_class.get_name(role)
        page_limit = getattr(proposal, code + '_page_lim')
        max_size = int(get_config().get('upload', 'max_pdf_size'))
        message = None

        if file is not None:
            try:
                if not file:
                    raise UserError('No file was received.')

                # Read the file, raising an error if it is too large.
                try:
                    filename = file.filename
                    buff = file.read(max_size * 1024 * 1024)

                    # Did we get all of the file within the size limit?
                    if len(file.read(1)):
                        raise UserError('The uploaded file was too large.')

                finally:
                    file.close()

                type_ = determine_figure_type(buff)
                if type_ != FigureType.PDF:
                    raise UserError('File was of type {} rather than PDF.',
                                    FigureType.get_name(type_))

                page_count = determine_pdf_page_count(buff)
                if page_count > page_limit:
                    raise UserError(
                        'PDF is too long: {} / {} {}',
                        page_count, page_limit,
                        ('page' if page_limit == 1 else 'pages'))

                db.set_proposal_pdf(
                    role_class, proposal.id, role, buff, page_count,
                    filename, session['person']['id'])

                flash('The {} has been uploaded.', name.lower())

                raise HTTPRedirect(url_for(
                    '.case_edit', proposal_id=proposal.id, role=role))

            except UserError as e:
                message = e.message

        return {
            'title': 'Upload {} PDF'.format(name.title()),
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'message': message,
            'mime_types': [FigureType.get_mime_type(FigureType.PDF)],
            'max_size': max_size,
            'target': url_for('.case_edit_pdf',
                              proposal_id=proposal.id, role=role),
        }

    @with_proposal(permission=PermissionType.VIEW)
    def view_case_view_pdf(self, db, proposal, can, role, md5sum):
        try:
            return db.get_proposal_pdf(proposal.id, role, md5sum=md5sum)
        except NoSuchRecord:
            raise HTTPNotFound('{} PDF not found.'.format(
                role_class.get_name(role).capitalize()))

    @with_proposal(permission=PermissionType.VIEW)
    def view_case_view_pdf_preview(self, db, proposal, can, page, role,
                                   md5sum):
        try:
            return db.get_proposal_pdf_preview(proposal.id, role, page,
                                               md5sum=md5sum)
        except NoSuchRecord:
            raise HTTPNotFound('PDF preview page not found.')

    @with_proposal(permission=PermissionType.EDIT)
    def view_calculation_manage(self, db, proposal, can, form):
        message = None
        calculations = db.search_calculation(proposal_id=proposal.id)

        if form is not None:
            try:
                calculations_present = [int(param[12:])
                                        for param in form
                                        if param.startswith('calculation_')]

                for calculation_id in list(calculations.keys()):
                    if calculation_id not in calculations_present:
                        del calculations[calculation_id]

                (n_insert, n_update, n_delete) = \
                    db.sync_proposal_calculation(proposal.id, calculations)

                if n_delete:
                    flash('{} {} been removed.', n_delete,
                          ('calculation has' if n_delete == 1 else
                           'calculations have'))

                raise HTTPRedirect(url_for(
                    '.proposal_view', proposal_id=proposal.id,
                    _anchor='calculations'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Manage Calculations',
            'message': message,
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'calculations': self._prepare_calculations(calculations),
        }

    @with_proposal(permission=PermissionType.FEEDBACK, with_decision_note=True)
    def view_proposal_feedback(self, db, proposal):
        proposal_code = self.make_proposal_code(db, proposal)

        ctx = {
            'title': '{}: Feedback'.format(proposal_code),
            'proposal_id': proposal.id,
            'proposal_code': proposal_code,
        }

        ctx.update(self._view_proposal_feedback_extra(db, proposal))

        return ctx

    def _view_proposal_feedback_extra(self, db, proposal):
        """
        Method to gather additional information for the proposal feedback page.
        """

        role_class = self.get_reviewer_roles()

        reviewers = db.search_reviewer(
            proposal_id=proposal.id, role=role_class.FEEDBACK,
            with_review=True, with_review_text=True)

        # Show the decision note if viewing as an administrator.
        if (session.get('is_admin', False) and auth.can_be_admin(db) and
                proposal.decision_note):
            decision_note = ProposalText(
                text=proposal.decision_note,
                format=proposal.decision_note_format)
        else:
            decision_note = None

        return {
            'feedback_reviews': reviewers.values(),
            'decision_note': decision_note,
        }

    def _edit_text(self, db, proposal, role, word_limit, target, form, rows,
                   figures=None, calculations=None, target_redir=None,
                   extra_initialization=None, extra_form_read=None,
                   extra_form_proc=None):
        role_class = self.get_text_roles()
        name = role_class.get_name(role)
        message = None

        try:
            text = db.get_proposal_text(proposal.id, role)
            is_update = True
        except NoSuchRecord:
            text = ProposalText('', FormatType.PLAIN)
            is_update = False

        if extra_initialization is None:
            ctx = {}
        else:
            ctx = extra_initialization(db, proposal, role)

        if form is not None:
            text = text._replace(text=form['text'],
                                 format=int(form['format']))

            if extra_form_read is not None:
                ctx = extra_form_read(db, proposal, role, form, ctx)

            try:
                word_count = count_words(text)
                if word_count > word_limit:
                    raise UserError(
                        '{} is too long: {} / {} words',
                        name.capitalize(), word_count, word_limit)

                db.set_proposal_text(role_class, proposal.id, role,
                                     text.text, text.format, word_count,
                                     session['person']['id'], is_update)

                if extra_form_proc is not None:
                    ctx = extra_form_proc(db, proposal, role, ctx)

                flash('The {} has been saved.', name.lower())
                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id)
                                   if target_redir is None else target_redir)

            except UserError as e:
                message = e.message

        is_case_text = (role in
                        (role_class.TECHNICAL_CASE, role_class.SCIENCE_CASE))

        title_suffix = 'Text' if is_case_text else ''

        ctx.update({
            'title': 'Edit {} {}'.format(name.title(), title_suffix),
            'message': message,
            'proposal_id': proposal.id,
            'text': text,
            'target': target,
            'proposal_code': self.make_proposal_code(db, proposal),
            'word_limit': word_limit,
            'rows': rows,
            'figures': figures,
            'calculations': calculations,
            'show_save_reminder': is_case_text,
            'role': role,
        })

        return ctx

    def _prepare_calculations(self, raw_calculations):
        calculations = []

        for calc in raw_calculations.values():
            calc_info = self.calculators.get(calc.calculator_id)
            if (calc_info is None or
                    not calc_info.calculator.is_valid_mode(calc.mode)):
                calculations.append(CalculationExtra(
                    *calc,
                    calculator_name='Calculator {}'.format(calc.calculator_id),
                    inputs=[CalculatorValue(x, x, None, '{}', None)
                            for x in calc.input],
                    outputs=[CalculatorValue(x, x, None, '{}', None)
                             for x in calc.output],
                    mode_info=CalculatorMode(None,
                                             'Mode {}'.format(calc.mode)),
                    target_view=None))
            else:
                calculator = calc_info.calculator
                mode_info = calculator.get_mode_info(calc.mode)

                calculation = CalculationExtra(
                    *calc,
                    calculator_name=calc_info.name,
                    inputs=calculator.get_inputs(calc.mode, calc.version),
                    outputs=calculator.get_outputs(calc.mode, calc.version),
                    mode_info=mode_info,
                    target_view=url_for(
                        '.calc_{}_{}'.format(calculator.get_code(),
                                             mode_info.code),
                        calculation_id=calc.id))

                # Call the calculator method to compact the calculation
                # where possible.
                calculator.condense_calculation(calc.mode, calc.version,
                                                calculation)

                calculations.append(calculation)

        return calculations
