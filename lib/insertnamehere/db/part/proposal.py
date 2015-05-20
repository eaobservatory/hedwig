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
from sqlalchemy.sql.functions import coalesce, count
from sqlalchemy.sql.functions import max as max_

from ...error import ConsistencyError, UserError
from ...type import Member, MemberCollection, Proposal
from ..meta import call, member, proposal


class ProposalPart(object):
    def add_call(self):
        """
        Add a call for proposals to the database.
        """

        with self._transaction() as conn:
            result = conn.execute(call.insert().values({
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
                not self._exists_person_id(conn, person_id)):
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
                    not self._exists_call_id(conn, call_id)):
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

    def _exists_call_id(self, conn, call_id):
        """Test whether a call exists."""
        return 0 < conn.execute(select([count(call.c.id)]).where(
            call.c.id == call_id,
        )).scalar()
