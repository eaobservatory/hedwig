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

from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_, false, not_
from sqlalchemy.sql.functions import coalesce, count
from sqlalchemy.sql.functions import max as max_

from ...error import ConsistencyError, Error, \
    MultipleRecords, NoSuchRecord, UserError
from ...type import Affiliation, Call, Member, MemberCollection, \
    Proposal, ProposalState, \
    Queue, QueueInfo, ResultCollection, Semester, SemesterInfo
from ..meta import affiliation, call, facility, institution, member, \
    person, proposal, queue, semester


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
                 _test_skip_check=False):
        """
        Add a call for proposals to the database.
        """

        if date_close < date_open:
            raise UserError('Closing date is before opening date.')

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

            result = conn.execute(member.insert().values({
                member.c.proposal_id: proposal_id,
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

            result = conn.execute(proposal.insert().values({
                proposal.c.call_id: call_id,
                proposal.c.number: select(
                    [coalesce(max_(proposal.c.number), 0) + 1]).where(
                    proposal.c.call_id == call_id),
                proposal.c.state: state,
                proposal.c.title: title,
            }))

            proposal_id = result.inserted_primary_key[0]

            self.add_member(proposal_id, person_id, affiliation_id,
                            True, True, False,
                            _conn=conn, _test_skip_check=_test_skip_check)

        return proposal_id

    def add_queue(self, facility_id, name, code, description='',
                  _test_skip_check=False):
        """
        Add a queue to the database.
        """

        if not name:
            raise UserError('The queue name can not be blank.')

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
            }))

            return result.inserted_primary_key[0]

    def add_semester(self, facility_id, name, code,
                     date_start, date_end, description='',
                     _test_skip_check=False):
        """
        Add a semester to the database.
        """

        if not name:
            raise UserError('The semester name can not be blank.')

        if date_end < date_start:
            raise UserError('Semester end date is before start date.')

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
            }))

            return result.inserted_primary_key[0]

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

    def get_call(self, facility_id, call_id):
        """
        Get a call record.
        """

        return self.search_call(facility_id=facility_id,
                                call_id=call_id).get_single()

    def get_proposal(self, facility_id, proposal_id, with_members=False,
                     _conn=None):
        """
        Get a proposal record.
        """

        members = None
        stmt = select([
            proposal,
            call.c.semester_id,
            semester.c.name.label('semester_name'),
            call.c.queue_id,
            queue.c.name.label('queue_name'),
            queue.c.code.label('queue_code'),
            semester.c.facility_id,
        ]).select_from(
            proposal.join(call).join(semester).join(queue)
        ).where(
            proposal.c.id == proposal_id
        )

        if facility_id is not None:
            stmt = stmt.where(semester.c.facility_id == facility_id)

        with self._transaction(_conn=_conn) as conn:
            result = conn.execute(stmt).first()

            if result is None:
                raise NoSuchRecord('proposal does not exist with id={0}',
                                   proposal_id)

            if with_members:
                members = self.search_member(proposal_id=proposal_id,
                                             _conn=conn)

        return Proposal(members=members, **result)

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
                    _conn=None):
        """
        Search for call records.
        """

        fields = [
            call,
            semester.c.facility_id,
            semester.c.name.label('semester_name'),
            queue.c.name.label('queue_name')
        ]

        default = {}

        if with_queue_description:
            fields.append(queue.c.description.label('queue_description'))
        else:
            default['queue_description'] = None

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
            for row in conn.execute(stmt.order_by(member.c.id)):
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

    def sync_proposal_member(self, proposal_id, records, editor_person_id):
        """
        Update the member records for a proposal.

        Only the "pi", "editor" and "observer" flags are updated.
        """

        records.validate(editor_person_id=editor_person_id)

        with self._transaction() as conn:
            if not self._exists_id(conn, proposal, proposal_id):
                raise ConsistencyError(
                    'proposal does not exist with id={0}', proposal_id)

            return self._sync_records(
                conn, member, member.c.proposal_id, proposal_id, records,
                update_columns=(
                    member.c.pi, member.c.editor, member.c.observer,
                    member.c.affiliation_id
                ), forbid_add=True)

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

    def update_proposal(self, proposal_id, state=None,
                        _test_skip_check=False):
        """
        Update a proposal record.
        """

        values = {}

        if state is not None:
            if not ProposalState.is_valid(state):
                raise Error('Invalid state.')
            values['state'] = state

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

    def update_queue(self, queue_id, name=None, code=None, description=None,
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

    def _exists_queue_affiliation(self, conn, queue_id, affiliation_id):
        """
        Test whether an identifier exists in the given table.
        """

        return 0 < conn.execute(select([count(affiliation.c.id)]).where(and_(
            affiliation.c.queue_id == queue_id,
            affiliation.c.id == affiliation_id,
            affiliation.c.hidden == false()
        ))).scalar()
