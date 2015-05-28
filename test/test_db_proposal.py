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
    NoSuchRecord, UserError
from insertnamehere.type import Affiliation, Call, \
    Member, MemberCollection, Proposal, ResultCollection
from .dummy_db import DBTestCase


class DBProposalTest(DBTestCase):
    def test_facility(self):
        # Test the ensure_facility method.
        facility_id = self.db.ensure_facility('my_tel')
        self.assertIsInstance(facility_id, int)

        facility_id_copy = self.db.ensure_facility('my_tel')
        facility_id_diff = self.db.ensure_facility('my_other_tel')

        self.assertEqual(facility_id_copy, facility_id)
        self.assertNotEqual(facility_id_diff, facility_id)

    def test_affiliation(self):
        # Get test facility ID.
        facility_id = self.db.ensure_facility('test_tel')
        self.assertIsInstance(facility_id, int)

        # Check we have no affiliations to start.
        result = self.db.search_affiliation(facility_id=facility_id)
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(len(result), 0)

        # Generate a collection of 2 records and sync it.
        records = ResultCollection()
        records[0] = Affiliation(None, facility_id, 'Aff 1', True)
        records[1] = Affiliation(None, facility_id, 'Aff 2', False)

        n = self.db.sync_facility_affiliation(facility_id, records)
        self.assertEqual(n, (2, 0, 0))

        # Check that we now have the expected 2 records.
        result = self.db.search_affiliation(facility_id=facility_id)
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(len(result), 2)
        for (row, expect_name, expect_hidden) in zip(
                result.values(), ('Aff 1', 'Aff 2'), (True, False)):
            self.assertIsInstance(row.id, int)
            self.assertEqual(row.name, expect_name)
            self.assertEqual(row.hidden, expect_hidden)

        # Check we can't remove an affiliation once it is in use.
        semester_id = self.db.add_semester(facility_id, 'Sem1')
        queue_id = self.db.add_queue(facility_id, 'Queue1')
        call_id = self.db.add_call(semester_id, queue_id)
        person_id = self.db.add_person('Person1')
        (affiliation_id, affiliation_record) = result.popitem()
        self.db.add_proposal(call_id, person_id, affiliation_id, 'Title')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.sync_facility_affiliation(facility_id, result)

    def test_semester(self):
        # Test add_semeseter method.
        facility_id = self.db.ensure_facility('my_tel')
        self.assertIsInstance(facility_id, int)

        with self.assertRaisesRegexp(ConsistencyError, 'facility does not'):
            self.db.add_semester(999, '99A')

        semester_id = self.db.add_semester(facility_id, '99A')
        self.assertIsInstance(semester_id, int)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_semester(facility_id, '99A')

        semester_id_2 = self.db.add_semester(facility_id, '99B')
        self.assertIsInstance(semester_id_2, int)
        self.assertNotEqual(semester_id_2, semester_id)

        semesters = self.db.search_semester(facility_id=facility_id)
        self.assertIsInstance(semesters, ResultCollection)
        self.assertEqual(len(semesters), 2)

        # Try updating a record.
        self.assertEqual(self.db.get_semester(facility_id, semester_id).name,
                         '99A')
        self.db.update_semester(semester_id, name='99 (a)')
        self.assertEqual(self.db.get_semester(facility_id, semester_id).name,
                         '99 (a)')
        with self.assertRaisesRegexp(ConsistencyError, 'semester does not ex'):
            self.db.update_semester(999, name='bad semester')

        # Check for semesters which don't exist or have wrong facility.
        with self.assertRaises(NoSuchRecord):
            self.db.get_semester(facility_id, 999)
        with self.assertRaises(NoSuchRecord):
            self.db.get_semester(999, semester_id)

    def test_queue(self):
        # Test add_queue method.
        facility_id = self.db.ensure_facility('my_tel')
        self.assertIsInstance(facility_id, int)

        with self.assertRaisesRegexp(ConsistencyError, 'facility does not'):
            self.db.add_queue(999, 'INT')

        queue_id = self.db.add_queue(facility_id, 'INT')
        self.assertIsInstance(queue_id, int)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_queue(facility_id, 'INT')

        queue_id_2 = self.db.add_queue(facility_id, 'XYZ')
        self.assertIsInstance(queue_id_2, int)
        self.assertNotEqual(queue_id_2, queue_id)

        # Try searching: add a queue for another facility first.
        facility_id_2 = self.db.ensure_facility('my_other_tel')
        queue_id_3 = self.db.add_queue(facility_id_2, '???')
        self.assertIsInstance(queue_id_3, int)
        queues = self.db.search_queue(facility_id=facility_id)
        self.assertIsInstance(queues, ResultCollection)
        self.assertEqual(list(queues.keys()), [queue_id, queue_id_2])
        queues = self.db.search_queue(facility_id=facility_id_2)
        self.assertEqual(list(queues.keys()), [queue_id_3])

        # Try updating a record.
        queue = self.db.get_queue(facility_id_2, queue_id_3)
        self.assertEqual(queue.name, '???')
        self.db.update_queue(queue_id_3, name='!!!')
        queue = self.db.get_queue(facility_id_2, queue_id_3)
        self.assertEqual(queue.name, '!!!')

        # Check test for non-existant queue or facility.
        with self.assertRaises(NoSuchRecord):
            self.db.get_queue(facility_id_2, 999)
        with self.assertRaises(NoSuchRecord):
            self.db.get_queue(999, queue_id_3)

    def test_call(self):
        # Check that we can create a call for proposals.
        facility_id = self.db.ensure_facility('my_tel')
        self.assertIsInstance(facility_id, int)
        semester_id = self.db.add_semester(facility_id, 'My Semester')
        self.assertIsInstance(semester_id, int)
        queue_id = self.db.add_queue(facility_id, 'My Queue')
        self.assertIsInstance(queue_id, int)

        call_id = self.db.add_call(semester_id, queue_id)
        self.assertIsInstance(call_id, int)

        # Check tests for bad values.
        with self.assertRaisesRegexp(ConsistencyError, 'semester does not'):
            self.db.add_call(999, queue_id)
        with self.assertRaisesRegexp(ConsistencyError, 'queue does not'):
            self.db.add_call(semester_id, 999)

        # Check uniqueness constraint.
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_call(semester_id, queue_id)

        # Check facility consistency check.
        facility_id_2 = self.db.ensure_facility('my_other_tel')
        semester_id_2 = self.db.add_semester(facility_id_2, 'My Semester')
        with self.assertRaisesRegexp(ConsistencyError,
                                     'inconsistent facility references'):
            self.db.add_call(semester_id_2, queue_id)

        # Try the search_call method.
        result = self.db.search_call(call_id=call_id)
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(list(result.keys()), [call_id])
        expected = Call(id=call_id, semester_id=semester_id, queue_id=queue_id,
                        facility_id=facility_id,
                        semester_name='My Semester', queue_name='My Queue')
        self.assertEqual(result[call_id], expected)
        self.assertEqual(self.db.get_call(facility_id, call_id), expected)

        with self.assertRaises(NoSuchRecord):
            self.db.get_call(facility_id, 999)

        with self.assertRaises(NoSuchRecord):
            self.db.get_call(999, call_id)

    def test_add_proposal(self):
        (call_id_1, affiliation_id_1) = self._create_test_call(
            'semester1', 'queue1')
        self.assertIsInstance(call_id_1, int)
        (call_id_2, affiliation_id_2) = self._create_test_call(
            'semester2', 'queue2')
        self.assertIsInstance(call_id_2, int)

        person_id = self.db.add_person('Person 1')
        self.assertIsInstance(person_id, int)

        # Create proposals and check the numbers are as expected.
        for (call_id, affiliation_id) in ((call_id_1, affiliation_id_1),
                                          (call_id_2, affiliation_id_2)):
            for i in range(1, 11):
                title = 'Proposal {0}'.format(i)
                proposal_id = self.db.add_proposal(call_id, person_id,
                                                   affiliation_id, title)
                self.assertIsInstance(proposal_id, int)

                proposal = self.db.get_proposal(None, proposal_id,
                                                with_members=True)
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
            self.db.add_proposal(call_id_1, person_id, affiliation_id_1, '')

        # Check for error raised when the call or person doesn't exist.
        with self.assertRaisesRegexp(ConsistencyError, '^call does not'):
            self.db.add_proposal(999, person_id, affiliation_id_1, 'Title')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_proposal(999, person_id, affiliation_id_1, 'Title',
                                 _test_skip_check=True)

        with self.assertRaisesRegexp(ConsistencyError, '^person does not'):
            self.db.add_proposal(call_id, 999, affiliation_id_1, 'Title')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_proposal(call_id, 999, affiliation_id_1, 'Title',
                                 _test_skip_check=True)

        # Check for error raised when the affiliation is for the wrong
        # facility.
        other_facility_id = self.db.ensure_facility('another_tel')
        other_affiliation_id = self.db.add_affiliation(other_facility_id,
                                                       'another aff/n')
        with self.assertRaisesRegexp(ConsistencyError, 'affiliation does not'):
            self.db.add_proposal(call_id_1, person_id, other_affiliation_id,
                                 'title')

        # Check that the "with_proposals" option of "get_user" works.
        result = self.db.get_person(person_id, with_proposals=True)
        self.assertIsInstance(result.proposals, ResultCollection)
        self.assertEqual(len(result.proposals), 20)

    def test_add_member(self):
        # Create test records and check we have integer identifiers for all.
        (call_id, affiliation_id) = self._create_test_call(
            'semester1', 'queue1')
        person_id_1 = self.db.add_person('Person 1')
        person_id_2 = self.db.add_person('Person 2')
        person_id_3 = self.db.add_person('Person 3')
        proposal_id = self.db.add_proposal(call_id, person_id_1,
                                           affiliation_id, 'Proposal 1')

        for id_ in (call_id, person_id_1, person_id_2, person_id_3,
                    proposal_id):
            self.assertIsInstance(id_, int)

        # Check the member list as we add members one at a time.
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(_member_person_set(result), [person_id_1])

        self.db.add_member(proposal_id, person_id_2, affiliation_id,
                           False, False, True)
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(_member_person_set(result),
                         [person_id_1, person_id_2])

        self.db.add_member(proposal_id, person_id_3, affiliation_id,
                           False, True, True)
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(_member_person_set(result),
                         [person_id_1, person_id_2, person_id_3])

        self.assertEqual(result.get_pi().person_id, person_id_1)

        # Ensure we can't add a member twice.
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_member(proposal_id, person_id_2, affiliation_id,
                               False, False, False)

        # Ensure we can't add a member with an affiliation for the wrong
        # facility.
        person_id_4 = self.db.add_person('Person 4')
        other_facility = self.db.ensure_facility('another_tel')
        other_affiliation = self.db.add_affiliation(other_facility, 'Aff/n')
        with self.assertRaisesRegexp(ConsistencyError, 'affiliation does not'):
            self.db.add_member(proposal_id, person_id_4, other_affiliation)

        # Try searching instead by person_id.
        result = self.db.search_member(person_id=person_id_2)
        member = result.get_single()
        self.assertEqual(member.proposal_id, proposal_id)
        self.assertEqual(member.person_id, person_id_2)

    def _create_test_call(self, semester_name, queue_name):
        facility_id = self.db.ensure_facility('my_tel')
        self.assertIsInstance(facility_id, int)
        semester_id = self.db.add_semester(facility_id, semester_name)
        self.assertIsInstance(semester_id, int)
        queue_id = self.db.add_queue(facility_id, queue_name)
        self.assertIsInstance(queue_id, int)

        call_id = self.db.add_call(semester_id, queue_id)
        self.assertIsInstance(call_id, int)

        affiliations = self.db.search_affiliation(facility_id=facility_id)
        if affiliations:
            affiliation_id = affiliations.values()[0].id
        else:
            affiliation_id = self.db.add_affiliation(facility_id, 'test aff/n')
        self.assertIsInstance(affiliation_id, int)

        return (call_id, affiliation_id)


def _member_person_set(member_collection):
    return map(lambda x: x.person_id, member_collection.values())
