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

from datetime import datetime
from hashlib import md5

from sqlalchemy.sql.expression import and_, column, not_
from sqlalchemy.sql.functions import coalesce, count
from sqlalchemy.sql.functions import max as max_

from ...compat import str_to_unicode
from ...error import ConsistencyError, Error, FormattedError, \
    MultipleRecords, NoSuchRecord, UserError
from ...type.collection import AffiliationCollection, AnnotationCollection, \
    CallCollection, CallMidCloseCollection, CallPreambleCollection, \
    MemberCollection, \
    PrevProposalCollection, ProposalCollection, ProposalCategoryCollection, \
    ProposalFigureCollection, ProposalTextCollection, \
    RequestCollection, ResultCollection, TargetCollection
from ...type.enum import AnnotationType, AttachmentState, \
    CallState, FigureType, FormatType, \
    PersonLogEvent, ProposalState, ProposalType, PublicationType, \
    RequestState, SemesterState
from ...type.simple import Affiliation, Annotation, \
    Call, CallMidClose, CallPreamble, Category, CoMemberInfo, \
    Member, MemberInfo, MemberPIInfo, \
    PrevProposal, PrevProposalPub, \
    Proposal, ProposalCategory, ProposalFigure, \
    ProposalFigureInfo, ProposalPDFInfo, \
    ProposalText, \
    Queue, QueueInfo, \
    RequestPropCopy, RequestPropPDF, \
    ReviewerInfo, Semester, SemesterInfo, Target
from ...util import is_list_like
from ..compat import case, row_as_dict, row_as_mapping, scalar_subquery, select
from ..meta import affiliation, affiliation_weight, \
    call, call_mid_close, call_preamble, category, decision, \
    facility, institution, \
    member, person, prev_proposal, prev_proposal_pub, \
    proposal, proposal_annotation, proposal_category, \
    proposal_fig, proposal_fig_link, \
    proposal_fig_preview, proposal_fig_thumbnail, \
    proposal_pdf, proposal_pdf_link, proposal_pdf_preview, \
    proposal_text, proposal_text_link, \
    queue, request_prop_copy, request_prop_pdf, \
    review, reviewer, semester, target
from ..util import require_not_none


