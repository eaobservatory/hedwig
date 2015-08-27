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
from sqlalchemy.sql.expression import and_
from sqlalchemy.sql.functions import count

from ...error import ConsistencyError, Error, NoSuchRecord, UserError
from ...type import FormatType, \
    GroupMember, GroupMemberCollection, GroupType, \
    NoteRole, ProposalNote, Review, Reviewer, ReviewerRole
from ..meta import group_member, person, proposal, proposal_note, queue, \
    review, reviewer


class ReviewPart(object):
    def add_group_member(self, queue_id, group_type, person_id,
                         _conn=None, _test_skip_check=False):
        if not GroupType.is_valid(group_type):
            raise Error('invalid group type')

        with self._transaction(_conn=_conn) as conn:
            if not _test_skip_check:
                if not self._exists_id(conn, queue, queue_id):
                    raise ConsistencyError('queue does not exist with id={}',
                                           queue_id)
                if not self._exists_id(conn, person, person_id):
                    raise ConsistencyError('person does not exist with id={}',
                                           person_id)

            result = conn.execute(group_member.insert().values({
                group_member.c.queue_id: queue_id,
                group_member.c.group_type: group_type,
                group_member.c.person_id: person_id,
            }))

        return result.inserted_primary_key[0]

    def get_proposal_note(self, proposal_id, role):
        """
        Get the given review process note associated with a proposal.
        """

        if not NoteRole.is_valid(role):
            raise Error('invalid note role')

        with self._transaction() as conn:
            row = conn.execute(proposal_note.select().where(and_(
                proposal_note.c.proposal_id == proposal_id,
                proposal_note.c.role == role
            ))).first()

        if row is None:
            raise NoSuchRecord('note does not exist for {} role {}',
                               proposal_id, role)

        return ProposalNote(**row)

    def search_group_member(self, queue_id, group_type, _conn=None):
        stmt = group_member.select()

        if queue_id is not None:
            stmt = stmt.where(group_member.c.queue_id == queue_id)

        if group_type is not None:
            stmt = stmt.where(group_member.c.group_type == group_type)

        ans = GroupMemberCollection()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt.order_by(group_member.c.id)):
                ans[row['id']] = GroupMember(**row)

        return ans

    def set_proposal_note(self, proposal_id, role, text, format_, is_update,
                          _test_skip_check=False):
        if not NoteRole.is_valid(role):
            raise Error('invalid note role')

        if not format_:
            raise UserError('Text format not specified.')
        if not FormatType.is_valid(format_):
            raise UserError('Text format not recognised.')

        with self._transaction() as conn:
            if not _test_skip_check:
                if not self._exists_id(conn, proposal, proposal_id):
                    raise ConsistencyError('proposal does not exist with id={}',
                                           proposal_id)

                already_exists = self._exists_proposal_note(
                    conn, proposal_id, role)
                if is_update and not already_exists:
                    raise ConsistencyError(
                        'note does not exist for proposal {} role {}',
                        proposal_id, role)
                elif already_exists and not is_update:
                    raise ConsistencyError(
                        'note already exists for proposal {} role {}',
                        proposal_id, role)

            values = {
                proposal_note.c.text: text,
                proposal_note.c.format: format_,
                proposal_note.c.edited: datetime.utcnow(),
            }

            if is_update:
                result = conn.execute(proposal_note.update().where(and_(
                    proposal_note.c.proposal_id == proposal_id,
                    proposal_note.c.role == role
                )).values(values))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched updating proposal text {} role {}',
                        proposal_id, role)

            else:
                values.update({
                    proposal_note.c.proposal_id: proposal_id,
                    proposal_note.c.role: role,
                })

                result = conn.execute(proposal_note.insert().values(values))

    def sync_group_member(self, queue_id, group_type, records):
        """
        Update the member records of the given group for the given queue.

        Currently this just allows removing members of the group,
        but could be extended if group members gain extra attributes.
        (E.g. the chair of a group representing a committee.)
        """

        if not GroupType.is_valid(group_type):
            raise Error('invalid group type')

        with self._transaction() as conn:
            if not self._exists_id(conn, queue, queue_id):
                raise ConsistencyError('queue does not exist with id={}',
                                       queue_id)

            self._sync_records(
                conn, group_member,
                key_column=(group_member.c.queue_id,
                            group_member.c.group_type),
                key_value=(queue_id, group_type),
                records=records,
                update_columns=(),
                forbid_add=True)

    def _exists_proposal_note(self, conn, proposal_id, role):
        """
        Test whether a note of the given role already exists for a proposal.
        """

        return 0 < conn.execute(select([count(proposal_note.c.id)]).where(and_(
            proposal_note.c.proposal_id == proposal_id,
            proposal_note.c.role == role
        ))).scalar()
