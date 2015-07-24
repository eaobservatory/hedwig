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

from collections import namedtuple

from ...astro.coord import CoordSystem
from ...email.format import render_email_template
from ...config import get_config
from ...error import ConsistencyError, NoSuchRecord, UserError
from ...file.info import determine_figure_type, determine_pdf_page_count
from ...type import Affiliation, \
    Calculation, CalculatorInfo, CalculatorMode, CalculatorValue, Call, \
    FigureType, FormatType, \
    ProposalCategory, ProposalFigureInfo, ProposalState, ProposalText, \
    Queue, ResultCollection, Semester, Target, \
    TargetCollection, TargetToolInfo, TextRole, \
    ValidationMessage, \
    null_tuple
from ...util import get_countries
from ...view import auth
from ...web.util import ErrorPage, HTTPError, HTTPForbidden, \
    HTTPNotFound, HTTPRedirect, \
    flash, session, url_for
from ...view.util import count_words, organise_collection, with_proposal

ProposalFigureExtra = namedtuple(
    'ProposalFigureExtra',
    ProposalFigureInfo._fields + ('target_view', 'target_edit', 'target_full'))

CalculationExtra = namedtuple(
    'CalculationExtra',
    Calculation._fields + ('calculator_name',
                           'inputs', 'outputs', 'mode_info', 'target_view'))

CalculatorInfoExtra = namedtuple(
    'CalculatorInfoExtra',
    CalculatorInfo._fields + ('target_view', ))

TargetToolInfoExtra = namedtuple(
    'TargetToolInfoExtra',
    TargetToolInfo._fields + ('target_view', ))