class ProposalPart(object):
    def add_affiliation(self, type_class, queue_id, name, type_=None):
        """
        Add an affiliation to the database.
        """

        if type_ is None:
            type_ = type_class.STANDARD
        elif not type_class.is_valid(type_):
            raise FormattedError('Invalid affiliation type {}', type_)

        with self._transaction() as conn:
            result = conn.execute(affiliation.insert().values({
                affiliation.c.queue_id: queue_id,
                affiliation.c.name: name,
                affiliation.c.type: type_,
            }))

        return result.inserted_primary_key[0]

    def add_call(self, type_class, semester_id, queue_id, type_,
                 date_open, date_close,
                 abst_word_lim,
                 tech_word_lim, tech_fig_lim, tech_page_lim,
                 sci_word_lim, sci_fig_lim, sci_page_lim,
                 capt_word_lim, expl_word_lim,
                 tech_note, sci_note, prev_prop_note, note_format,
                 multi_semester, separate, preamble, preamble_format, hidden,
                 allow_continuation,
                 cnrq_note, cnrq_word_lim, cnrq_fig_lim, cnrq_page_lim,
                 cnrq_max_age,
                 _test_skip_check=False):
        """
        Add a call for proposals to the database.
        """

        if not type_class.is_valid(type_):
            raise UserError('The selected call type is not recognised.')

        if date_close < date_open:
            raise UserError('Closing date is before opening date.')

        if not FormatType.is_valid(note_format, is_system=True):
            raise UserError('Note text format not recognised.')

        if preamble is None:
            preamble_format = None

        else:
            if preamble_format is None:
                raise Error('Preamble text format not specified.')

            elif not FormatType.is_valid(preamble_format, is_system=True):
                raise UserError('Preamble text format not recognised.')

        with self._transaction() as conn:
            if not _test_skip_check:
                try:
                    semester = self.get_semester(None, semester_id, _conn=conn)
                    queue = self.get_queue(None, queue_id, _conn=conn)
                except NoSuchRecord as e:
                    raise ConsistencyError(e.message)

                # Then check they are for the same facility.
                if not semester.facility_id == queue.facility_id:
                    raise ConsistencyError(
                        'call has inconsistent facility references: '
                        'semester {} is for facility {} but '
                        'queue {} is for facility {}',
                        semester_id, semester.facility_id,
                        queue_id, queue.facility_id)

            result = conn.execute(call.insert().values({
                call.c.semester_id: semester_id,
                call.c.queue_id: queue_id,
                call.c.type: type_,
                call.c.date_open: date_open,
                call.c.date_close: date_close,
                call.c.abst_word_lim: abst_word_lim,
                call.c.tech_word_lim: tech_word_lim,
                call.c.tech_fig_lim: tech_fig_lim,
                call.c.tech_page_lim: tech_page_lim,
                call.c.sci_word_lim: sci_word_lim,
                call.c.sci_fig_lim: sci_fig_lim,
                call.c.sci_page_lim: sci_page_lim,
                call.c.capt_word_lim: capt_word_lim,
                call.c.expl_word_lim: expl_word_lim,
                call.c.tech_note: tech_note,
                call.c.sci_note: sci_note,
                call.c.prev_prop_note: prev_prop_note,
                call.c.note_format: note_format,
                call.c.multi_semester: multi_semester,
                call.c.separate: separate,
                call.c.preamble: preamble,
                call.c.preamble_format: preamble_format,
                call.c.hidden: hidden,
                call.c.allow_continuation: allow_continuation,
                call.c.cnrq_note: cnrq_note,
                call.c.cnrq_word_lim: cnrq_word_lim,
                call.c.cnrq_fig_lim: cnrq_fig_lim,
                call.c.cnrq_page_lim: cnrq_page_lim,
                call.c.cnrq_max_age: cnrq_max_age,
            }))

        return result.inserted_primary_key[0]

    def add_member(self, proposal_id, person_id, affiliation_id,
                   pi=False, editor=False, observer=False, reviewer=False,
                   adder_person_id=None, is_invite=False,
                   _conn=None, _test_skip_check=False):
        with self._transaction(_conn=_conn) as conn:
            if not _test_skip_check:
                if not self._exists_id(conn, person, person_id):
                    raise ConsistencyError('person does not exist with id={}',
                                           person_id)
                proposal_record = self.get_proposal(None, proposal_id,
                                                    _conn=conn)
                if not self._exists_queue_affiliation(
                        conn, proposal_record.queue_id, affiliation_id):
                    raise ConsistencyError(
                        'affiliation does not exist with id={} '
                        'for queue with id={}'.format(
                            affiliation_id, proposal_record.queue_id))

                if 0 < conn.execute(select([count(member.c.id)]).where(and_(
                        member.c.proposal_id == proposal_id,
                        member.c.person_id == person_id))).scalar():
                    raise UserError('The selected person is already a member '
                                    'of the proposal.')

            member_alias = member.alias()

            result = conn.execute(member.insert().values({
                member.c.proposal_id: proposal_id,
                member.c.sort_order: scalar_subquery(select(
                    [coalesce(max_(member_alias.c.sort_order), 0) + 1]).where(
                    member_alias.c.proposal_id == proposal_id)),
                member.c.person_id: person_id,
                member.c.pi: pi,
                member.c.editor: editor,
                member.c.observer: observer,
                member.c.reviewer: reviewer,
                member.c.affiliation_id: affiliation_id,
            }))

            if adder_person_id is not None:
                self.add_person_log_entry(
                    adder_person_id,
                    (PersonLogEvent.MEMBER_INVITE if is_invite else
                     PersonLogEvent.MEMBER_ADD),
                    proposal_id=proposal_id, other_person_id=person_id,
                    _conn=conn)

        return result.inserted_primary_key[0]

    def add_proposal(self, call_id, person_id, affiliation_id, title,
                     type_=ProposalType.STANDARD,
                     state=ProposalState.PREPARATION, person_is_reviewer=False,
                     is_copy=False,
                     _test_skip_check=False):
        """
        Add a new proposal to the database.

        The given person will be added as a member, assumed to be PI
        and with "editor" permission so that they can continue to
        prepare the proposal.  This person's affiliation (for the
        relevant facility) should be given for inclusion in the
        member table.
        """

        if not title:
            raise UserError('The proposal title should not be blank.')

        if not ProposalType.is_valid(type_):
            raise Error('Invalid proposal type.')

        if not ProposalState.is_valid(state):
            raise Error('Invalid state.')

        with self._transaction() as conn:
            if not _test_skip_check:
                try:
                    call = self.search_call(
                        call_id=call_id, _conn=conn).get_single()
                except NoSuchRecord:
                    raise ConsistencyError('call does not exist with id={}',
                                           call_id)

                if not self._exists_queue_affiliation(
                        conn, call.queue_id, affiliation_id):
                    raise ConsistencyError(
                        'affiliation does not exist with id={} '
                        'for queue with id={}'.format(
                            affiliation_id, call.queue_id))

            proposal_alias = proposal.alias()

            result = conn.execute(proposal.insert().values({
                proposal.c.call_id: call_id,
                proposal.c.number: scalar_subquery(select(
                    [coalesce(max_(proposal_alias.c.number), 0) + 1]).where(
                    proposal_alias.c.call_id == call_id)),
                proposal.c.state: state,
                proposal.c.title: title,
                proposal.c.type: type_,
            }))

            proposal_id = result.inserted_primary_key[0]

            self.add_member(proposal_id, person_id, affiliation_id,
                            True, True, False, reviewer=person_is_reviewer,
                            _conn=conn, _test_skip_check=_test_skip_check)

            # If this is a copy we should have already logged the copy request.
            if not is_copy:
                self.add_person_log_entry(
                    person_id, PersonLogEvent.PROPOSAL_CREATE,
                    proposal_id=proposal_id, _conn=conn)

        return proposal_id

    def add_proposal_annotation(
            self, proposal_id, type_, annotation,
            _test_skip_check=False, _conn=None):
        if not AnnotationType.is_valid(type_):
            raise Error('Invalid annotation type.')

        with self._transaction(_conn=_conn) as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, proposal, proposal_id):
                raise ConsistencyError(
                    'proposal does not exist with id={}', proposal_id)

            result = conn.execute(proposal_annotation.insert().values({
                proposal_annotation.c.proposal_id: proposal_id,
                proposal_annotation.c.type: type_,
                proposal_annotation.c.date: datetime.utcnow(),
                proposal_annotation.c.annotation: annotation,
            }))

            return result.inserted_primary_key[0]

    def add_proposal_figure(
            self, role_class, proposal_id, role,
            type_, figure, caption, filename, uploader_person_id,
            _test_skip_check=False):
        if not role_class.is_valid(role):
            raise Error('Invalid text role.')

        return self._add_figure(
            proposal_fig, proposal_fig_link, proposal_fig_link.c.proposal_id,
            proposal_id, proposal,
            type_, figure, caption, filename, uploader_person_id,
            extra={proposal_fig_link.c.role: role},
            _test_skip_check=_test_skip_check)

    def _add_figure(
            self, table, table_link, key_column, key_value, foreign_table,
            type_, figure, caption, filename, uploader_person_id,
            extra={}, _test_skip_check=False):
        if not FigureType.is_valid(type_):
            raise UserError('Figure type is not permitted or not recognised.')
        if not figure:
            # Shouldn't happen as we should have already checked the figure
            # type.
            raise UserError('Uploaded figure appears to be empty.')

        with self._transaction() as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, foreign_table, key_value)):
                raise ConsistencyError('fig parent does not exist with id={}',
                                       key_value)
            if (not _test_skip_check and
                    not self._exists_id(conn, person, uploader_person_id)):
                raise ConsistencyError('person does not exist with id={}',
                                       uploader_person_id)

            # Create entry in main figure table.
            values = {
                table.c.type: type_,
                table.c.state: AttachmentState.NEW,
                table.c.figure: figure,
                table.c.md5sum: str_to_unicode(md5(figure).hexdigest()),
                table.c.filename: filename,
                table.c.uploaded: datetime.utcnow(),
                table.c.uploader: uploader_person_id,
            }

            result = conn.execute(table.insert().values(values))

            fig_id = result.inserted_primary_key[0]

            # Create entry in link table.  Do this here rather than calling
            # link_proposal_figure so that we can also handle review figures
            # (while we don't have a method to link them).
            table_alias = table_link.alias()
            key_column_alias = table_alias.columns[key_column.name]

            values = {
                key_column: key_value,
                table_link.c.sort_order: scalar_subquery(select(
                    [coalesce(max_(table_alias.c.sort_order), 0) + 1]
                    ).where(key_column_alias == key_value)),
                table_link.c.caption: caption,
                table_link.c.fig_id: fig_id,
            }

            values.update(extra)

            result = conn.execute(table_link.insert().values(values))

            link_id = result.inserted_primary_key[0]

        return (link_id, fig_id)

    def add_queue(self, facility_id, name, code, description='',
                  description_format=FormatType.PLAIN,
                  _test_skip_check=False):
        """
        Add a queue to the database.
        """

        if not name:
            raise UserError('The queue name can not be blank.')

        if not FormatType.is_valid(description_format, is_system=True):
            raise UserError('Text format not recognised.')

        with self._transaction() as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, facility, facility_id)):
                raise ConsistencyError('facility does not exist with id={}',
                                       facility_id)

            result = conn.execute(queue.insert().values({
                queue.c.facility_id: facility_id,
                queue.c.name: name,
                queue.c.code: code,
                queue.c.description: description,
                queue.c.description_format: description_format,
            }))

            return result.inserted_primary_key[0]

    def add_request_prop_copy(
            self, proposal_id, requester_person_id,
            call_id, affiliation_id, copy_members, continuation,
            _test_skip_check=False):
        with self._transaction() as conn:
            request_id = self._add_request_prop(
                request_prop_copy, proposal_id, requester_person_id,
                extra_values={
                    request_prop_copy.c.call_id: call_id,
                    request_prop_copy.c.affiliation_id: affiliation_id,
                    request_prop_copy.c.copy_members: copy_members,
                    request_prop_copy.c.continuation: continuation,
                },
                _conn=conn, _test_skip_check=_test_skip_check)

            self.add_person_log_entry(
                requester_person_id,
                (PersonLogEvent.PROPOSAL_REQUEST_CONTINUATION
                    if continuation else
                    PersonLogEvent.PROPOSAL_REQUEST_COPY),
                proposal_id=proposal_id, _conn=conn)

        return request_id

    def add_request_prop_pdf(
            self, proposal_id, requester_person_id,
            _test_skip_check=False):
        return self._add_request_prop(
            request_prop_pdf, proposal_id, requester_person_id,
            _test_skip_check=_test_skip_check)

    def _add_request_prop(
            self, table, proposal_id, requester_person_id, extra_values=None,
            _conn=None, _test_skip_check=False):
        values = {
            table.c.proposal_id: proposal_id,
            table.c.state: RequestState.NEW,
            table.c.requested: datetime.utcnow(),
            table.c.requester: requester_person_id,
        }

        if extra_values is not None:
            values.update(extra_values)

        with self._transaction(_conn=_conn) as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, proposal, proposal_id):
                raise ConsistencyError(
                    'proposal does not exist with id={}', proposal_id)

            if not _test_skip_check and not self._exists_id(
                    conn, person, requester_person_id):
                raise ConsistencyError(
                    'person does not exist with id={}', uploader_person_id)

            result = conn.execute(table.insert().values(values))

            return result.inserted_primary_key[0]

    def add_semester(self, facility_id, name, code,
                     date_start, date_end, description='',
                     description_format=FormatType.PLAIN,
                     _test_skip_check=False):
        """
        Add a semester to the database.
        """

        if not name:
            raise UserError('The semester name can not be blank.')

        if date_end < date_start:
            raise UserError('Semester end date is before start date.')

        if not FormatType.is_valid(description_format, is_system=True):
            raise UserError('Text format not recognised.')

        with self._transaction() as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, facility, facility_id)):
                raise ConsistencyError('facility does not exist with id={}',
                                       facility_id)

            result = conn.execute(semester.insert().values({
                semester.c.facility_id: facility_id,
                semester.c.name: name,
                semester.c.code: code,
                semester.c.date_start: date_start,
                semester.c.date_end: date_end,
                semester.c.description: description,
                queue.c.description_format: description_format,
            }))

            return result.inserted_primary_key[0]

    def delete_member_person(self, proposal_id, person_id):
        """
        Remove a member from a proposal, by person identifier.
        """

        with self._transaction() as conn:
            result = conn.execute(member.delete().where(and_(
                member.c.proposal_id == proposal_id,
                member.c.person_id == person_id
            )))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no row matched deleting member person {} for {}',
                    person_id, proposal_id)

            # Check that the proposal still has at least one member: if not,
            # raise an exception to abort the transaction.
            if 1 > conn.execute(select([count(member.c.id)]).where(and_(
                    member.c.proposal_id == proposal_id,
                    member.c.editor))).scalar():
                raise ConsistencyError(
                    'deleting this member would leave no editors')

    def delete_proposal_figure(
            self, proposal_id, role, id_,
            _allow_any=False, _conn=None):
        """
        Delete one (or more) figure(s) associated with a proposal.

        :param proposal_id: the proposal identifier
        :param role: the role number
        :param id_: the figure identifier
        :param _allow_any: if true, allows the `id_` parameter to be omitted,
            and skips the check that one figure was successfully deleted
        :param _conn: database connection object, if a transaction has already
            been started
        """

        where_extra = []

        if proposal_id is not None:
            where_extra.append(proposal_fig_link.c.proposal_id == proposal_id)
        elif _allow_any:
            raise Error('figure proposal_id not specified with _allow_any')

        if role is not None:
            where_extra.append(proposal_fig_link.c.role == role)
        elif _allow_any:
            raise Error('figure role not specified with _allow_any')

        return self._delete_figure(
            proposal_fig, proposal_fig_link, id_, where_extra=where_extra,
            _allow_any=_allow_any, _conn=_conn)

    def _delete_figure(
            self, table, table_link, id_, where_extra=[],
            _allow_any=False, _conn=None):
        stmt = table_link.delete()

        for where_clause in where_extra:
            stmt = stmt.where(where_clause)

        if id_ is not None:
            stmt = stmt.where(table_link.c.fig_id == id_)
        elif not _allow_any:
            raise Error('figure identifier not specified')

        with self._transaction(_conn=_conn) as conn:
            result = conn.execute(stmt)

            if result.rowcount != 1 and not _allow_any:
                raise ConsistencyError(
                    'no row matched deleting figure identifier {}',
                    id_)

            self._remove_orphan_records(conn, table, table_link.c.fig_id)

    def delete_proposal_pdf(self, proposal_id, role,
                            _skip_check=False, _allow_count=(1,), _conn=None):
        """
        Delete a PDF file associated with a proposal.

        :param proposal_id: the proposal identifier
        :param role: the role number
        :param _skip_check: if true, do not first check that the PDF exists
        :param tuple _allow_count: allowed numbers of PDF files to be deleted
        :param _conn: database connection object, if a transaction has already
            been started
        """

        with self._transaction(_conn=_conn) as conn:
            if (not _skip_check
                    and (self._get_proposal_text_id(
                        conn, proposal_pdf_link, proposal_id, role) is None)):
                raise ConsistencyError('PDF does not exist for {} role {}',
                                       proposal_id, role)

            result = conn.execute(proposal_pdf_link.delete().where(and_(
                proposal_pdf_link.c.proposal_id == proposal_id,
                proposal_pdf_link.c.role == role
            )))

            if result.rowcount not in _allow_count:
                raise ConsistencyError(
                    'mismatch deleting PDF for {} role {}',
                    proposal_id, role)

            self._remove_orphan_records(
                conn, proposal_pdf, proposal_pdf_link.c.pdf_id)

    def delete_proposal_text(self, proposal_id, role,
                             _skip_check=False, _allow_count=(1,), _conn=None):
        """
        Delete a piece of text associated with a proposal.

        :param proposal_id: the proposal identifier
        :param role: the role number
        :param _skip_check: if true, do not first check that the text exists
        :param tuple _allow_count: allowed numbers of text blocks to be deleted
        :param _conn: database connection object, if a transaction has already
            been started
        """

        with self._transaction(_conn=_conn) as conn:
            if not _skip_check and not self._get_proposal_text_id(
                    conn, proposal_text_link, proposal_id, role):
                raise ConsistencyError('text does not exist for {} role {}',
                                       proposal_id, role)

            result = conn.execute(proposal_text_link.delete().where(and_(
                proposal_text_link.c.proposal_id == proposal_id,
                proposal_text_link.c.role == role
            )))

            if result.rowcount not in _allow_count:
                raise ConsistencyError(
                    'mismatch deleting text for {} role {}',
                    proposal_id, role)

            self._remove_orphan_records(
                conn, proposal_text, proposal_text_link.c.text_id)

    def delete_request_prop_copy(self, request_id, _test_skip_check=False):
        self._delete_request(
            request_prop_copy, request_id, _test_skip_check=_test_skip_check)

    def delete_request_prop_pdf(self, request_id, _test_skip_check=False):
        self._delete_request(
            request_prop_pdf, request_id, _test_skip_check=_test_skip_check)

    def _delete_request(
            self, table, request_id,
            _conn=None, _test_skip_check=False):
        with self._transaction(_conn=_conn) as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, table, request_id):
                raise ConsistencyError(
                    'request does not exist with id {}', request_id)

            result = conn.execute(table.delete().where(
                table.c.id == request_id))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched deleting request {}', request_id)

    def ensure_facility(self, code, _read_only=False):
        """
        Ensure that a facility exists in the database.

        If the facility already exists, just return its identifier.

        Otherwise add it and return the new identifier.
        """

        if not code:
            raise ConsistencyError('The facility code can not be blank.')

        with self._transaction() as conn:
            result = conn.execute(facility.select().where(
                facility.c.code == code
            )).first()

            if result is not None:
                return result.id

            if _read_only:
                raise FormattedError(
                    'read-only option: can not create facility \'{}\'', code)

            result = conn.execute(facility.insert().values({
                facility.c.code: code,
            }))

            return result.inserted_primary_key[0]

    def get_call(self, facility_id, call_id):
        """
        Get a call record.
        """

        return self.search_call(
            facility_id=facility_id, call_id=call_id,
            with_case_notes=True, with_preamble=True,
        ).get_single()

    def get_call_preamble(self, semester_id, type_):
        """
        Get the call preamble for a given semester and call type.
        """

        return self.search_call_preamble(
            semester_id=semester_id, type_=type_
        ).get_single()

    def get_original_proposal_ids(self, proposals, _conn=None):
        """
        Determine how to look up associated data for proposals.

        For example continuation requests do not have their own target list,
        so we must fetch the corresponding previous proposal IDs and use
        these to find the targets.

        :return: a set of proposal IDs, containing the IDs of standard
            proposals or the previous proposal of continuation requests,
            and a dictionary mapping continuation request IDs to their
            previous proposals.
        """

        proposal_ids = set()
        proposal_ids_cr = set()
        previous_proposal_ids = {}
        for proposal in proposals.values():
            (proposal_ids_cr
             if proposal.type == ProposalType.CONTINUATION
             else proposal_ids).add(proposal.id)

        if proposal_ids_cr:
            for prev_proposal in self.search_prev_proposal(
                    proposal_id=proposal_ids_cr,
                    continuation=True, resolved=True,
                    with_publications=False,
                    _conn=_conn).values():
                id_ = prev_proposal.proposal_id
                proposal_ids.add(id_)
                previous_proposal_ids[prev_proposal.this_proposal_id] = id_

        return (proposal_ids, previous_proposal_ids)

    def get_proposal(self, facility_id, proposal_id,
                     with_members=False, with_reviewers=False,
                     with_decision=False, with_decision_note=False,
                     with_categories=False,
                     _conn=None):
        """
        Get a proposal record.
        """

        return self.search_proposal(
            facility_id=facility_id, proposal_id=proposal_id,
            with_members=with_members, with_reviewers=with_reviewers,
            with_decision=with_decision, with_decision_note=with_decision_note,
            with_categories=with_categories,
            _conn=_conn
        ).get_single()

    def get_proposal_figure(
            self, proposal_id, role, link_id, fig_id=None, md5sum=None):
        """
        Get a figure associated with a proposal.

        Returned as a ProposalFigure object.
        """

        where_extra = []

        if proposal_id is not None:
            where_extra.append(proposal_fig_link.c.proposal_id == proposal_id)

        if role is not None:
            where_extra.append(proposal_fig_link.c.role == role)

        return self._get_figure(
            proposal_fig, proposal_fig_link, link_id, fig_id, md5sum,
            where_extra=where_extra)

    def _get_figure(
            self, table, table_link, link_id, fig_id, md5sum, where_extra=[]):
        stmt = select([
            table.c.figure,
            table.c.type,
            table.c.filename,
        ])

        stmt = stmt.select_from(table.join(table_link))

        for where_clause in where_extra:
            stmt = stmt.where(where_clause)

        have_id = False
        if link_id is not None:
            stmt = stmt.where(table_link.c.id == link_id)
            have_id = True
        if fig_id is not None:
            stmt = stmt.where(table.c.id == fig_id)
            have_id = True
        if not have_id:
            raise Error('figure identifier not specified')

        if md5sum is not None:
            stmt = stmt.where(table.c.md5sum == md5sum)

        with self._transaction() as conn:
            row = conn.execute(stmt).first()

        if row is None:
            raise NoSuchRecord('figure does not exist')

        return ProposalFigure(row.figure, row.type, row.filename)

    def get_proposal_figure_preview(
            self, proposal_id, role, link_id, fig_id=None, md5sum=None):
        where_extra = []

        if proposal_id is not None:
            where_extra.append(proposal_fig_link.c.proposal_id == proposal_id)

        if role is not None:
            where_extra.append(proposal_fig_link.c.role == role)

        return self._get_figure_alternate(
            proposal_fig, proposal_fig_link, proposal_fig_preview.c.preview,
            link_id, fig_id, md5sum, where_extra=where_extra)

    def get_proposal_figure_thumbnail(
            self, proposal_id, role, link_id, fig_id=None, md5sum=None):
        where_extra = []

        if proposal_id is not None:
            where_extra.append(proposal_fig_link.c.proposal_id == proposal_id)

        if role is not None:
            where_extra.append(proposal_fig_link.c.role == role)

        return self._get_figure_alternate(
            proposal_fig, proposal_fig_link, proposal_fig_thumbnail.c.thumbnail,
            link_id, fig_id, md5sum, where_extra=where_extra)

    def _get_figure_alternate(
            self, table, table_link, column, link_id, fig_id, md5sum,
            where_extra=[]):
        stmt = select([column])

        if (where_extra or (md5sum is not None) or (link_id is not None)):
            stmt = stmt.select_from(column.table.join(table).join(table_link))

            for where_clause in where_extra:
                stmt = stmt.where(where_clause)

            if md5sum is not None:
                stmt = stmt.where(table.c.md5sum == md5sum)

        have_id = False
        if link_id is not None:
            stmt = stmt.where(table_link.c.id == link_id)
            have_id = True
        if fig_id is not None:
            stmt = stmt.where(column.table.c.fig_id == fig_id)
            have_id = True
        if not have_id:
            raise Error('figure identifier not specified')

        with self._transaction() as conn:
            row = conn.execute(stmt).first()

        if row is None:
            raise NoSuchRecord('figure preview/thumbnail does not exist')

        return row[0]

    def get_proposal_pdf(self, proposal_id, role, pdf_id=None, md5sum=None,
                         _conn=None):
        """
        Get the given PDF associated with a proposal.
        """

        stmt = select([proposal_pdf.c.pdf, proposal_pdf.c.filename])

        stmt = stmt.select_from(proposal_pdf.join(proposal_pdf_link))

        if (proposal_id is not None) and (role is not None):
            stmt = stmt.where(and_(
                proposal_pdf_link.c.proposal_id == proposal_id,
                proposal_pdf_link.c.role == role
            ))

        elif pdf_id is not None:
            stmt = stmt.where(proposal_pdf.c.id == pdf_id)

        else:
            raise Error('neither PDF nor proposal and role specified.')

        if md5sum is not None:
            stmt = stmt.where(proposal_pdf.c.md5sum == md5sum)

        with self._transaction(_conn=_conn) as conn:
            row = conn.execute(stmt).first()

        if row is None:
            raise NoSuchRecord('PDF does not exist for {} role {}',
                               proposal_id, role)

        return ProposalFigure(row.pdf, FigureType.PDF, row.filename)

    def get_proposal_pdf_preview(self, proposal_id, role, page, md5sum=None):
        """
        Get a preview page from a PDF associated with a proposal.
        """

        stmt = select([proposal_pdf_preview.c.preview]).select_from(
            proposal_pdf.join(proposal_pdf_link).join(proposal_pdf_preview)
        ).where(and_(
            proposal_pdf_link.c.proposal_id == proposal_id,
            proposal_pdf_link.c.role == role,
            proposal_pdf_preview.c.page == page
        ))

        if md5sum is not None:
            stmt = stmt.where(proposal_pdf.c.md5sum == md5sum)

        with self._transaction() as conn:
            preview = conn.execute(stmt).scalar()

        if preview is None:
            raise NoSuchRecord(
                'PDF preview does not exist for {} role {} page {}',
                proposal_id, role, page)

        return preview

    def get_proposal_text(self, proposal_id, role, _conn=None):
        """
        Get the given text associated with a proposal.
        """

        return self.search_proposal_text(
            proposal_id=proposal_id, role=role, with_text=True,
            _conn=_conn
        ).get_single()

    def get_semester(self, facility_id, semester_id, _conn=None):
        """
        Get a semester record.
        """

        stmt = semester.select().where(semester.c.id == semester_id)

        if facility_id is not None:
            stmt = stmt.where(semester.c.facility_id == facility_id)

        with self._transaction(_conn=_conn) as conn:
            result = conn.execute(stmt).first()

        if result is None:
            raise NoSuchRecord('semester does not exist')

        return Semester(**row_as_mapping(result))

    def get_queue(self, facility_id, queue_id, _conn=None):
        """
        Get a queue record.
        """

        stmt = queue.select().where(queue.c.id == queue_id)

        if facility_id is not None:
            stmt = stmt.where(queue.c.facility_id == facility_id)

        with self._transaction(_conn=_conn) as conn:
            result = conn.execute(stmt).first()

        if result is None:
            raise NoSuchRecord('queue does not exist')

        return Queue(**row_as_mapping(result))

    def link_proposal_pdf(
            self, role_class, proposal_id, role, pdf_id,
            _conn=None, _test_skip_check=False):
        """
        Link the given proposal PDF to a proposal.

        :return: the link identifier
        """

        with self._transaction(_conn=_conn) as conn:
            link_id = self._link_proposal_attachment(
                conn, role_class, proposal_pdf, proposal_pdf_link,
                proposal_pdf_link.c.pdf_id,
                proposal_id, role, pdf_id,
                _test_skip_check=_test_skip_check)

            # Delete any previous proposal text and figures for the same role.
            self.delete_proposal_text(
                proposal_id, role,
                _skip_check=True, _allow_count=(0, 1), _conn=conn)

            self.delete_proposal_figure(
                proposal_id, role, id_=None,
                _allow_any=True, _conn=conn)

        return link_id

    def link_proposal_text(
            self, role_class, proposal_id, role, text_id,
            _conn=None, _test_skip_check=False):
        """
        Link the given proposal text to a proposal.

        :return: the link identifier
        """

        with self._transaction(_conn=_conn) as conn:
            link_id = self._link_proposal_attachment(
                conn, role_class, proposal_text, proposal_text_link,
                proposal_text_link.c.text_id,
                proposal_id, role, text_id,
                _test_skip_check=_test_skip_check)

            # Delete any previous proposal PDF for the same role.
            self.delete_proposal_pdf(
                proposal_id, role,
                _skip_check=True, _allow_count=(0, 1), _conn=conn)

        return link_id

    def link_proposal_figure(
            self, role_class, proposal_id, role, fig_id, sort_order, caption,
            _conn=None, _test_skip_check=False):
        """
        Link the given figure to a proposal.

        :return: the link identifier
        """

        values = {
            proposal_fig_link.c.sort_order: sort_order,
            proposal_fig_link.c.caption: caption,
        }

        with self._transaction(_conn=_conn) as conn:
            link_id = self._link_proposal_attachment(
                conn, role_class,
                proposal_fig, proposal_fig_link,
                proposal_fig_link.c.fig_id,
                proposal_id, role, fig_id,
                extra_values=values, allow_multiple=True,
                _test_skip_check=_test_skip_check)

        return link_id

    def _link_proposal_attachment(
            self, conn, role_class, table, table_link, key_field,
            proposal_id, role, key_value, extra_values=None,
            allow_multiple=False, _test_skip_check=False):
        if not role_class.is_valid(role):
            raise FormattedError(
                'proposal text role not recognised: {}', role)

        if not _test_skip_check:
            if not self._exists_id(conn, table, key_value):
                raise ConsistencyError(
                    'link target {} {} does not exist',
                    table.name, key_value)

            if not allow_multiple:
                if self._get_proposal_text_id(
                        conn, table_link, proposal_id, role) is not None:
                    raise ConsistencyError(
                        'proposal {} already has a {} link role {}',
                        proposal_id, table.name, role)

        values = {
            table_link.c.proposal_id: proposal_id,
            table_link.c.role: role,
            key_field: key_value,
        }

        if extra_values is not None:
            values.update(extra_values)

        result = conn.execute(table_link.insert().values(values))

        return result.inserted_primary_key[0]

    def search_affiliation(
            self, queue_id=None, hidden=None, type_=None,
            with_weight_call_id=None, with_weight_separate=False,
            order_by_id=False):
        """
        Search for affiliation records.
        """

        default = {}
        field_hidden = affiliation.c.hidden
        field_type = affiliation.c.type

        if with_weight_call_id is None:
            stmt = affiliation.select()
            default['weight'] = None

        else:
            if with_weight_separate:
                select_columns = [
                    affiliation,
                    affiliation_weight.c.weight,
                    affiliation_weight.c.hidden.label('weight_hidden'),
                    affiliation_weight.c.type.label('weight_type'),
                ]

            else:
                field_hidden = coalesce(
                    affiliation_weight.c.hidden,
                    affiliation.c.hidden)
                field_type = coalesce(
                    affiliation_weight.c.type,
                    affiliation.c.type)
                select_columns = [
                    affiliation.c.id,
                    affiliation.c.queue_id,
                    affiliation.c.name,
                    field_hidden.label('hidden'),
                    field_type.label('type'),
                    affiliation_weight.c.weight,
                ]

            stmt = select(select_columns).select_from(
                affiliation.outerjoin(affiliation_weight, and_(
                    affiliation_weight.c.affiliation_id == affiliation.c.id,
                    affiliation_weight.c.call_id == with_weight_call_id))
            )

        if queue_id is not None:
            stmt = stmt.where(affiliation.c.queue_id == queue_id)

        if hidden is not None:
            if hidden:
                stmt = stmt.where(field_hidden)
            else:
                stmt = stmt.where(not_(field_hidden))

        if type_ is not None:
            if is_list_like(type_):
                stmt = stmt.where(field_type.in_(type_))
            else:
                stmt = stmt.where(field_type == type_)

        if order_by_id:
            stmt = stmt.order_by(affiliation.c.id.asc())
        else:
            stmt = stmt.order_by(affiliation.c.name.asc())

        ans = AffiliationCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt):
                values = default.copy()
                values.update(**row_as_mapping(row))

                if with_weight_separate:
                    values['weight'] = Affiliation(
                        id=None,
                        queue_id=None,
                        name=None,
                        hidden=values.pop('weight_hidden'),
                        type=values.pop('weight_type'),
                        weight=values.pop('weight'))

                ans[values['id']] = Affiliation(**values)

        return ans

    def search_call(self, call_id=None, facility_id=None,
                    semester_id=None, semester_code=None,
                    queue_id=None, queue_code=None,
                    type_=None, state=None,
                    has_proposal_state=None, date_close_before=None,
                    separate=None, hidden=None,
                    with_queue_description=False, with_case_notes=False,
                    with_preamble=False,
                    with_proposal_count=False, with_proposal_count_state=None,
                    _conn=None):
        """
        Search for call records.
        """

        fields_exclude = set()

        if not with_case_notes:
            fields_exclude.update((
                'tech_note', 'sci_note', 'prev_prop_note', 'cnrq_note'))

        if not with_preamble:
            fields_exclude.update(('preamble',))

        fields = [x for x in call.columns if x.name not in fields_exclude]
        default = {x: None for x in fields_exclude}

        dt_current = datetime.utcnow()

        state_expr = case([
            (call.c.date_open > dt_current, CallState.UNOPENED),
            (call.c.date_close >= dt_current, CallState.OPEN),
        ], else_=CallState.CLOSED)

        fields.extend([
            state_expr.label('state'),
            semester.c.facility_id,
            semester.c.name.label('semester_name'),
            queue.c.name.label('queue_name')
        ])

        select_from = call.join(semester).join(queue)

        if with_queue_description:
            fields.append(queue.c.description.label('queue_description'))
            fields.append(
                queue.c.description_format.label('queue_description_format'))
        else:
            default['queue_description'] = None
            default['queue_description_format'] = None

        if with_proposal_count:
            proposal_count = select([
                count(proposal.c.id),
            ]).where(proposal.c.call_id == call.c.id)

            if with_proposal_count_state is not None:
                if is_list_like(with_proposal_count_state):
                    proposal_count = proposal_count.where(
                        proposal.c.state.in_(with_proposal_count_state))

                else:
                    proposal_count = proposal_count.where(
                        proposal.c.state == with_proposal_count_state)

            fields.append(proposal_count.label('proposal_count'))
        else:
            default['proposal_count'] = None

        stmt = select(fields).select_from(select_from)

        if call_id is not None:
            stmt = stmt.where(call.c.id == call_id)

        if facility_id is not None:
            stmt = stmt.where(semester.c.facility_id == facility_id)

        if semester_id is not None:
            stmt = stmt.where(call.c.semester_id == semester_id)

        if semester_code is not None:
            stmt = stmt.where(semester.c.code == semester_code)

        if queue_id is not None:
            if is_list_like(queue_id):
                stmt = stmt.where(call.c.queue_id.in_(queue_id))
            else:
                stmt = stmt.where(call.c.queue_id == queue_id)

        if queue_code is not None:
            stmt = stmt.where(queue.c.code == queue_code)

        if type_ is not None:
            if is_list_like(type_):
                stmt = stmt.where(call.c.type.in_(type_))
            else:
                stmt = stmt.where(call.c.type == type_)

        if state is not None:
            stmt = stmt.where(state_expr == state)

        if has_proposal_state is not None:
            proposal_calls = select([proposal.c.call_id])

            if is_list_like(has_proposal_state):
                proposal_calls = proposal_calls.where(
                    proposal.c.state.in_(has_proposal_state))
            else:
                proposal_calls = proposal_calls.where(
                    proposal.c.state == has_proposal_state)

            stmt = stmt.where(call.c.id.in_(proposal_calls.distinct()))

        if date_close_before is not None:
            stmt = stmt.where(call.c.date_close < date_close_before)

        if separate is not None:
            if separate:
                stmt = stmt.where(call.c.separate)
            else:
                stmt = stmt.where(not_(call.c.separate))

        if hidden is not None:
            if hidden:
                stmt = stmt.where(call.c.hidden)
            else:
                stmt = stmt.where(not_(call.c.hidden))

        ans = CallCollection()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt.order_by(semester.c.date_start.desc(),
                                                  semester.c.code.desc(),
                                                  call.c.type.asc(),
                                                  queue.c.name.asc())):
                values = default.copy()
                values.update(**row_as_mapping(row))
                ans[row.id] = Call(**values)

        return ans

    def search_call_mid_close(
            self, call_id=None, closed=None, date_before=None,
            _conn=None):
        """
        Search for intermediate call close dates.
        """

        stmt = call_mid_close.select()

        iter_field = None
        iter_list = None

        if call_id is not None:
            if is_list_like(call_id):
                assert iter_field is None
                iter_field = call_mid_close.c.call_id
                iter_list = call_id
            else:
                stmt = stmt.where(call_mid_close.c.call_id == call_id)

        if closed is not None:
            if closed:
                stmt = stmt.where(call_mid_close.c.closed)
            else:
                stmt = stmt.where(not_(call_mid_close.c.closed))

        if date_before is not None:
            stmt = stmt.where(call_mid_close.c.date < date_before)

        ans = CallMidCloseCollection()

        with self._transaction(_conn=_conn) as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(
                        iter_stmt.order_by(call_mid_close.c.date.asc())):
                    ans[row.id] = CallMidClose(**row_as_mapping(row))

        return ans

    def search_call_preamble(self, semester_id=None, type_=None, _conn=None):
        """
        Search for call preamble text records.
        """

        ans = CallPreambleCollection()

        stmt = call_preamble.select()

        if semester_id is not None:
            stmt = stmt.where(call_preamble.c.semester_id == semester_id)

        if type_ is not None:
            stmt = stmt.where(call_preamble.c.type == type_)

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(
                    call_preamble.c.semester_id.asc(),
                    call_preamble.c.type.asc())):
                ans[row.id] = CallPreamble(**row_as_mapping(row))

        return ans

    def search_category(self, facility_id, hidden=None, order_by_id=False,
                        _conn=None):
        """
        Search for categories.
        """

        stmt = category.select()

        if facility_id is not None:
            stmt = stmt.where(category.c.facility_id == facility_id)

        if hidden is not None:
            if hidden:
                stmt = stmt.where(category.c.hidden)
            else:
                stmt = stmt.where(not_(category.c.hidden))

        ans = ResultCollection()

        if order_by_id:
            stmt = stmt.order_by(category.c.id.asc())
        else:
            stmt = stmt.order_by(category.c.name.asc())

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt):
                ans[row.id] = Category(**row_as_mapping(row))

        return ans

    def search_co_member(
            self, person_id,
            editor=None, proposal_state=None,
            with_institution_id=False,
            _conn=None):
        """
        Search for proposal co-membership.

        For a given person, search for other people who have proposal
        membership in common.  This returns:

        * Whether the given person is an editor of the common proposal.

        * The person identifier for the co-member and optionally their
          institution.
        """

        co_member = member.alias()

        fields = [
            co_member.c.id,
            member.c.editor,
            co_member.c.person_id.label('co_member_person_id'),
        ]

        default = {}

        select_from = member.join(
            co_member, member.c.proposal_id == co_member.c.proposal_id)

        if proposal_state is not None:
            select_from = select_from.join(
                proposal, member.c.proposal_id == proposal.c.id)

        if with_institution_id:
            fields.append(coalesce(
                co_member.c.institution_id, person.c.institution_id).label(
                    'co_member_institution_id'))
            select_from = select_from.outerjoin(
                person, person.c.id == co_member.c.person_id)

        else:
            default['co_member_institution_id'] = None

        stmt = select(fields).select_from(select_from).where(and_(
            member.c.person_id == person_id,
            co_member.c.person_id != person_id))

        if editor is not None:
            if editor:
                stmt = stmt.where(member.c.editor)
            else:
                stmt = stmt.where(not_(member.c.editor))

        if proposal_state is not None:
            if is_list_like(proposal_state):
                stmt = stmt.where(proposal.c.state.in_(proposal_state))
            else:
                stmt = stmt.where(proposal.c.state == proposal_state)

        ans = ResultCollection()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt):
                values = default.copy()
                values.update(**row_as_mapping(row))
                ans[values['id']] = CoMemberInfo(**values)

        return ans

    def search_member(
            self, proposal_id=None, person_id=None, editor=None,
            institution_id=None, with_institution=True,
            _conn=None):
        """
        Search for proposal members.

        :param proposal_id: the proposal identifier(s)
        :param person_id: the person idenfifier
        :param editor: whether or not the member is an editor
        :param institution_id: institution identifier(s) query constraint,
            applied only to institutions "frozen" into the member record
        :param with_institution: whether to include institution information,
            via the "frozen" institution if present, otherwise the person
        """

        select_columns = [
            x for x in member.columns if x.name not in ('institution_id',)]

        select_columns.extend([
            person.c.name.label('person_name'),
            person.c.public.label('person_public'),
            (person.c.user_id.isnot(None)).label('person_registered'),
            person.c.user_id.label('user_id'),
            affiliation.c.name.label('affiliation_name'),
            coalesce(member.c.institution_id, person.c.institution_id).label(
                'resolved_institution_id'),
        ])

        select_from = member.join(person).join(affiliation)

        default = {}

        if with_institution:
            select_columns.extend([
                institution.c.name.label('institution_name'),
                institution.c.department.label('institution_department'),
                institution.c.organization.label('institution_organization'),
                institution.c.country.label('institution_country'),
                institution.c.name_abbr.label('institution_name_abbr'),
                institution.c.department_abbr.label('institution_department_abbr'),
                institution.c.organization_abbr.label('institution_organization_abbr'),
            ])

            select_from = select_from.outerjoin(
                institution, institution.c.id == coalesce(
                    member.c.institution_id, person.c.institution_id
                ))

        else:
            default.update({
                'institution_name': None,
                'institution_department': None,
                'institution_organization': None,
                'institution_country': None,
                'institution_name_abbr': None,
                'institution_department_abbr': None,
                'institution_organization_abbr': None,
            })

        stmt = select(select_columns).select_from(select_from)

        iter_field = None
        iter_list = None

        if proposal_id is not None:
            if is_list_like(proposal_id):
                assert iter_field is None
                iter_field = member.c.proposal_id
                iter_list = proposal_id
            else:
                stmt = stmt.where(member.c.proposal_id == proposal_id)

        if person_id is not None:
            stmt = stmt.where(member.c.person_id == person_id)

        if editor is not None:
            if editor:
                stmt = stmt.where(member.c.editor)
            else:
                stmt = stmt.where(not_(member.c.editor))

        if institution_id is not None:
            if is_list_like(institution_id):
                assert iter_field is None
                iter_field = member.c.institution_id
                iter_list = institution_id
            else:
                stmt = stmt.where(member.c.institution_id == institution_id)

        ans = MemberCollection()

        with self._transaction(_conn=_conn) as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(
                        iter_stmt.order_by(member.c.sort_order.asc())):
                    values = default.copy()
                    values.update(**row_as_mapping(row))
                    ans[row.id] = Member(**values)

        return ans

    def search_semester(self, facility_id=None, state=None):
        dt_current = datetime.utcnow()
        state_expr = case([
            (semester.c.date_start > dt_current, SemesterState.FUTURE),
            (semester.c.date_end >= dt_current, SemesterState.CURRENT),
        ], else_=SemesterState.PAST)

        stmt = select([
            semester.c.id,
            semester.c.facility_id,
            semester.c.name,
            semester.c.code,
            semester.c.date_start,
            semester.c.date_end,
            state_expr.label('state'),
        ])

        if facility_id is not None:
            stmt = stmt.where(semester.c.facility_id == facility_id)

        if state is not None:
            if is_list_like(state):
                stmt = stmt.where(state_expr.in_(state))
            else:
                stmt = stmt.where(state_expr == state)

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(
                    stmt.order_by(semester.c.date_start.desc())):
                ans[row.id] = SemesterInfo(**row_as_mapping(row))

        return ans

    def search_prev_proposal(
            self, proposal_id, continuation=None, resolved=None,
            with_publications=True, with_proposal_info=False,
            _conn=None):
        """
        Search for the previous proposal associated with a given proposal.
        """

        select_columns = [prev_proposal]
        select_from = prev_proposal
        order_by = [prev_proposal.c.sort_order.asc()]
        default = {}

        if with_proposal_info:
            select_from = select_from.outerjoin(
                proposal, prev_proposal.c.proposal_id == proposal.c.id
            ).outerjoin(
                call, proposal.c.call_id == call.c.id)
            select_columns.extend((
                proposal.c.state.label('proposal_state'),
                proposal.c.type.label('proposal_type'),
                proposal.c.call_id.label('proposal_call_id'),
                call.c.type.label('proposal_call_type'),
                call.c.semester_id.label('proposal_semester_id'),
                call.c.queue_id.label('proposal_queue_id'),
            ))
        else:
            default.update({
                'proposal_state': None,
                'proposal_type': None,
                'proposal_call_id': None,
                'proposal_call_type': None,
                'proposal_semester_id': None,
                'proposal_queue_id': None,
            })

        if with_publications:
            non_id_pub_columns = [
                x for x in prev_proposal_pub.columns
                if x.name != 'id']

            select_columns.extend(non_id_pub_columns)
            select_columns.append(prev_proposal_pub.c.id.label('pp_pub_id'))

            select_from = select_from.outerjoin(prev_proposal_pub)

            order_by.append(prev_proposal_pub.c.id.asc())

        stmt = select(select_columns).select_from(select_from)

        iter_field = None
        iter_list = None

        if is_list_like(proposal_id):
            assert iter_field is None
            iter_field = prev_proposal.c.this_proposal_id
            iter_list = proposal_id
        else:
            stmt = stmt.where(prev_proposal.c.this_proposal_id == proposal_id)

        if continuation is not None:
            if continuation:
                stmt = stmt.where(prev_proposal.c.continuation)
            else:
                stmt = stmt.where(not_(prev_proposal.c.continuation))

        if resolved is not None:
            if resolved:
                stmt = stmt.where(prev_proposal.c.proposal_id.isnot(None))
            else:
                stmt = stmt.where(prev_proposal.c.proposal_id.is_(None))

        ans = PrevProposalCollection()

        with self._transaction(_conn=_conn) as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(iter_stmt.order_by(*order_by)):
                    values = default.copy()
                    values.update(**row_as_mapping(row))
                    id_ = values['id']

                    if with_publications:
                        # Move the entries relating to the publication table
                        # to another dictionary.
                        pub_id = values.pop('pp_pub_id')
                        pub = {'id': pub_id, 'proposal_id': None}
                        for col in [x.name for x in non_id_pub_columns]:
                            pub[col] = values.pop(col)
                        if pub_id is None:
                            pub = None
                        else:
                            pub = PrevProposalPub(**pub)

                        # Either make a new entry in the result table or just
                        # add the publication to it if it already exists.
                        if id_ in ans and (pub is not None):
                            ans[id_].publications.append(pub)
                        else:
                            ans[id_] = PrevProposal(
                                publications=([] if pub is None else [pub]),
                                **values)

                    else:
                        ans[id_] = PrevProposal(
                            publications=None, **values)

        return ans

    def search_prev_proposal_pub(self, state=None, type_=None,
                                 with_proposal_id=False, order_by_date=False):
        """
        Search for publications associated with previous proposals.

        If requested, include the identifier of the parent proposal.
        (I.e. return prev_proposal.this_proposal_id,
        not prev_proposal.proposal_id).
        """

        select_columns = [prev_proposal_pub]
        select_from = prev_proposal_pub

        default = {
            'proposal_id': None,
        }

        if with_proposal_id:
            select_columns.append(
                prev_proposal.c.this_proposal_id.label('proposal_id'))
            select_from = select_from.join(prev_proposal)
            del default['proposal_id']

        stmt = select(select_columns).select_from(select_from)

        if state is not None:
            if is_list_like(state):
                stmt = stmt.where(prev_proposal_pub.c.state.in_(state))
            else:
                stmt = stmt.where(prev_proposal_pub.c.state == state)

        if type_ is not None:
            if is_list_like(type_):
                stmt = stmt.where(prev_proposal_pub.c.type.in_(type_))
            else:
                stmt = stmt.where(prev_proposal_pub.c.type == type_)

        if order_by_date:
            stmt = stmt.order_by(prev_proposal_pub.c.edited.desc())

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt):
                values = default.copy()
                values.update(**row_as_mapping(row))
                ans[values['id']] = PrevProposalPub(**values)

        return ans

    def search_proposal(self, call_id=None, facility_id=None, proposal_id=None,
                        person_id=None, person_is_editor=None, state=None,
                        type_=None,
                        with_member_pi=False, with_members=False,
                        with_reviewers=False,
                        with_review_info=False, with_review_text=False,
                        with_reviewer_role=None, with_review_state=None,
                        with_reviewer_notified=None, with_reviewer_accepted=(),
                        with_reviewer_thanked=(),
                        with_reviewer_note=False,
                        reviewer_person_id=None,
                        with_categories=False,
                        with_decision=False, with_decision_note=False,
                        decision_accept=None, decision_ready=None,
                        decision_accept_defined=None,
                        proposal_number=None, call_type=None,
                        semester_code=None, queue_code=None, queue_id=None,
                        category=None,
                        _conn=None):
        """
        Search for proposals.

        If "person_id" is specified, then this method searches for proposals
        with this person as a member, and also sets "member" in the
        returned "Proposal" object to a "MemberInfo" object summarizing
        that person's role.  Alternatively if "with_member_pi" is enabled, then
        the PI's information is returned as a "MemberPIInfo" object.

        Otherwise if "with_members" is set, then the "Proposal" object's
        "members" attribute is a "MemberCollection" with information about
        all the members of the proposal.

        If "with_reviewers" is set then the "Proposal" object's "reviewers"
        attribute is a "ReviewerCollection" with information about the
        proposal's reviewers.  The contents of this collection are influenced
        by the "with_review_info", "with_review_text", "with_reviewer_role",
        "with_review_state", "with_reviewer_note" arguments.

        However if "reviewer_person_id" is set then the "reviewer" attribute
        in the results is a "ReviewerInfo" object describing the role of
        the given person.  Since in this mode there may be more than one
        result per proposal, the keys in the returned result collection
        are reviewer identifiers rather than proposal identifiers.
        """

        default = {}

        select_columns = [
            proposal,
            call.c.semester_id,
            semester.c.name.label('semester_name'),
            semester.c.code.label('semester_code'),
            semester.c.date_start.label('semester_start'),
            semester.c.date_end.label('semester_end'),
            call.c.queue_id,
            queue.c.name.label('queue_name'),
            queue.c.code.label('queue_code'),
            call.c.type.label('call_type'),
            call.c.separate.label('call_separate'),
            call.c.hidden.label('call_hidden'),
            semester.c.facility_id,
            call.c.abst_word_lim,
            call.c.tech_word_lim,
            call.c.tech_fig_lim,
            call.c.tech_page_lim,
            call.c.sci_word_lim,
            call.c.sci_fig_lim,
            call.c.sci_page_lim,
            call.c.capt_word_lim,
            call.c.expl_word_lim,
            call.c.date_close,
            call.c.multi_semester,
            call.c.cnrq_word_lim,
            call.c.cnrq_fig_lim,
            call.c.cnrq_page_lim,
        ]

        select_from = proposal.join(call).join(semester).join(queue)

        # Determine query: add member results if person_id specified.
        if person_id is not None:
            select_columns.extend([
                member.c.id.label('member_id'),
                member.c.pi,
                member.c.editor,
                member.c.observer,
                member.c.person_id,
            ])
            select_from = select_from.join(member)

        elif with_member_pi:
            select_columns.extend([
                member.c.person_id,
                person.c.name.label('pi_name'),
                person.c.public.label('pi_public'),
                person.c.user_id.label('pi_user_id'),
                affiliation.c.name.label('pi_affiliation'),
            ])
            select_from = select_from.outerjoin(
                member, and_(
                    proposal.c.id == member.c.proposal_id,
                    member.c.pi)
            ).outerjoin(
                person,
                member.c.person_id == person.c.id
            ).outerjoin(
                affiliation,
                member.c.affiliation_id == affiliation.c.id
            )

        if reviewer_person_id:
            select_columns.extend([
                reviewer.c.id.label('reviewer_id'),
                reviewer.c.role.label('reviewer_role'),
                self._expr_review_state().label('review_state'),
                reviewer.c.person_id.label('reviewer_person_id'),
                reviewer.c.accepted.label('reviewer_accepted'),
            ])
            select_from = select_from.join(
                reviewer,
                proposal.c.id == reviewer.c.proposal_id
            ).outerjoin(review)

        if with_decision:
            select_columns.extend([
                case([
                    (decision.c.proposal_id.isnot(None), True)
                ], else_=False).label('has_decision'),
                decision.c.accept.label('decision_accept'),
                decision.c.exempt.label('decision_exempt'),
                decision.c.ready.label('decision_ready'),
            ])
        else:
            default.update({
                'has_decision': None,
                'decision_accept': None,
                'decision_exempt': None,
                'decision_ready': None,
            })

        if with_decision_note:
            select_columns.extend([
                decision.c.note.label('decision_note'),
                decision.c.note_format.label('decision_note_format'),
            ])
        else:
            default.update({
                'decision_note': None,
                'decision_note_format': None,
            })

        if (with_decision or with_decision_note or
                (decision_accept is not None) or
                (decision_ready is not None) or
                (decision_accept_defined is not None)):

            select_from = select_from.outerjoin(
                decision,
                proposal.c.id == decision.c.proposal_id)

        if category is not None:
            select_from = select_from.join(
                proposal_category,
                proposal.c.id == proposal_category.c.proposal_id)

        stmt = select(select_columns).select_from(select_from)

        # Determine constraints.
        if call_id is not None:
            stmt = stmt.where(proposal.c.call_id == call_id)

        if facility_id is not None:
            if is_list_like(facility_id):
                stmt = stmt.where(semester.c.facility_id.in_(facility_id))
            else:
                stmt = stmt.where(semester.c.facility_id == facility_id)

        if queue_id is not None:
            if is_list_like(queue_id):
                stmt = stmt.where(call.c.queue_id.in_(queue_id))
            else:
                stmt = stmt.where(call.c.queue_id == queue_id)

        if proposal_id is not None:
            if is_list_like(proposal_id):
                stmt = stmt.where(proposal.c.id.in_(proposal_id))
            else:
                stmt = stmt.where(proposal.c.id == proposal_id)

        if person_id is not None:
            stmt = stmt.where(member.c.person_id == person_id)

            if person_is_editor is not None:
                if person_is_editor:
                    stmt = stmt.where(member.c.editor)
                else:
                    stmt = stmt.where(not_(member.c.editor))

        if reviewer_person_id is not None:
            stmt = stmt.where(reviewer.c.person_id == reviewer_person_id)

            if with_reviewer_role is not None:
                if is_list_like(with_reviewer_role):
                    stmt = stmt.where(reviewer.c.role.in_(with_reviewer_role))
                else:
                    stmt = stmt.where(reviewer.c.role == with_reviewer_role)

            if with_review_state is not None:
                if is_list_like(with_review_state):
                    stmt = stmt.where(self._expr_review_state().in_(with_review_state))
                else:
                    stmt = stmt.where(self._expr_review_state() == with_review_state)

        if state is not None:
            if is_list_like(state):
                stmt = stmt.where(proposal.c.state.in_(state))
            else:
                stmt = stmt.where(proposal.c.state == state)

        if type_ is not None:
            if is_list_like(type_):
                stmt = stmt.where(proposal.c.type.in_(type_))
            else:
                stmt = stmt.where(proposal.c.type == type_)

        if decision_accept is not None:
            if decision_accept:
                stmt = stmt.where(decision.c.accept)
            else:
                stmt = stmt.where(not_(decision.c.accept))

        if decision_ready is not None:
            if decision_ready:
                stmt = stmt.where(decision.c.ready)
            else:
                stmt = stmt.where(not_(decision.c.ready))

        if decision_accept_defined is not None:
            if decision_accept_defined:
                stmt = stmt.where(decision.c.accept.isnot(None))
            else:
                stmt = stmt.where(decision.c.accept.is_(None))

        if proposal_number is not None:
            stmt = stmt.where(proposal.c.number == proposal_number)

        if call_type is not None:
            stmt = stmt.where(call.c.type == call_type)

        if semester_code is not None:
            stmt = stmt.where(semester.c.code == semester_code)

        if queue_code is not None:
            stmt = stmt.where(queue.c.code == queue_code)

        if category is not None:
            if is_list_like(category):
                stmt = stmt.where(proposal_category.c.category_id.in_(category))
            else:
                stmt = stmt.where(proposal_category.c.category_id == category)

        # Determine ordering: don't sort if only selecting one proposal.
        # This ordering was originally intended for the personal proposal list
        # and personal review list.  However these pages now perform their own
        # sorting of the proposals.  (The ordering specified here should still
        # be useful as a pre-sort for those operations.)
        # If other pages rely on the sort order of results of this method,
        # perhaps the ordering should be controlled by more arguments.
        if proposal_id is None:
            stmt = stmt.order_by(
                semester.c.facility_id,
                call.c.semester_id,
                call.c.queue_id,
                call.c.type,
                proposal.c.number)

        # Perform query and collect results.
        ans = ProposalCollection()
        proposal_ids = set()
        previous_proposal_ids = {}
        extra = {}
        extra_via_previous = set()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt):
                member_info = None
                reviewer_info = None
                values = default.copy()
                values.update(**row_as_mapping(row))
                row_key = values['id']
                proposal_ids.add(row_key)

                if person_id is not None:
                    member_info = MemberInfo(
                        values.pop('member_id'),
                        values.pop('pi'),
                        values.pop('editor'),
                        values.pop('observer'),
                        values.pop('person_id'))

                elif with_member_pi:
                    member_info = MemberPIInfo(
                        values.pop('person_id'),
                        values.pop('pi_name'),
                        values.pop('pi_public'),
                        values.pop('pi_user_id'),
                        values.pop('pi_affiliation'))

                    # If there was no such person, set the whole "member_info"
                    # to None, but do this after popping the values.
                    if member_info.person_id is None:
                        member_info = None

                if reviewer_person_id is not None:
                    # There may be more than one reviewer record per person
                    # and proposal, therefore in this case we need to use the
                    # reviewer ID as the result collection key.
                    row_key = values['reviewer_id']

                    reviewer_info = ReviewerInfo(
                        id=values.pop('reviewer_id'),
                        role=values.pop('reviewer_role'),
                        review_state=values.pop('review_state'),
                        person_id=values.pop('reviewer_person_id'),
                        proposal_id=values['id'],
                        accepted=values.pop('reviewer_accepted'))

                ans[row_key] = Proposal(
                    member=member_info, members=None,
                    reviewer=reviewer_info, reviewers=None,
                    categories=None,
                    **values)

            # Now check if there is extra information which we need to attach.
            if with_members:
                extra['members'] = self.search_member(
                    proposal_id=proposal_ids, _conn=conn)

            if with_reviewers:
                extra['reviewers'] = self.search_reviewer(
                    proposal_id=proposal_ids,
                    with_review=with_review_info,
                    with_review_text=with_review_text,
                    role=with_reviewer_role,
                    review_state=with_review_state,
                    notified=with_reviewer_notified,
                    accepted=with_reviewer_accepted,
                    thanked=with_reviewer_thanked,
                    with_note=with_reviewer_note,
                    _conn=conn)

            if with_categories:
                (all_proposal_ids, previous_proposal_ids) = \
                    self.get_original_proposal_ids(ans, _conn=conn)

                extra_via_previous.add('categories')
                extra['categories'] = self.search_proposal_category(
                    proposal_id=all_proposal_ids, _conn=conn)

        # Attach extra information to the proposal records.
        # Do this outside the database transaction block as the
        # database querying process is complete.
        if extra:
            for key in list(ans.keys()):
                row = ans[key]
                id_ = row.id

                ans[key] = row._replace(**{
                    k: v.subset_by_proposal(
                        previous_proposal_ids.get(id_, id_)
                        if k in extra_via_previous else id_)
                    for (k, v) in extra.items()})

        return ans

    def search_proposal_annotation(self, proposal_id, type_=None, _conn=None):
        """
        Search for annotations associated with a proposal.
        """

        stmt = proposal_annotation.select()

        if proposal_id is not None:
            stmt = stmt.where(proposal_annotation.c.proposal_id == proposal_id)

        if type_ is not None:
            stmt = stmt.where(proposal_annotation.c.type == type_)

        ans = AnnotationCollection()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt.order_by(
                    proposal_annotation.c.date.asc())):
                ans[row.id] = Annotation(**row_as_mapping(row))

        return ans

    def search_proposal_category(self, proposal_id, _conn=None):
        """
        Search for the categories associated with a proposal.
        """

        stmt = select([
            proposal_category,
            category.c.name.label('category_name'),
            category.c.name_abbr.label('category_name_abbr'),
        ]).select_from(proposal_category.join(category))

        iter_field = None
        iter_list = None

        if proposal_id is not None:
            if is_list_like(proposal_id):
                assert iter_field is None
                iter_field = proposal_category.c.proposal_id
                iter_list = proposal_id
            else:
                stmt = stmt.where(
                    proposal_category.c.proposal_id == proposal_id)

        ans = ProposalCategoryCollection()

        with self._transaction(_conn=_conn) as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(
                        iter_stmt.order_by(category.c.name.asc())):
                    ans[row.id] = ProposalCategory(**row_as_mapping(row))

        return ans

    def search_proposal_figure(
            self, proposal_id=None, role=None, state=None,
            link_id=None, fig_id=None,
            with_caption=False, with_uploader_name=False,
            with_has_preview=False, order_by_date=False,
            no_link=False):
        where_extra = []
        select_extra = []
        default_extra = {}

        if proposal_id is not None:
            if no_link:
                raise Error('proposal_id specified with no_link')
            where_extra.append(proposal_fig_link.c.proposal_id == proposal_id)

        if role is not None:
            if no_link:
                raise Error('role specified with no_link')
            where_extra.append(proposal_fig_link.c.role == role)

        if no_link:
            default_extra.update({
                'proposal_id': None,
                'role': None,
            })

        else:
            select_extra.extend([
                proposal_fig_link.c.proposal_id,
                proposal_fig_link.c.role,
            ])

        return self._search_figure(
            proposal_fig, (None if no_link else proposal_fig_link),
            ProposalFigureInfo, ProposalFigureCollection,
            state, link_id, fig_id,
            with_caption, with_uploader_name, order_by_date,
            with_has_preview_table=(
                proposal_fig_preview if with_has_preview else None),
            select_extra=select_extra, default_extra=default_extra,
            where_extra=where_extra)

    def _search_figure(
            self, table, table_link, result_class, result_collection_class,
            state, link_id, fig_id,
            with_caption, with_uploader_name, order_by_date,
            with_has_preview_table=None,
            select_extra=[], default_extra={}, where_extra=[]):
        select_from = table

        select_columns = [
            table.c.id.label('fig_id'),
            table.c.type,
            table.c.state,
            table.c.md5sum,
            table.c.filename,
            table.c.uploaded,
            table.c.uploader,
        ]

        select_columns.extend(select_extra)

        default = {
            'caption': None,
            'has_preview': None,
            'uploader_name': None,
        }

        default.update(default_extra)

        if table_link is None:
            default.update({
                'sort_order': None,
                'id': None,
            })

            key_col = 'fig_id'

        else:
            select_from = select_from.join(table_link)

            select_columns.extend([
                table_link.c.sort_order,
                table_link.c.id,
            ])

            key_col = 'id'

        if with_caption:
            if table_link is None:
                raise Error('with_caption specified with no link table')
            select_columns.append(table_link.c.caption)
            del default['caption']

        if with_uploader_name:
            select_columns.append(person.c.name.label('uploader_name'))
            select_from = select_from.join(person)
            del default['uploader_name']

        if with_has_preview_table is not None:
            select_columns.append(case([
                (with_has_preview_table.c.fig_id.isnot(None), True)
                ], else_=False).label('has_preview'))
            select_from = select_from.outerjoin(with_has_preview_table)
            del default['has_preview']

        stmt = select(select_columns).select_from(select_from)

        for where_clause in where_extra:
            stmt = stmt.where(where_clause)

        if state is not None:
            if is_list_like(state):
                stmt = stmt.where(table.c.state.in_(state))
            else:
                stmt = stmt.where(table.c.state == state)

        if fig_id is not None:
            stmt = stmt.where(table.c.id == fig_id)

        if link_id is not None:
            if table_link is None:
                raise Error('link_id specified with no link table')
            stmt = stmt.where(table_link.c.id == link_id)

        if order_by_date:
            stmt = stmt.order_by(table.c.uploaded.desc())
        elif table_link is not None:
            stmt = stmt.order_by(table_link.c.sort_order.asc())

        ans = result_collection_class()

        with self._transaction() as conn:
            for row in conn.execute(stmt):
                values = default.copy()
                values.update(**row_as_mapping(row))
                ans[getattr(row, key_col)] = result_class(**values)

        return ans

    def search_proposal_pdf(
            self, proposal_id=None, role=None, state=None,
            with_uploader_name=False, order_by_date=False,
            no_link=False):
        select_from = proposal_pdf

        select_columns = [
            proposal_pdf.c.id.label('pdf_id'),
            proposal_pdf.c.md5sum,
            proposal_pdf.c.state,
            proposal_pdf.c.pages,
            proposal_pdf.c.filename,
            proposal_pdf.c.uploaded,
            proposal_pdf.c.uploader,
        ]

        default = {
            'uploader_name': None,
        }

        if no_link:
            default.update({
                'proposal_id': None,
                'role': None,
                'id': None,
            })

            key_col = 'pdf_id'

        else:
            select_from = select_from.join(proposal_pdf_link)

            select_columns.extend([
                proposal_pdf_link.c.proposal_id,
                proposal_pdf_link.c.role,
                proposal_pdf_link.c.id,
            ])

            key_col = 'id'

        if with_uploader_name:
            select_columns.append(person.c.name.label('uploader_name'))
            select_from = select_from.join(person)
            del default['uploader_name']

        stmt = select(select_columns).select_from(select_from)

        if proposal_id is not None:
            if no_link:
                raise Error('proposal_id specified with no_link')
            stmt = stmt.where(proposal_pdf_link.c.proposal_id == proposal_id)

        if role is not None:
            if no_link:
                raise Error('role specified with no_link')
            stmt = stmt.where(proposal_pdf_link.c.role == role)

        if state is not None:
            if is_list_like(state):
                stmt = stmt.where(proposal_pdf.c.state.in_(state))
            else:
                stmt = stmt.where(proposal_pdf.c.state == state)

        if order_by_date:
            stmt = stmt.order_by(proposal_pdf.c.uploaded.desc())

        ans = ProposalTextCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt):
                values = default.copy()
                values.update(**row_as_mapping(row))
                ans[getattr(row, key_col)] = ProposalPDFInfo(**values)

        return ans

    def search_proposal_text(
            self, proposal_id=None, role=None,
            with_text=False,
            _conn=None):
        default = {}

        select_columns = [
            proposal_text.c.id.label('text_id'),
            proposal_text_link.c.proposal_id,
            proposal_text_link.c.role,
            proposal_text.c.format,
            proposal_text.c.words,
            proposal_text.c.edited,
            proposal_text.c.editor,
            person.c.name.label('editor_name'),
            proposal_text_link.c.id,
        ]

        if with_text:
            select_columns.append(proposal_text.c.text)
        else:
            default['text'] = None

        select_from = proposal_text.join(proposal_text_link).join(person)

        stmt = select(select_columns).select_from(select_from)

        if proposal_id is not None:
            stmt = stmt.where(proposal_text_link.c.proposal_id == proposal_id)

        if role is not None:
            stmt = stmt.where(proposal_text_link.c.role == role)

        ans = ProposalTextCollection()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt):
                values = default.copy()
                values.update(**row_as_mapping(row))
                ans[values['id']] = ProposalText(**values)

        return ans

    def search_queue(self, facility_id=None, has_affiliation=None):
        stmt = select([
            queue.c.id,
            queue.c.facility_id,
            queue.c.name,
            queue.c.code,
        ])

        if facility_id is not None:
            stmt = stmt.where(queue.c.facility_id == facility_id)

        if has_affiliation is not None:
            affiliation_queues = select([affiliation.c.queue_id]).distinct()

            if has_affiliation:
                stmt = stmt.where(queue.c.id.in_(affiliation_queues))
            else:
                stmt = stmt.where(queue.c.id.notin_(affiliation_queues))

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by((queue.c.name))):
                ans[row.id] = QueueInfo(**row_as_mapping(row))

        return ans

    def search_request_prop_copy(
            self, request_id=None, proposal_id=None, state=None,
            continuation=None, **kwargs):
        where_extra = []

        if continuation is not None:
            if continuation:
                where_extra.append(request_prop_copy.c.continuation)
            else:
                where_extra.append(not_(request_prop_copy.c.continuation))

        return self._search_request_prop(
            request_prop_copy, RequestPropCopy,
            request_id=request_id, proposal_id=proposal_id, state=state,
            where_extra=where_extra,
            **kwargs)

    def search_request_prop_pdf(
            self, request_id=None, proposal_id=None, state=None, **kwargs):
        return self._search_request_prop(
            request_prop_pdf, RequestPropPDF,
            request_id=request_id, proposal_id=proposal_id, state=state,
            **kwargs)

    def _search_request_prop(
            self, table, result_class, request_id, proposal_id, state,
            requested_before=None, processed_before=None,
            with_requester_name=False,
            where_extra=[],
            _conn=None):
        select_from = table
        select_columns = [table]

        default = {
            'requester_name': None,
        }

        if with_requester_name:
            select_columns.append(person.c.name.label('requester_name'))
            select_from = select_from.join(
                person, table.c.requester == person.c.id)
            del default['requester_name']

        stmt = select(select_columns).select_from(select_from)

        for where_clause in where_extra:
            stmt = stmt.where(where_clause)

        iter_field = None
        iter_list = None

        if request_id is not None:
            stmt = stmt.where(table.c.id == request_id)

        if proposal_id is not None:
            if is_list_like(proposal_id):
                assert iter_field is None
                iter_field = table.c.proposal_id
                iter_list = proposal_id
            else:
                stmt = stmt.where(
                    table.c.proposal_id == proposal_id)

        if state is not None:
            if is_list_like(state):
                stmt = stmt.where(table.c.state.in_(state))
            else:
                stmt = stmt.where(table.c.state == state)

        if requested_before is not None:
            stmt = stmt.where(table.c.requested < requested_before)

        if processed_before is not None:
            stmt = stmt.where(table.c.processed < processed_before)

        ans = RequestCollection()

        with self._transaction(_conn=_conn) as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(
                        iter_stmt.order_by(table.c.id.asc())):
                    values = default.copy()
                    values.update(**row_as_mapping(row))
                    ans[values['id']] = result_class(**values)

        return ans

    def search_target(self, proposal_id):
        """
        Retrieve the targets of a given proposal.
        """

        iter_field = None
        iter_list = None

        stmt = target.select()

        if is_list_like(proposal_id):
            assert iter_field is None
            iter_field = target.c.proposal_id
            iter_list = proposal_id
        else:
            stmt = stmt.where(target.c.proposal_id == proposal_id)

        ans = TargetCollection()

        with self._transaction() as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(
                        iter_stmt.order_by(target.c.sort_order.asc())):
                    ans[row.id] = Target(**row_as_mapping(row))

        return ans

    def set_call_preamble(self, type_class, semester_id, type_,
                          description, description_format,
                          _test_skip_check=False):
        if not type_class.is_valid(type_):
            raise UserError('The selected call type is not recognised.')
        if not description_format:
            raise UserError('Description format not specified.')
        if not FormatType.is_valid(description_format, is_system=True):
            raise UserError('Description format not recognised.')

        with self._transaction() as conn:
            if not _test_skip_check:
                try:
                    self.get_semester(None, semester_id, _conn=conn)
                except NoSuchRecord as e:
                    raise ConsistencyError(e.message)

            preamble_id = self._get_call_preamble_id(
                conn, semester_id, type_)

            values = {
                call_preamble.c.description: description,
                call_preamble.c.description_format: description_format,
            }

            if preamble_id is not None:
                result = conn.execute(call_preamble.update().where(and_(
                    call_preamble.c.semester_id == semester_id,
                    call_preamble.c.type == type_
                )).values(values))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating call preamble {} {}',
                        semester_id, type_)
            else:
                values.update({
                    call_preamble.c.semester_id: semester_id,
                    call_preamble.c.type: type_,
                })

                result = conn.execute(
                    call_preamble.insert().values(values))

                preamble_id = result.inserted_primary_key[0]

        return preamble_id

    def set_member_institution(
            self, member_id, institution_id, _test_skip_check=False):
        with self._transaction() as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, institution, institution_id):
                raise ConsistencyError(
                    'institution does not exist with id {}', institution_id)

            result = conn.execute(member.update().where(
                member.c.id == member_id
            ).values({
                member.c.institution_id: institution_id,
            }))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating member {} institution',
                    member_id)

    def set_proposal_figure_preview(self, fig_id, preview):
        self._set_figure_alternate(
            proposal_fig_preview.c.preview, fig_id, preview)

    def set_proposal_figure_thumbnail(self, fig_id, thumbnail):
        self._set_figure_alternate(
            proposal_fig_thumbnail.c.thumbnail, fig_id, thumbnail)

    def _set_figure_alternate(self, column, fig_id, alternate):
        table = column.table

        with self._transaction() as conn:
            if 0 < conn.execute(select([count(column)]).where(
                    table.c.fig_id == fig_id)).scalar():
                # Update existing alternate.
                result = conn.execute(table.update().where(
                    table.c.fig_id == fig_id
                ).values({
                    column: alternate,
                }))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating figure alternate')

            else:
                # Add new alternate.
                conn.execute(table.insert().values({
                    table.c.fig_id: fig_id,
                    column: alternate,
                }))

    def set_proposal_pdf(self, role_class, proposal_id, role, pdf, pages,
                         filename, uploader_person_id, _test_skip_check=False):
        """
        Insert or update a given proposal PDF.

        :return: a (`link_id`, `pdf_id`) tuple
        """

        if not role_class.is_valid(role):
            raise FormattedError('proposal text role not recognised: {}',
                                 role)

        with self._transaction() as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, person, uploader_person_id)):
                raise ConsistencyError('person does not exist with id={}',
                                       uploader_person_id)

            link_id = self._get_proposal_text_id(
                conn, proposal_pdf_link, proposal_id, role)

            result = conn.execute(proposal_pdf.insert().values({
                proposal_pdf.c.pdf: pdf,
                proposal_pdf.c.md5sum: str_to_unicode(md5(pdf).hexdigest()),
                proposal_pdf.c.state: AttachmentState.NEW,
                proposal_pdf.c.pages: pages,
                proposal_pdf.c.filename: filename,
                proposal_pdf.c.uploaded: datetime.utcnow(),
                proposal_pdf.c.uploader: uploader_person_id,
            }))

            pdf_id = result.inserted_primary_key[0]

            if link_id is None:
                result = conn.execute(proposal_pdf_link.insert().values({
                    proposal_pdf_link.c.proposal_id: proposal_id,
                    proposal_pdf_link.c.role: role,
                    proposal_pdf_link.c.pdf_id: pdf_id,
                }))

                link_id = result.inserted_primary_key[0]

            else:
                result = conn.execute(proposal_pdf_link.update().where(
                    proposal_pdf_link.c.id == link_id
                ).values({
                    proposal_pdf_link.c.pdf_id: pdf_id,
                }))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating proposal PDF {} role {}',
                        proposal_id, role)

                self._remove_orphan_records(
                    conn, proposal_pdf, proposal_pdf_link.c.pdf_id)

            # Delete any previous proposal text for the same role which
            # this PDF is replacing.
            self.delete_proposal_text(
                proposal_id, role,
                _skip_check=True, _allow_count=(0, 1), _conn=conn)

            # Also delete any previous figures attached for the old text
            # version.
            self.delete_proposal_figure(
                proposal_id, role, id_=None,
                _allow_any=True, _conn=conn)

        return (link_id, pdf_id)

    def set_proposal_pdf_preview(self, pdf_id, pngs):
        """
        Set the preview images for a PDF file attached to a proposal.
        """

        stmt = proposal_pdf_preview.insert()
        n = 0

        with self._transaction() as conn:
            conn.execute(proposal_pdf_preview.delete().where(
                proposal_pdf_preview.c.pdf_id == pdf_id))

            for png in pngs:
                n += 1

                conn.execute(stmt.values({
                    proposal_pdf_preview.c.pdf_id: pdf_id,
                    proposal_pdf_preview.c.page: n,
                    proposal_pdf_preview.c.preview: png,
                }))

    def set_proposal_text(self, role_class, proposal_id, role, text, format,
                          words, editor_person_id,
                          _test_skip_check=False):
        """
        Insert or update a given piece of proposal text.

        :return: a (`link_id`, `text_id`) tuple
        """

        if not format:
            raise UserError('Text format not specified.')
        if not FormatType.is_valid(format):
            raise UserError('Text format not recognised.')
        if not role_class.is_valid(role):
            raise FormattedError('proposal text role not recognised: {}',
                                 role)

        with self._transaction() as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, person, editor_person_id)):
                raise ConsistencyError('person does not exist with id={}',
                                       editor_person_id)

            link_id = self._get_proposal_text_id(
                conn, proposal_text_link, proposal_id, role)

            result = conn.execute(proposal_text.insert().values({
                proposal_text.c.text: text,
                proposal_text.c.format: format,
                proposal_text.c.words: words,
                proposal_text.c.edited: datetime.utcnow(),
                proposal_text.c.editor: editor_person_id,
            }))

            text_id = result.inserted_primary_key[0]

            if link_id is None:
                result = conn.execute(proposal_text_link.insert().values({
                    proposal_text_link.c.proposal_id: proposal_id,
                    proposal_text_link.c.role: role,
                    proposal_text_link.c.text_id: text_id,
                }))

                link_id = result.inserted_primary_key[0]

            else:
                result = conn.execute(proposal_text_link.update().where(
                    proposal_text_link.c.id == link_id
                ).values({
                    proposal_text_link.c.text_id: text_id,
                }))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating proposal text {} role {}',
                        proposal_id, role)

                self._remove_orphan_records(
                    conn, proposal_text, proposal_text_link.c.text_id)

            # Delete any previous proposal PDF for the same role which
            # this text is replacing.
            self.delete_proposal_pdf(
                proposal_id, role,
                _skip_check=True, _allow_count=(0, 1), _conn=conn)

        return (link_id, text_id)

    def sync_affiliation_weight(self, type_class, call_id, records):
        """
        Update the affiliation weighting values and possible hidden
        and type overrides for a given call.

        This takes a set of Affiliation records including weights,
        where the "id" is actually the "affiliation.id" rather than
        the "affiliation_weight.id".
        """

        records.validate(type_class, allow_type_none=True)

        with self._transaction() as conn:
            if not self._exists_id(conn, call, call_id):
                raise ConsistencyError(
                    'call does not exist with id={}', call_id)

            return self._sync_records(
                conn, affiliation_weight,
                key_column=affiliation_weight.c.call_id, key_value=call_id,
                records=records,
                update_columns=(
                    affiliation_weight.c.weight,
                    affiliation_weight.c.hidden,
                    affiliation_weight.c.type,
                ),
                record_match_column=affiliation_weight.c.affiliation_id)

    def sync_call_call_mid_close(self, call_id, records):
        """
        Update intermediate close records associated with a call.

        Note: the sync operation is currently performed without handling
        of the unique constraint (on date) so circular updates will
        not succeed.
        """

        with self._transaction() as conn:
            if not self._exists_id(conn, call, call_id):
                raise ConsistencyError(
                    'call does not exist with id={}', call_id)

            return self._sync_records(
                conn, call_mid_close,
                key_column=call_mid_close.c.call_id, key_value=call_id,
                records=records,
                update_columns=(call_mid_close.c.date,))

    def sync_facility_category(self, facility_id, records):
        """
        Update the categories available for proposal for a facility.
        """

        with self._transaction() as conn:
            if not self._exists_id(conn, facility, facility_id):
                raise ConsistencyError(
                    'facility does not exist with id={}', facility_id)

            return self._sync_records(
                conn, category, category.c.facility_id, facility_id, records,
                unique_columns=(category.c.name,),
                forbid_circular_reinsert=True)

    def sync_proposal_category(self, proposal_id, records, _conn=None):
        """
        Update the categories associated with a proposal.
        """

        with self._transaction(_conn=_conn) as conn:
            return self._sync_records(
                conn, proposal_category, proposal_category.c.proposal_id,
                proposal_id, records)

    def sync_proposal_figure(self, proposal_id, role, records):
        """
        Update the figures for a proposal.

        Currently only deleting figures and changing the sort order
        is supported.
        """

        records.ensure_sort_order()

        with self._transaction() as conn:
            if not self._exists_id(conn, proposal, proposal_id):
                raise ConsistencyError(
                    'proposal does not exist with id={}', proposal_id)

            (n_insert, n_update, n_delete) = self._sync_records(
                conn, proposal_fig_link,
                (proposal_fig_link.c.proposal_id, proposal_fig_link.c.role),
                (proposal_id, role),
                records,
                update_columns=(
                    proposal_fig_link.c.sort_order,
                ), forbid_add=True)

            if n_delete:
                self._remove_orphan_records(
                    conn, proposal_fig, proposal_fig_link.c.fig_id)

        return (n_insert, n_update, n_delete)

    def sync_proposal_member(self, proposal_id, records, editor_person_id):
        """
        Update the member records for a proposal.

        Only the "pi", "editor" and "observer" flags are updated.
        """

        records.validate(editor_person_id=editor_person_id)

        records.ensure_sort_order()

        with self._transaction() as conn:
            if not self._exists_id(conn, proposal, proposal_id):
                raise ConsistencyError(
                    'proposal does not exist with id={}', proposal_id)

            return self._sync_records(
                conn, member, member.c.proposal_id, proposal_id, records,
                update_columns=(
                    member.c.sort_order,
                    member.c.pi, member.c.editor, member.c.observer,
                    member.c.reviewer,
                    member.c.affiliation_id
                ), forbid_add=True)

    def sync_proposal_member_institution(self, proposal_id, records):
        """
        Update the institution of members of a proposal.
        """

        with self._transaction() as conn:
            return self._sync_records(
                conn, member, member.c.proposal_id, proposal_id, records,
                update_columns=(member.c.institution_id,),
                forbid_add=True, forbid_delete=True)

    def sync_proposal_member_student(self, proposal_id, records):
        """
        Update the 'student' flag of members of a proposal.
        """

        with self._transaction() as conn:
            return self._sync_records(
                conn, member, member.c.proposal_id, proposal_id, records,
                update_columns=(member.c.student,),
                forbid_add=True, forbid_delete=True)

    def sync_proposal_prev_proposal(
            self, proposal_id, records, retain_resolved=False):
        """
        Update the prev_proposal records related to a proposal.

        :param retain_resolved: if true, for newly added records, retain
            the resolved information (title, author and year).  (For existing
            records being updated, these values are cleared for now.)
        """

        records.validate()

        records.ensure_sort_order()

        # Initialize debugging counters.
        n_insert = n_update = n_delete = 0

        with self._transaction() as conn:
            existing = self.search_prev_proposal(proposal_id=proposal_id,
                                                 _conn=conn)

            for value in records.values():
                id_ = value.id

                if id_ is None:
                    previous = None
                else:
                    previous = existing.pop(id_, None)

                if previous is None:
                    result = conn.execute(prev_proposal.insert().values({
                        prev_proposal.c.this_proposal_id: proposal_id,
                        prev_proposal.c.proposal_id: value.proposal_id,
                        prev_proposal.c.proposal_code: value.proposal_code,
                        prev_proposal.c.continuation: value.continuation,
                        prev_proposal.c.sort_order: value.sort_order,
                    }))

                    prev_proposal_id = result.inserted_primary_key[0]

                    n_insert += 1

                    # For now, count all changes to publications as "updates".
                    n_update += self._sync_proposal_prev_proposal_pub(
                        conn, prev_proposal_id, [], value.publications,
                        retain_resolved=retain_resolved)

                else:
                    # Check if needs update
                    if ((previous.proposal_id != value.proposal_id) or
                            (previous.proposal_code != value.proposal_code) or
                            (previous.continuation != value.continuation) or
                            (previous.sort_order != value.sort_order)):
                        conn.execute(prev_proposal.update().where(
                            prev_proposal.c.id == id_
                        ).values({
                            prev_proposal.c.proposal_id: value.proposal_id,
                            prev_proposal.c.proposal_code: value.proposal_code,
                            prev_proposal.c.continuation: value.continuation,
                            prev_proposal.c.sort_order: value.sort_order,
                        }))

                        n_update += 1

                    # For now, count all changes to publications as "updates".
                    n_update += self._sync_proposal_prev_proposal_pub(
                        conn, id_,
                        previous.publications, value.publications)

            # Delete remaining un-matched entries.
            for id_ in existing:
                conn.execute(prev_proposal.delete().where(
                    prev_proposal.c.id == id_))

                n_delete += 1

        return (n_insert, n_update, n_delete)

    def _sync_proposal_prev_proposal_pub(
            self, conn, prev_proposal_id, existing, publications,
            retain_resolved=False):
        n_change = 0

        for value in publications:
            try:
                previous = existing.pop(0)
            except IndexError:
                previous = None

            # If it is a "plain" publication reference, insert it in the
            # "ready" state, otherwise mark it as "new" so that we can
            # look up the reference later.
            if value.type == PublicationType.PLAIN:
                new_state = AttachmentState.READY
            else:
                new_state = AttachmentState.NEW

            values = {
                prev_proposal_pub.c.description: value.description,
                prev_proposal_pub.c.type: value.type,
                prev_proposal_pub.c.state: new_state,
                prev_proposal_pub.c.title: None,
                prev_proposal_pub.c.author: None,
                prev_proposal_pub.c.year: None,
                prev_proposal_pub.c.edited: datetime.utcnow(),
            }

            if previous is None:
                if retain_resolved and AttachmentState.is_ready(value.state):
                    values.update({
                        prev_proposal_pub.c.state: value.state,
                        prev_proposal_pub.c.title: value.title,
                        prev_proposal_pub.c.author: value.author,
                        prev_proposal_pub.c.year: value.year,
                    })

                values[prev_proposal_pub.c.prev_proposal_id] = prev_proposal_id

                conn.execute(prev_proposal_pub.insert().values(values))

                n_change += 1

            elif ((previous.description != value.description) or
                    (previous.type != value.type)):
                conn.execute(prev_proposal_pub.update().where(
                    prev_proposal_pub.c.id == previous.id
                ).values(values))

                n_change += 1

        # Delete remaining un-matched entries.
        for previous in existing:
            conn.execute(prev_proposal_pub.delete().where(
                prev_proposal_pub.c.id == previous.id))

            n_change += 1

        return n_change

    def sync_proposal_target(self, proposal_id, records):
        """
        Update the target records for a proposal.
        """

        records.ensure_sort_order()

        with self._transaction() as conn:
            return self._sync_records(
                conn, target, target.c.proposal_id, proposal_id, records)

    def sync_queue_affiliation(self, type_class, queue_id, records):
        """
        Update the affiliation records for a queue to match those
        given by "records".
        """

        records.validate(type_class)

        with self._transaction() as conn:
            if not self._exists_id(conn, queue, queue_id):
                raise ConsistencyError(
                    'queue does not exist with id={}', queue_id)

            return self._sync_records(
                conn, affiliation, affiliation.c.queue_id, queue_id,
                records, unique_columns=(affiliation.c.name,),
                forbid_circular_reinsert=True)

    def update_call(self, call_id, date_open=None, date_close=None,
                    abst_word_lim=None,
                    tech_word_lim=None, tech_fig_lim=None, tech_page_lim=None,
                    sci_word_lim=None, sci_fig_lim=None, sci_page_lim=None,
                    capt_word_lim=None, expl_word_lim=None,
                    tech_note=None, sci_note=None, prev_prop_note=None,
                    note_format=None, multi_semester=None, separate=None,
                    preamble=(), preamble_format=(), hidden=None,
                    allow_continuation=None, cnrq_note=None,
                    cnrq_word_lim=None, cnrq_fig_lim=None, cnrq_page_lim=None,
                    cnrq_max_age=(),
                    _test_skip_check=False):
        """
        Update a call for proposals record.
        """

        values = {}

        if date_open is not None:
            values['date_open'] = date_open
            # If given both dates, we can easily make this sanity check.
            if date_close is not None:
                if date_close < date_open:
                    raise UserError('Closing date is before opening date.')
        if date_close is not None:
            values['date_close'] = date_close
        if abst_word_lim is not None:
            values['abst_word_lim'] = abst_word_lim
        if tech_word_lim is not None:
            values['tech_word_lim'] = tech_word_lim
        if tech_fig_lim is not None:
            values['tech_fig_lim'] = tech_fig_lim
        if tech_page_lim is not None:
            values['tech_page_lim'] = tech_page_lim
        if sci_word_lim is not None:
            values['sci_word_lim'] = sci_word_lim
        if sci_fig_lim is not None:
            values['sci_fig_lim'] = sci_fig_lim
        if sci_page_lim is not None:
            values['sci_page_lim'] = sci_page_lim
        if capt_word_lim is not None:
            values['capt_word_lim'] = capt_word_lim
        if expl_word_lim is not None:
            values['expl_word_lim'] = expl_word_lim
        if tech_note is not None:
            values['tech_note'] = tech_note
        if sci_note is not None:
            values['sci_note'] = sci_note
        if prev_prop_note is not None:
            values['prev_prop_note'] = prev_prop_note
        if cnrq_note is not None:
            values['cnrq_note'] = cnrq_note
        if cnrq_word_lim is not None:
            values['cnrq_word_lim'] = cnrq_word_lim
        if cnrq_fig_lim is not None:
            values['cnrq_fig_lim'] = cnrq_fig_lim
        if cnrq_page_lim is not None:
            values['cnrq_page_lim'] = cnrq_page_lim
        if cnrq_max_age != ():
            values['cnrq_max_age'] = cnrq_max_age
        if note_format is not None:
            if not FormatType.is_valid(note_format, is_system=True):
                raise UserError('Note text format not recognised.')
            values['note_format'] = note_format
        if multi_semester is not None:
            values['multi_semester'] = multi_semester
        if separate is not None:
            values['separate'] = separate

        if preamble != ():
            values['preamble'] = preamble

            if preamble is None:
                preamble_format = None
            elif (preamble_format is None) or (preamble_format == ()):
                raise Error('Preamble text format not specified.')
            elif not FormatType.is_valid(preamble_format, is_system=True):
                raise UserError('Preamble text format not recognised.')

            values['preamble_format'] = preamble_format

        elif preamble_format != ():
            raise Error('Preamble text format specified without preamble.')

        if hidden is not None:
            values['hidden'] = hidden

        if allow_continuation is not None:
            values['allow_continuation'] = allow_continuation

        if not values:
            raise Error('no call updates specified')

        with self._transaction() as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, call, call_id):
                raise ConsistencyError(
                    'call does not exist with id={}', call_id)

            result = conn.execute(call.update().where(
                call.c.id == call_id
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating call with id={}', call_id)

    def update_call_mid_close(self, id_, closed=None, _test_skip_check=False):
        """
        Update a call intermediate close record.
        """

        values = {}

        if closed is not None:
            values[call_mid_close.c.closed] = closed

        if not values:
            raise Error('no intermediate close updates specified')

        with self._transaction() as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, call_mid_close, id_):
                raise ConsistencyError(
                    'call intermediate close does not exist with id={}', id_)

            result = conn.execute(call_mid_close.update().where(
                call_mid_close.c.id == id_
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating call inter. close with id={}',
                    id_)

    def update_prev_proposal_pub(self, type_=None, description=None,
                                 pp_pub_id=None,
                                 state=None, title=(), author=(),
                                 year=(), state_prev=None):
        """
        Update all previous proposal publication records for the given
        reference.

        Can either select records to update by the "pp_pub_id"
        (prev_proposal_pub.id) or by type and description,
        in which case all matching entries are updated.
        """

        stmt = prev_proposal_pub.update()

        # Determine how to select the records to update.
        has_type_desc = ((type_ is not None) and (description is not None))

        if pp_pub_id is not None:
            if has_type_desc:
                raise Error('previous proposal publication identified by both '
                            'ID and type and description')

            stmt = stmt.where(prev_proposal_pub.c.id == pp_pub_id)

        elif has_type_desc:
            stmt = stmt.where(and_(
                prev_proposal_pub.c.type == type_,
                prev_proposal_pub.c.description == description))

        else:
            raise Error('previous proposal publication not identified by '
                        'ID or type and description')

        # Apply previous state restriction if given.
        if state_prev is not None:
            stmt = stmt.where(prev_proposal_pub.c.state == state_prev)

        # Determine which values to update.
        values = {}

        if state is not None:
            values['state'] = state
        if title != ():
            values['title'] = title
        if author != ():
            values['author'] = author
        if year != ():
            values['year'] = year

        if not values:
            raise Error('no previous proposal publication updates specified')

        # Apply the update.
        with self._transaction() as conn:
            result = conn.execute(stmt.values(values))

            if result.rowcount == 0:
                raise ConsistencyError(
                    'Did not update previous proposal publication info')

    def update_request_prop_copy(
            self, request_id, state=None, processed=None,
            state_prev=None, copy_proposal_id=None,
            state_is_system=False,
            _test_skip_check=False):
        values = {}

        if copy_proposal_id is not None:
            values['copy_proposal_id'] = copy_proposal_id

        self._update_request_prop(
            request_prop_copy, request_id, state=state, processed=processed,
            state_prev=state_prev, extra_values=values,
            state_is_system=state_is_system,
            _test_skip_check=_test_skip_check)

    def update_request_prop_pdf(
            self, request_id, state=None, processed=None,
            state_prev=None,
            state_is_system=False,
            _test_skip_check=False):
        self._update_request_prop(
            request_prop_pdf, request_id, state=state, processed=processed,
            state_prev=state_prev,
            state_is_system=state_is_system,
            _test_skip_check=_test_skip_check)

    def _update_request_prop(
            self, table,  request_id, state=None, processed=None,
            state_prev=None, extra_values=None, state_is_system=False,
            _conn=None, _test_skip_check=False):
        values = {}

        stmt = table.update().where(
            table.c.id == request_id)

        if state is not None:
            if not RequestState.is_valid(state, is_system=state_is_system):
                raise Error('invalid request state')
            values['state'] = state

        if processed is not None:
            values['processed'] = processed

        if state_prev is not None:
            if not RequestState.is_valid(state_prev, is_system=True):
                raise Error('Invalid previous state.')
            stmt = stmt.where(table.c.state == state_prev)

        if extra_values is not None:
            values.update(extra_values)

        if not values:
            raise Error('no request updates specified')

        with self._transaction(_conn=_conn) as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, table, request_id):
                raise ConsistencyError(
                    'request does not exist with id {}', request_id)

            result = conn.execute(stmt.values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating request {}', request_id)

    def update_semester(self, semester_id, name=None, code=None,
                        date_start=None, date_end=None, description=None,
                        description_format=None,
                        _test_skip_check=False):
        """
        Update a semester record.
        """

        values = {}

        if name is not None:
            values['name'] = name
        if code is not None:
            values['code'] = code
        if date_start is not None:
            values['date_start'] = date_start
            # If given both dates, we can easily make this sanity check.
            if date_end is not None:
                if date_end < date_start:
                    raise UserError('Semester end date is before start date.')
        if date_end is not None:
            values['date_end'] = date_end
        if description is not None:
            values['description'] = description
        if description_format is not None:
            if not FormatType.is_valid(description_format, is_system=True):
                raise UserError('Text format not recognised.')
            values['description_format'] = description_format

        if not values:
            raise Error('no semester updates specified')

        with self._transaction() as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, semester, semester_id):
                raise ConsistencyError(
                    'semester does not exist with id={}', semester_id)

            result = conn.execute(semester.update().where(
                semester.c.id == semester_id
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating semester with id={}',
                    semester_id)

    def update_proposal(self, proposal_id, state=None, title=None,
                        state_prev=None,
                        _test_skip_check=False):
        """
        Update a proposal record.
        """

        values = {}

        stmt = proposal.update().where(proposal.c.id == proposal_id)

        if state is not None:
            if not ProposalState.is_valid(state):
                raise Error('Invalid state.')
            values['state'] = state

        if state_prev is not None:
            if not ProposalState.is_valid(state_prev):
                raise Error('Invalid previous state.')
            stmt = stmt.where(proposal.c.state == state_prev)

        if title is not None:
            if not title:
                raise UserError('The proposal title should not be blank.')
            values['title'] = title

        if not values:
            raise Error('No proposal updates specified.')

        with self._transaction() as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, proposal, proposal_id):
                raise ConsistencyError(
                    'proposal does not exist with id={}', proposal_id)

            result = conn.execute(stmt.values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating proposal with id={}',
                    proposal_id)

    def update_proposal_figure(self, proposal_id, role, link_id, fig_id=None,
                               figure=None, type_=None,
                               filename=None, uploader_person_id=None,
                               state=None, state_prev=None,
                               caption=None, state_is_system=False):
        """
        Update the record of a figure attached to a proposal.

        Can be used to update the figure or the state.

        If the figure is updated, then the type, filename and uploader
        must be specified and the state will be set to NEW -- the state
        must not be specifed explicitly.

        :return: the internal figure ID (not link ID) if it changed,
            for test purposes only
        """

        where_extra = []

        if proposal_id is not None:
            where_extra.append(proposal_fig_link.c.proposal_id == proposal_id)

        if role is not None:
            where_extra.append(proposal_fig_link.c.role == role)

        return self._update_figure(
            proposal_fig, proposal_fig_link,
            proposal_fig_preview, proposal_fig_thumbnail,
            link_id, fig_id, figure, type_, filename, uploader_person_id,
            state, state_prev, caption,
            where_extra=where_extra, state_is_system=state_is_system,
        )

    def _update_figure(
            self, table, table_link, table_preview, table_thumbnail,
            link_id, fig_id, figure, type_, filename, uploader_person_id,
            state, state_prev, caption,
            where_extra=[], state_is_system=False):
        where = []
        where_link = []
        values = {}
        values_link = {}
        figure_updated = False

        # Determine the update constraints.

        if link_id is not None:
            where_link.append(table_link.c.id == link_id)
        elif fig_id is None:
            # If present, the fig_id constraint will be applied differently
            # for each table at a later stage.

            # We need at least one of link_id and fig_id.
            raise Error('figure identifier not specified')

        if state_prev is not None:
            if not AttachmentState.is_valid(state_prev, is_system=True):
                raise Error('Invalid previous state.')
            where.append(table.c.state == state_prev)

        where_link.extend(where_extra)

        # Determine which update to perform.

        if figure is not None:
            figure_updated = True

            # We need a link_id to know where to record the new fig_id.
            if link_id is None:
                raise Error('link_id not specified with new figure')

            # New figures should be set to "NEW" state, so prevent figure
            # and state both being specified.
            if state is not None:
                raise Error('updated figure and state both specified')

            if type_ is None:
                raise Error('updated figure type not specified')
            if filename is None:
                raise Error('updated figure filename not specified')
            if uploader_person_id is None:
                raise Error('updated figure uploader not specified')

            values.update({
                table.c.type: type_,
                table.c.state: AttachmentState.NEW,
                table.c.figure: figure,
                table.c.md5sum: str_to_unicode(md5(figure).hexdigest()),
                table.c.filename: filename,
                table.c.uploaded: datetime.utcnow(),
                table.c.uploader: uploader_person_id,
            })

        elif state is not None:
            if not AttachmentState.is_valid(state, is_system=state_is_system):
                raise Error('Invalid state.')
            values['state'] = state

        if caption is not None:
            values_link['caption'] = caption

        # Check if the update is permissible.

        if not (values or values_link):
            raise Error('No figure updates specified.')

        if values_link and (link_id is None):
            # If updating a link-specific value, we need to know
            # which link to update.
            raise Error('No link_id specified with link update')

        if where and values and (values_link or figure_updated):
            # If updating the link table (explicitly or via figure update)
            # and the main table, then there could be a problem if there
            # are constraints on the main table.  (It is updated first
            # and the constrained values may have changed.)
            raise Error(
                'Link update may not have main-table constraints '
                'when that table is also being updated.')

        # Finally perform the update.

        new_fig_id = None

        with self._transaction() as conn:
            if figure_updated:
                result = conn.execute(table.insert().values(values))

                new_fig_id = result.inserted_primary_key[0]

                # We already checked we have a link_id, so update that
                # link to refer to the new figure.
                values_link['fig_id'] = new_fig_id

            elif values:
                stmt = table.update()

                if fig_id is not None:
                    stmt = stmt.where(table.c.id == fig_id)

                if where:
                    stmt = stmt.where(and_(*where))

                if where_link:
                    stmt = stmt.where(table.c.id.in_(
                        select([table_link.c.fig_id]).where(
                            and_(*where_link))))

                result = conn.execute(stmt.values(values))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating figure with id={}',
                        fig_id)

            if values_link:
                stmt = table_link.update()

                if fig_id is not None:
                    stmt = stmt.where(table_link.c.fig_id == fig_id)

                if where_link:
                    stmt = stmt.where(and_(*where_link))

                if where:
                    stmt = stmt.where(table_link.c.fig_id.in_(
                        select([table.c.id]).where(and_(*where))))

                result = conn.execute(stmt.values(values_link))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating figure link with id={}',
                        fig_id)

            if figure_updated:
                # If the figure was updated then also remove the old version.
                # The preview and thumbnail should be removed by cascade.
                self._remove_orphan_records(conn, table, table_link.c.fig_id)

        return new_fig_id

    def update_proposal_pdf(
            self, pdf_id, state=None, state_prev=None, state_is_system=False,
            _test_skip_check=False):
        """
        Update the record for a PDF attached to a proposal.
        """

        values = {}
        stmt = proposal_pdf.update().where(proposal_pdf.c.id == pdf_id)

        if state is not None:
            if not AttachmentState.is_valid(state, is_system=state_is_system):
                raise Error('Invalid state.')
            values['state'] = state

        if state_prev is not None:
            if not AttachmentState.is_valid(state, is_system=True):
                raise Error('Invalid previous state.')
            stmt = stmt.where(proposal_pdf.c.state == state_prev)

        if not values:
            raise Error('No proposal PDF updates specified.')

        with self._transaction() as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, proposal_pdf, pdf_id):
                raise ConsistencyError(
                    'proposal PDF does not exist with id={}'.format(pdf_id))

            result = conn.execute(stmt.values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating proposal PDF with id={}', pdf_id)

    def update_queue(self, queue_id, name=None, code=None, description=None,
                     description_format=None,
                     _test_skip_check=False):
        """
        Update a queue record.
        """

        values = {}

        if name is not None:
            values['name'] = name
        if code is not None:
            values['code'] = code
        if description is not None:
            values['description'] = description
        if description_format is not None:
            if not FormatType.is_valid(description_format, is_system=True):
                raise UserError('Text format not recognised.')
            values['description_format'] = description_format

        if not values:
            raise Error('no queue updates specified')

        with self._transaction() as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, queue, queue_id):
                raise ConsistencyError(
                    'queue does not exist with id={}', queue_id)

            result = conn.execute(queue.update().where(
                queue.c.id == queue_id
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating queue with id={}',
                    queue_id)

    def _get_proposal_text_id(self, conn, table, proposal_id, role):
        """
        Test whether text of the given role already exists for a proposal,
        and if it does, returns its identifier.
        """

        return conn.execute(select([table.c.id]).where(and_(
            table.c.proposal_id == proposal_id,
            table.c.role == role
        ))).scalar()

    def _get_call_preamble_id(self, conn, semester_id, type_):
        """
        Test whether a preamble for the given semester and call type exists,
        and if it does, returns its identifier.
        """

        return conn.execute(select([call_preamble.c.id]).where(and_(
            call_preamble.c.semester_id == semester_id,
            call_preamble.c.type == type_
        ))).scalar()

    def _exists_queue_affiliation(self, conn, queue_id, affiliation_id):
        """
        Test whether an identifier exists in the given table.
        """

        return 0 < conn.execute(select([count(affiliation.c.id)]).where(and_(
            affiliation.c.queue_id == queue_id,
            affiliation.c.id == affiliation_id,
            not_(affiliation.c.hidden)
        ))).scalar()
