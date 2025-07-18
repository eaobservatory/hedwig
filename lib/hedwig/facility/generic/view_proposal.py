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

from collections import OrderedDict, namedtuple
from datetime import timedelta
from itertools import chain, count

from ...astro.coord import CoordSystem
from ...astro.catalog import parse_source_list, write_source_list
from ...compat import first_value
from ...email.format import render_email_template
from ...config import get_config
from ...error import ConsistencyError, MultipleRecords, \
    NoSuchRecord, NoSuchValue, ParseError, UserError
from ...file.info import determine_figure_type, determine_pdf_page_count
from ...file.pdf import pdf_to_svg
from ...pdf.request import get_proposal_filename
from ...publication.url import make_publication_url
from ...type.collection import CalculationCollection, \
    PrevProposalCollection, ResultCollection, \
    TargetCollection
from ...type.enum import AttachmentState, \
    CallState, FigureType, FormatType, \
    GroupType, MessageThreadType, \
    PermissionType, PersonLogEvent, PersonTitle, \
    ProposalState, ProposalType, PublicationType, \
    RequestState, ReviewState
from ...type.misc import SectionedList, SkipSection
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
    flash, get_logger, url_for
from ...view.util import count_words, int_or_none, \
    with_proposal, with_relevant_text_role

CalculationExtra = namedtuple(
    'CalculationExtra', Calculation._fields + (
        'calculator_name', 'inputs', 'outputs', 'mode_info'))

PrevProposalExtra = namedtuple(
    'PrevProposalExtra',
    PrevProposal._fields + ('links', 'can_view_proposal', 'can_view_review'))

PrevProposalPubExtra = namedtuple(
    'PrevProposalPubExtra',
    PrevProposalPub._fields + ('url',))