class GenericProposal(object):
    def view_proposal_new(self, db, call_id, form, is_post):
        try:
            call = db.search_call(
                facility_id=self.id_, call_id=call_id, is_open=True
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

        if is_post:
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
                                           proposal_id=proposal_id))

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

    @with_proposal(permission='view')
    def view_proposal_view(self, db, proposal, can):
        countries = get_countries()

        ctx = {
            'title': proposal.title,
            'can_edit': can.edit,
            'can_remove_self': (ProposalState.can_edit(proposal.state) and
                                any(x.person_id == session['person']['id']
                                    for x in proposal.members.values())),
            'is_submitted': ProposalState.is_submitted(proposal.state),
            'proposal': proposal._replace(members=[
                x._replace(institution_country=countries.get(
                    x.institution_country, 'Unknown country'))
                for x in proposal.members.values()]),
            'proposal_code': self.make_proposal_code(db, proposal),
        }

        ctx.update(self._view_proposal_extra(db, proposal))

        return ctx

    def _view_proposal_extra(self, db, proposal):
        """
        Method to gather additional information for the proposal view page.

        Sub-classes can override this method to add additional information
        to the proposal.
        """

        proposal_text = db.get_all_proposal_text(proposal.id)
        proposal_pdf = db.search_proposal_pdf(proposal.id)

        proposal_fig = db.search_proposal_figure(proposal.id,
                                                 with_caption=True,
                                                 with_has_preview=True)

        tech_case_fig = [
            ProposalFigureExtra(*x, target_view=url_for(
                ('.tech_view_figure_preview'
                    if x.has_preview
                    else '.tech_view_figure'),
                proposal_id=proposal.id, fig_id=x.id,
                md5sum=x.md5sum), target_full=(
                    url_for('.tech_view_figure',
                            proposal_id=proposal.id, fig_id=x.id,
                            md5sum=x.md5sum)
                    if x.has_preview else None),
                target_edit=None)
            for x in proposal_fig.values()
            if x.role == TextRole.TECHNICAL_CASE]
        sci_case_fig = [
            ProposalFigureExtra(*x, target_view=url_for(
                ('.sci_view_figure_preview'
                    if x.has_preview
                    else '.sci_view_figure'),
                proposal_id=proposal.id, fig_id=x.id,
                md5sum=x.md5sum), target_full=(
                    url_for('.sci_view_figure',
                            proposal_id=proposal.id, fig_id=x.id,
                            md5sum=x.md5sum)
                    if x.has_preview else None),
                target_edit=None)
            for x in proposal_fig.values()
            if x.role == TextRole.SCIENCE_CASE]

        targets = [
            x._replace(system=CoordSystem.get_name(x.system)) for x in
            db.search_target(
                proposal_id=proposal.id).to_formatted_collection().values()]

        calculations = db.search_calculation(proposal_id=proposal.id)

        return {
            'abstract': proposal_text.get(TextRole.ABSTRACT, None),
            'tech_case_text': proposal_text.get(
                TextRole.TECHNICAL_CASE, None),
            'sci_case_text': proposal_text.get(
                TextRole.SCIENCE_CASE, None),
            'tech_case_fig': tech_case_fig,
            'sci_case_fig': sci_case_fig,
            'tech_case_pdf': proposal_pdf.get_role(
                TextRole.TECHNICAL_CASE, None),
            'sci_case_pdf': proposal_pdf.get_role(
                TextRole.SCIENCE_CASE, None),
            'targets': targets,
            'calculators': [
                CalculatorInfoExtra(*x, target_view=url_for(
                    '.calc_{}_{}'.format(x.code, x.modes.values()[0].code),
                    proposal_id=proposal.id))
                for x in self.calculators.values()],
            'calculations': self._prepare_calculations(calculations),
            'target_tools': [
                TargetToolInfoExtra(*x, target_view=url_for(
                    '.tool_proposal_{}'.format(x.code,),
                    proposal_id=proposal.id))
                for x in self.target_tools.values()],
            'categories': db.search_proposal_category(
                proposal_id=proposal.id).values(),
        }

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

    def _validate_proposal_extra(self, db, proposal, extra):
        messages = []

        if extra['abstract'] is None:
            messages.append(ValidationMessage(
                True,
                'The proposal does not have an abstract.',
                'Edit the proposal abstract',
                url_for('.abstract_edit', proposal_id=proposal.id)))

        if not extra['targets']:
            messages.append(ValidationMessage(
                False,
                'No target objects have been specified.',
                'Edit target list',
                url_for('.target_edit', proposal_id=proposal.id)))

        if not extra['calculations']:
            messages.append(ValidationMessage(
                False,
                'The proposal does not have any calculation results attached.',
                'See available calculators',
                url_for('.facility_home', _anchor='calc')))

        if ((extra['tech_case_text'] is None) and
                (extra['tech_case_pdf'] is None)):
            messages.append(ValidationMessage(
                False,
                'The proposal does not have a technical justification.',
                'Edit technical justification',
                url_for('.tech_edit', proposal_id=proposal.id)))

        if ((extra['sci_case_text'] is None) and
                (extra['sci_case_pdf'] is None)):
            messages.append(ValidationMessage(
                False,
                'The proposal does not have a scientific justification.',
                'Edit scientific justification',
                url_for('.sci_edit', proposal_id=proposal.id)))

        return messages

    @with_proposal(permission='edit')
    def view_proposal_submit(self, db, proposal, can, form, is_post):
        if ProposalState.is_submitted(proposal.state):
            raise ErrorPage('The proposal has already been submitted.')

        messages = self._validate_proposal(db, proposal)
        has_error = any(x.is_error for x in messages)

        if is_post:
            if 'submit_confirm' in form:
                if has_error:
                    raise ErrorPage(
                        'The proposal can not be submitted while there are '
                        'errors in validation.')

                db.update_proposal(proposal.id, state=ProposalState.SUBMITTED)

                proposal_code = self.make_proposal_code(db, proposal)

                db.add_message(
                    'Proposal {0} submitted'.format(proposal_code),
                    render_email_template(
                        'proposal_submitted.txt', {
                            'proposal': proposal,
                            'proposal_code': proposal_code,
                            'target_url': url_for(
                                '.proposal_view',
                                proposal_id=proposal.id, _external=True),
                        },
                        facility=self),
                    [x.person_id for x in proposal.members.values()])

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

    @with_proposal(permission='view')
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

    @with_proposal(permission='edit')
    def view_proposal_withdraw(self, db, proposal, can, form, is_post):
        if not ProposalState.is_submitted(proposal.state):
            raise ErrorPage('The proposal has not been submitted.')

        if is_post:
            if 'submit_confirm' in form:
                db.update_proposal(proposal.id, state=ProposalState.WITHDRAWN)

                proposal_code = self.make_proposal_code(db, proposal)

                db.add_message(
                    'Proposal {0} withdrawn'.format(proposal_code),
                    render_email_template(
                        'proposal_withdrawn.txt', {
                            'proposal': proposal,
                            'proposal_code': proposal_code,
                        },
                        facility=self),
                    [x.person_id for x in proposal.members.values()])

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

    @with_proposal(permission='edit')
    def view_title_edit(self, db, proposal, can, form, is_post):
        message = None

        if is_post:
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

    @with_proposal(permission='edit')
    def view_abstract_edit(self, db, proposal, can, form):
        return self._edit_text(
            db, proposal, TextRole.ABSTRACT, proposal.abst_word_lim,
            url_for('.abstract_edit', proposal_id=proposal.id), form, 10,
            extra_initialization=self._view_abstract_edit_init,
            extra_form_read=self._view_abstract_edit_read,
            extra_form_proc=self._view_abstract_edit_proc)

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

    @with_proposal(permission='edit')
    def view_member_edit(self, db, proposal, can, form, is_post):
        message = None
        records = proposal.members

        affiliations = db.search_affiliation(
            queue_id=proposal.queue_id, hidden=False)
        if not affiliations:
            raise HTTPError('No affiliations appear to be available.')

        if is_post:
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
                    affiliation_str = form.get('affiliation_{0}'.format(id_))
                    if affiliation_str is None:
                        del records[id_]
                        continue

                    records[id_] = record._replace(
                        pi=(id_ == pi),
                        editor=('editor_{0}'.format(id_) in form),
                        observer=('observer_{0}'.format(id_) in form),
                        affiliation_id=int(affiliation_str))

                db.sync_proposal_member(
                    proposal.id, records,
                    editor_person_id=session['person']['id'])

                flash('The proposal member list has been updated.')
                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Members',
            'message': message,
            'proposal_id': proposal.id,
            'members': records.values(),
            'affiliations': affiliations.values(),
            'proposal_code': self.make_proposal_code(db, proposal),
        }

    @with_proposal(permission='edit')
    def view_member_add(self, db, proposal, can, form, is_post):
        message_link = message_invite = None
        member = dict(editor=None, observer=None, person_id=None,
                      name='', email='')

        affiliations = db.search_affiliation(
            queue_id=proposal.queue_id, hidden=False)
        if not affiliations:
            raise HTTPError('No affiliations appear to be available.')

        if is_post:
            member['editor'] = 'editor' in form
            member['observer'] = 'observer' in form
            if 'person_id' in form:
                member['person_id'] = int(form['person_id'])
            member['name'] = form.get('name', '')
            member['email'] = form.get('email', '')
            member['affiliation_id'] = int(form['affiliation_id'])

            if 'submit-link' in form:
                try:
                    if member['person_id'] is None:
                        raise UserError(
                            'No-one was selected from the directory.')

                    try:
                        person = db.get_person(person_id=member['person_id'])
                    except NoSuchRecord:
                        raise ErrorPage('This person\'s record was not found')

                    if not person.public:
                        raise ErrorPage('This person\'s record is private.')

                    db.add_member(proposal.id, member['person_id'],
                                  member['affiliation_id'],
                                  editor=member['editor'],
                                  observer=member['observer'])

                    db.add_message(
                        'Proposal {0} invitation'.format(
                            self.make_proposal_code(db, proposal)),
                        render_email_template(
                            'proposal_invitation.txt', {
                                'proposal': proposal,
                                'recipient_name': person.name,
                                'inviter_name': session['person']['name'],
                                'target_url': url_for(
                                    '.proposal_view',
                                    proposal_id=proposal.id, _external=True),
                            },
                            facility=self),
                        [member['person_id']])

                    flash('{0} has been added to the proposal.', person.name)
                    raise HTTPRedirect(url_for('.proposal_view',
                                       proposal_id=proposal.id))

                except UserError as e:
                    message_link = e.message

            elif 'submit-invite' in form:
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
                    (token, expiry) = db.add_invitation(person_id)

                    db.add_message(
                        'Proposal {0} invitation'.format(
                            self.make_proposal_code(db, proposal)),
                        render_email_template(
                            'proposal_invitation.txt', {
                                'token': token,
                                'expiry': expiry,
                                'proposal': proposal,
                                'recipient_name': member['name'],
                                'inviter_name': session['person']['name'],
                                'target_url': url_for(
                                    'people.invitation_token_enter',
                                    token=token, _external=True),
                                'target_plain': url_for(
                                    'people.invitation_token_enter',
                                    _external=True),
                            },
                            facility=self),
                        [person_id])

                    flash('{0} has been added to the proposal.',
                          member['name'])

                    # Return to the proposal page after editing the new
                    # member's institution.
                    session['next_page'] = url_for('.proposal_view',
                                                   proposal_id=proposal.id)

                    raise HTTPRedirect(url_for(
                        'people.person_edit_institution', person_id=person_id))

                except UserError as e:
                    message_invite = e.message

            else:
                raise ErrorPage('Unknown action.')

        # Prepare list of people to display as the registered member
        # directory, filtering out current proposal members.
        countries = get_countries()
        current_persons = [m.person_id for m in proposal.members.values()]
        persons = [
            p._replace(institution_country=countries.get(
                p.institution_country))
            for p in db.search_person(registered=True, public=True,
                                      with_institution=True).values()
            if p.id not in current_persons
        ]

        return {
            'title': 'Add Member',
            'message_link': message_link,
            'message_invite': message_invite,
            'proposal_id': proposal.id,
            'persons': persons,
            'affiliations': affiliations.values(),
            'member': member,
            'proposal_code': self.make_proposal_code(db, proposal),
        }

    @with_proposal(permission='view')
    def view_member_remove_self(self, db, proposal, can, form):
        if not ProposalState.can_edit(proposal.state):
            raise ErrorPage('This proposal is not in an editable state.')

        proposal_code = self.make_proposal_code(db, proposal)

        if form:
            if 'submit_cancel' in form:
                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id))

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
                raise HTTPRedirect(url_for('home_page'))

        return {
            'title': 'Remove Yourself from Proposal',
            'message':
                'Are you sure you wish to remove yourself from '
                'proposal {}?'.format(proposal_code),
        }

    @with_proposal(permission='edit')
    def view_target_edit(self, db, proposal, can, form, is_post):
        message = None

        records = db.search_target(
            proposal_id=proposal.id).to_formatted_collection()

        if is_post:
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
                                           proposal_id=proposal.id))

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

    @with_proposal(permission='edit')
    def view_request_edit(self, db, proposal, can, form, is_post):
        raise ErrorPage('Observing request not implemented for this facility.')

    @with_proposal(permission='edit')
    def view_case_edit(self, db, proposal, can, role):
        code = TextRole.short_name(role)
        call = db.get_call(facility_id=None, call_id=proposal.call_id)

        text_info = db.search_proposal_text(proposal_id=proposal.id, role=role)

        pdf_info = db.search_proposal_pdf(proposal_id=proposal.id, role=role,
                                          with_uploader_name=True)

        figures = [
            ProposalFigureExtra(
                *x,
                target_full=url_for('.{}_view_figure'.format(code),
                                    proposal_id=proposal.id, fig_id=x.id,
                                    md5sum=x.md5sum),
                target_view=url_for('.{}_view_figure_thumbnail'.format(code),
                                    proposal_id=proposal.id, fig_id=x.id,
                                    md5sum=x.md5sum),
                target_edit=url_for('.{}_edit_figure'.format(code),
                                    proposal_id=proposal.id, fig_id=x.id))
            for x in db.search_proposal_figure(
                proposal_id=proposal.id, role=role,
                with_caption=True, with_uploader_name=True).values()]

        return {
            'title': 'Edit {}'.format(TextRole.get_name(role).title()),
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'note': getattr(call, code + '_note'),
            'word_limit': getattr(proposal, code + '_word_lim'),
            'fig_limit': getattr(proposal, code + '_fig_lim'),
            'page_limit': getattr(proposal, code + '_page_lim'),
            'target_text': url_for(
                '.{}_edit_text'.format(code), proposal_id=proposal.id),
            'target_new_figure': url_for(
                '.{}_new_figure'.format(code), proposal_id=proposal.id),
            'target_manage_figure': url_for(
                '.{}_manage_figure'.format(code), proposal_id=proposal.id),
            'target_pdf': url_for(
                '.{}_edit_pdf'.format(code), proposal_id=proposal.id),
            'target_pdf_view': url_for(
                '.{}_view_pdf'.format(code), proposal_id=proposal.id),
            'text': text_info.get_single(None),
            'figures': figures,
            'pdf': pdf_info.get_single(None),
        }

    @with_proposal(permission='edit')
    def view_case_edit_text(self, db, proposal, can, role, form):
        code = TextRole.short_name(role)

        figures = [
            ProposalFigureExtra(
                *x, target_edit=None, target_full=None,
                target_view=url_for('.{}_view_figure_thumbnail'.format(code),
                                    proposal_id=proposal.id, fig_id=x.id,
                                    md5sum=x.md5sum))
            for x in db.search_proposal_figure(
                proposal_id=proposal.id, role=role).values()]

        return self._edit_text(
            db, proposal, role,
            getattr(proposal, code + '_word_lim'),
            url_for('.{}_edit_text'.format(code), proposal_id=proposal.id),
            form, 30, figures,
            url_for('.{}_edit'.format(code), proposal_id=proposal.id))

    @with_proposal(permission='edit')
    def view_case_edit_figure(self, db, proposal, can, fig_id, role,
                              form, file):
        code = TextRole.short_name(role)
        name = TextRole.get_name(role)
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

            target = url_for('.{}_new_figure'.format(code),
                             proposal_id=proposal.id)

        else:
            figure = db.search_proposal_figure(
                proposal_id=proposal.id, role=role,
                fig_id=fig_id, with_caption=True).get_single()

            target = url_for('.{}_edit_figure'.format(code),
                             proposal_id=proposal.id, fig_id=fig_id)

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
                            proposal.id, role, **figure_args)

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
                    '.{}_edit'.format(code), proposal_id=proposal.id))

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
            'mime_types': FigureType.all_mime_types(),
            'target': target,
        }

    @with_proposal(permission='edit')
    def view_case_manage_figure(self, db, proposal, can, role, form):
        code = TextRole.short_name(role)
        name = TextRole.get_name(role)
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
                    '.{}_edit'.format(code), proposal_id=proposal.id))

            except UserError as e:
                message = e.message

        return {
            'title': 'Manage {} Figures'.format(name.title()),
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'message': message,
            'target': url_for('.{}_manage_figure'.format(code),
                              proposal_id=proposal.id),
            'figures': [
                ProposalFigureExtra(
                    *x, target_full=None, target_edit=None,
                    target_view=url_for(
                        '.{}_view_figure_thumbnail'.format(code),
                        proposal_id=proposal.id, fig_id=x.id, md5sum=x.md5sum))
                for x in figures.values()],
        }

    @with_proposal(permission='view')
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

    @with_proposal(permission='edit')
    def view_case_edit_pdf(self, db, proposal, can, role, file):
        code = TextRole.short_name(role)
        name = TextRole.get_name(role)
        page_limit = getattr(proposal, code + '_page_lim'),
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
                    raise UserError('File was of type {0} rather than PDF.',
                                    FigureType.get_name(type_))

                page_count = determine_pdf_page_count(buff)
                if page_count > page_limit:
                    raise UserError(
                        'PDF is too long: {0} / {1} {2}',
                        page_count, page_limit,
                        ('page' if page_limit == 1 else 'pages'))

                db.set_proposal_pdf(proposal.id, role, buff, page_count,
                                    filename, session['person']['id'])

                flash('The {0} has been uploaded.', name.lower())

                raise HTTPRedirect(url_for(
                    '.{}_edit'.format(code), proposal_id=proposal.id))

            except UserError as e:
                message = e.message

        return {
            'title': 'Upload {0} PDF'.format(name.title()),
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'message': message,
            'mime_types': [FigureType.get_mime_type(FigureType.PDF)],
            'max_size': max_size,
            'target': url_for('.{}_edit_pdf'.format(code),
                              proposal_id=proposal.id),
        }

    @with_proposal(permission='view')
    def view_case_view_pdf(self, db, proposal, can, role):
        try:
            return db.get_proposal_pdf(proposal.id, role)
        except NoSuchRecord:
            raise HTTPNotFound('{} PDF not found.'.format(
                TextRole.get_name(role).capitalize()))

    @with_proposal(permission='view')
    def view_case_view_pdf_preview(self, db, proposal, can, page, role,
                                   md5sum):
        try:
            return db.get_proposal_pdf_preview(proposal.id, role, page,
                                               md5sum=md5sum)
        except NoSuchRecord:
            raise HTTPNotFound('PDF preview page not found.')

    @with_proposal(permission='edit')
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
                    '.proposal_view', proposal_id=proposal.id))

            except UserError as e:
                message = e.message

        return {
            'title': 'Manage Calculations',
            'message': message,
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'calculations': self._prepare_calculations(calculations),
        }

    def _edit_text(self, db, proposal, role, word_limit, target, form, rows,
                   figures=None, target_redir=None,
                   extra_initialization=None, extra_form_read=None,
                   extra_form_proc=None):
        name = TextRole.get_name(role)
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
                        '{0} is too long: {1} / {2} words',
                        name.capitalize(), word_count, word_limit)

                db.set_proposal_text(proposal.id, role,
                                     text.text, text.format, word_count,
                                     session['person']['id'], is_update)

                if extra_form_proc is not None:
                    ctx = extra_form_proc(db, proposal, role, ctx)

                flash('The {0} has been saved.', name.lower())
                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id)
                                   if target_redir is None else target_redir)

            except UserError as e:
                message = e.message

        ctx.update({
            'title': 'Edit {0} Text'.format(name.title()),
            'message': message,
            'proposal_id': proposal.id,
            'text': text,
            'target': target,
            'proposal_code': self.make_proposal_code(db, proposal),
            'word_limit': word_limit,
            'rows': rows,
            'figures': figures,
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
