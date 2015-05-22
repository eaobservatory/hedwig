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

from sqlalchemy.sql import select
from sqlalchemy.sql.expression import desc
from sqlalchemy.sql.functions import coalesce, count
from sqlalchemy.sql.functions import max as max_

from ...error import ConsistencyError, NoSuchRecord, UserError
from ...type import Member, MemberCollection, Proposal, \
    Queue, QueueInfo, ResultCollection, Semester, SemesterInfo
from ..meta import call, facility, member, person, proposal, queue, semester


class ProposalPart(object):
    def add_call(self, semester_id, queue_id, _test_skip_check=False):
        """
        Add a call for proposals to the database.
        """

        with self._transaction() as conn:
            if not _test_skip_check:
                try:
                    semester = self._get_semester(conn, semester_id)
                    queue = self._get_queue(conn, queue_id)
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
            }))

        return result.inserted_primary_key[0]

    def add_member(self, proposal_id, person_id, pi=False, editor=False,
                   observer=False, _test_skip_check=False):
        with self._transaction() as conn:
            return self._add_member(conn, proposal_id, person_id, pi, editor,
                                    observer, _test_skip_check)

    def _add_member(self, conn, proposal_id, person_id, pi, editor, observer,
                    _test_skip_check=False):
        if (not _test_skip_check and
                not self._exists_id(conn, person, person_id)):
            raise ConsistencyError('person does not exist with id={0}',
                                   person_id)

        result = conn.execute(member.insert().values({
            member.c.proposal_id: proposal_id,
            member.c.person_id: person_id,
            member.c.pi: pi,
            member.c.editor: editor,
            member.c.observer: observer,
        }))

        return result.inserted_primary_key[0]

    def add_proposal(self, call_id, person_id, title, _test_skip_check=False):
        """
        Add a new proposal to the database.

        The given person will be added as a member, assumed to be PI
        and with "editor" permission so that they can continue to
        prepare the proposal.
        """

        if not title:
            raise UserError('The proposal title should not be blank.')

        with self._transaction() as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, call, call_id)):
                raise ConsistencyError('call does not exist with id={0}',
                                       call_id)

            result = conn.execute(proposal.insert().values({
                proposal.c.call_id: call_id,
                proposal.c.number: select(
                    [coalesce(max_(proposal.c.number), 0) + 1]).where(
                    proposal.c.call_id == call_id),
                proposal.c.title: title,
            }))

            proposal_id = result.inserted_primary_key[0]

            self._add_member(conn, proposal_id, person_id, True, True, False,
                             _test_skip_check=_test_skip_check)

        return proposal_id

    def add_queue(self, facility_id, name, _test_skip_check=False):
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
            }))

            return result.inserted_primary_key[0]

    def add_semester(self, facility_id, name, _test_skip_check=False):
        """
        Add a semester to the database.
        """

        if not name:
            raise UserError('The semester name can not be blank.')

        with self._transaction() as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, facility, facility_id)):
                raise ConsistencyError('facility does not exist with id={0}',
                                       facility_id)

            result = conn.execute(semester.insert().values({
                queue.c.facility_id: facility_id,
                queue.c.name: name,
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

    def get_proposal(self, proposal_id, with_members=False):
        """
        Get a proposal record.
        """

        members = None

        with self._transaction() as conn:
            result = conn.execute(proposal.select().where(
                proposal.c.id == proposal_id
            )).first()

            if result is None:
                raise NoSuchRecord('proposal does not exist with id={0}',
                                   proposal_id)

            if with_members:
                members = self._search_member(conn, proposal_id=proposal_id)

        return Proposal(members=members, **result)

    def get_semester(self, *args, **kwargs):
        """
        Get a semester record.
        """

        with self._transaction() as conn:
            return self._get_semester(conn, *args, **kwargs)

    def _get_semester(self, conn, semester_id):
        result = conn.execute(semester.select().where(
            semester.c.id == semester_id
        )).first()

        if result is None:
            raise NoSuchRecord('semester does not exist with id={0}',
                               semester_id)

        return Semester(**result)

    def get_queue(self, *args, **kwargs):
        """
        Get a queue record.
        """

        with self._transaction() as conn:
            return self._get_queue(conn, *args, **kwargs)

    def _get_queue(self, conn, queue_id):
        result = conn.execute(queue.select().where(
            queue.c.id == queue_id
        )).first()

        if result is None:
            raise NoSuchRecord('queue does not exist with id={0}',
                               queue_id)

        return Queue(**result)

    def search_member(self, proposal_id=None, person_id=None):
        with self._transaction() as conn:
            return self._search_member(conn, proposal_id, person_id)

    def _search_member(self, conn, proposal_id=None, person_id=None):
        stmt = member.select()
        if proposal_id is not None:
            stmt = stmt.where(member.c.proposal_id == proposal_id)
        if person_id is not None:
            stmt = stmt.where(member.c.person_id == person_id)

        ans = MemberCollection()

        for row in conn.execute(stmt.order_by(member.c.id)):
            ans[row['id']] = Member(**row)

        return ans

    def search_semester(self, facility_id=None):
        stmt = select([semester.c.id, semester.c.facility_id, semester.c.name])

        if facility_id is not None:
            stmt = stmt.where(semester.c.facility_id == facility_id)

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(desc(semester.c.id))):
                ans[row['id']] = SemesterInfo(**row)

        return ans

    def search_queue(self, facility_id=None):
        stmt = select([queue.c.id, queue.c.facility_id, queue.c.name])

        if facility_id is not None:
            stmt = stmt.where(queue.c.facility_id == facility_id)

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by((queue.c.name))):
                ans[row['id']] = QueueInfo(**row)

        return ans

    def update_semester(self, semester_id, name=None, _test_skip_check=False):
        """
        Update a semester record.
        """

        values = {}

        if name is not None:
            values['name'] = name

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

    def update_queue(self, queue_id, name=None, _test_skip_check=False):
        """
        Update a queue record.
        """

        values = {}

        if name is not None:
            values['name'] = name

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
