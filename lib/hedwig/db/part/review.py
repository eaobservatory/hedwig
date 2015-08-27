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

from ...error import ConsistencyError, Error
from ...type import GroupMember, GroupMemberCollection, GroupType, \
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
