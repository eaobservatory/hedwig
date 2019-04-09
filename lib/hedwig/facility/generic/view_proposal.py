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

from collections import namedtuple
from itertools import chain, count

from ...astro.coord import CoordSystem
from ...astro.catalog import parse_source_list, write_source_list
from ...email.format import render_email_template
from ...config import get_config
from ...error import ConsistencyError, NoSuchRecord, ParseError, UserError
from ...file.info import determine_figure_type, determine_pdf_page_count
from ...publication.url import make_publication_url
from ...type.collection import CalculationCollection, \
    PrevProposalCollection, ResultCollection, \
    TargetCollection
from ...type.enum import AffiliationType, AnnotationType, AttachmentState, \
    CallState, FigureType, FormatType, \
    GroupType, MessageThreadType, \
    PermissionType, PersonTitle, ProposalState, PublicationType, ReviewState
from ...type.misc import SectionedList
from ...type.simple import Affiliation, \
    Calculation, CalculatorInfo, CalculatorMode, CalculatorValue, Call, \
    Member, MemberInstitution, PrevProposal, PrevProposalPub, \
    ProposalCategory, ProposalFigureInfo, ProposalText, ProposalWithCode, \
    Queue, Semester, Target, TargetToolInfo, \
    TextCopyInfo, ValidationMessage
from ...type.util import null_tuple, with_can_edit, with_can_view
from ...view import auth
from ...web.util import ErrorPage, HTTPError, HTTPForbidden, \
    HTTPNotFound, HTTPRedirect, \
    flash, get_logger, session, url_for
from ...view.util import count_words, int_or_none, \
    with_proposal, with_verified_admin

CalculationExtra = namedtuple(
    'CalculationExtra', Calculation._fields + (
        'calculator_name', 'inputs', 'outputs', 'mode_info'))

PrevProposalExtra = namedtuple(
    'PrevProposalExtra',
    PrevProposal._fields + ('links',))

PrevProposalPubExtra = namedtuple(
    'PrevProposalPubExtra',
    PrevProposalPub._fields + ('url',))


