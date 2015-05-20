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

from insertnamehere.error import ConsistencyError, DatabaseIntegrityError, \
    UserError
from insertnamehere.type import Member, MemberCollection, Proposal
from .dummy_db import DBTestCase


class DBProposalTest(DBTestCase):
    def test_call(self):
        # Check that we can create a call for proposals.
        call_id = self.db.add_call()
        self.assertIsInstance(call_id, int)

    def test_add_proposal(self):
        call_id_1 = self.db.add_call()
        self.assertIsInstance(call_id_1, int)
        call_id_2 = self.db.add_call()
        self.assertIsInstance(call_id_2, int)

        person_id = self.db.add_person('Person 1')
        self.assertIsInstance(person_id, int)

        # Create proposals and check the numbers are as expected.
        for call_id in (call_id_1, call_id_2):
            for i in range(1, 11):
                title = 'Proposal {0}'.format(i)
                proposal_id = self.db.add_proposal(call_id, person_id, title)
                self.assertIsInstance(proposal_id, int)

                proposal = self.db.get_proposal(proposal_id, with_members=True)
                self.assertIsInstance(proposal, Proposal)

                self.assertEqual(proposal.number, i)

                # Check remaining proposal records.
                self.assertEqual(proposal.id, proposal_id)
                self.assertEqual(proposal.title, title)
                self.assertEqual(proposal.call_id, call_id)
                self.assertIsInstance(proposal.members, MemberCollection)
                self.assertEqual(len(proposal.members), 1)
                member = proposal.members.get_single()
                self.assertIsInstance(member, Member)
                self.assertEqual(member.person_id, person_id)
                self.assertEqual(member.proposal_id, proposal_id)
                self.assertTrue(member.pi)
                self.assertTrue(member.editor)
                self.assertFalse(member.observer)

        # The proposal must have a title.
        with self.assertRaisesRegexp(UserError, 'blank'):
            self.db.add_proposal(call_id_1, person_id, '')

        # Check for error raised when the call or person doesn't exist.
        with self.assertRaisesRegexp(ConsistencyError, '^call does not'):
            self.db.add_proposal(999, person_id, 'Title')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_proposal(999, person_id, 'Title',
                                 _test_skip_check=True)

        with self.assertRaisesRegexp(ConsistencyError, '^person does not'):
            self.db.add_proposal(call_id, 999, 'Title')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_proposal(call_id, 999, 'Title', _test_skip_check=True)

    def test_add_member(self):
        # Create test records and check we have integer identifiers for all.
        call_id = self.db.add_call()
        person_id_1 = self.db.add_person('Person 1')
        person_id_2 = self.db.add_person('Person 2')
        person_id_3 = self.db.add_person('Person 3')
        proposal_id = self.db.add_proposal(call_id, person_id_1, 'Proposal 1')

        for id_ in (call_id, person_id_1, person_id_2, person_id_3,
                    proposal_id):
            self.assertIsInstance(id_, int)

        # Check the member list as we add members one at a time.
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(_member_person_set(result), [person_id_1])

        self.db.add_member(proposal_id, person_id_2, False, False, True)
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(_member_person_set(result),
                         [person_id_1, person_id_2])

        self.db.add_member(proposal_id, person_id_3, False, True, True)
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(_member_person_set(result),
                         [person_id_1, person_id_2, person_id_3])

        self.assertEqual(result.get_pi().person_id, person_id_1)

        # Ensure we can't add a member twice.
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_member(proposal_id, person_id_2, False, False, False)

        # Try searching instead by person_id.
        result = self.db.search_member(person_id=person_id_2)
        member = result.get_single()
        self.assertEqual(member.proposal_id, proposal_id)
        self.assertEqual(member.person_id, person_id_2)


def _member_person_set(member_collection):
    return map(lambda x: x.person_id, member_collection.values())