class GenericProposal(object):
    def view_proposal_new(self, current_user, db, call_id, form):
        type_class = self.get_call_types()
        role_class = self.get_reviewer_roles()
        auth_cache = {}

        try:
            call = db.search_call(
                facility_id=self.id_, call_id=call_id, state=CallState.OPEN
            ).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Call not found')
        except MultipleRecords:
            raise HTTPError('Multiple calls found')

        if not auth.for_call(
                current_user, db, call, auth_cache=auth_cache).view:
            raise HTTPForbidden('Permission denied for this call.')

        affiliations = db.search_affiliation(
            queue_id=call.queue_id, hidden=False,
            with_weight_call_id=call_id)
        if not affiliations:
            raise HTTPError('No affiliations appear to be available.')

        message = None

        proposal_title = ''
        affiliation_id = None
        copy_proposal_id = None
        continuation_proposal_id = None
        member_copy = False
        continuation_earliest = None
        if call.allow_continuation and (call.cnrq_max_age is not None):
            continuation_earliest = \
                call.date_open - timedelta(days=call.cnrq_max_age)

        if form is not None:
            try:
                affiliation_id = int_or_none(form['affiliation_id'])

                proposal_title = form['proposal_title'].strip()

                if 'proposal_copy' in form:
                    copy_proposal_id = int(form['proposal_copy'])

                if 'proposal_continuation' in form:
                    continuation_proposal_id = int(form['proposal_continuation'])

                member_copy = 'member_copy' in form

                if affiliation_id is None:
                    raise UserError('Please select an affiliation.')
                if affiliation_id not in affiliations:
                    raise ErrorPage('Invalid affiliation selected.')

                if 'submit_new' in form:
                    proposal_id = db.add_proposal(
                        call_id=call_id, person_id=current_user.person.id,
                        affiliation_id=affiliation_id,
                        title=proposal_title,
                        person_is_reviewer=type_class.has_reviewer_role(
                            call.type, role_class.PEER))

                    flash('Your new proposal has been created.')

                    raise HTTPRedirect(url_for(
                        '.proposal_view', proposal_id=proposal_id,
                        first_view='true'))

                elif 'submit_copy' in form or 'submit_continue' in form:
                    if 'submit_copy' in form:
                        is_continuation = False

                        if copy_proposal_id is None:
                            raise UserError('No proposal was selected to copy.')

                        try:
                            old_proposal = db.get_proposal(
                                self.id_, copy_proposal_id, with_members=True)
                        except NoSuchRecord:
                            raise ErrorPage('Proposal to copy not found.')

                        assert old_proposal.id == copy_proposal_id

                    elif 'submit_continue' in form:
                        is_continuation = True

                        if not call.allow_continuation:
                            raise ErrorPage(
                                'Continuation requests may not be submitted'
                                ' for this call.')

                        if continuation_proposal_id is None:
                            raise UserError('No proposal was selected to continue.')

                        try:
                            old_proposal = db.get_proposal(
                                self.id_, continuation_proposal_id, with_members=True)
                        except NoSuchRecord:
                            raise ErrorPage('Proposal to continue not found.')

                        assert old_proposal.id == continuation_proposal_id

                        if continuation_earliest is not None:
                            if old_proposal.semester_start < continuation_earliest:
                                raise ErrorPage('Proposal to continue is too old.')

                    else:
                        raise ErrorPage('Action unexpectedly didn\'t match.')

                    role_class = self.get_reviewer_roles()
                    can = auth.for_proposal(
                        role_class, current_user, db, old_proposal,
                        auth_cache=auth_cache)

                    if not can.view:
                        raise HTTPForbidden(
                            'Permission denied for the original proposal.')

                    if not old_proposal.members.has_person(
                            current_user.person.id):
                        raise HTTPForbidden(
                            'You can only copy or continue proposals '
                            'of which you are a member.')

                    if is_continuation:
                        if old_proposal.state != ProposalState.ACCEPTED:
                            raise ErrorPage('Proposal to continue not accepted.')

                    else:
                        if ProposalState.is_open(old_proposal.state):
                            raise ErrorPage('Proposal to copy is still open.')

                    requests = db.search_request_prop_copy(
                        proposal_id=old_proposal.id,
                        state=RequestState.pre_ready_states(),
                        continuation=is_continuation)

                    if requests:
                        request = first_value(requests)

                        flash(
                            'A {} of this proposal '
                            'has already been requested.'.format(
                                'continuation' if is_continuation else 'copy'))

                        raise HTTPRedirect(url_for(
                            '.proposal_copy_request_status',
                            proposal_id=old_proposal.id,
                            request_id=request.id))

                    request_id = db.add_request_prop_copy(
                        proposal_id=old_proposal.id,
                        requester_person_id=current_user.person.id,
                        call_id=call_id, affiliation_id=affiliation_id,
                        copy_members=(
                            False if is_continuation else member_copy),
                        continuation=is_continuation)

                    if is_continuation:
                        flash('Your continuation request is being prepared.')
                    else:
                        flash('Your proposal copy has been requested.')

                    raise HTTPRedirect(url_for(
                        '.proposal_copy_request_status',
                        proposal_id=old_proposal.id, request_id=request_id))

                else:
                    raise ErrorPage('Unknown action selected.')

            except UserError as e:
                message = e.message

        # Find proposals which can be copied or continued.  Allow all closed
        # proposals to be copied.  Of these, accepted proposals in the same
        # queue can be continued.  Continuation requests themselves can not
        # be copied or continued.
        proposals = db.search_proposal(
            facility_id=self.id_,
            person_id=current_user.person.id,
            state=ProposalState.closed_states(),
            type_=ProposalType.STANDARD
        ).map_values(
            lambda x: ProposalWithCode(
                *x, code=self.make_proposal_code(db, x)))

        if not call.allow_continuation:
            proposals_continuable = None
        else:
            proposals_continuable = proposals.map_values(
                filter_value=lambda x:
                    x.state == ProposalState.ACCEPTED
                    and x.queue_id == call.queue_id
                    and (
                        continuation_earliest is None
                        or not x.semester_start < continuation_earliest))

        return {
            'title': 'New Proposal',
            'call': call,
            'message': message,
            'proposal_title': proposal_title,
            'affiliations': affiliations,
            'affiliation_id': affiliation_id,
            'proposals': proposals,
            'proposal_copy': copy_proposal_id,
            'proposals_continuable': proposals_continuable,
            'proposal_continuation': continuation_proposal_id,
            'member_copy': member_copy,
        }

    @with_proposal(permission=PermissionType.VIEW)
    def view_proposal_copy_request_status(
            self, current_user, db, proposal, can, request_id):
        try:
            request = db.search_request_prop_copy(
                proposal_id=proposal.id, request_id=request_id).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Request not found.')

        if RequestState.is_ready(request.state):
            raise HTTPRedirect(url_for(
                '.proposal_view', proposal_id=request.copy_proposal_id,
                first_view='true'))

        proposal_code = self.make_proposal_code(db, proposal)

        return {
            'title': '{}: {}'.format(
                proposal_code,
                'Continuation Request' if request.continuation else 'Copy'),
            'proposal': proposal,
            'proposal_code': proposal_code,
            'request': request,
            'dynamic': self._get_proposal_copy_request_dynamic(request),
            'message': (
                'Please wait while your continuation request is prepared.'
                if request.continuation else
                'Please wait while your proposal is copied.'),
            'target_query': url_for(
                '.proposal_copy_request_query',
                proposal_id=proposal.id, request_id=request.id),
            'target_redirect': None,
        }

    @with_proposal(permission=PermissionType.VIEW)
    def view_proposal_copy_request_query(
            self, current_user, db, proposal, can, request_id):
        try:
            request = db.search_request_prop_copy(
                proposal_id=proposal.id, request_id=request_id).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Request not found.')

        return self._get_proposal_copy_request_dynamic(request)

    def _get_proposal_copy_request_dynamic(self, request):
        redirect_url = None
        is_ready = RequestState.is_ready(request.state)
        if is_ready:
            redirect_url = url_for(
                '.proposal_view', proposal_id=request.copy_proposal_id,
                first_view='true')

        return {
            'state_name': RequestState.get_name(request.state),
            'is_ready': is_ready,
            'is_pre_ready': RequestState.is_pre_ready(request.state),
            'redirect_url': redirect_url,
        }

    def _copy_proposal(
            self, current_user, db, old_proposal, proposal, copy_members,
            extra_text_roles=[]):
        role_class = self.get_text_roles()
        old_proposal_code = self.make_proposal_code(db, old_proposal)

        atn = self._copy_proposal_annotation(
            current_user, old_proposal, old_proposal_code)

        # Copy members (if requested) and student flag (including copier).
        with atn['notes'].accumulate_notes('proposal_members') as notes:
            self._copy_proposal_members(
                notes, current_user, db,
                old_proposal, old_proposal_code, proposal,
                copy_members=copy_members)

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
            self._copy_proposal_previous(
                notes, current_user, db,
                old_proposal, old_proposal_code, proposal)

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

        # Copy categories.
        with atn['notes'].accumulate_notes('proposal_abstract') as notes:
            records = db.search_proposal_category(
                proposal_id=old_proposal.id)

            categories = db.search_category(
                facility_id=self.id_, hidden=False)

            records_invalid = []

            for id_, record in records.items():
                if record.category_id not in categories:
                    records_invalid.append(id_)
                    notes.append({
                        'item': record.category_name,
                        'comment': 'category is no longer available.'})

            for id_ in records_invalid:
                del records[id_]

            if records:
                (n_insert, n_update, n_delete) = db.sync_proposal_category(
                    proposal.id, records=records.map_values(
                        lambda x: x._replace(id=None)))

                notes.append({
                    'item': '{} {}'.format(
                        n_insert,
                        'categories' if n_insert > 1 else 'category'),
                    'comment': 'copied to the proposal.'})

        return atn

    def _copy_proposal_annotation(
            self, current_user, old_proposal, old_proposal_code):
        return {
            'old_proposal_id': old_proposal.id,
            'old_proposal_code': old_proposal_code,
            'copier_person_id': current_user.person.id,
            'notes': SectionedList(
                note_format=lambda x: {'item': 'Error', 'comment': x}),
        }

    def _copy_proposal_members(
            self, notes, current_user, db,
            old_proposal, old_proposal_code, proposal,
            copy_members=False):
        copier_person_id = current_user.person.id

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
                queue_id=proposal.queue_id, hidden=False,
                with_weight_call_id=proposal.call_id)

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
                proposal.id, member_person_id, member.affiliation_id,
                editor=member.editor, observer=member.observer)

            self._message_proposal_invite(
                current_user, db, proposal=proposal,
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

    def _copy_proposal_previous(
            self, notes, current_user, db,
            old_proposal, old_proposal_code, proposal,
            is_continuation=False):
        override = {'id': None, 'sort_order': None}
        if is_continuation:
            override['continuation'] = False

        records = db.search_prev_proposal(
            proposal_id=old_proposal.id
        ).map_values(
            lambda x: x._replace(**override)
        )

        n_prev = len(records)

        if is_continuation or ProposalState.is_submitted(old_proposal.state):
            records['copied'] = null_tuple(PrevProposal)._replace(
                proposal_id=old_proposal.id,
                proposal_code=old_proposal_code,
                continuation=is_continuation,
                sort_order=1,
                publications=[])

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
                proposal_id=proposal.id, records=records,
                retain_resolved=True)

            if n_prev:
                notes.append({
                    'item': '{} previous {}'.format(
                        n_prev, 'proposals' if n_prev > 1 else 'proposal'),
                    'comment': 'copied to the proposal.'})

    def _continue_proposal(
            self, current_user, db, old_proposal, proposal):
        old_proposal_code = self.make_proposal_code(db, old_proposal)

        atn = self._copy_proposal_annotation(
            current_user, old_proposal, old_proposal_code)

        # Copy members and student flag (including copier).
        with atn['notes'].accumulate_notes('proposal_members') as notes:
            self._copy_proposal_members(
                notes, current_user, db,
                old_proposal, old_proposal_code, proposal,
                copy_members=True)

        # Copy previous proposals.
        with atn['notes'].accumulate_notes('proposal_previous') as notes:
            self._copy_proposal_previous(
                notes, current_user, db,
                old_proposal, old_proposal_code, proposal,
                is_continuation=True)

        return atn

    @with_proposal(permission=PermissionType.VIEW)
    def view_proposal_view(self, current_user, db, proposal, can, args):
        role_class = self.get_reviewer_roles()
        review_can = auth.for_review(
            role_class, current_user, db, reviewer=None, proposal=proposal,
            auth_cache=can.cache)
        feedback_can = auth.for_proposal_feedback(
            role_class, current_user, db, proposal=proposal,
            auth_cache=can.cache)

        type_class = self.get_call_types()
        call_mid_closes = None
        if type_class.get_info(proposal.call_type).mid_close:
            call_mid_closes = db.search_call_mid_close(
                call_id=proposal.call_id, closed=False)

        is_admin = current_user.is_admin
        is_first_view = ('first_view' in args)

        ctx = {
            'title': proposal.title,
            'can_edit': can.edit,
            'can_remove_self': (ProposalState.can_edit(proposal.state) and
                                any(x.person_id == current_user.person.id
                                    for x in proposal.members.values())),
            'can_view_review': review_can.view,
            'can_edit_review': review_can.edit,
            'can_view_feedback': feedback_can.view,
            'can_request_pdf': get_config().getboolean('pdf_request', 'enable_request'),
            'is_submitted': ProposalState.is_submitted(proposal.state),
            'proposal': proposal._replace(members=proposal.members.map_values(
                lambda x: with_can_view(
                    x, auth.for_person_member(
                        current_user, db, x, auth_cache=can.cache).view))),
            'students': proposal.members.get_students(),
            'proposal_code': self.make_proposal_code(db, proposal),
            'show_person_proposals_callout': is_first_view,
            'show_admin_links': is_admin,
            'proposal_order': self.get_proposal_order_names(
                type_=proposal.type),
            'call_mid_closes': call_mid_closes,
        }

        ctx.update(self._view_proposal_extra(
            current_user, db, proposal, auth_cache=can.cache))

        if is_first_view:
            ctx['proposal_annotations'] = db.search_proposal_annotation(
                proposal_id=proposal.id)

        return ctx

    def _view_proposal_extra(
            self, current_user, db, proposal, extra_text_roles={},
            auth_cache=None):
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

        prev_proposals = db.search_prev_proposal(
            proposal_id=proposal.id, with_proposal_info=True)

        extra = {
            'abstract': proposal_text.get_role(role_class.ABSTRACT, None),
            'targets': targets,
            'target_total_time': target_total_time,
            'calculators': self.calculators,
            'calculations': self._prepare_calculations(calculations),
            'target_tools': self.target_tools,
            'tool_note': proposal_text.get_role(role_class.TOOL_NOTE, None),
            'categories': db.search_proposal_category(
                proposal_id=proposal.id),
            'prev_proposals': prev_proposals.map_values(
                lambda x: PrevProposalExtra(
                    *x._replace(publications=[
                        PrevProposalPubExtra(
                            *p,
                            url=make_publication_url(p.type, p.description))
                        for p in x.publications]),
                    links=self.make_proposal_info_urls(x.proposal_code),
                    # For the purpose of estimating authorization to view the
                    # previous proposals and their reviews, assume that the
                    # membership is the same as this proposal.
                    can_view_proposal=(
                        False if x.proposal_id is None
                        else auth.for_proposal_prev_proposal(
                            current_user, db, x, members=proposal.members,
                            auth_cache=auth_cache).view),
                    can_view_review=(
                        False if x.proposal_id is None
                        else auth.for_review_prev_proposal(
                            current_user, db, x, members=proposal.members,
                            auth_cache=auth_cache).view))),
            'text_roles': role_class,
            'systems': CoordSystem.get_options(),
        }

        for role in (
                role_class.TECHNICAL_CASE,
                role_class.SCIENCE_CASE,
                role_class.CONTINUATION_REQUEST):
            extra['{}_case'.format(role_class.get_code(role))] = {
                'role': role,
                'text': proposal_text.get_role(role, None),
                'pdf': proposal_pdf.get_role(role, None),
                'fig': proposal_fig.values_by_role(role),
            }

        for (role_attr, role) in extra_text_roles.items():
            extra[role_attr] = proposal_text.get_role(role, None)

        return extra

    def view_proposal_sections(self, current_user, db, *args, **kwargs):
        """
        Method to view a proposal as a series of sections.

        This calls the view_proposal_view method and then splits up the
        proposal into separate sections, each of which is either a
        template context (with restricted proposal_order selection) or
        a PDF file.  Then a complete proposal can be generated by
        applying the templates and concatenating the resulting sections.
        """

        role_class = self.get_text_roles()

        pdf_sections = {
            'science_case': role_class.SCIENCE_CASE,
            'technical_case': role_class.TECHNICAL_CASE,
            'continuation_request': role_class.CONTINUATION_REQUEST,
        }

        ctx = self.view_proposal_view(current_user, db, *args, **kwargs)

        result = []

        def push_section(section, section_name, extra={}):
            """Add the given section to the results list."""

            if result and isinstance(result[-1], dict):
                # We already have a template section at the end of the list.
                section_ctx = result[-1]

                section_ctx['proposal_order'][section] = section_name
                section_ctx.update(extra)

            else:
                # We don't already have a template section: add one now.
                section_ctx = ctx.copy()

                section_ctx['proposal_order'] = OrderedDict(((section, section_name),))
                section_ctx.update(extra)

                # Omit the title in sections after the first.
                if result:
                    del section_ctx['title']

                result.append(section_ctx)

        for (section, section_name) in ctx['proposal_order'].items():
            role = pdf_sections.get(section)

            if role is not None:
                # This is a section which could include a PDF file.
                case = ctx['{}_case'.format(role_class.get_code(role))]

                # Replicate template logic: prefer text to PDF version
                # in the case that both are present (shouldn't happen).
                # Also require the PDF to be ready - if not let the
                # template show a warning.
                pdf = case['pdf']
                if ((case['text'] is None) and (pdf is not None) and
                        AttachmentState.is_ready(pdf.state)):
                    push_section(section, section_name, {
                        '{}_order'.format(section):
                            ['{}_intro'.format(section)],
                    })

                    result.append((
                        FigureType.get_mime_type(FigureType.PDF),
                        db.get_proposal_pdf(
                            proposal_id=None, role=None, pdf_id=pdf.pdf_id).data))

                    push_section(section, section_name, {
                        '{}_order'.format(section):
                            ['{}_extra'.format(section)],
                    })

                    continue

            # Did not continue: this is a plain template section.
            push_section(section, section_name)

        return result

    @with_proposal(permission=PermissionType.NONE)
    def view_proposal_alter_state(self, current_user, db, proposal, form):
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

    def _validate_proposal(
            self, current_user, db, proposal, proposal_order, auth_cache):
        # Validate the "extra" parts of the proposal.
        extra = self._view_proposal_extra(
            current_user, db, proposal, auth_cache=auth_cache)

        report = self._validate_proposal_extra(
            db, proposal, extra, proposal_order)

        # Validate common parts of the proposal.
        with report.accumulate_notes('proposal_summary') as messages:
            # Check the title.
            if not proposal.title:
                messages.append(ValidationMessage(
                    True,
                    'The proposal does not have a title.',
                    'Edit the proposal title',
                    url_for('.title_edit', proposal_id=proposal.id)))

        # Return the list of messages.
        return report

    def _validate_proposal_extra(self, db, proposal, extra, proposal_order,
                                 skip_missing_targets=False,
                                 check_excluded_pi=False):
        affiliation_type_class = self.get_affiliation_types()
        type_class = self.get_call_types()
        reviewer_role_class = self.get_reviewer_roles()
        role_class = self.get_text_roles()

        report = SectionedList(
            note_format=lambda x: ValidationMessage(True, x, None, None))

        with report.accumulate_notes('proposal_members') as messages:
            try:
                proposal.members.validate(editor_person_id=None)
            except UserError as e:
                messages.append(ValidationMessage(
                    True, e.message,
                    'Edit the proposal members',
                    url_for('.member_edit', proposal_id=proposal.id)))

            if type_class.has_reviewer_role(
                    proposal.call_type, reviewer_role_class.PEER):
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

            if check_excluded_pi:
                member_pi = proposal.members.get_pi(default=None)

                # Ignore if there's no PI: the previous members.validate test
                # should have generated an error for that.
                if member_pi is not None:
                    exclude = db.search_affiliation(
                        queue_id=proposal.queue_id,
                        type_=affiliation_type_class.EXCLUDED,
                        with_weight_call_id=proposal.call_id)

                    if member_pi.affiliation_id in exclude:
                        exclude_names = [
                            x.name for x in exclude.values()
                            if ((not x.hidden) or
                                (x.id == member_pi.affiliation_id))]

                        messages.append(ValidationMessage(
                            True,
                            'The principal investigator (PI) has an '
                            'ineligible affiliation.  The PI should '
                            'not be someone with ' +
                            ('one of the following affiliations: '
                             if len(exclude_names) > 1 else
                             'the following affiliation: ') +
                            ', '.join(exclude_names) +
                            '.',
                            'Select a different proposal member as the PI',
                            url_for('.member_edit', proposal_id=proposal.id)))

        with report.accumulate_notes('proposal_abstract') as messages:
            if 'proposal_abstract' not in proposal_order:
                raise SkipSection()

            if extra['abstract'] is None:
                messages.append(ValidationMessage(
                    True,
                    'The proposal does not have an abstract.',
                    'Edit the proposal abstract',
                    url_for('.abstract_edit', proposal_id=proposal.id)))

        with report.accumulate_notes('proposal_previous') as messages:
            message_template = ValidationMessage(
                True, None,
                'Edit previous proposals and publications',
                url_for('.previous_edit', proposal_id=proposal.id))

            if proposal.type == ProposalType.CONTINUATION:
                try:
                    previous = extra['prev_proposals'].get_continuation()

                except MultipleRecords:
                    messages.append(message_template._replace(
                        description='This proposal is a continuation request, '
                        'but the continuation box is checked for '
                        'multiple entries in the previous proposals list.'))

                except NoSuchValue:
                    messages.append(message_template._replace(
                        description='This proposal is a continuation request, '
                        'so the previous proposal list must indicate '
                        'which project you wish to continue. '
                        'Please ensure the continuation box is checked for '
                        'one entry in the previous proposals list.'))

                else:
                    if previous.proposal_id is None:
                        messages.append(message_template._replace(
                            description='This proposal is a continuation '
                            'request, but the proposal for which the '
                            'continuation box is checked is not recognized.'))

                    else:
                        try:
                            prev_prop = db.get_proposal(
                                self.id_, previous.proposal_id)
                        except NoSuchRecord as e:
                            messages.append(message_template._replace(
                                description='The proposal to continue could '
                                'not be found.'))

                        if prev_prop.type != ProposalType.STANDARD:
                            messages.append(message_template._replace(
                                description='The proposal selected for '
                                'continuation is not a standard proposal.  '
                                'Please give the original proposal identifier '
                                'rather than a subsequent '
                                'continuation request.'))

            elif not extra['prev_proposals']:
                messages.append(message_template._replace(
                    is_error=False,
                    description='No previous proposals have been listed.  '
                    'If you do not '
                    'have any previously accepted proposals you should '
                    'ignore this warning.'))

        with report.accumulate_notes('proposal_targets') as messages:
            if 'proposal_targets' not in proposal_order:
                raise SkipSection()

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

            for target in extra['targets'].values():
                if (target.x == 0.0) and (target.y == 0.0):
                    messages.append(ValidationMessage(
                        False,
                        'Target {} has coordinates (0, 0). '
                        'This can cause your proposal to be processed '
                        'incorrectly unless you really intend to observe '
                        'at (0, 0). '
                        'If the target does not have suitable fixed '
                        'coordinates, please leave its position blank '
                        'instead.'.format(target.name),
                        'Edit target list',
                        url_for('.target_edit', proposal_id=proposal.id)))

        with report.accumulate_notes('proposal_calculations') as messages:
            if extra['calculators'] and (not extra['calculations']):
                messages.append(ValidationMessage(
                    False,
                    'The proposal does not have any calculation results '
                    'attached.',
                    'See available calculators',
                    url_for('.facility_home', _anchor='calc')))

        for (role, role_section) in (
                (role_class.TECHNICAL_CASE, 'technical_case'),
                (role_class.SCIENCE_CASE, 'science_case'),
                (role_class.CONTINUATION_REQUEST, 'continuation_request')):
            with report.accumulate_notes(role_section) as messages:
                if role_section not in proposal_order:
                    raise SkipSection()

                role_name = role_class.get_name(role)
                case = extra['{}_case'.format(role_class.get_code(role))]

                if case['text'] is not None:
                    for fig in case['fig']:
                        if fig.state == AttachmentState.ERROR:
                            messages.append(ValidationMessage(
                                False,
                                'A figure in the {} could not be processed. '
                                'Please check the file is valid and contact '
                                'us for help in the event that this error '
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

        return report

    @with_proposal(permission=PermissionType.EDIT)
    def view_proposal_submit(self, current_user, db, proposal, can, form):
        if ProposalState.is_submitted(proposal.state):
            raise ErrorPage('The proposal has already been submitted.')

        type_class = self.get_call_types()
        immediate_review = type_class.has_immediate_review(proposal.call_type)

        proposal_order = self.get_proposal_order_names(type_=proposal.type)
        messages = self._validate_proposal(
            current_user, db, proposal, proposal_order, auth_cache=can.cache)
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

                self._message_proposal_submit(current_user, db, proposal)

                self._message_proposal_review_notification(db, proposal)

                if immediate_review:
                    # Freeze member institution ID values.
                    db.sync_proposal_member_institution(proposal.id, {
                        x.id: MemberInstitution(
                            x.id, x.resolved_institution_id)
                        for x in proposal.members.values()})

                db.add_person_log_entry(
                    current_user.person.id, PersonLogEvent.PROPOSAL_SUBMIT,
                    proposal_id=proposal.id)

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
            'proposal_order': proposal_order,
        }

    def _message_proposal_submit(self, current_user, db, proposal):
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
                    'submitter_name': current_user.person.name,
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
    def view_proposal_validate(self, current_user, db, proposal, can):
        proposal_order = self.get_proposal_order_names(type_=proposal.type)
        messages = self._validate_proposal(
            current_user, db, proposal, proposal_order, auth_cache=can.cache)

        return {
            'title': 'Proposal Validation',
            'proposal': proposal,
            'proposal_code': self.make_proposal_code(db, proposal),
            'validation_messages': messages,
            'can_edit': can.edit,
            'is_submit_page': False,
            'proposal_order': proposal_order,
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_proposal_withdraw(self, current_user, db, proposal, can, form):
        if not ProposalState.is_submitted(proposal.state):
            raise ErrorPage('The proposal has not been submitted.')

        if form is not None:
            if 'submit_confirm' in form:
                db.update_proposal(proposal.id, state=ProposalState.WITHDRAWN)

                self._message_proposal_withdraw(current_user, db, proposal)

                db.add_person_log_entry(
                    current_user.person.id, PersonLogEvent.PROPOSAL_WITHDRAW,
                    proposal_id=proposal.id)

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

    def _message_proposal_withdraw(self, current_user, db, proposal):
        proposal_code = self.make_proposal_code(db, proposal)

        db.add_message(
            'Proposal {} withdrawn'.format(proposal_code),
            render_email_template(
                'proposal_withdrawn.txt', {
                    'proposal': proposal,
                    'proposal_code': proposal_code,
                    'withdrawer_name': current_user.person.name,
                },
                facility=self),
            [x.person_id for x in proposal.members.values()],
            thread_type=MessageThreadType.PROPOSAL_STATUS,
            thread_id=proposal.id)

    @with_proposal(permission=PermissionType.EDIT)
    def view_title_edit(self, current_user, db, proposal, can, form):
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
    def view_abstract_edit(self, current_user, db, proposal, can, form):
        role_class = self.get_text_roles()
        return self._edit_text(
            current_user, db,
            proposal, role_class.ABSTRACT, proposal.abst_word_lim,
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
    def view_member_edit(self, current_user, db, proposal, can, form):
        type_class = self.get_call_types()
        role_class = self.get_reviewer_roles()
        has_peer_review = type_class.has_reviewer_role(
            proposal.call_type, role_class.PEER)

        message = None
        records = proposal.members
        person_id = current_user.person.id

        affiliations = db.search_affiliation(
            queue_id=proposal.queue_id, hidden=False,
            with_weight_call_id=proposal.call_id)
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
            'queue_id': proposal.queue_id,
            'call_type': proposal.call_type,
            'call_separate': proposal.call_separate,
            'members': records.map_values(
                lambda x: with_can_edit(x, x.person_id != person_id)),
            'affiliations': affiliations,
            'proposal_code': self.make_proposal_code(db, proposal),
            'has_peer_review': has_peer_review,
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_member_add(self, current_user, db, proposal, can, form):
        message_link = message_invite = None
        member = dict(editor=None, observer=None, person_id=None,
                      name='', title=None, email='')

        affiliations = db.search_affiliation(
            queue_id=proposal.queue_id, hidden=False,
            with_weight_call_id=proposal.call_id)
        if not affiliations:
            raise HTTPError('No affiliations appear to be available.')

        member_info = self._read_member_form(form)

        with member_info.catch_() as member:
            if form is not None:
                member['editor'] = 'editor' in form
                member['observer'] = 'observer' in form
                member['affiliation_id'] = int_or_none(form['affiliation_id'])
                if member['affiliation_id'] is None:
                    raise UserError('Please select an affiliation.')

                affiliation = affiliations.get(member['affiliation_id'])
                if affiliation is None:
                    raise ErrorPage('Selected affiliation not found.')

        with member_info.release() as member:
            if member['is_link'] is None:
                member_info.raise_()

            elif member['is_link']:
                try:
                    member_info.raise_()

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
                                  observer=member['observer'],
                                  adder_person_id=current_user.person.id)

                    self._message_proposal_invite(
                        current_user, db, proposal=proposal,
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

            else:
                try:
                    member_info.raise_()

                    person_id = db.add_person(
                        member['name'], title=member['title'],
                        primary_email=member['email'])
                    db.add_member(proposal.id, person_id,
                                  member['affiliation_id'],
                                  editor=member['editor'],
                                  observer=member['observer'],
                                  adder_person_id=current_user.person.id,
                                  is_invite=True)

                    self._message_proposal_invite(
                        current_user, db, proposal=proposal,
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

        # Prepare list of current members to exclude from the directory.
        current_persons = [m.person_id for m in proposal.members.values()]

        return {
            'title': 'Add Member',
            'message_link': message_link,
            'message_invite': message_invite,
            'proposal_id': proposal.id,
            'semester_id': proposal.semester_id,
            'queue_id': proposal.queue_id,
            'call_type': proposal.call_type,
            'call_separate': proposal.call_separate,
            'person_list_url': url_for('query.person_list'),
            'persons_exclude': current_persons,
            'affiliations': affiliations,
            'member': member_info.data,
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
            self, current_user, db, proposal, person_id, person_name,
            is_editor, affiliation_name, send_token,
            copy_proposal_code=None):
        type_class = self.get_call_types()
        proposal_code = self.make_proposal_code(db, proposal)

        email_ctx = {
            'recipient_name': person_name,
            'proposal': proposal,
            'proposal_code': proposal_code,
            'call_type': type_class.get_name(proposal.call_type),
            'inviter_name': current_user.person.name,
            'affiliation': affiliation_name,
            'is_editor': is_editor,
            'target_semester': (
                url_for(
                    '.semester_call_separate',
                    semester_id=proposal.semester_id,
                    call_type=proposal.call_type, queue_id=proposal.queue_id,
                    _external=True)
                if proposal.call_separate else
                url_for(
                    '.semester_calls',
                    semester_id=proposal.semester_id,
                    call_type=proposal.call_type, _external=True)),
            'copy_proposal_code': copy_proposal_code,
            'is_continuation': (proposal.type == ProposalType.CONTINUATION),
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
    def view_member_reinvite(
            self, current_user, db, proposal, can, member_id, form):
        member = proposal.members.get(member_id)
        if member is None:
            raise HTTPNotFound('Proposal member not found.')

        if member.person_registered:
            raise ErrorPage('This proposal member has already registered.')

        proposal_code = self.make_proposal_code(db, proposal)

        if form:
            if 'submit_confirm' in form:
                self._message_proposal_invite(
                    current_user, db, proposal=proposal,
                    person_id=member.person_id,
                    person_name=member.person_name,
                    is_editor=member.editor,
                    affiliation_name=member.affiliation_name,
                    send_token=True)

                db.add_person_log_entry(
                    current_user.person.id, PersonLogEvent.MEMBER_REINVITE,
                    proposal_id=proposal.id, other_person_id=member.person_id)

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
    def view_member_remove_self(self, current_user, db, proposal, can, form):
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
                        person_id=current_user.person.id)
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
    def view_student_edit(self, current_user, db, proposal, can, form):
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

    @with_proposal(permission=PermissionType.NONE)
    def view_member_affiliation_edit(
            self, current_user, db, proposal, member_id, form):
        message = None
        records = proposal.members

        if member_id not in records:
            raise HTTPNotFound('Proposal member not found.')

        affiliations = db.search_affiliation(
            queue_id=proposal.queue_id, hidden=False,
            with_weight_call_id=proposal.call_id)
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

    @with_proposal(permission=PermissionType.NONE)
    def view_member_institution_edit(
            self, current_user, db, proposal, member_id, form):
        message = None
        records = proposal.members

        if member_id not in records:
            raise HTTPNotFound('Proposal member not found.')

        if form is not None:
            try:
                records[member_id] = records[member_id]._replace(
                    resolved_institution_id=int_or_none(form['institution_id']))

                if records[member_id].resolved_institution_id is None:
                    raise UserError('No institution was selected.')

                # Note: we can not use sync_proposal_member_institution
                # here since that would freeze all other member institutions.
                db.set_member_institution(
                    member_id, records[member_id].resolved_institution_id)

                flash('The institution has been updated.')

                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id,
                                           _anchor='members'))

            except UserError as e:
                message = e.message

        member = records[member_id]

        return {
            'title': 'Edit institution: {}'.format(member.person_name),
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'message': message,
            'member': member,
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_previous_edit(self, current_user, db, proposal, can, form):
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
                    sort_order=int_or_none(form['sort_order_' + id_]),
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
            facility_id=self.id_, person_id=current_user.person.id,
            state=ProposalState.ACCEPTED)

        accepted_proposal_codes = [
            self.make_proposal_code(db, x)
            for x in accepted_proposals.values()]

        return {
            'title': 'Previous Proposals and Publications',
            'proposal': proposal,
            'message': message,
            'proposal_code': self.make_proposal_code(db, proposal),
            'accepted_proposals': accepted_proposal_codes,
            'prev_proposals': records,
            'publication_types': PublicationType.get_options(),
            'note': call.prev_prop_note,
            'note_format': call.note_format,
        }

    @with_proposal(permission=PermissionType.EDIT)
    def view_target_edit(self, current_user, db, proposal, can, form):
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
                    form['priority_' + id_],
                    form['note_' + id_])

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
    def view_target_upload(self, current_user, db, proposal, can, form, file_):
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
    def view_target_download(self, current_user, db, proposal, can):
        targets = db.search_target(proposal_id=proposal.id)

        return (
            write_source_list(targets),
            'text/plain',
            '{}-targets.txt'.format(self.make_proposal_code(db, proposal)))

    @with_proposal(permission=PermissionType.EDIT)
    def view_tool_note_edit(self, current_user, db, proposal, can, form):
        role_class = self.get_text_roles()
        return self._edit_text(
            current_user, db,
            proposal, role_class.TOOL_NOTE, proposal.expl_word_lim,
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
    def view_request_edit(self, current_user, db, proposal, can, form):
        raise ErrorPage('Observing request not implemented for this facility.')

    @with_proposal(permission=PermissionType.EDIT)
    @with_relevant_text_role
    def view_case_edit(
            self, current_user, db, proposal, can, role_class, role):
        code = role_class.get_code(role)
        call = db.get_call(facility_id=None, call_id=proposal.call_id)

        text_info = db.search_proposal_text(
            proposal_id=proposal.id, role=role).get_single(None)

        pdf_info = db.search_proposal_pdf(
            proposal_id=proposal.id, role=role,
            with_uploader_name=True).get_single(None)

        figures = db.search_proposal_figure(
            proposal_id=proposal.id, role=role,
            with_caption=True, with_uploader_name=True)

        is_admin = current_user.is_admin

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
    @with_relevant_text_role
    def view_case_edit_text(
            self, current_user, db, proposal, can, role_class, role, form):
        code = role_class.get_code(role)

        figures = db.search_proposal_figure(
            proposal_id=proposal.id, role=role)

        if role in (
                role_class.TECHNICAL_CASE,
                role_class.CONTINUATION_REQUEST):
            calculations = self._prepare_calculations(
                db.search_calculation(proposal_id=proposal.id))
        else:
            calculations = None

        return self._edit_text(
            current_user, db, proposal, role,
            getattr(proposal, code + '_word_lim'),
            url_for('.case_edit_text', proposal_id=proposal.id, role=role),
            form, 30, figures, calculations,
            url_for('.case_edit', proposal_id=proposal.id, role=role))

    @with_proposal(permission=PermissionType.EDIT)
    @with_relevant_text_role
    def view_case_edit_figure(
            self, current_user, db, proposal, can, role_class, role,
            fig_id, form, file_):
        code = role_class.get_code(role)
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
                    link_id=fig_id, with_caption=True).get_single()
            except NoSuchRecord:
                raise HTTPNotFound('Figure not found.')

            target = url_for('.case_edit_figure',
                             proposal_id=proposal.id, role=role,
                             fig_id=fig_id)

        return self._view_edit_figure(
            current_user, db, form, file_, figure, proposal, None,
            title=name.title(),
            target_edit=target,
            target_redirect=url_for(
                '.case_edit', proposal_id=proposal.id, role=role),
            word_limit=proposal.capt_word_lim)

    def _view_edit_figure(
            self, current_user, db, form, file_, figure, proposal, reviewer,
            title, target_edit, target_redirect, word_limit=None):
        config = get_config()
        max_size = int(config.get('upload', 'max_fig_size'))
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
                        (page_count, major_max, minor_max) = determine_pdf_page_count(
                            buff, with_max_size=True)

                        if page_count != 1:
                            raise UserError(
                                'The uploaded PDF has multiple pages.')

                        if (major_max > float(config.get('proposal_fig', 'pdf_max_major'))
                                or minor_max > float(config.get('proposal_fig', 'pdf_max_minor'))):
                            raise UserError(
                                'PDF page size is too large: {:.1f} \u00d7 {:.1f}\u2033.',
                                major_max, minor_max)

                    figure_args = {
                        'figure': buff,
                        'type_': type_,
                        'filename': filename,
                        'uploader_person_id': current_user.person.id,
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
    @with_relevant_text_role
    def view_case_manage_figure(
            self, current_user, db, proposal, can, role_class, role, form):
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
    def view_case_view_figure(
            self, current_user, db, proposal, can, fig_id, role, md5sum,
            type_=None):
        if (type_ is None) or (type_ == 'svg'):
            try:
                figure = db.get_proposal_figure(
                    proposal.id, role, fig_id, md5sum=md5sum)
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
    @with_relevant_text_role
    def view_case_edit_pdf(
            self, current_user, db, proposal, can, role_class, role, file):
        code = role_class.get_code(role)
        name = role_class.get_name(role)
        config = get_config()
        page_limit = getattr(proposal, code + '_page_lim')
        max_size = int(config.get('upload', 'max_pdf_size'))
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

                (page_count, major_max, minor_max) = determine_pdf_page_count(
                    buff, with_max_size=True)

                if page_count > page_limit:
                    raise UserError(
                        'PDF is too long: {} {}.',
                        page_count,
                        ('page' if page_count == 1 else 'pages'))

                if (major_max > float(config.get('proposal_pdf', 'max_size_major'))
                        or minor_max > float(config.get('proposal_pdf', 'max_size_minor'))):
                    raise UserError(
                        'PDF page size is too large: {:.1f} \u00d7 {:.1f}\u2033.',
                        major_max, minor_max)

                db.set_proposal_pdf(
                    role_class, proposal.id, role, buff, page_count,
                    filename, current_user.person.id)

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
            'max_page_size': config.get('proposal_pdf', 'max_size_description'),
            'page_limit': page_limit,
            'target': url_for('.case_edit_pdf',
                              proposal_id=proposal.id, role=role),
        }

    @with_proposal(permission=PermissionType.VIEW)
    def view_case_view_pdf(
            self, current_user, db, proposal, can, role, md5sum):
        role_class = self.get_text_roles()
        try:
            return db.get_proposal_pdf(proposal.id, role, md5sum=md5sum)
        except NoSuchRecord:
            raise HTTPNotFound('{} PDF not found.'.format(
                role_class.get_name(role).capitalize()))

    @with_proposal(permission=PermissionType.VIEW)
    def view_case_view_pdf_preview(
            self, current_user, db, proposal, can, page, role, md5sum):
        try:
            return db.get_proposal_pdf_preview(proposal.id, role, page,
                                               md5sum=md5sum)
        except NoSuchRecord:
            raise HTTPNotFound('PDF preview page not found.')

    @with_proposal(permission=PermissionType.VIEW)
    def view_calculation_manage(self, current_user, db, proposal, can, form):
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
    def view_calculation_view(
            self, current_user, db, proposal, can, calculation_id):
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

        return view_func(
            calculation=calculation, can=can, parent_proposal=proposal)

    @with_proposal(permission=PermissionType.VIEW)
    def view_proposal_pdf_request(
            self, current_user, db, proposal, can, form):
        if not get_config().getboolean('pdf_request', 'enable_request'):
            raise ErrorPage('PDF download is not currently available.')

        requests = db.search_request_prop_pdf(
            proposal_id=proposal.id, state=RequestState.visible_states())

        # Are there already requests pending?  If so, we can redirect there
        # automatically because the PDF will be up to date once processed.
        requests_pre_ready = requests.subset_by_state(
            RequestState.pre_ready_states())
        if requests_pre_ready:
            request = first_value(requests_pre_ready)

            flash(
                'A PDF file download of this proposal '
                'has already been requested.')

            raise HTTPRedirect(url_for(
                '.proposal_pdf_request_status', proposal_id=proposal.id,
                request_id=request.id))

        if form is not None:
            if 'submit_confirm' in form:
                request_id = db.add_request_prop_pdf(
                    proposal_id=proposal.id,
                    requester_person_id=current_user.person.id)

                flash('Your PDF file download has been requested.')

                raise HTTPRedirect(url_for(
                    '.proposal_pdf_request_status', proposal_id=proposal.id,
                    request_id=request_id))

            else:
                raise HTTPRedirect(url_for(
                    '.proposal_view', proposal_id=proposal.id))

        proposal_code = self.make_proposal_code(db, proposal)

        return {
            'title': '{}: Download PDF File'.format(proposal_code),
            'proposal': proposal,
            'proposal_code': proposal_code,
            'requests': requests,
        }

    @with_proposal(permission=PermissionType.VIEW)
    def view_proposal_pdf_request_status(
            self, current_user, db, proposal, can, request_id):
        try:
            request = db.search_request_prop_pdf(
                proposal_id=proposal.id, request_id=request_id).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Request not found.')

        if RequestState.is_ready(request.state):
            raise HTTPRedirect(url_for(
                '.proposal_pdf_download', proposal_id=proposal.id,
                request_id=request_id))

        proposal_code = self.make_proposal_code(db, proposal)

        return {
            'title': '{}: Download PDF File'.format(proposal_code),
            'proposal': proposal,
            'proposal_code': proposal_code,
            'request': request,
            'dynamic': self._get_proposal_pdf_request_dynamic(request),
            'message': 'Please wait while your PDF file download is prepared.',
            'target_query': url_for(
                '.proposal_pdf_request_query',
                proposal_id=proposal.id, request_id=request.id),
            'target_redirect': url_for(
                '.proposal_pdf_download',
                proposal_id=proposal.id, request_id=request.id),
        }

    @with_proposal(permission=PermissionType.VIEW)
    def view_proposal_pdf_request_query(
            self, current_user, db, proposal, can, request_id):
        try:
            request = db.search_request_prop_pdf(
                proposal_id=proposal.id, request_id=request_id).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Request not found.')

        return self._get_proposal_pdf_request_dynamic(request)

    def _get_proposal_pdf_request_dynamic(self, request):
        return {
            'state_name': RequestState.get_name(request.state),
            'is_ready': RequestState.is_ready(request.state),
            'is_pre_ready': RequestState.is_pre_ready(request.state),
        }

    @with_proposal(permission=PermissionType.VIEW)
    def view_proposal_pdf_download(
            self, current_user, db, proposal, can, request_id):
        try:
            request = db.search_request_prop_pdf(
                proposal_id=proposal.id, request_id=request_id).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Request not found.')

        if RequestState.is_expired(request.state):
            raise HTTPError('Request has expired.')

        if not RequestState.is_ready(request.state):
            raise HTTPError('Request not ready.')

        with open(get_proposal_filename(request), 'rb') as f:
            pdf = f.read(50 * 1024 * 1024)

            # Did we get all of the file within the size limit?
            if len(f.read(1)):
                raise UserError('The generated PDF is too large.')

        return (
            pdf,
            FigureType.PDF,
            '{}.pdf'.format(self.make_proposal_code(db, proposal)))

    @with_proposal(permission=PermissionType.FEEDBACK, with_decision_note=True)
    def view_proposal_feedback(self, current_user, db, proposal, can):
        proposal_code = self.make_proposal_code(db, proposal)

        ctx = {
            'title': '{}: Feedback'.format(proposal_code),
            'proposal_id': proposal.id,
            'proposal_code': proposal_code,
        }

        ctx.update(self._view_proposal_feedback_extra(
            current_user, db, proposal, can))

        return ctx

    def _view_proposal_feedback_extra(self, current_user, db, proposal, can):
        """
        Method to gather additional information for the proposal feedback page.
        """

        role_class = self.get_reviewer_roles()

        reviewers = db.search_reviewer(
            proposal_id=proposal.id, role=role_class.FEEDBACK,
            review_state=ReviewState.DONE,
            with_review=True, with_review_text=True)

        # Show the decision note if viewing as an administrator.
        if current_user.is_admin and proposal.decision_note:
            decision_note = null_tuple(ProposalText)._replace(
                text=proposal.decision_note,
                format=proposal.decision_note_format)
        else:
            decision_note = None

        return {
            'feedback_reviews': reviewers,
            'decision_note': decision_note,
        }

    def view_proposal_by_code(self, current_user, db, args):
        message = None
        code = args.get('code', '')

        if code:
            try:
                proposal_id = self.parse_proposal_code(db, code)

                raise HTTPRedirect(url_for(
                    '.proposal_view', proposal_id=proposal_id))

            except ParseError:
                message = (
                    'The given proposal identifier '
                    'is not of the expected format.')

            except NoSuchRecord:
                message = 'The specified proposal was not found.'

        return {
            'title': 'Find Proposal by Identifier',
            'message': message,
            'code': code,
        }

    def _edit_text(
            self, current_user, db,
            proposal, role, word_limit, target, form, rows,
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
                                     current_user.person.id)

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
