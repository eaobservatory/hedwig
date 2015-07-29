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

from datetime import datetime
from hashlib import md5

from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_, case, false, not_
from sqlalchemy.sql.functions import coalesce, count
from sqlalchemy.sql.functions import max as max_

from ...error import ConsistencyError, Error, FormattedError, \
    MultipleRecords, NoSuchRecord, UserError
from ...type import Affiliation, AttachmentState, Call, Category, \
    FigureType, FormatType, \
    Member, MemberCollection, MemberInfo, MemberPIInfo, \
    Proposal, ProposalCategory, ProposalState, \
    ProposalFigure, ProposalFigureInfo, ProposalPDFInfo, \
    ProposalText, ProposalTextCollection, ProposalTextInfo, \
    Queue, QueueInfo, ResultCollection, Semester, SemesterInfo, \
    Target, TargetCollection, TextRole
from ..meta import affiliation, call, category, facility, institution, \
    member, person, proposal, proposal_category, \
    proposal_fig, proposal_fig_preview, proposal_fig_thumbnail, \
    proposal_pdf, proposal_pdf_preview, proposal_text, queue, semester, target
from ..util import require_not_none


class ProposalPart(object):
    def add_affiliation(self, queue_id, name, hidden=False):
        """
        Add an affiliation to the database.
        """

        with self._transaction() as conn:
            result = conn.execute(affiliation.insert().values({
                affiliation.c.queue_id: queue_id,
                affiliation.c.name: name,
                affiliation.c.hidden: hidden,
            }))

        return result.inserted_primary_key[0]

    def add_call(self, semester_id, queue_id,
                 date_open, date_close,
                 abst_word_lim,
                 tech_word_lim, tech_fig_lim, tech_page_lim,
                 sci_word_lim, sci_fig_lim, sci_page_lim,
                 capt_word_lim, expl_word_lim,
                 tech_note, sci_note, note_format,
                 _test_skip_check=False):
        """
        Add a call for proposals to the database.
        """

        if date_close < date_open:
            raise UserError('Closing date is before opening date.')

        if not FormatType.is_valid(note_format, is_system=True):
            raise UserError('Text format not recognised.')

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
                        'semester {0} is for facility {1} but '
                        'queue {2} is for facility {3}',
                        semester_id, semester.facility_id,
                        queue_id, queue.facility_id)

            result = conn.execute(call.insert().values({
                call.c.semester_id: semester_id,
                call.c.queue_id: queue_id,
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
                call.c.note_format: note_format,
            }))

        return result.inserted_primary_key[0]

    def add_member(self, proposal_id, person_id, affiliation_id,
                   pi=False, editor=False,
                   observer=False, _conn=None, _test_skip_check=False):
        with self._transaction(_conn=_conn) as conn:
            if not _test_skip_check:
                if not self._exists_id(conn, person, person_id):
                    raise ConsistencyError('person does not exist with id={0}',
                                           person_id)
                proposal_record = self.get_proposal(None, proposal_id,
                                                    _conn=conn)
                if not self._exists_queue_affiliation(
                        conn, proposal_record.queue_id, affiliation_id):
                    raise ConsistencyError(
                        'affiliation does not exist with id={0} '
                        'for queue with id={1}'.format(
                            affiliation_id, proposal_record.queue_id))

            member_alias = member.alias()

            result = conn.execute(member.insert().values({
                member.c.proposal_id: proposal_id,
                member.c.sort_order: select(
                    [coalesce(max_(member_alias.c.sort_order), 0) + 1]).where(
                    member_alias.c.proposal_id == proposal_id),
                member.c.person_id: person_id,
                member.c.pi: pi,
                member.c.editor: editor,
                member.c.observer: observer,
                member.c.affiliation_id: affiliation_id,
            }))

        return result.inserted_primary_key[0]

    def add_proposal(self, call_id, person_id, affiliation_id, title,
                     state=ProposalState.PREPARATION, _test_skip_check=False):
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

        if not ProposalState.is_valid(state):
            raise Error('Invalid state.')

        with self._transaction() as conn:
            if not _test_skip_check:
                try:
                    call = self.search_call(
                        call_id=call_id, _conn=conn).get_single()
                except NoSuchRecord:
                    raise ConsistencyError('call does not exist with id={0}',
                                           call_id)

                if not self._exists_queue_affiliation(
                        conn, call.queue_id, affiliation_id):
                    raise ConsistencyError(
                        'affiliation does not exist with id={0} '
                        'for queue with id={1}'.format(
                            affiliation_id, call.queue_id))

            proposal_alias = proposal.alias()

            result = conn.execute(proposal.insert().values({
                proposal.c.call_id: call_id,
                proposal.c.number: select(
                    [coalesce(max_(proposal_alias.c.number), 0) + 1]).where(
                    proposal_alias.c.call_id == call_id),
                proposal.c.state: state,
                proposal.c.title: title,
            }))

            proposal_id = result.inserted_primary_key[0]

            self.add_member(proposal_id, person_id, affiliation_id,
                            True, True, False,
                            _conn=conn, _test_skip_check=_test_skip_check)

        return proposal_id

    def add_proposal_figure(self, proposal_id, role, type_, figure,
                            caption, filename, uploader_person_id,
                            _test_skip_check=False):
        if not FigureType.is_valid(type_):
            raise Error('Invalid figure type.')
        if not TextRole.is_valid(role):
            raise Error('Invalid text role.')
        if not figure:
            # Shouldn't happen as we should have already checked the figure
            # type.
            raise UserError('Uploaded figure appears to be empty.')

        with self._transaction() as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, proposal, proposal_id)):
                raise ConsistencyError('proposal does not exist with id={0}',
                                       proposal_id)
            if (not _test_skip_check and
                    not self._exists_id(conn, person, uploader_person_id)):
                raise ConsistencyError('person does not exist with id={}',
                                       uploader_person_id)

            fig_alias = proposal_fig.alias()

            result = conn.execute(proposal_fig.insert().values({
                proposal_fig.c.proposal_id: proposal_id,
                proposal_fig.c.sort_order: select(
                    [coalesce(max_(fig_alias.c.sort_order), 0) + 1]
                    ).where(fig_alias.c.proposal_id == proposal_id),
                proposal_fig.c.role: role,
                proposal_fig.c.type: type_,
                proposal_fig.c.state: AttachmentState.NEW,
                proposal_fig.c.figure: figure,
                proposal_fig.c.md5sum: md5(figure).hexdigest(),
                proposal_fig.c.caption: caption,
                proposal_fig.c.filename: filename,
                proposal_fig.c.uploaded: datetime.utcnow(),
                proposal_fig.c.uploader: uploader_person_id,
            }))

        return result.inserted_primary_key[0]

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
                raise ConsistencyError('facility does not exist with id={0}',
                                       facility_id)

            result = conn.execute(queue.insert().values({
                queue.c.facility_id: facility_id,
                queue.c.name: name,
                queue.c.code: code,
                queue.c.description: description,
                queue.c.description_format: description_format,
            }))

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
                raise ConsistencyError('facility does not exist with id={0}',
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
                    'no row matched deleting member person {0} for {0}',
                    person_id, proposal_id)

            # Check that the proposal still has at least one member: if not,
            # raise an exception to abort the transaction.
            if 1 > conn.execute(select([count(member.c.id)]).where(and_(
                    member.c.proposal_id == proposal_id,
                    member.c.editor))).scalar():
                raise ConsistencyError(
                    'deleting this member would leave no editors')

    def delete_proposal_figure(self, proposal_id, role, id_):
        stmt = proposal_fig.delete()

        if proposal_id is not None:
            stmt = stmt.where(proposal_fig.c.proposal_id == proposal_id)

        if role is not None:
            stmt = stmt.where(proposal_fig.c.role == role)

        if id_ is not None:
            stmt = stmt.where(proposal_fig.c.id == id_)
        else:
            raise Error('figure identifier not specified')

        with self._transaction() as conn:
            result = conn.execute(stmt)

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no row matched deleting proposal figure '
                    'for proposal {} role {} figure {}',
                    proposal_id, role, fig_id)

    def delete_proposal_pdf(self, proposal_id, role,
                            _test_skip_check=False):
        with self._transaction() as conn:
            if not _test_skip_check and (self._get_proposal_pdf_id(
                    conn, proposal_id, role) is None):
                raise ConsistencyError('PDF does not exist for {0} role {1}',
                                       proposal_id, role)

            result = conn.execute(proposal_pdf.delete().where(and_(
                proposal_pdf.c.proposal_id == proposal_id,
                proposal_pdf.c.role == role
            )))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no row matched deleting PDF for {0} role {1}',
                    proposal_id, role)

    def delete_proposal_text(self, proposal_id, role,
                             _test_skip_check=False):
        with self._transaction() as conn:
            if not _test_skip_check and not self._exists_proposal_text(
                    conn, proposal_id, role):
                raise ConsistencyError('text does not exist for {0} role {1}',
                                       proposal_id, role)

            result = conn.execute(proposal_text.delete().where(and_(
                proposal_text.c.proposal_id == proposal_id,
                proposal_text.c.role == role
            )))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no row matched deleting text for {0} role {1}',
                    proposal_id, role)

    def ensure_facility(self, code):
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
                return result['id']

            result = conn.execute(facility.insert().values({
                facility.c.code: code,
            }))

            return result.inserted_primary_key[0]

    def get_all_proposal_text(self, proposal_id, _conn=None):
        """
        Get all pieces of text associated with a proposal.

        The results are returned as a dictionary of ProposalText objects
        organized by role identifier.
        """

        ans = {}

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(proposal_text.select().where(
                    proposal_text.c.proposal_id == proposal_id)):
                ans[row['role']] = ProposalText(text=row['text'],
                                                format=row['format'])

        return ans

    def get_call(self, facility_id, call_id):
        """
        Get a call record.
        """

        return self.search_call(
            facility_id=facility_id, call_id=call_id, with_case_notes=True
        ).get_single()

    def get_proposal(self, facility_id, proposal_id, with_members=False,
                     _conn=None):
        """
        Get a proposal record.
        """

        return self.search_proposal(
            facility_id=facility_id, proposal_id=proposal_id,
            with_members=with_members, _conn=_conn
        ).get_single()

    def get_proposal_facility_code(self, proposal_id):
        """
        Determine the facility code associated with the given proposal.
        """

        with self._transaction() as conn:
            result = conn.execute(select([
                facility.c.code
            ]).select_from(
                facility.join(semester).join(call).join(proposal)
            ).where(
                proposal.c.id == proposal_id
            )).first()

        if result is None:
            raise NoSuchRecord('facility or proposal does not exist')

        return result['code']

    def get_proposal_figure(self, proposal_id, role, id_, md5sum=None):
        """
        Get a figure associated with a proposal.

        Returned as a ProposalFigure object.
        """

        stmt = select([
            proposal_fig.c.figure,
            proposal_fig.c.type,
            proposal_fig.c.filename,
        ])

        if proposal_id is not None:
            stmt = stmt.where(proposal_fig.c.proposal_id == proposal_id)

        if role is not None:
            stmt = stmt.where(proposal_fig.c.role == role)

        if id_ is not None:
            stmt = stmt.where(proposal_fig.c.id == id_)
        else:
            raise Error('proposal figure identifier not specified')

        if md5sum is not None:
            stmt = stmt.where(proposal_fig.c.md5sum == md5sum)

        with self._transaction() as conn:
            row = conn.execute(stmt).first()

        if row is None:
            raise NoSuchRecord('figure does not exist')

        return ProposalFigure(row['figure'], row['type'], row['filename'])

    def get_proposal_figure_preview(self, proposal_id, role, id_,
                                    md5sum=None):
        return self._get_proposal_figure_alternate(
            proposal_fig_preview.c.preview, proposal_id, role, id_,
            md5sum)

    def get_proposal_figure_thumbnail(self, proposal_id, role, id_,
                                     md5sum=None):
        return self._get_proposal_figure_alternate(
            proposal_fig_thumbnail.c.thumbnail, proposal_id, role, id_,
            md5sum)

    def _get_proposal_figure_alternate(self, column,
                                       proposal_id, role, id_, md5sum):
        stmt = select([column])

        if ((proposal_id is not None) or (role is not None) or
                (md5sum is not None)):
            stmt = stmt.select_from(column.table.join(proposal_fig))
            if proposal_id is not None:
                stmt = stmt.where(proposal_fig.c.proposal_id == proposal_id)
            if role is not None:
                stmt = stmt.where(proposal_fig.c.role == role)
            if md5sum is not None:
                stmt = stmt.where(proposal_fig.c.md5sum == md5sum)

        if id_ is not None:
            stmt = stmt.where(column.table.c.fig_id == id_)
        else:
            raise Error('proposal figure identifier not specified')

        with self._transaction() as conn:
            row = conn.execute(stmt).first()

        if row is None:
            raise NoSuchRecord('figure preview/thumbnail does not exist')

        return row[0]

    def get_proposal_pdf(self, proposal_id, role, id_=None, _conn=None):
        """
        Get the given PDF associated with a proposal.
        """

        stmt = select([proposal_pdf.c.pdf, proposal_pdf.c.filename])

        if (proposal_id is not None) and (role is not None):
            if not TextRole.is_valid(role):
                raise FormattedError('proposal text role not recognised: {0}',
                                     role)

            stmt = stmt.where(and_(
                proposal_pdf.c.proposal_id == proposal_id,
                proposal_pdf.c.role == role
            ))

        elif id_ is not None:
            stmt = stmt.where(proposal_pdf.c.id == id_)

        else:
            raise Error('neither PDF nor proposal and role specified.')

        with self._transaction(_conn=_conn) as conn:
            row = conn.execute(stmt).first()

        if row is None:
            raise NoSuchRecord('PDF does not exist for {0} role {1}',
                               proposal_id, role)

        return ProposalFigure(row['pdf'], FigureType.PDF, row['filename'])

    def get_proposal_pdf_preview(self, proposal_id, role, page, md5sum=None):
        """
        Get a preview page from a PDF associated with a proposal.
        """

        stmt = select([proposal_pdf_preview.c.preview]).select_from(
            proposal_pdf.join(proposal_pdf_preview)
        ).where(and_(
            proposal_pdf.c.proposal_id == proposal_id,
            proposal_pdf.c.role == role,
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

    def get_proposal_text(self, proposal_id, role):
        """
        Get the given text associated with a proposal.
        """

        if not TextRole.is_valid(role):
            raise FormattedError('proposal text role not recognised: {0}',
                                 role)

        with self._transaction() as conn:
            row = conn.execute(proposal_text.select().where(and_(
                proposal_text.c.proposal_id == proposal_id,
                proposal_text.c.role == role
            ))).first()

        if row is None:
            raise NoSuchRecord('text does not exist for {0} role {1}',
                               proposal_id, role)

        return ProposalText(text=row['text'], format=row['format'])

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

        return Semester(**result)

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

        return Queue(**result)

    def search_affiliation(self, queue_id=None, hidden=None):
        """
        Search for affiliation records.
        """

        stmt = affiliation.select()

        if queue_id is not None:
            stmt = stmt.where(affiliation.c.queue_id == queue_id)

        if hidden is not None:
            stmt = stmt.where(affiliation.c.hidden == hidden)

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(affiliation.c.name.asc())):
                ans[row['id']] = Affiliation(**row)

        return ans

    def search_call(self, call_id=None, facility_id=None, semester_id=None,
                    queue_id=None, is_open=None, with_queue_description=False,
                    with_case_notes=False,
                    _conn=None):
        """
        Search for call records.
        """

        default = {}

        if with_case_notes:
            fields = [call]
        else:
            fields = [x for x in call.columns
                      if x.name not in ('tech_note', 'sci_note')]
            default['tech_note'] = None
            default['sci_note'] = None

        fields.extend([
            semester.c.facility_id,
            semester.c.name.label('semester_name'),
            queue.c.name.label('queue_name')
        ])

        if with_queue_description:
            fields.append(queue.c.description.label('queue_description'))
            fields.append(
                queue.c.description_format.label('queue_description_format'))
        else:
            default['queue_description'] = None
            default['queue_description_format'] = None

        stmt = select(fields).select_from(
            call.join(semester).join(queue)
        )

        if call_id is not None:
            stmt = stmt.where(call.c.id == call_id)

        if facility_id is not None:
            stmt = stmt.where(semester.c.facility_id == facility_id)

        if semester_id is not None:
            stmt = stmt.where(call.c.semester_id == semester_id)

        if queue_id is not None:
            stmt = stmt.where(call.c.queue_id == queue_id)

        if is_open is not None:
            dt_current = datetime.utcnow()
            condition = and_(call.c.date_open <= dt_current,
                             call.c.date_close >= dt_current)
            if is_open:
                stmt = stmt.where(condition)
            else:
                stmt = stmt.where(not_(condition))

        ans = ResultCollection()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt.order_by(semester.c.id.desc(),
                                                  queue.c.name.asc())):
                values = default.copy()
                values.update(**row)
                ans[row['id']] = Call(**values)

        return ans

    def search_category(self, facility_id, hidden=None, _conn=None):
        """
        Search for categories.
        """

        stmt = category.select()

        if facility_id is not None:
            stmt = stmt.where(category.c.facility_id == facility_id)

        if hidden is not None:
            stmt = stmt.where(category.c.hidden == hidden)

        ans = ResultCollection()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt.order_by(category.c.name.asc())):
                ans[row['id']] = Category(**row)

        return ans

    def search_member(self, proposal_id=None, person_id=None,
                      co_member_person_id=None,
                      co_member_institution_id=None,
                      editor=None, _conn=None):
        """
        Search for proposal members.
        """

        stmt = select([
            x for x in member.columns if x.name not in ('institution_id',)
        ] + [
            person.c.name.label('person_name'),
            person.c.public.label('person_public'),
            (person.c.user_id.isnot(None)).label('person_registered'),
            affiliation.c.name.label('affiliation_name'),
            coalesce(member.c.institution_id, person.c.institution_id).label(
                'resolved_institution_id'),
            institution.c.name.label('institution_name'),
            institution.c.organization.label('institution_organization'),
            institution.c.country.label('institution_country'),
        ]).select_from(
            member.join(person).join(affiliation).outerjoin(
                institution, institution.c.id == coalesce(
                    member.c.institution_id, person.c.institution_id
                )))

        if proposal_id is not None:
            stmt = stmt.where(member.c.proposal_id == proposal_id)
        if person_id is not None:
            stmt = stmt.where(member.c.person_id == person_id)
        if co_member_person_id is not None:
            stmt = stmt.where(and_(
                member.c.person_id != co_member_person_id,
                member.c.proposal_id.in_(
                    select([member.c.proposal_id]).where(
                        member.c.person_id == co_member_person_id
                    ))))
        if co_member_institution_id is not None:
            stmt = stmt.where(
                member.c.proposal_id.in_(
                    select([member.c.proposal_id]).select_from(
                        member.join(person)
                    ).where(
                        coalesce(member.c.institution_id,
                                 person.c.institution_id) ==
                        co_member_institution_id
                    )))
        if editor is not None:
            if editor:
                stmt = stmt.where(member.c.editor)
            else:
                stmt = stmt.where(not_(member.c.editor))

        ans = MemberCollection()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt.order_by(member.c.sort_order.asc())):
                ans[row['id']] = Member(**row)

        return ans

    def search_semester(self, facility_id=None):
        stmt = select([
            semester.c.id,
            semester.c.facility_id,
            semester.c.name,
            semester.c.code,
            semester.c.date_start,
            semester.c.date_end,
        ])

        if facility_id is not None:
            stmt = stmt.where(semester.c.facility_id == facility_id)

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(semester.c.id.desc())):
                ans[row['id']] = SemesterInfo(**row)

        return ans

    def search_proposal(self, call_id=None, facility_id=None, proposal_id=None,
                        person_id=None, person_is_editor=None, person_pi=False,
                        state=None, with_members=False,
                        proposal_number=None,
                        semester_code=None, queue_code=None,
                        _conn=None):
        """
        Search for proposals.

        If "person_id" is specified, then this method searches for proposals
        with this person as a member, and also sets "members" in the
        returned "Proposal" object to a "MemberInfo" object summarizing
        that person's role.  Alternatively if "person_pi" is enabled, then
        the PI's information is returned as a "MemberPIInfo" object.

        Otherwise if "with_members" is set, then the "Proposal" object's
        "members" attribute is a "MemberCollection" with information about
        all the members of the proposal.
        """

        select_columns = [
            proposal,
            call.c.semester_id,
            semester.c.name.label('semester_name'),
            semester.c.code.label('semester_code'),
            call.c.queue_id,
            queue.c.name.label('queue_name'),
            queue.c.code.label('queue_code'),
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
        ]

        select_from = proposal.join(call).join(semester).join(queue)

        # Determine query: add member results if person_id specified.
        if person_id is not None:
            select_columns.extend([
                member.c.pi,
                member.c.editor,
                member.c.observer,
            ])
            select_from = select_from.join(member)

        elif person_pi:
            select_columns.extend([
                member.c.person_id,
                person.c.name.label('pi_name'),
                affiliation.c.name.label('pi_affiliation'),
            ])
            select_from = select_from.outerjoin(
                member, and_(
                    proposal.c.id == member.c.proposal_id,
                    member.c.pi)
            ).outerjoin(person).outerjoin(
                affiliation,
                member.c.affiliation_id == affiliation.c.id
            )

        stmt = select(select_columns).select_from(select_from)

        # Determine constraints.
        if call_id is not None:
            stmt = stmt.where(proposal.c.call_id == call_id)

        if facility_id is not None:
            stmt = stmt.where(semester.c.facility_id == facility_id)

        if proposal_id is not None:
            stmt = stmt.where(proposal.c.id == proposal_id)

        if person_id is not None:
            stmt = stmt.where(member.c.person_id == person_id)

            if person_is_editor is not None:
                if person_is_editor:
                    stmt = stmt.where(member.c.editor)
                else:
                    stmt = stmt.where(not_(member.c.editor))

        if state is not None:
            if isinstance(state, list) or isinstance(state, tuple):
                stmt = stmt.where(proposal.c.state.in_(state))
            else:
                stmt = stmt.where(proposal.c.state == state)

        if proposal_number is not None:
            stmt = stmt.where(proposal.c.number == proposal_number)

        if semester_code is not None:
            stmt = stmt.where(semester.c.code == semester_code)

        if queue_code is not None:
            stmt = stmt.where(queue.c.code == queue_code)

        # Determine ordering: don't sort if only selecting one proposal.
        # This ordering is intended for the personal dashboard.  If other
        # pages start using this method, perhaps the ordering should be
        # controlled by more arguments.
        if proposal_id is None:
            stmt = stmt.order_by(
                semester.c.facility_id,
                call.c.semester_id.desc(),
                call.c.queue_id,
                proposal.c.number)

        # Perform query and collect results.
        ans = ResultCollection()

        with self._transaction(_conn=_conn) as conn:
            # Fetch all results before loop so that we can also query for
            # members if requested.
            for row in conn.execute(stmt).fetchall():
                members = None

                if person_id is not None:
                    row = dict(row.items())
                    members = MemberInfo(
                        row.pop('pi'),
                        row.pop('editor'),
                        row.pop('observer'))

                elif person_pi:
                    row = dict(row.items())
                    members = MemberPIInfo(
                        row.pop('person_id'),
                        row.pop('pi_name'),
                        row.pop('pi_affiliation'))

                elif with_members:
                    members = self.search_member(proposal_id=row['id'],
                                                 _conn=conn)

                ans[row['id']] = Proposal(members=members, **row)

        return ans

    def search_proposal_category(self, proposal_id, _conn=None):
        """
        Search for the categories associated with a proposal.
        """

        stmt = select([
            proposal_category,
            category.c.name.label('category_name')
        ]).select_from(proposal_category.join(category))

        if proposal_id is not None:
            stmt = stmt.where(proposal_category.c.proposal_id == proposal_id)

        ans = ResultCollection()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt.order_by(category.c.name.asc())):
                ans[row['id']] = ProposalCategory(**row)

        return ans

    def search_proposal_figure(self, proposal_id=None, role=None, state=None,
                               fig_id=None,
                               with_caption=False, with_uploader_name=False,
                               with_has_preview=False):
        select_columns = [
            proposal_fig.c.id,
            proposal_fig.c.proposal_id,
            proposal_fig.c.role,
            proposal_fig.c.type,
            proposal_fig.c.state,
            proposal_fig.c.md5sum,
            proposal_fig.c.filename,
            proposal_fig.c.uploaded,
            proposal_fig.c.uploader,
        ]

        select_from = proposal_fig

        default = {
            'caption': None,
            'has_preview': None,
            'uploader_name': None,
        }

        if with_caption:
            select_columns.append(proposal_fig.c.caption)
            del default['caption']

        if with_uploader_name:
            select_columns.append(person.c.name.label('uploader_name'))
            select_from = select_from.join(person)
            del default['uploader_name']

        if with_has_preview:
            select_columns.append(case([
                (proposal_fig_preview.c.fig_id.isnot(None), True)
                ], else_=False).label('has_preview'))
            select_from = select_from.outerjoin(proposal_fig_preview)
            del default['has_preview']

        stmt = select(select_columns).select_from(select_from)

        if proposal_id is not None:
            stmt = stmt.where(proposal_fig.c.proposal_id == proposal_id)

        if role is not None:
            stmt = stmt.where(proposal_fig.c.role == role)

        if state is not None:
            stmt = stmt.where(proposal_fig.c.state == state)

        if fig_id is not None:
            stmt = stmt.where(proposal_fig.c.id == fig_id)

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(
                    stmt.order_by(proposal_fig.c.sort_order.asc())):
                values = default.copy()
                values.update(**row)
                ans[row['id']] = ProposalFigureInfo(**values)

        return ans

    def search_proposal_pdf(self, proposal_id=None, role=None, state=None,
                            with_uploader_name=False):
        select_columns = [
            proposal_pdf.c.id,
            proposal_pdf.c.proposal_id,
            proposal_pdf.c.role,
            proposal_pdf.c.md5sum,
            proposal_pdf.c.state,
            proposal_pdf.c.pages,
            proposal_pdf.c.filename,
            proposal_pdf.c.uploaded,
            proposal_pdf.c.uploader,
        ]

        default = {}

        if with_uploader_name:
            select_columns.append(person.c.name.label('uploader_name'))
            stmt = select(select_columns).select_from(
                proposal_pdf.join(person))
        else:
            stmt = select(select_columns)
            default['uploader_name'] = None

        if proposal_id is not None:
            stmt = stmt.where(proposal_pdf.c.proposal_id == proposal_id)

        if role is not None:
            stmt = stmt.where(proposal_pdf.c.role == role)

        if state is not None:
            stmt = stmt.where(proposal_pdf.c.state == state)

        ans = ProposalTextCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt):
                values = default.copy()
                values.update(**row)
                ans[row['id']] = ProposalPDFInfo(**values)

        return ans

    def search_proposal_text(self, proposal_id=None, role=None):
        stmt = select([
            proposal_text.c.id,
            proposal_text.c.proposal_id,
            proposal_text.c.role,
            proposal_text.c.format,
            proposal_text.c.words,
            proposal_text.c.edited,
            proposal_text.c.editor,
            person.c.name.label('editor_name'),
        ]).select_from(proposal_text.join(person))

        if proposal_id is not None:
            stmt = stmt.where(proposal_text.c.proposal_id == proposal_id)

        if role is not None:
            stmt = stmt.where(proposal_text.c.role == role)

        ans = ProposalTextCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt):
                ans[row['id']] = ProposalTextInfo(**row)

        return ans

    def search_queue(self, facility_id=None):
        stmt = select([
            queue.c.id,
            queue.c.facility_id,
            queue.c.name,
            queue.c.code,
        ])

        if facility_id is not None:
            stmt = stmt.where(queue.c.facility_id == facility_id)

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by((queue.c.name))):
                ans[row['id']] = QueueInfo(**row)

        return ans

    def search_target(self, proposal_id):
        """
        Retrieve the targets of a given proposal.
        """

        stmt = target.select().where(target.c.proposal_id == proposal_id)

        ans = TargetCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(target.c.sort_order.asc())):
                ans[row['id']] = Target(**row)

        return ans

    def set_proposal_figure_preview(self, fig_id, preview):
        self._set_proposal_figure_alternate(
            proposal_fig_preview.c.preview, fig_id, preview)

    def set_proposal_figure_thumbnail(self, fig_id, thumbnail):
        self._set_proposal_figure_alternate(
            proposal_fig_thumbnail.c.thumbnail, fig_id, thumbnail)

    def _set_proposal_figure_alternate(self, column, fig_id, alternate):
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
                        'no rows matched updating proposal figure alternate')

            else:
                # Add new alternate.
                conn.execute(table.insert().values({
                    table.c.fig_id: fig_id,
                    column: alternate,
                }))

    def set_proposal_pdf(self, proposal_id, role, pdf, pages, filename,
                         uploader_person_id, _test_skip_check=False):
        """
        Insert or update a given proposal PDF.

        Returns the PDF identifier.
        """

        if not TextRole.is_valid(role):
            raise FormattedError('proposal text role not recognised: {0}',
                                 role)

        with self._transaction() as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, person, uploader_person_id)):
                raise ConsistencyError('person does not exist with id={}',
                                       uploader_person_id)

            pdf_id = self._get_proposal_pdf_id(conn, proposal_id, role)

            values = {
                proposal_pdf.c.pdf: pdf,
                proposal_pdf.c.md5sum: md5(pdf).hexdigest(),
                proposal_pdf.c.pages: pages,
                proposal_pdf.c.state: AttachmentState.NEW,
                proposal_pdf.c.filename: filename,
                proposal_pdf.c.uploaded: datetime.utcnow(),
                proposal_pdf.c.uploader: uploader_person_id,
            }

            if pdf_id is not None:
                result = conn.execute(proposal_pdf.update().where(
                    proposal_pdf.c.id == pdf_id
                ).values(values))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating proposal PDF {0} role {1}',
                        proposal_id, role)

                result = conn.execute(proposal_pdf_preview.delete().where(
                    proposal_pdf_preview.c.pdf_id == pdf_id))

            else:
                values.update({
                    proposal_pdf.c.proposal_id: proposal_id,
                    proposal_pdf.c.role: role,
                })

                result = conn.execute(proposal_pdf.insert().values(values))

                pdf_id = result.inserted_primary_key[0]

            # Delete any previous proposal text for the same role which
            # this PDF is replacing.
            result = conn.execute(proposal_text.delete().where(and_(
                proposal_text.c.proposal_id == proposal_id,
                proposal_text.c.role == role)))

            if result.rowcount not in (0, 1):
                raise ConsistencyError(
                    'multiple rows deleted removing replaced text '
                    'for proposal {} role {}', proposal_id, role)

            # Also delete any previous figures attached for the old text
            # version.
            conn.execute(proposal_fig.delete().where(and_(
                proposal_fig.c.proposal_id == proposal_id,
                proposal_fig.c.role == role)))

            return pdf_id

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

    def set_proposal_text(self, proposal_id, role, text, format,
                          words, editor_person_id, is_update,
                          _test_skip_check=False):
        """
        Insert or update a given piece of proposal text.

        The "is_update" boolean argument must be used to indicated whether
        this is a new piece of text to insert or an update to an existing
        piece.
        """

        if not format:
            raise UserError('Text format not specified.')
        if not FormatType.is_valid(format):
            raise UserError('Text format not recognised.')
        if not TextRole.is_valid(role):
            raise FormattedError('proposal text role not recognised: {0}',
                                 role)

        with self._transaction() as conn:
            if not _test_skip_check:
                already_exists = self._exists_proposal_text(
                    conn, proposal_id, role)
                if is_update and not already_exists:
                    raise ConsistencyError(
                        'text does not exist for proposal {0} role {1}',
                        proposal_id, role)
                elif not is_update and already_exists:
                    raise ConsistencyError(
                        'text already exists for proposal {0} role {1}',
                        proposal_id, role)

            values = {
                proposal_text.c.text: text,
                proposal_text.c.format: format,
                proposal_text.c.words: words,
                proposal_text.c.edited: datetime.utcnow(),
                proposal_text.c.editor: editor_person_id,
            }

            if is_update:
                result = conn.execute(proposal_text.update().where(and_(
                    proposal_text.c.proposal_id == proposal_id,
                    proposal_text.c.role == role
                )).values(values))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating proposal text {0} role {1}',
                        proposal_id, role)

            else:
                values.update({
                    proposal_text.c.proposal_id: proposal_id,
                    proposal_text.c.role: role,
                })

                result = conn.execute(proposal_text.insert().values(values))

            # Delete any previous proposal PDF for the same role which
            # this text is replacing.
            result = conn.execute(proposal_pdf.delete().where(and_(
                proposal_pdf.c.proposal_id == proposal_id,
                proposal_pdf.c.role == role)))

            if result.rowcount not in (0, 1):
                raise ConsistencyError(
                    'multiple rows deleted removing replaced PDF '
                    'for proposal {} role {}', proposal_id, role)

    def sync_facility_category(self, facility_id, records):
        """
        Update the categories available for proposal for a facility.
        """

        with self._transaction() as conn:
            if not self._exists_id(conn, facility, facility_id):
                raise ConsistencyError(
                    'facility does not exist with id={}', facility_id)

            return self._sync_records(
                conn, category, category.c.facility_id, facility_id, records)

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

        Currently only deleting figures is supported -- no columns are updated.
        """

        with self._transaction() as conn:
            if not self._exists_id(conn, proposal, proposal_id):
                raise ConsistencyError(
                    'proposal does not exist with id={0}', proposal_id)

            return self._sync_records(
                conn, proposal_fig,
                (proposal_fig.c.proposal_id, proposal_fig.c.role),
                (proposal_id, role),
                records,
                update_columns=(), forbid_add=True)

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
                    'proposal does not exist with id={0}', proposal_id)

            return self._sync_records(
                conn, member, member.c.proposal_id, proposal_id, records,
                update_columns=(
                    member.c.sort_order,
                    member.c.pi, member.c.editor, member.c.observer,
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

    def sync_proposal_target(self, proposal_id, records):
        """
        Update the target records for a proposal.
        """

        records.ensure_sort_order()

        with self._transaction() as conn:
            return self._sync_records(
                conn, target, target.c.proposal_id, proposal_id, records)

    def sync_queue_affiliation(self, queue_id, records):
        """
        Update the affiliation records for a queue to match those
        given by "records".
        """

        with self._transaction() as conn:
            if not self._exists_id(conn, queue, queue_id):
                raise ConsistencyError(
                    'queue does not exist with id={0}', queue_id)

            return self._sync_records(
                conn, affiliation, affiliation.c.queue_id, queue_id,
                records)

    def update_call(self, call_id, date_open=None, date_close=None,
                    abst_word_lim=None,
                    tech_word_lim=None, tech_fig_lim=None, tech_page_lim=None,
                    sci_word_lim=None, sci_fig_lim=None, sci_page_lim=None,
                    capt_word_lim=None, expl_word_lim=None,
                    tech_note=None, sci_note=None, note_format=None,
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
        if note_format is not None:
            if not FormatType.is_valid(note_format, is_system=True):
                raise UserError('Text format not recognised.')
            values['note_format'] = note_format

        if not values:
            raise Error('no call updates specified')

        with self._transaction() as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, call, call_id):
                raise ConsistencyError(
                    'call does not exist with id={0}', call_id)

            result = conn.execute(call.update().where(
                call.c.id == call_id
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating call with id={0}', call_id)

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
                    'semester does not exist with id={0}', semester_id)

            result = conn.execute(semester.update().where(
                semester.c.id == semester_id
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating semester with id={0}',
                    semester_id)

    def update_proposal(self, proposal_id, state=None, title=None,
                        _test_skip_check=False):
        """
        Update a proposal record.
        """

        values = {}

        if state is not None:
            if not ProposalState.is_valid(state):
                raise Error('Invalid state.')
            values['state'] = state

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
                    'proposal does not exist with id={0}', proposal_id)

            result = conn.execute(proposal.update().where(
                proposal.c.id == proposal_id
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating proposal with id={0}',
                    proposal_id)

    def update_proposal_figure(self, proposal_id, role, fig_id,
                               figure=None, type_=None,
                               filename=None, uploader_person_id=None,
                               state=None, state_prev=None,
                               caption=None):
        """
        Update the record of a figure attached to a proposal.

        Can be used to update the figure or the state.

        If the figure is updated, then the type, filename and uploader
        must be specified and the state will be set to NEW -- the state
        must bot be speicifed explicitly.
        """

        values = {}
        figure_updated = False

        stmt = proposal_fig.update()

        if proposal_id is not None:
            stmt = stmt.where(proposal_fig.c.proposal_id == proposal_id)

        if role is not None:
            stmt = stmt.where(proposal_fig.c.role == role)

        if fig_id is not None:
            stmt = stmt.where(proposal_fig.c.id == fig_id)
        else:
            raise Error('figure identifier not specified')

        if state_prev is not None:
            if not AttachmentState.is_valid(state_prev):
                raise Error('Invalid previous state.')
            stmt = stmt.where(proposal_fig.c.state == state_prev)

        if figure is not None:
            figure_updated = True

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
                proposal_fig.c.type: type_,
                proposal_fig.c.state: AttachmentState.NEW,
                proposal_fig.c.figure: figure,
                proposal_fig.c.md5sum: md5(figure).hexdigest(),
                proposal_fig.c.filename: filename,
                proposal_fig.c.uploaded: datetime.utcnow(),
                proposal_fig.c.uploader: uploader_person_id,
            })

        elif state is not None:
            if not AttachmentState.is_valid(state):
                raise Error('Invalid state.')
            values['state'] = state

        if caption is not None:
            values['caption'] = caption

        if not values:
            raise Error('No proposal figure updates specified.')

        with self._transaction() as conn:
            result = conn.execute(stmt.values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating proposal figure with id={}',
                    fig_id)

            # If the figure was updated then also remove the old preview
            # and thumbnail.
            if figure_updated:
                result = conn.execute(proposal_fig_preview.delete().where(
                    proposal_fig_preview.c.fig_id == fig_id))

                if result.rowcount not in (0, 1):
                    raise ConsistencyError(
                        'multiple rows deleted removing old figure preview')

                result = conn.execute(proposal_fig_thumbnail.delete().where(
                    proposal_fig_thumbnail.c.fig_id == fig_id))

                if result.rowcount not in (0, 1):
                    raise ConsistencyError(
                        'multiple rows deleted removing old figure thumbnail')

    def update_proposal_pdf(self, pdf_id, state=None, state_prev=None,
                            _test_skip_check=False):
        """
        Update the record for a PDF attached to a proposal.
        """

        values = {}
        stmt = proposal_pdf.update().where(proposal_pdf.c.id == pdf_id)

        if state is not None:
            if not AttachmentState.is_valid(state):
                raise Error('Invalid state.')
            values['state'] = state

        if state_prev is not None:
            if not AttachmentState.is_valid(state):
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
                    'queue does not exist with id={0}', queue_id)

            result = conn.execute(queue.update().where(
                queue.c.id == queue_id
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating queue with id={0}',
                    queue_id)

    def _get_proposal_pdf_id(self, conn, proposal_id, role):
        """
        Test whether text of the given role already exists for a proposal,
        and if it does, returns its identifier.
        """

        return conn.execute(select([proposal_pdf.c.id]).where(and_(
            proposal_pdf.c.proposal_id == proposal_id,
            proposal_pdf.c.role == role
        ))).scalar()

    def _exists_proposal_text(self, conn, proposal_id, role):
        """
        Test whether text of the given role already exists for a proposal.
        """

        return 0 < conn.execute(select([count(proposal_text.c.id)]).where(and_(
            proposal_text.c.proposal_id == proposal_id,
            proposal_text.c.role == role
        ))).scalar()

    def _exists_queue_affiliation(self, conn, queue_id, affiliation_id):
        """
        Test whether an identifier exists in the given table.
        """

        return 0 < conn.execute(select([count(affiliation.c.id)]).where(and_(
            affiliation.c.queue_id == queue_id,
            affiliation.c.id == affiliation_id,
            affiliation.c.hidden == false()
        ))).scalar()