class GenericProposal(object):
    def view_proposal_new(self, db, call_id, form):
        type_class = self.get_call_types()
        role_class = self.get_reviewer_roles()

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
        old_proposal_id = None
        member_copy = False

        if form is not None:
            try:
                old_proposal = None

                affiliation_id = int(form['affiliation_id'])
                if affiliation_id not in affiliations:
                    raise ErrorPage('Invalid affiliation selected.')

                proposal_title = form['proposal_title'].strip()

                if 'proposal_id' in form:
                    old_proposal_id = int(form['proposal_id'])

                member_copy = 'member_copy' in form

                if 'submit_new' in form:
                    pass

                elif 'submit_copy' in form:
                    if old_proposal_id is None:
                        raise UserError('No proposal was selected to copy.')

                    try:
                        old_proposal = db.get_proposal(
                            self.id_, old_proposal_id, with_members=True)
                    except NoSuchRecord:
                        raise ErrorPage('Proposal to copy not found.')

                    assert old_proposal.id == old_proposal_id

                    role_class = self.get_reviewer_roles()
                    can = auth.for_proposal(role_class, db, old_proposal)

                    if not can.view:
                        raise HTTPForbidden(
                            'Permission denied for the proposal '
                            'selected for copying.')

                    if not old_proposal.members.has_person(
                            session['person']['id']):
                        raise HTTPForbidden(
                            'You can only copy proposals '
                            'of which you are a member.')

                    if ProposalState.is_open(old_proposal.state):
                        raise ErrorPage('Proposal to copy is still open.')

                else:
                    raise ErrorPage('Unknown action selected.')

                proposal_id = db.add_proposal(
                    call_id=call_id, person_id=session['person']['id'],
                    affiliation_id=affiliation_id,
                    title=(proposal_title if old_proposal is None
                           else old_proposal.title),
                    person_is_reviewer=type_class.has_reviewer_role(
                        call.type, role_class.PEER))

                if old_proposal is None:
                    flash('Your new proposal has been created.')

                else:
                    try:
                        proposal = db.get_proposal(
                            self.id_, proposal_id, with_members=True)

                        assert proposal.id == proposal_id

                        atn = self._copy_proposal(
                            db, old_proposal, proposal,
                            copy_members=member_copy)

                        db.add_proposal_annotation(
                            proposal.id, AnnotationType.PROPOSAL_COPY, atn)

                    except:
                        get_logger().exception(
                            'Failed to copy from proposal {} to {}',
                            old_proposal.id, proposal_id)

                        flash('An unexpected error occurred while your '
                              'proposal was being copied. '
                              'It may not be complete.')

                    else:
                        flash('Your proposal has been copied.')

                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal_id,
                                           first_view='true'))

            except UserError as e:
                message = e.message

        proposals = db.search_proposal(
            facility_id=self.id_,
            person_id=session['person']['id'],
            state=ProposalState.closed_states())

        return {
            'title': 'New Proposal',
            'call': call,
            'message': message,
            'proposal_title': proposal_title,
            'affiliations': affiliations,
            'affiliation_id': affiliation_id,
            'proposals': proposals.map_values(
                lambda x: ProposalWithCode(
                    *x, code=self.make_proposal_code(db, x))),
            'proposal_id': old_proposal_id,
            'member_copy': member_copy,
        }

    def _copy_proposal(
            self, db, old_proposal, proposal, copy_members,
            extra_text_roles=[]):
        role_class = self.get_text_roles()
        copier_person_id = session['person']['id']
        old_proposal_code = self.make_proposal_code(db, old_proposal)

        atn = {
            'old_proposal_id': old_proposal.id,
            'old_proposal_code': old_proposal_code,
            'copier_person_id': copier_person_id,
            'notes': SectionedList(
                note_format=lambda x: {'item': 'Error', 'comment': x}),
        }

        # Copy members (if requested) and student flag (including copier).
        with atn['notes'].accumulate_notes('proposal_members') as notes:
            affiliations = None

            if not copy_members:
                notes.append({
                    'item': 'Previous members',
                    'comment': 'not invited to the new proposal.',
                })

            elif proposal.queue_id != old_proposal.queue_id:
                # Affiliation IDs are different in different queues.
                notes.append({
                    'item': 'Previous members',
                    'comment': 'can not be copied from a proposal '
                    'in a different queue.'})

            else:
                # Get a list of the affiliations which are available now.
                affiliations = db.search_affiliation(
                    queue_id=proposal.queue_id, hidden=False)

            copier_old_member = old_proposal.members.get_person(
                copier_person_id)
            copier_member = proposal.members.get_single()

            for member in old_proposal.members.values():
                if member.person_id == copier_person_id:
                    # The copier should already have been added (as the 1st
                    # member).  We just need to copy the "student" flag.
                    proposal.members[copier_member.id] = \
                        copier_member._replace(student=member.student)

                    continue

                elif affiliations is None:
                    # Skip other members unless asked to copy.

                    continue

                elif member.affiliation_id not in affiliations:
                    notes.append({
                        'item': member.person_name,
                        'comment': 'not added to the proposal because '
                        'the affiliation "{}" is no longer available.'.format(
                            member.affiliation_name)})

                    continue

                send_token = False

                if member.person_registered:
                    # The person was registered, so we can link their profile.
                    member_person_id = member.person_id

                elif copier_old_member.editor:
                    # The person was not registered, so make a new profile.
                    old_person = db.get_person(
                        member.person_id, with_email=True)

                    member_person_id = db.add_person(
                        old_person.name, title=old_person.title,
                        primary_email=old_person.email.get_primary().address,
                        institution_id=member.resolved_institution_id)

                    send_token = True

                else:
                    notes.append({
                        'item': member.person_name,
                        'comment': 'not added to the proposal because '
                        'they did not register for an account and you were '
                        'not an editor of the original proposal.'})

                    continue

                member_id = db.add_member(
                    proposal.id, member_person_id,
                    member.affiliation_id, member.editor, member.observer)

                self._message_proposal_invite(
                    db, proposal=proposal,
                    person_id=member_person_id,
                    person_name=member.person_name,
                    is_editor=member.editor,
                    affiliation_name=member.affiliation_name,
                    send_token=send_token,
                    copy_proposal_code=old_proposal_code)

                proposal.members[member_id] = null_tuple(Member)._replace(
                    id=member_id, student=member.student)

                notes.append({
                    'item': member.person_name,
                    'comment': (
                        'invited to register.'
                        if send_token else 'added to the proposal.'),
                })

            db.sync_proposal_member_student(proposal.id, proposal.members)

        # Copy target objects.
        with atn['notes'].accumulate_notes('proposal_targets') as notes:
            records = db.search_target(proposal_id=old_proposal.id)

            if records:
                sort_counter = count(1)
                (n_insert, n_update, n_delete) = db.sync_proposal_target(
                    proposal_id=proposal.id, records=records.map_values(
                        lambda x: x._replace(
                            id=None, sort_order=next(sort_counter))))

                notes.append({
                    'item': '{} {}'.format(
                        n_insert, 'targets' if n_insert > 1 else 'target'),
                    'comment': 'copied to the proposal.'})

        # Copy calculations.
        with atn['notes'].accumulate_notes('proposal_calculations') as notes:
            records = db.search_calculation(proposal_id=old_proposal.id)

            if records:
                for (calc_number, calculation) in enumerate(
                        records.values(), 1):
                    calc_name = 'Calculation {}'.format(calc_number)
                    if calculation.title:
                        calc_name = '{}. {}'.format(
                            calc_name, calculation.title)

                    calc_info = self.calculators.get(calculation.calculator_id)
                    if (calc_info is None or not
                            calc_info.calculator.is_valid_mode(
                                calculation.mode)):
                        notes.append({
                            'item': calc_name,
                            'comment': 'not copied because this calculator or '
                            'calculation mode has been removed.'})
                        continue

                    calculator = calc_info.calculator
                    mode = calculation.mode
                    input_ = calculation.input
                    calc_version = calculator.get_calc_version()

                    if not calculation.title:
                        mode_info = calculator.get_mode_info(mode)
                        calc_name = '{}. {} {}'.format(
                            calc_name, calc_info.name, mode_info.name)

                    # Convert to current interface version.
                    if calculation.version != calculator.version:
                        input_ = calculator.convert_input_version(
                            mode, calculation.version, input_)

                        notes.append({
                            'item': calc_name,
                            'comment': 'adjusted because the calculator '
                            'interface has changed.'})

                    elif calc_version != calculation.calc_version:
                        notes.append({
                            'item': calc_name,
                            'comment': 'recalculated because the calculator '
                            'has been updated.'})

                    else:
                        # "calc_version" is only supposed to be informational,
                        # so we should probably not use it to assume we need
                        # not recalculate.
                        notes.append({
                            'item': calc_name,
                            'comment': 'results might have changed slightly.'})

                    # Repeat the calculation in case anything changed.
                    result = calculator(mode, input_)

                    db.add_calculation(
                        proposal.id, calculation.calculator_id,
                        mode=mode,
                        version=calculator.version,
                        input_=input_,
                        output=result.output,
                        calc_version=calc_version,
                        title=calculation.title)

        # Copy previous proposals.
        with atn['notes'].accumulate_notes('proposal_previous') as notes:
            records = db.search_prev_proposal(proposal_id=old_proposal.id)
            n_prev = len(records)

            if ProposalState.is_submitted(old_proposal.state):
                records['copied'] = null_tuple(PrevProposal)._replace(
                    proposal_id=old_proposal.id,
                    proposal_code=old_proposal_code,
                    continuation=False, publications=[])

                notes.append({
                    'item': old_proposal_code,
                    'comment': 'added to the list of previous proposals.'})

            else:
                notes.append({
                    'item': old_proposal_code,
                    'comment': 'not added to the list of previous proposals '
                    'because it was not submitted.'})

            if records:
                db.sync_proposal_prev_proposal(
                    proposal_id=proposal.id, records=records.map_values(
                        lambda x: x._replace(id=None)),
                    retain_resolved=True)

                if n_prev:
                    notes.append({
                        'item': '{} previous {}'.format(
                            n_prev, 'proposals' if n_prev > 1 else 'proposal'),
                        'comment': 'copied to the proposal.'})

        # Copy PDF files, text and figures.
        pdfs = db.search_proposal_pdf(old_proposal.id)

        texts = db.search_proposal_text(old_proposal.id)

        figures = db.search_proposal_figure(
            proposal_id=old_proposal.id, with_caption=True)

        text_roles = [
            TextCopyInfo(
                role_class.ABSTRACT, 'proposal_abstract',
                proposal.abst_word_lim, 0, 0, 0),
            TextCopyInfo(
                role_class.TOOL_NOTE, 'proposal_targets',
                proposal.expl_word_lim, 0, 0, 0),
            TextCopyInfo(
                role_class.TECHNICAL_CASE, 'technical_case',
                proposal.tech_word_lim, proposal.tech_fig_lim,
                proposal.capt_word_lim, proposal.tech_page_lim),
            TextCopyInfo(
                role_class.SCIENCE_CASE, 'science_case',
                proposal.sci_word_lim, proposal.sci_fig_lim,
                proposal.capt_word_lim, proposal.sci_page_lim),
        ]

        for attachment in chain(text_roles, extra_text_roles):
            role = attachment.role
            role_name = role_class.get_name(role)

            with atn['notes'].accumulate_notes(attachment.section) as notes:
                pdf = pdfs.get_role(role, None)
                if pdf is not None:
                    if not attachment.page_lim:
                        notes.append({
                            'item': role_name,
                            'comment': 'PDF file not copied because uploading '
                            'of PDF files is no longer available here.'})

                    elif pdf.pages > attachment.page_lim:
                        notes.append({
                            'item': role_name,
                            'comment': 'PDF file not copied because it is '
                            'too long ({} / {} {}).'.format(
                                pdf.pages, attachment.page_lim,
                                ('page' if attachment.page_lim == 1
                                 else 'pages'))})

                    else:
                        db.link_proposal_pdf(
                            role_class, proposal.id, role, pdf.pdf_id)

                        notes.append({
                            'item': role_name,
                            'comment': 'PDF file was copied to the proposal.'})

                    # If there was a PDF, there should be no text or figures,
                    # so stop processing the attachment type.
                    continue

                text = texts.get_role(role, None)
                if text is not None:
                    if not attachment.word_lim:
                        notes.append({
                            'item': role_name,
                            'comment': 'text not copied because online '
                            'entry of text is no longer available here.'})

                    elif text.words > attachment.word_lim:
                        notes.append({
                            'item': role_name,
                            'comment': 'text not copied because it is '
                            'too long ({} / {} words).'.format(
                                text.words, attachment.word_lim)})

                    else:
                        db.link_proposal_text(
                            role_class, proposal.id, role, text.text_id)

                        notes.append({
                            'item': role_name,
                            'comment': 'the text was copied to the proposal.'})

                for (figure_number, figure) in enumerate(
                        figures.values_by_role(role), 1):
                    figure_name = 'Figure {}'.format(figure_number)

                    if not attachment.fig_lim:
                        notes.append({
                            'item': figure_name,
                            'comment': 'not copied because figures can '
                            'no longer be uploaded here.'})

                    elif figure_number > attachment.fig_lim:
                        notes.append({
                            'item': figure_name,
                            'comment': 'not copied because only {} {} '
                            'can be uploaded here.'.format(
                                attachment.fig_lim,
                                ('figure' if attachment.fig_lim == 1
                                 else 'figures'))})

                    elif not FigureType.is_valid(figure.type):
                        notes.append({
                            'item': figure_name,
                            'comment': 'not copied because this figure '
                            'type is no longer supported.'})

                    else:
                        caption = figure.caption
                        word_count = count_words(caption)
                        if word_count > attachment.capt_word_lim:
                            caption = ''

                            notes.append({
                                'item': figure_name,
                                'comment': 'caption removed because it is too '
                                'long ({} / {} words).'.format(
                                    word_count, attachment.capt_word_lim)})

                        db.link_proposal_figure(
                            role_class, proposal.id, role, figure.fig_id,
                            figure_number, caption)

                        notes.append({
                            'item': figure_name,
                            'comment': 'the figure was copied to the proposal.'})

        return atn

    @with_proposal(permission=PermissionType.VIEW)
    def view_proposal_view(self, db, proposal, can, args):
        role_class = self.get_reviewer_roles()
        review_can = auth.for_review(
            role_class, db, reviewer=None, proposal=proposal,
            auth_cache=can.cache)
        feedback_can = auth.for_proposal_feedback(
            role_class, db, proposal=proposal, auth_cache=can.cache)

        type_class = self.get_call_types()
        call_mid_closes = None
        if type_class.get_info(proposal.call_type).mid_close:
            call_mid_closes = db.search_call_mid_close(
                call_id=proposal.call_id, closed=False)

        is_admin = session.get('is_admin', False)
        is_first_view = ('first_view' in args)

        ctx = {
            'title': proposal.title,
            'can_edit': can.edit,
            'can_remove_self': (ProposalState.can_edit(proposal.state) and
                                any(x.person_id == session['person']['id']
                                    for x in proposal.members.values())),
            'can_view_review': review_can.view,
            'can_edit_review': review_can.edit,
            'can_view_feedback': feedback_can.view,
            'is_submitted': ProposalState.is_submitted(proposal.state),
            'proposal': proposal._replace(members=proposal.members.map_values(
                lambda x: with_can_view(
                    x, (is_admin or x.person_public
                        or (can.edit and not x.person_registered))))),
            'students': proposal.members.get_students(),
            'proposal_code': self.make_proposal_code(db, proposal),
            'show_person_proposals_callout': is_first_view,
            'show_admin_links': is_admin,
            'proposal_order': self.get_proposal_order_names(),
            'call_mid_closes': call_mid_closes,
        }

        ctx.update(self._view_proposal_extra(db, proposal))

        if is_first_view:
            ctx['copy_annotations'] = db.search_proposal_annotation(
                proposal_id=proposal.id)

        return ctx

    def _view_proposal_extra(self, db, proposal, extra_text_roles={}):
        """
        Method to gather additional information for the proposal view page.

        Sub-classes can override this method to add additional information
        to the proposal.
        """

        role_class = self.get_text_roles()

        proposal_text = db.search_proposal_text(proposal.id, with_text=True)
        proposal_pdf = db.search_proposal_pdf(proposal.id)

        proposal_fig = db.search_proposal_figure(proposal.id,
                                                 with_caption=True,
                                                 with_has_preview=True)

        targets = db.search_target(proposal_id=proposal.id)
        target_total_time = targets.total_time()

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
            'abstract': proposal_text.get_role(role_class.ABSTRACT, None),
            'targets': targets.to_formatted_collection(),
            'target_total_time': target_total_time,
            'calculators': self.calculators,
            'calculations': self._prepare_calculations(calculations),
            'target_tools': self.target_tools,
            'tool_note': proposal_text.get_role(role_class.TOOL_NOTE, None),
            'categories': db.search_proposal_category(
                proposal_id=proposal.id),
            'prev_proposals': prev_proposals,
        }

        for role in (role_class.TECHNICAL_CASE, role_class.SCIENCE_CASE):
            extra['{}_case'.format(role_class.short_name(role))] = {
                'role': role,
                'text': proposal_text.get_role(role, None),
                'pdf': proposal_pdf.get_role(role, None),
                'fig': proposal_fig.values_by_role(role),
            }

        for (role_attr, role) in extra_text_roles.items():
            extra[role_attr] = proposal_text.get_role(role, None)

        return extra

    @with_verified_admin
    @with_proposal(permission=PermissionType.NONE)
    def view_proposal_alter_state(self, db, proposal, form):
        message = None

        if form is not None:
            try:
                db.update_proposal(proposal_id=proposal.id,
                                   state=int(form['state']),
                                   state_prev=int(form['state_prev']))

                flash('The proposal state has been updated.')

                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id))

            except UserError as e:
                message = e.message

            except ConsistencyError:
                    raise ErrorPage(
                        'The state could not be updated.  Perhaps it changed '
                        'since you opened the alter state page.')

        proposal_code = self.make_proposal_code(db, proposal)

        return {
            'title': 'Alter status: {}'.format(proposal_code),
            'proposal_id': proposal.id,
            'proposal_code': proposal_code,
            'message': message,
            'state': proposal.state,
            'states': ProposalState.get_options(),
        }

    def _validate_proposal(self, db, proposal):
        type_class = self.get_call_types()
        role_class = self.get_reviewer_roles()

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

        if type_class.has_reviewer_role(proposal.call_type, role_class.PEER):
            reviewer = proposal.members.get_reviewer(default=None)
            if reviewer is None:
                messages.append(ValidationMessage(
                    True,
                    'A member has not been designated to act as the '
                    'peer reviewer.',
                    'Select a peer reviewer',
                    url_for('.member_edit', proposal_id=proposal.id)))
            elif not reviewer.person_registered:
                messages.append(ValidationMessage(
                    False,
                    'The designated peer reviewer has not yet registed '
                    'with this system.',
                    'Select a different peer reviewer',
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

        elif (extra['targets'] and extra['target_tools']
                and (extra['tool_note'] is None)):
            messages.append(ValidationMessage(
                False,
                'A note on the target tool results has not been added.',
                'Check targets with tools and edit note',
                url_for('.tool_note_edit', proposal_id=proposal.id)))

        if extra['calculators'] and (not extra['calculations']):
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

        type_class = self.get_call_types()
        immediate_review = type_class.has_immediate_review(proposal.call_type)

        messages = self._validate_proposal(db, proposal)
        has_error = any(x.is_error for x in messages)

        if form is not None:
            if 'submit_confirm' in form:
                if has_error:
                    raise ErrorPage(
                        'The proposal can not be submitted while there are '
                        'errors in validation.')

                db.update_proposal(proposal.id, state=(
                    ProposalState.REVIEW if immediate_review else
                    ProposalState.SUBMITTED))

                self._message_proposal_submit(db, proposal)

                self._message_proposal_review_notification(db, proposal)

                if immediate_review:
                    # Freeze member institution ID values.
                    db.sync_proposal_member_institution(proposal.id, {
                        x.id: MemberInstitution(
                            x.id, x.resolved_institution_id)
                        for x in proposal.members.values()})

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
            'immediate_review': immediate_review,
        }

    def _message_proposal_submit(self, db, proposal):
        type_class = self.get_call_types()
        proposal_code = self.make_proposal_code(db, proposal)
        immediate_review = type_class.has_immediate_review(proposal.call_type)

        db.add_message(
            'Proposal {} submitted'.format(proposal_code),
            render_email_template(
                'proposal_submitted.txt', {
                    'proposal': proposal,
                    'proposal_code': proposal_code,
                    'immediate_review': immediate_review,
                    'target_url': url_for(
                        '.proposal_view',
                        proposal_id=proposal.id, _external=True),
                    'submitter_name': session['person']['name'],
                },
                facility=self),
            [x.person_id for x in proposal.members.values()],
            thread_type=MessageThreadType.PROPOSAL_STATUS,
            thread_id=proposal.id)

    def _message_proposal_review_notification(self, db, proposal):
        """
        Send message to notify committee members about a proposal
        having been submitted, perhaps for immediate review.

        :param db: database control object.
        :param proposal: the Proposal object.
        """

        type_class = self.get_call_types()
        proposal_code = self.make_proposal_code(db, proposal)
        immediate_review = type_class.has_immediate_review(proposal.call_type)

        notify_group = type_class.get_notify_group(proposal.call_type)

        if not notify_group:
            return

        group_recipients = db.search_group_member(queue_id=proposal.queue_id,
                                                  group_type=notify_group)

        if not group_recipients:
            return

        recipient_ids = set((x.person_id for x in group_recipients.values()))

        # Also send the notification to site administrators.
        site_administrators = db.search_person(admin=True)
        recipient_ids.update((x.id for x in site_administrators.values()))

        db.add_message(
            'Proposal {} received{}'.format(
                proposal_code,
                (' for immediate review' if immediate_review else '')),
            render_email_template(
                'proposal_review_notification.txt', {
                    'proposal': proposal,
                    'proposal_code': proposal_code,
                    'call_type': type_class.get_name(proposal.call_type),
                    'immediate_review': immediate_review,
                    'target_view': url_for(
                        '.proposal_view',
                        proposal_id=proposal.id, _external=True),
                    'target_reviews': url_for(
                        '.proposal_reviews',
                        proposal_id=proposal.id, _external=True),
                },
                facility=self),
            recipient_ids,
            thread_type=MessageThreadType.PROPOSAL_REVIEW,
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
                proposal = proposal._replace(
                    title=form['proposal_title'].strip())
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
        type_class = self.get_call_types()
        role_class = self.get_reviewer_roles()
        has_peer_review = type_class.has_reviewer_role(
            proposal.call_type, role_class.PEER)

        message = None
        records = proposal.members
        person_id = session['person']['id']

        affiliations = db.search_affiliation(
            queue_id=proposal.queue_id, hidden=False)
        if not affiliations:
            raise HTTPError('No affiliations appear to be available.')

        if form is not None:
            if 'pi' in form:
                pi = int(form['pi'])
            else:
                pi = None

            if has_peer_review and ('reviewer' in form):
                reviewer = int(form['reviewer'])
            else:
                reviewer = None

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
                        sort_order=int(form['sort_order_{}'.format(id_)]),
                        pi=(id_ == pi),
                        editor=('editor_{}'.format(id_) in form),
                        observer=('observer_{}'.format(id_) in form),
                        reviewer=(id_ == reviewer),
                        affiliation_id=int(affiliation_str))

                db.sync_proposal_member(
                    proposal.id, records, editor_person_id=person_id)

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
            'call_type': proposal.call_type,
            'members': records.map_values(
                lambda x: with_can_edit(x, x.person_id != person_id)),
            'affiliations': affiliations,
            'proposal_code': self.make_proposal_code(db, proposal),
            'has_peer_review': has_peer_review,
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_member_add(self, db, proposal, can, form):
        message_link = message_invite = None
        member = dict(editor=None, observer=None, person_id=None,
                      name='', title=None, email='')

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
            if 'person_title' in form:
                member['title'] = int_or_none(form['person_title'])
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

                    member['name'] = member['name'].strip()
                    member['email'] = member['email'].strip()

                    person_id = db.add_person(
                        member['name'], title=member['title'],
                        primary_email=member['email'])
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
                    raise HTTPRedirect(url_for(
                        'people.person_edit_institution',
                        person_id=person_id, next_page=url_for(
                            '.proposal_view',
                            proposal_id=proposal.id, _anchor='members')))

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
            'call_type': proposal.call_type,
            'persons': persons,
            'affiliations': affiliations,
            'member': member,
            'proposal_code': self.make_proposal_code(db, proposal),
            'target': url_for('.member_add', proposal_id=proposal.id),
            'title_link': 'Add a Member from the Directory',
            'title_invite': 'Invite a New Member to the Proposal',
            'submit_link': 'Add to proposal',
            'submit_invite': 'Invite to register',
            'label_link': 'Member',
            'titles': PersonTitle.get_options(),
        }

    def _message_proposal_invite(
            self, db, proposal, person_id, person_name,
            is_editor, affiliation_name, send_token,
            copy_proposal_code=None):
        type_class = self.get_call_types()
        proposal_code = self.make_proposal_code(db, proposal)

        email_ctx = {
            'recipient_name': person_name,
            'proposal': proposal,
            'proposal_code': proposal_code,
            'call_type': type_class.get_name(proposal.call_type),
            'inviter_name': session['person']['name'],
            'affiliation': affiliation_name,
            'is_editor': is_editor,
            'target_semester': url_for(
                '.semester_calls', semester_id=proposal.semester_id,
                call_type=proposal.call_type, _external=True),
            'copy_proposal_code': copy_proposal_code,
        }

        if send_token:
            (token, expiry) = db.issue_invitation(person_id)

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
            'members': records,
            'proposal_code': self.make_proposal_code(db, proposal),
        }

    @with_verified_admin
    @with_proposal(permission=PermissionType.NONE)
    def view_member_affiliation_edit(self, db, proposal, member_id, form):
        message = None
        records = proposal.members

        if member_id not in records:
            raise ErrorPage('Proposal member not found.')

        affiliations = db.search_affiliation(
            queue_id=proposal.queue_id, hidden=False)
        if not affiliations:
            raise HTTPError('No affiliations appear to be available.')

        if form is not None:
            try:
                records[member_id] = records[member_id]._replace(
                    affiliation_id=int(form['affiliation_id']))

                (n_insert, n_update, n_delete) = \
                    db.sync_proposal_member(
                        proposal.id, records, editor_person_id=None)

                if n_update:
                    flash('The affiliation has been updated.')

                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id,
                                           _anchor='members'))

            except UserError as e:
                message = e.message

        member = records[member_id]

        return {
            'title': 'Edit affiliation: {}'.format(member.person_name),
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'message': message,
            'member': member,
            'affiliations': affiliations,
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

                prev_proposal_code = form[param].strip()
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
                    except ParseError:
                        # The given proposal code was not understood.
                        pass
                    except NoSuchRecord:
                        # The given proposal code was understood,
                        # but no matching record was found.
                        pass

                publications = []

                for i in range(6):
                    pub_desc = form['publication_{}_{}'.format(i, id_)].strip()
                    if not pub_desc:
                        continue
                    pub_type = int(form['pub_type_{}_{}'.format(i, id_)])

                    pub_type_info = PublicationType.get_info(pub_type)

                    # Remove prefix (e.g. "doi:") from reference.
                    if pub_type_info.prefix is not None:
                        pub_desc_lower = pub_desc.lower()
                        for prefix in pub_type_info.prefix:
                            if pub_desc_lower.startswith(prefix):
                                pub_desc = pub_desc[len(prefix):]

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

            records = PrevProposalCollection.organize_collection(
                updated_records, added_records)

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
            'prev_proposals': records,
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
                    target_id, proposal.id,
                    int_or_none(form['sort_order_' + id_]),
                    form[param].strip(),
                    int(form['system_' + id_]),
                    form['x_' + id_],
                    form['y_' + id_],
                    form['time_' + id_],
                    form['priority_' + id_])

            records = TargetCollection.organize_collection(
                updated_records, added_records)

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
            'targets': records,
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

                added_records = parse_source_list(buff,
                                                  number_from=max_record + 1)

                # TODO: would be more efficient to have a store-only
                # version of the sync method.
                if overwrite:
                    new_records = added_records
                else:
                    new_records = records.copy()
                    new_records.update(added_records)

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

    @with_proposal(permission=PermissionType.VIEW)
    def view_target_download(self, db, proposal, can):
        targets = db.search_target(proposal_id=proposal.id)

        return (
            write_source_list(targets),
            'text/plain',
            '{}-targets.txt'.format(self.make_proposal_code(db, proposal)))

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
                                 _anchor='checking-your-targets'),
            'target_tools': self.target_tools,
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_request_edit(self, db, proposal, can, form):
        raise ErrorPage('Observing request not implemented for this facility.')

    @with_proposal(permission=PermissionType.EDIT)
    def view_case_edit(self, db, proposal, can, role):
        role_class = self.get_text_roles()
        code = role_class.short_name(role)
        call = db.get_call(facility_id=None, call_id=proposal.call_id)

        text_info = db.search_proposal_text(
            proposal_id=proposal.id, role=role).get_single(None)

        pdf_info = db.search_proposal_pdf(
            proposal_id=proposal.id, role=role,
            with_uploader_name=True).get_single(None)

        figures = db.search_proposal_figure(
            proposal_id=proposal.id, role=role,
            with_caption=True, with_uploader_name=True)

        is_admin = session.get('is_admin', False)

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
            'text': text_info,
            'figures': figures,
            'pdf': pdf_info,
            'help_link': url_for('help.user_page',
                                 page_name=role_class.url_path(role)),
            'can_view_text_editor': is_admin,
            'can_view_pdf_uploader': is_admin,
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_case_edit_text(self, db, proposal, can, role, form):
        role_class = self.get_text_roles()
        code = role_class.short_name(role)

        figures = db.search_proposal_figure(
            proposal_id=proposal.id, role=role)

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
                              form, file_):
        role_class = self.get_text_roles()
        code = role_class.short_name(role)
        name = role_class.get_name(role)
        fig_limit = getattr(proposal, code + '_fig_lim')

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

            figure = null_tuple(ProposalFigureInfo)._replace(
                caption='', role=role)

            target = url_for('.case_new_figure',
                             proposal_id=proposal.id, role=role)

        else:
            try:
                figure = db.search_proposal_figure(
                    proposal_id=proposal.id, role=role,
                    fig_id=fig_id, with_caption=True).get_single()
            except NoSuchRecord:
                raise HTTPNotFound('Figure not found.')

            target = url_for('.case_edit_figure',
                             proposal_id=proposal.id, role=role,
                             fig_id=fig_id)

        return self._view_edit_figure(
            db, form, file_, figure, proposal, None, title=name.title(),
            target_edit=target,
            target_redirect=url_for(
                '.case_edit', proposal_id=proposal.id, role=role),
            word_limit=proposal.capt_word_lim)

    def _view_edit_figure(
            self, db, form, file_, figure, proposal, reviewer,
            title, target_edit, target_redirect, word_limit=None):
        max_size = int(get_config().get('upload', 'max_fig_size'))
        message = None

        if form is not None:
            try:
                # Put the caption text into the figure object first in case
                # of errors later.
                figure = figure._replace(caption=form['text'])

                if word_limit is not None:
                    word_count = count_words(figure.caption)
                    if word_count > word_limit:
                        raise UserError(
                            'Caption is too long: {} / {} words',
                            word_count, word_limit)

                if file_:
                    try:
                        filename = file_.filename
                        buff = file_.read(max_size * 1024 * 1024)

                        # Did we get all of the file within the size limit?
                        if len(file_.read(1)):
                            raise UserError(
                                'The uploaded figure was too large.')

                    finally:
                        file_.close()

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
                        if reviewer is None:
                            role_class = self.get_text_roles()
                            db.add_proposal_figure(
                                role_class, proposal.id, figure.role,
                                **figure_args)
                        else:
                            db.add_review_figure(
                                reviewer.id, **figure_args)

                        flash('The new figure has been uploaded.')

                    else:
                        # Update existing figure.
                        if reviewer is None:
                            db.update_proposal_figure(
                                proposal.id, figure.role, figure.id,
                                **figure_args)
                        else:
                            db.update_review_figure(
                                reviewer.id, figure.id, **figure_args)

                        flash('The replacement figure has been uploaded.')

                elif figure.id is None:
                    # We weren't updating an existing figure, so the lack
                    # of a file upload is an error.
                    raise UserError('No new figure file was received.')

                else:
                    # No file uploaded for an existing figure: just edit the
                    # caption.
                    if reviewer is None:
                        db.update_proposal_figure(
                            proposal.id, figure.role, figure.id,
                            caption=figure.caption)
                    else:
                        db.update_review_figure(
                            reviewer.id, figure.id, caption=figure.caption)

                    flash('The figure caption has been updated.')

                raise HTTPRedirect(target_redirect)

            except UserError as e:
                message = e.message

        return {
            'title': '{} {} Figure'.format(
                ('New' if figure.id is None else 'Edit'), title),
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'reviewer_id': (None if reviewer is None else reviewer.id),
            'reviewer_role': (None if reviewer is None else reviewer.role),
            'figure': figure,
            'word_limit': word_limit,
            'message': message,
            'max_size': max_size,
            'mime_types': FigureType.allowed_mime_types(),
            'mime_type_names': FigureType.allowed_type_names(),
            'target': target_edit,
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_case_manage_figure(self, db, proposal, can, role, form):
        role_class = self.get_text_roles()
        name = role_class.get_name(role)

        return self._view_manage_figure(
            db, form, proposal=proposal, reviewer=None,
            role=role, title=name.title(),
            target_edit=url_for(
                '.case_manage_figure', proposal_id=proposal.id, role=role),
            target_redirect=url_for(
                '.case_edit', proposal_id=proposal.id, role=role))

    def _view_manage_figure(
            self, db, form, proposal, reviewer, role,
            title, target_edit, target_redirect):
        message = None

        if reviewer is None:
            figures = db.search_proposal_figure(
                proposal_id=proposal.id, role=role, with_uploader_name=True)
        else:
            figures = db.search_review_figure(
                reviewer_id=reviewer.id, with_uploader_name=True)

        if form is not None:
            try:
                # Create a new list from the items so that it is safe
                # to update and/or delete from records (for Python-3).
                for (id_, figure) in list(figures.items()):
                    # If the sort order parameter is missing, the figure
                    # must have been deleted from the form.
                    sort_order_str = form.get('sort_order_{}'.format(id_))
                    if sort_order_str is None:
                        del figures[id_]
                        continue

                    figures[id_] = figure._replace(
                        sort_order=int(sort_order_str))

                if reviewer is None:
                    (n_insert, n_update, n_delete) = \
                        db.sync_proposal_figure(proposal.id, role, figures)
                else:
                    (n_insert, n_update, n_delete) = \
                        db.sync_review_figure(reviewer.id, figures)

                if n_delete:
                    flash('{} {} been removed.', n_delete,
                          ('figure has' if n_delete == 1 else 'figures have'))

                raise HTTPRedirect(target_redirect)

            except UserError as e:
                message = e.message

        return {
            'title': 'Manage {} Figures'.format(title),
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'reviewer_id': (None if reviewer is None else reviewer.id),
            'reviewer_role': (None if reviewer is None else reviewer.role),
            'role': role,
            'message': message,
            'target': target_edit,
            'figures': figures,
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
        role_class = self.get_text_roles()
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

    @with_proposal(permission=PermissionType.VIEW)
    def view_calculation_manage(self, db, proposal, can, form):
        return self._view_calculation_manage(
            db, proposal, None, can, form,
            title='{} Calculations'.format('Manage' if can.edit else 'View'),
            target_redirect=url_for(
                '.proposal_view', proposal_id=proposal.id,
                _anchor='calculations'))

    def _view_calculation_manage(
            self, db, proposal, reviewer, can, form,
            title, target_redirect):
        """
        Internal method to handle the calculation management page for either
        proposals or reviews.
        """

        proposal_code = self.make_proposal_code(db, proposal)

        if reviewer is None:
            calculations = db.search_calculation(proposal_id=proposal.id)

        else:
            title = '{}: {}'.format(proposal_code, title)
            calculations = db.search_review_calculation(
                reviewer_id=reviewer.id)

        message = None

        if form is not None:
            if not can.edit:
                raise HTTPForbidden(
                    'Edit permission denied for these calculations.')

            try:
                # Create a new list from the items so that it is safe
                # to update and/or delete from records (for Python-3).
                for (id_, calculation) in list(calculations.items()):
                    # If the sort order parameter is missing, the figure
                    # must have been deleted from the form.
                    sort_order_str = form.get('sort_order_{}'.format(id_))
                    if sort_order_str is None:
                        del calculations[id_]
                        continue

                    calculations[id_] = calculation._replace(
                        sort_order=int(sort_order_str))

                if reviewer is None:
                    (n_insert, n_update, n_delete) = \
                        db.sync_proposal_calculation(proposal.id, calculations)

                else:
                    (n_insert, n_update, n_delete) = \
                        db.sync_review_calculation(reviewer.id, calculations)

                if n_delete:
                    flash('{} {} been removed.', n_delete,
                          ('calculation has' if n_delete == 1 else
                           'calculations have'))

                raise HTTPRedirect(target_redirect)

            except UserError as e:
                message = e.message

                # Sort the calculation collection in case the user re-ordered
                # it.  Note we don't generally want to do this (e.g. in the
                # template) because this view function is also used for the
                # read-only case of seeing full calculation information.
                calculations = CalculationCollection((
                    (x.id, x) for x in calculations.values_in_sorted_order()))

        return {
            'title': title,
            'message': message,
            'proposal_id': proposal.id,
            'proposal_code': proposal_code,
            'reviewer_id': (None if reviewer is None else reviewer.id),
            'reviewer_role': (None if reviewer is None else reviewer.role),
            'calculations': self._prepare_calculations(
                calculations, condense=False),
            'can_edit': can.edit,
        }

    @with_proposal(permission=PermissionType.VIEW)
    def view_calculation_view(self, db, proposal, can, calculation_id):
        # Retrieve the calculation to identify the calculator and mode.
        try:
            calculation = db.search_calculation(
                calculation_id=calculation_id,
                proposal_id=proposal.id).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Calculation not found.')

        calculator_info = self.calculators.get(calculation.calculator_id)
        if calculator_info is None:
            raise HTTPNotFound('Calculator not found.')

        # Find the view function associated with this mode and call it.
        view_func = calculator_info.view_functions.get(calculation.mode)
        if view_func is None:
            raise HTTPNotFound('Calculator mode not found.')

        return view_func(calculation=calculation, can=can)

    @with_proposal(permission=PermissionType.FEEDBACK, with_decision_note=True)
    def view_proposal_feedback(self, db, proposal, can):
        proposal_code = self.make_proposal_code(db, proposal)

        ctx = {
            'title': '{}: Feedback'.format(proposal_code),
            'proposal_id': proposal.id,
            'proposal_code': proposal_code,
        }

        ctx.update(self._view_proposal_feedback_extra(db, proposal, can))

        return ctx

    def _view_proposal_feedback_extra(self, db, proposal, can):
        """
        Method to gather additional information for the proposal feedback page.
        """

        role_class = self.get_reviewer_roles()

        reviewers = db.search_reviewer(
            proposal_id=proposal.id, role=role_class.FEEDBACK,
            review_state=ReviewState.DONE,
            with_review=True, with_review_text=True)

        # Show the decision note if viewing as an administrator.
        if (session.get('is_admin', False)
                and auth.can_be_admin(db, auth_cache=can.cache)
                and proposal.decision_note):
            decision_note = null_tuple(ProposalText)._replace(
                text=proposal.decision_note,
                format=proposal.decision_note_format)
        else:
            decision_note = None

        return {
            'feedback_reviews': reviewers,
            'decision_note': decision_note,
        }

    def _edit_text(self, db, proposal, role, word_limit, target, form, rows,
                   figures=None, calculations=None, target_redir=None,
                   extra_initialization=None, extra_form_read=None,
                   extra_form_proc=None):
        role_class = self.get_text_roles()
        name = role_class.get_name(role)
        message = None

        if extra_initialization is None:
            ctx = {}
        else:
            ctx = extra_initialization(db, proposal, role)

        if form is not None:
            text = null_tuple(ProposalText)._replace(
                text=form['text'], format=int(form['format']))

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
                                     session['person']['id'])

                if extra_form_proc is not None:
                    ctx = extra_form_proc(db, proposal, role, ctx)

                flash('The {} has been saved.', name.lower())
                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id)
                                   if target_redir is None else target_redir)

            except UserError as e:
                message = e.message

        else:
            try:
                text = db.get_proposal_text(proposal.id, role)
            except NoSuchRecord:
                text = null_tuple(ProposalText)._replace(
                    text='', format=FormatType.PLAIN)

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

    def _prepare_calculations(self, raw_calculations, condense=True):
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
                                             'Mode {}'.format(calc.mode))))
            else:
                calculator = calc_info.calculator
                mode_info = calculator.get_mode_info(calc.mode)

                calculation = CalculationExtra(
                    *calc,
                    calculator_name=calc_info.name,
                    inputs=calculator.get_inputs(calc.mode, calc.version),
                    outputs=calculator.get_outputs(calc.mode, calc.version),
                    mode_info=mode_info)

                # Call the calculator method to compact the calculation
                # where possible.
                if condense:
                    calculator.condense_calculation(calc.mode, calc.version,
                                                    calculation)

                calculations.append(calculation)

        return calculations
