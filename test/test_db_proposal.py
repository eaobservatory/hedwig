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

from hedwig.db.meta import member
from hedwig.error import ConsistencyError, DatabaseIntegrityError, \
    Error, NoSuchRecord, UserError
from hedwig.type import Affiliation, AttachmentState, Call, Category, \
    FigureType, FormatType, \
    Member, MemberCollection, MemberInstitution,  \
    Proposal, ProposalCategory, \
    ProposalFigureInfo, ProposalPDFInfo, \
    ProposalState, \
    ProposalText, ProposalTextCollection, ProposalTextInfo, \
    ResultCollection, Target, TargetCollection, TextRole
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
        queue_id = self.db.add_queue(facility_id, 'Queue1', 'Q1')
        self.assertIsInstance(queue_id, int)

        # Check we have no affiliations to start.
        result = self.db.search_affiliation(queue_id=queue_id)
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(len(result), 0)

        # Generate a collection of 2 records and sync it.
        records = ResultCollection()
        records[0] = Affiliation(None, queue_id, 'Aff 1', True)
        records[1] = Affiliation(None, queue_id, 'Aff 2', False)

        n = self.db.sync_queue_affiliation(queue_id, records)
        self.assertEqual(n, (2, 0, 0))

        # Check that we now have the expected 2 records.
        result = self.db.search_affiliation(queue_id=queue_id)
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(len(result), 2)
        for (row, expect_name, expect_hidden) in zip(
                result.values(), ('Aff 1', 'Aff 2'), (True, False)):
            self.assertIsInstance(row.id, int)
            self.assertEqual(row.name, expect_name)
            self.assertEqual(row.hidden, expect_hidden)

        # Check we can't remove an affiliation once it is in use.
        semester_id = self.db.add_semester(
            facility_id, 'Sem1', 'S1',
            datetime(2000, 1, 1), datetime(2000, 6, 30))
        call_id = self.db.add_call(semester_id, queue_id,
                                   datetime(1999, 9, 1), datetime(1999, 9, 30),
                                   1, 1, 1, 1, 1, 1, 1, 1, 1, '', '', '',
                                   FormatType.PLAIN)
        person_id = self.db.add_person('Person1')
        (affiliation_id, affiliation_record) = result.popitem()
        self.db.add_proposal(call_id, person_id, affiliation_id, 'Title')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.sync_queue_affiliation(queue_id, result)

    def test_semester(self):
        # Test add_semeseter method.
        facility_id = self.db.ensure_facility('my_tel')
        self.assertIsInstance(facility_id, int)

        date_start = datetime(2002, 2, 2)
        date_end = datetime(2002, 8, 1)

        with self.assertRaisesRegexp(UserError, 'end date is before start'):
            self.db.add_semester(facility_id, '99A', '99A',
                                 date_end, date_start)

        with self.assertRaisesRegexp(ConsistencyError, 'facility does not'):
            self.db.add_semester(1999999, '99A', '99A', date_start, date_end)

        semester_id = self.db.add_semester(facility_id, '99A', '99A',
                                           date_start, date_end)
        self.assertIsInstance(semester_id, int)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_semester(facility_id, '99A', '99A2',
                                 date_start, date_end)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_semester(facility_id, '99A2', '99A',
                                 date_start, date_end)

        semester_id_2 = self.db.add_semester(facility_id, '99B', '99B',
                                             date_start, date_end)
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
            self.db.update_semester(1999999, name='bad semester')
        with self.assertRaisesRegexp(UserError, 'end date is before start'):
            self.db.update_semester(semester_id,
                                    date_start=date_end, date_end=date_start)

        # Check for semesters which don't exist or have wrong facility.
        with self.assertRaises(NoSuchRecord):
            self.db.get_semester(facility_id, 1999999)
        with self.assertRaises(NoSuchRecord):
            self.db.get_semester(1999999, semester_id)

    def test_queue(self):
        # Test add_queue method.
        facility_id = self.db.ensure_facility('my_tel')
        self.assertIsInstance(facility_id, int)

        with self.assertRaisesRegexp(ConsistencyError, 'facility does not'):
            self.db.add_queue(1999999, 'INT', 'I')

        queue_id = self.db.add_queue(facility_id, 'INT', 'I')
        self.assertIsInstance(queue_id, int)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_queue(facility_id, 'INT', 'I2')

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_queue(facility_id, 'INT2', 'I')

        queue_id_2 = self.db.add_queue(facility_id, 'XYZ', 'XYZ')
        self.assertIsInstance(queue_id_2, int)
        self.assertNotEqual(queue_id_2, queue_id)

        # Try searching: add a queue for another facility first.
        facility_id_2 = self.db.ensure_facility('my_other_tel')
        queue_id_3 = self.db.add_queue(facility_id_2, '???', '?')
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
            self.db.get_queue(facility_id_2, 1999999)
        with self.assertRaises(NoSuchRecord):
            self.db.get_queue(1999999, queue_id_3)

    def test_call(self):
        # Check that we can create a call for proposals.
        facility_id = self.db.ensure_facility('my_tel')
        self.assertIsInstance(facility_id, int)
        semester_id = self.db.add_semester(
            facility_id, 'My Semester', 'MS',
            datetime(2000, 1, 1), datetime(2000, 6, 30))
        self.assertIsInstance(semester_id, int)
        queue_id = self.db.add_queue(facility_id, 'My Queue', 'MQ')
        self.assertIsInstance(queue_id, int)

        date_open = datetime(1999, 9, 1)
        date_close = datetime(1999, 9, 30)

        call_id = self.db.add_call(
            semester_id, queue_id, date_open, date_close,
            abst_word_lim=1,
            tech_word_lim=2, tech_fig_lim=7, tech_page_lim=3,
            sci_word_lim=4, sci_fig_lim=5, sci_page_lim=6,
            capt_word_lim=8, expl_word_lim=9,
            tech_note='technical note', sci_note='scientific note',
            prev_prop_note='previous proposal note',
            note_format=FormatType.PLAIN)
        self.assertIsInstance(call_id, int)

        # Check tests for bad values.
        with self.assertRaisesRegexp(ConsistencyError, 'semester does not'):
            self.db.add_call(1999999, queue_id, date_open, date_close,
                             1, 1, 1, 1, 1, 1, 1, 1, 1,
                             '', '', '', FormatType.PLAIN)
        with self.assertRaisesRegexp(ConsistencyError, 'queue does not'):
            self.db.add_call(semester_id, 1999999, date_open, date_close,
                             1, 1, 1, 1, 1, 1, 1, 1, 1,
                             '', '', '', FormatType.PLAIN)
        with self.assertRaisesRegexp(UserError, 'Closing date is before open'):
            self.db.add_call(semester_id, queue_id, date_close, date_open,
                             1, 1, 1, 1, 1, 1, 1, 1, 1,
                             '', '', '', FormatType.PLAIN)

        # Check uniqueness constraint.
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_call(semester_id, queue_id, date_open, date_close,
                             1, 1, 1, 1, 1, 1, 1, 1, 1,
                             '', '', '', FormatType.PLAIN)

        # Check facility consistency check.
        facility_id_2 = self.db.ensure_facility('my_other_tel')
        semester_id_2 = self.db.add_semester(
            facility_id_2, 'My Semester', 'MS',
            datetime(2000, 2, 1), datetime(2000, 7, 31))
        with self.assertRaisesRegexp(ConsistencyError,
                                     'inconsistent facility references'):
            self.db.add_call(semester_id_2, queue_id, date_open, date_close,
                             1, 1, 1, 1, 1, 1, 1, 1, 1,
                             '', '', '', FormatType.PLAIN)

        # Try the search_call method.
        result = self.db.search_call(call_id=call_id)
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(list(result.keys()), [call_id])
        expected = Call(id=call_id, semester_id=semester_id, queue_id=queue_id,
                        date_open=date_open, date_close=date_close,
                        facility_id=facility_id,
                        semester_name='My Semester', queue_name='My Queue',
                        queue_description=None, queue_description_format=None,
                        abst_word_lim=1,
                        tech_word_lim=2, tech_fig_lim=7, tech_page_lim=3,
                        sci_word_lim=4, sci_fig_lim=5, sci_page_lim=6,
                        capt_word_lim=8, expl_word_lim=9,
                        tech_note='technical note', sci_note='scientific note',
                        prev_prop_note='previous proposal note',
                        note_format=FormatType.PLAIN)
        self.assertEqual(result[call_id],
                         expected._replace(tech_note=None, sci_note=None,
                                           prev_prop_note=None))
        self.assertEqual(self.db.get_call(facility_id, call_id), expected)

        with self.assertRaises(NoSuchRecord):
            self.db.get_call(facility_id, 1999999)

        with self.assertRaises(NoSuchRecord):
            self.db.get_call(1999999, call_id)

        # Try updating the call.
        with self.assertRaisesRegexp(ConsistencyError, 'call does not exist'):
            self.db.update_call(1999999, date_open=date_open)
        with self.assertRaisesRegexp(UserError, 'Closing date is before open'):
            self.db.update_call(call_id,
                                date_close=date_open, date_open=date_close)
        self.db.update_call(call_id, date_close=datetime(1999, 10, 1))
        call = self.db.get_call(facility_id, call_id)
        self.assertEqual(call.date_close.month, 10)

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
                self.assertEqual(proposal.state, ProposalState.PREPARATION)
                self.assertIsInstance(proposal.members, MemberCollection)
                self.assertEqual(len(proposal.members), 1)
                member = proposal.members.get_single()
                self.assertIsInstance(member, Member)
                self.assertEqual(member.person_id, person_id)
                self.assertEqual(member.proposal_id, proposal_id)
                self.assertTrue(member.pi)
                self.assertTrue(member.editor)
                self.assertFalse(member.observer)

                # Try updating the proposal.
                self.db.update_proposal(proposal_id,
                                        state=ProposalState.SUBMITTED)
                proposal_updated = self.db.get_proposal(None, proposal_id)
                self.assertEqual(proposal_updated, proposal._replace(
                    state=ProposalState.SUBMITTED,
                    members=None))

                # Try searching for proposals.
                result = self.db.search_proposal(call_id=call_id)
                self.assertIsInstance(result, ResultCollection)
                self.assertEqual(len(result), i)
                self.assertIn(proposal_id, result)
                proposal = result[proposal_id]
                self.assertIsInstance(proposal, Proposal)
                self.assertEqual(proposal.id, proposal_id)
                self.assertEqual(proposal.call_id, call_id)
                self.assertEqual(proposal.number, i)
                self.assertEqual(proposal.state, ProposalState.SUBMITTED)
                self.assertEqual(proposal.title, title)
                self.assertIsNone(proposal.members)

        # The proposal must have a title.
        with self.assertRaisesRegexp(UserError, 'blank'):
            self.db.add_proposal(call_id_1, person_id, affiliation_id_1, '')

        # Check for error raised when the call or person doesn't exist.
        with self.assertRaisesRegexp(ConsistencyError, '^call does not'):
            self.db.add_proposal(1999999, person_id, affiliation_id_1, 'Title')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_proposal(1999999, person_id, affiliation_id_1, 'Title',
                                 _test_skip_check=True)

        with self.assertRaisesRegexp(ConsistencyError, '^person does not'):
            self.db.add_proposal(call_id_1, 1999999, affiliation_id_1, 'Title')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_proposal(call_id_1, 1999999, affiliation_id_1, 'Title',
                                 _test_skip_check=True)

        # Check for error raised when the affiliation is for the wrong
        # queue.
        other_facility_id = self.db.ensure_facility('another_tel')
        other_queue_id = self.db.add_queue(other_facility_id, 'another queue',
                                           'aq')
        other_affiliation_id = self.db.add_affiliation(other_queue_id,
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

        self.assertEqual(self.db.get_proposal_facility_code(proposal_id),
                         'my_tel')

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
        other_queue = self.db.add_queue(other_facility, 'another queue', 'aq')
        other_affiliation = self.db.add_affiliation(other_queue, 'Aff/n')
        with self.assertRaisesRegexp(ConsistencyError, 'affiliation does not'):
            self.db.add_member(proposal_id, person_id_4, other_affiliation)

        # Try searching instead by person_id.
        result = self.db.search_member(person_id=person_id_2)
        member = result.get_single()
        self.assertEqual(member.proposal_id, proposal_id)
        self.assertEqual(member.person_id, person_id_2)

    def test_sync_proposal_member(self):
        (call_id, affiliation_id) = self._create_test_call('s1', 'q1')
        person_id_1 = self.db.add_person('Person 1')
        person_id_2 = self.db.add_person('Person 2')
        proposal_id = self.db.add_proposal(
            call_id, person_id_1, affiliation_id, 'Proposal Title')
        self.assertIsInstance(proposal_id, int)

        self.db.add_member(proposal_id, person_id_2, affiliation_id)

        members = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(len(members), 2)

        (member_id_1, member_id_2) = members.keys()
        self.assertEqual(members[member_id_1].person_id, person_id_1)
        self.assertEqual(members[member_id_2].person_id, person_id_2)

        (n_insert, n_update, n_delete) = self.db.sync_proposal_member(
            proposal_id, members, person_id_1)
        self.assertEqual(n_insert, 0)
        self.assertEqual(n_update, 0)
        self.assertEqual(n_delete, 0)

        with self.assertRaisesRegexp(UserError, 'no specified editors'):
            mem_c = members.copy()
            mem_c[member_id_1] = mem_c[member_id_1]._replace(editor=False)
            self.db.sync_proposal_member(proposal_id, mem_c, person_id_1)

        with self.assertRaisesRegexp(UserError, 'no PI specified'):
            mem_c = members.copy()
            mem_c[member_id_1] = mem_c[member_id_1]._replace(pi=False)
            self.db.sync_proposal_member(proposal_id, mem_c, person_id_1)

        with self.assertRaisesRegexp(UserError, 'more than one PI specified'):
            mem_c = members.copy()
            mem_c[member_id_2] = mem_c[member_id_2]._replace(pi=True)
            self.db.sync_proposal_member(proposal_id, mem_c, person_id_1)

        with self.assertRaisesRegexp(UserError, 'yourself as an editor'):
            mem_c = members.copy()
            mem_c[member_id_1] = mem_c[member_id_1]._replace(editor=False)
            mem_c[member_id_2] = mem_c[member_id_2]._replace(editor=True)
            self.db.sync_proposal_member(proposal_id, mem_c, person_id_1)

        del members[member_id_1]
        members[member_id_2] = members[member_id_2]._replace(
            editor=True, pi=True)

        with self.assertRaisesRegexp(UserError, 'can not remove yourself'):
            self.db.sync_proposal_member(proposal_id, members, person_id_1)

        (n_insert, n_update, n_delete) = self.db.sync_proposal_member(
            proposal_id, members, None)

        self.assertEqual(n_insert, 0)
        self.assertEqual(n_update, 1)
        self.assertEqual(n_delete, 1)

        members = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(list(members.keys()), [member_id_2])

    def test_sync_member_institution(self):
        (call_id, affiliation_id) = self._create_test_call(
            'semester1', 'queue1')
        institution_id_1 = self.db.add_institution('Inst 1', '', '', '', 'AX')
        institution_id_2 = self.db.add_institution('Inst 2', '', '', '', 'CX')
        institution_id_3 = self.db.add_institution('Inst 3', '', '', '', 'AX')
        person_id_1 = self.db.add_person('Person 1')
        person_id_2 = self.db.add_person('Person 2')
        person_id_3 = self.db.add_person('Person 3')
        self.db.update_person(person_id_3, institution_id=institution_id_3)
        proposal_id = self.db.add_proposal(call_id, person_id_1,
                                           affiliation_id, 'Proposal 1')

        self.db.add_member(proposal_id, person_id_2, affiliation_id,
                           False, False, False)
        self.db.add_member(proposal_id, person_id_3, affiliation_id,
                           False, False, False)

        # Institutions should be undefined at first except person 3.
        expect_ref = (institution_id_3, None, None)
        expect = list(expect_ref)
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(len(result), 3)
        for row in result.values():
            self.assertEqual(row.resolved_institution_id, expect.pop())

        # Create set of member institution records to sync.
        records = ResultCollection()
        inst_ref = (institution_id_3, institution_id_2, institution_id_1)
        institutions = list(inst_ref)
        with self.db._engine.begin() as conn:
            for row in conn.execute(
                    member.select().order_by(member.c.id.asc())):
                self.assertIsNone(row['institution_id'])

                records[row['id']] = MemberInstitution(row['id'],
                                                       institutions.pop())

        self.assertEqual(len(records), 3)
        result = self.db.sync_proposal_member_institution(proposal_id, records)
        self.assertEqual(result, (0, 3, 0))

        # Institutions should now be defined.
        institutions = list(inst_ref)
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(len(result), 3)
        for row in result.values():
            self.assertEqual(row.resolved_institution_id, institutions.pop())

        # Check also by manual query.
        institutions = list(inst_ref)
        records = ResultCollection()
        with self.db._engine.begin() as conn:
            for row in conn.execute(
                    member.select().order_by(member.c.id.asc())):
                self.assertEqual(row['institution_id'], institutions.pop())
                records[row['id']] = MemberInstitution(row['id'], None)
        self.assertEqual(institutions, [])

        # Sync all the records back to null.
        self.assertEqual(len(records), 3)
        result = self.db.sync_proposal_member_institution(proposal_id, records)
        self.assertEqual(result, (0, 3, 0))
        result = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(len(result), 3)
        expect = list(expect_ref)
        for row in result.values():
            self.assertEqual(row.resolved_institution_id, expect.pop())

    def test_delete_member_person(self):
        (call_id, affiliation_id) = self._create_test_call('s1', 'q1')
        person_id_1 = self.db.add_person('Person 1')
        person_id_2 = self.db.add_person('Person 2')
        person_id_3 = self.db.add_person('Person 3')
        proposal_id = self.db.add_proposal(
            call_id, person_id_1, affiliation_id, 'Proposal Title')
        self.assertIsInstance(proposal_id, int)

        self.db.add_member(proposal_id, person_id_2, affiliation_id)

        with self.assertRaisesRegexp(ConsistencyError,
                                     'would leave no editors'):
            self.db.delete_member_person(proposal_id, person_id_1)

        self.db.add_member(proposal_id, person_id_3, affiliation_id,
                           editor=True)

        self.db.delete_member_person(proposal_id, person_id_1)

        self.assertEqual(
            [x.person_id for x in
             self.db.search_member(proposal_id=proposal_id).values()],
            [person_id_2, person_id_3])

    def test_proposal_text(self):
        # "Define" extra text roles for the purpose of testing this
        # method before multiple roles are implemented.
        TextRole._info[40] = None
        TextRole._info[41] = None

        (call_id, affiliation_id) = self._create_test_call('sem1', 'queue1')
        person_id = self.db.add_person('Person 1')
        proposal_id_1 = self.db.add_proposal(call_id, person_id,
                                             affiliation_id, 'Proposal 1')
        self.assertIsInstance(proposal_id_1, int)
        proposal_id_2 = self.db.add_proposal(call_id, person_id,
                                             affiliation_id, 'Proposal 1')
        self.assertIsInstance(proposal_id_2, int)

        # Searching now should return nothing.
        self.assertEqual(len(self.db.search_proposal_text()), 0)

        # Test we can't use an invalid format code or role number.
        with self.assertRaisesRegexp(UserError, 'format not recognised'):
            self.db.set_proposal_text(proposal_id_1, TextRole.ABSTRACT,
                                      'test', 999, 1, person_id, False)
        with self.assertRaisesRegexp(Error, 'text role not recognised'):
            self.db.set_proposal_text(proposal_id_1, 999, 'test',
                                      FormatType.PLAIN, 1, person_id, False)

        # Test we can't get, delete or update a non-existant record.
        with self.assertRaisesRegexp(NoSuchRecord, '^text does not exist'):
            self.db.get_proposal_text(proposal_id_1, TextRole.ABSTRACT)

        with self.assertRaisesRegexp(ConsistencyError, '^text does not exist'):
            self.db.delete_proposal_text(proposal_id_1,
                                         TextRole.ABSTRACT)

        with self.assertRaisesRegexp(ConsistencyError, '^no row matched'):
            self.db.delete_proposal_text(proposal_id_1,
                                         TextRole.ABSTRACT,
                                         _test_skip_check=True)

        with self.assertRaisesRegexp(ConsistencyError, '^text does not exist'):
            self.db.set_proposal_text(proposal_id_1,
                                      TextRole.TECHNICAL_CASE, 'test',
                                      FormatType.PLAIN, 1, person_id, True)

        with self.assertRaisesRegexp(ConsistencyError, '^no rows matched'):
            self.db.set_proposal_text(proposal_id_1,
                                      TextRole.TECHNICAL_CASE, 'test',
                                      FormatType.PLAIN, 1, person_id, True,
                                      _test_skip_check=True)

        # Try creating and updating some text.
        self.db.set_proposal_text(
            proposal_id_1, TextRole.SCIENCE_CASE, 'test',
            FormatType.PLAIN, 1, person_id, False)
        self.assertEqual(self.db.get_proposal_text(
            proposal_id_1, TextRole.SCIENCE_CASE),
            ProposalText('test', FormatType.PLAIN))
        self.db.set_proposal_text(
            proposal_id_1, TextRole.SCIENCE_CASE, 'change',
            FormatType.PLAIN, 1, person_id, True)
        self.assertEqual(self.db.get_proposal_text(
            proposal_id_1, TextRole.SCIENCE_CASE),
            ProposalText('change', FormatType.PLAIN))

        # Check we can't re-create an existing text record.
        with self.assertRaisesRegexp(ConsistencyError, '^text already exists'):
            self.db.set_proposal_text(
                proposal_id_1, TextRole.SCIENCE_CASE, 'new',
                FormatType.PLAIN, 1, person_id, False)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.set_proposal_text(
                proposal_id_1, TextRole.SCIENCE_CASE, 'new',
                FormatType.PLAIN, 1, person_id, False,
                _test_skip_check=True)

        # Now delete the record.
        self.db.delete_proposal_text(
            proposal_id_1, TextRole.SCIENCE_CASE)
        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_text(
                proposal_id_1, TextRole.SCIENCE_CASE)

        # "Define" some extra format types just for the purpose of testing
        # this method before multiple formats have been implemented.
        FormatType._info[991] = FormatType.FormatTypeInfo('MD', True)
        FormatType._info[992] = FormatType.FormatTypeInfo('DocBook', True)
        FormatType._info[993] = FormatType.FormatTypeInfo('RST', True)

        # Add and change multiple records.
        self.db.set_proposal_text(proposal_id_1, 40, 'a',
                                  FormatType.PLAIN, 1, person_id, False)
        self.db.set_proposal_text(proposal_id_1, 41, 'b',
                                  FormatType.PLAIN, 1, person_id, False)
        self.db.set_proposal_text(proposal_id_2, 40, 'c',
                                  991, 1, person_id, False)
        self.db.set_proposal_text(proposal_id_2, 41, 'd',
                                  992, 1, person_id, False)

        self.db.set_proposal_text(proposal_id_2, 40, 'cc', 993,
                                  1, person_id, True)
        self.db.delete_proposal_text(proposal_id_1, 41)

        self.assertEqual(self.db.get_proposal_text(proposal_id_1, 40),
                         ProposalText('a', FormatType.PLAIN))
        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_text(proposal_id_1, 41)
        self.assertEqual(self.db.get_proposal_text(proposal_id_2, 40),
                         ProposalText('cc', 993))
        self.assertEqual(self.db.get_proposal_text(proposal_id_2, 41),
                         ProposalText('d', 992))

        # Try searching for text.
        result = self.db.search_proposal_text(proposal_id=proposal_id_2)
        self.assertIsInstance(result, ProposalTextCollection)
        self.assertEqual(len(result), 2)
        info = result.get_role(40)
        self.assertIsInstance(info, ProposalTextInfo)
        self.assertEqual(info.format, 993)
        self.assertEqual(info.words, 1)
        self.assertIsInstance(info.edited, datetime)
        self.assertEqual(info.editor, person_id)
        self.assertEqual(info.editor_name, 'Person 1')
        info = result.get_role(41)
        self.assertIsInstance(info, ProposalTextInfo)
        self.assertEqual(info.format, 992)
        with self.assertRaises(KeyError):
            result.get_role(43)

    def test_proposal_pdf(self):
        (call_id, affiliation_id) = self._create_test_call('sem1', 'queue1')
        pdf = b'dummy PDF file'
        role = TextRole.TECHNICAL_CASE

        person_id = self.db.add_person('Person 1')
        proposal_id = self.db.add_proposal(call_id, person_id,
                                           affiliation_id, 'Proposal 1')
        self.assertIsInstance(proposal_id, int)

        result = self.db.search_proposal_pdf(proposal_id=proposal_id)
        self.assertEqual(len(result), 0)

        pdf_id = self.db.set_proposal_pdf(proposal_id, role, pdf, 4,
                                          'test.pdf', person_id)
        self.assertIsInstance(pdf_id, int)

        self.assertEqual(self.db.get_proposal_pdf(proposal_id, role).data, pdf)
        self.assertEqual(self.db.get_proposal_pdf(None, None, id_=pdf_id).data,
                                                  pdf)

        result = self.db.search_proposal_pdf(proposal_id=proposal_id)
        self.assertEqual(len(result), 1)
        self.assertIn(pdf_id, result)
        pdf_info = result[pdf_id]
        self.assertIsInstance(pdf_info, ProposalPDFInfo)
        self.assertEqual(pdf_info.id, pdf_id)
        self.assertEqual(pdf_info.proposal_id, proposal_id)
        self.assertEqual(pdf_info.role, role)
        self.assertEqual(pdf_info.md5sum, b'46ee5ebd71065c1d4caa83e4c943c70a')
        self.assertEqual(pdf_info.state, AttachmentState.NEW, 4)
        self.assertEqual(pdf_info.filename, 'test.pdf')
        self.assertIsInstance(pdf_info.uploaded, datetime)
        self.assertEqual(pdf_info.uploader, person_id)
        self.assertEqual(pdf_info.uploader_name, None)

        # Try changing proposal state.
        self.db.update_proposal_pdf(
            pdf_id=pdf_id, state=AttachmentState.READY)

        result = self.db.search_proposal_pdf(proposal_id=proposal_id)
        self.assertEqual(result[pdf_id].state, AttachmentState.READY)

        # Check that the "state_prev" constraint works.
        with self.assertRaisesRegexp(ConsistencyError, 'no rows matched'):
            self.db.update_proposal_pdf(
                pdf_id=pdf_id, state=AttachmentState.READY,
                state_prev=AttachmentState.ERROR)

        self.db.update_proposal_pdf(
            pdf_id=pdf_id, state=AttachmentState.ERROR,
            state_prev=AttachmentState.READY)

        # Test setting preview images.
        self.db.set_proposal_pdf_preview(pdf_id, [b'dummy 1', b'dummy 2'])

        self.assertEqual(
            self.db.get_proposal_pdf_preview(proposal_id, role, 1),
            b'dummy 1')

        self.assertEqual(
            self.db.get_proposal_pdf_preview(proposal_id, role, 2),
            b'dummy 2')

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_pdf_preview(proposal_id, role, 3)

        # Test deleting the PDF.
        self.db.delete_proposal_pdf(proposal_id, role)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_pdf(proposal_id, role)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_pdf_preview(proposal_id, role, 1)

        result = self.db.search_proposal_pdf(proposal_id=proposal_id)
        self.assertEqual(len(result), 0)

    def test_proposal_fig(self):
        (call_id, affiliation_id) = self._create_test_call('sem1', 'queue1')
        fig = b'dummy figure'
        role = TextRole.TECHNICAL_CASE
        type_ = FigureType.PNG

        person_id = self.db.add_person('Person 1')
        proposal_id = self.db.add_proposal(call_id, person_id,
                                           affiliation_id, 'Proposal 1')
        self.assertIsInstance(proposal_id, int)

        result = self.db.search_proposal_figure(proposal_id=proposal_id)
        self.assertEqual(len(result), 0)

        fig_id = self.db.add_proposal_figure(proposal_id, role, type_, fig,
                                             'Figure caption.', 'test.png',
                                             person_id)
        self.assertIsInstance(fig_id, int)

        result = self.db.search_proposal_figure(proposal_id=proposal_id)
        self.assertEqual(len(result), 1)
        self.assertIn(fig_id, result)
        fig_info = result[fig_id]
        self.assertIsInstance(fig_info, ProposalFigureInfo)
        self.assertEqual(fig_info.id, fig_id)
        self.assertEqual(fig_info.proposal_id, proposal_id)
        self.assertEqual(fig_info.role, role)
        self.assertEqual(fig_info.md5sum, b'b41faa148ef23d1ddfa46debb3b66f35')
        self.assertEqual(fig_info.type, type_)
        self.assertEqual(fig_info.state, AttachmentState.NEW)
        self.assertEqual(fig_info.caption, None)
        self.assertEqual(fig_info.filename, 'test.png')
        self.assertIsInstance(fig_info.uploaded, datetime)
        self.assertEqual(fig_info.uploader, person_id)
        self.assertEqual(fig_info.uploader_name, None)
        self.assertEqual(fig_info.has_preview, None)

        result = self.db.search_proposal_figure(
            fig_id=fig_id, with_has_preview=True).get_single()
        self.assertEqual(result.has_preview, False)

        self.assertEqual(
            self.db.get_proposal_figure(proposal_id, role, fig_id).data,
            fig)

        # Try previews and thumbnails.
        preview = b'dummy preview'
        thumbnail = b'dummy thumbnail'

        self.db.set_proposal_figure_preview(fig_id, preview)
        self.db.set_proposal_figure_thumbnail(fig_id, thumbnail)

        self.assertEqual(
            self.db.get_proposal_figure_preview(proposal_id, role, fig_id),
            preview)

        self.assertEqual(
            self.db.get_proposal_figure_thumbnail(proposal_id, role, fig_id),
            thumbnail)

        preview = b'dummy preview updated'
        thumbnail = b'dummy thumbnail updated'

        self.db.set_proposal_figure_preview(fig_id, preview)
        self.db.set_proposal_figure_thumbnail(fig_id, thumbnail)

        self.assertEqual(
            self.db.get_proposal_figure_preview(proposal_id, role, fig_id),
            preview)

        self.assertEqual(
            self.db.get_proposal_figure_thumbnail(proposal_id, role, fig_id),
            thumbnail)

        # Try updating the figure...
        # ... change figure state.
        self.db.update_proposal_figure(
            None, None, fig_id, state=AttachmentState.ERROR,
            state_prev=AttachmentState.NEW)

        result = self.db.search_proposal_figure(proposal_id=proposal_id,
                                                with_has_preview=True)
        fig_info = result[fig_id]
        self.assertEqual(fig_info.state, AttachmentState.ERROR)
        self.assertEqual(fig_info.has_preview, True)

        # ... change figure image.
        fig = b'dummy figure updated'
        self.db.update_proposal_figure(
            proposal_id, role, fig_id,
            figure=fig, type_=type_, filename='test2.png',
            uploader_person_id=person_id)

        result = self.db.search_proposal_figure(proposal_id=proposal_id,
                                                with_caption=True)
        fig_info = result[fig_id]
        self.assertEqual(fig_info.md5sum, b'b9e7dfbc36883c26e5d2aff8c80f34db')
        self.assertEqual(fig_info.state, AttachmentState.NEW)
        self.assertEqual(fig_info.filename, 'test2.png')
        self.assertEqual(fig_info.caption, 'Figure caption.')

        self.assertEqual(
            self.db.get_proposal_figure(proposal_id, role, fig_id).data,
            fig)

        # ... changing the image should have removed the preview/thumbnail.
        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_preview(proposal_id, role, fig_id)

        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_figure_thumbnail(proposal_id, role, fig_id)

        # ... change the figure caption.
        self.db.update_proposal_figure(proposal_id, role, fig_id, caption='!')
        result = self.db.search_proposal_figure(proposal_id=proposal_id,
                                                with_caption=True)
        fig_info = result[fig_id]
        self.assertEqual(fig_info.caption, '!')

        # Try deleting the figure.
        self.db.delete_proposal_figure(proposal_id, role, fig_id)

        result = self.db.search_proposal_figure(proposal_id=proposal_id)
        self.assertEqual(len(result), 0)

    def test_proposal_target(self):
        (call_id, affiliation_id) = self._create_test_call('sem1', 'queue1')
        person_id = self.db.add_person('Person 1')
        proposal_id = self.db.add_proposal(call_id, person_id,
                                           affiliation_id, 'Proposal 1')
        self.assertIsInstance(proposal_id, int)

        result = self.db.search_target(proposal_id=proposal_id)
        self.assertIsInstance(result, TargetCollection)
        self.assertFalse(result)

        records = TargetCollection([
            (1, Target(1, proposal_id, 1, 'Obj 1', 1, 0.5, -0.5, 15.5, 1)),
            (2, Target(2, proposal_id, 2, 'Obj 2', None, None, None, 13.5, 2)),
            (3, Target(3, proposal_id, 3, 'Obj 3', 2, 335, 1.5, None, None)),
        ])

        n = self.db.sync_proposal_target(proposal_id, records)
        self.assertEqual(n, (3, 0, 0))

        result = self.db.search_target(proposal_id=proposal_id)
        self.assertIsInstance(result, TargetCollection)
        self.assertEqual(len(result), 3)

        i = 1
        for t in result.values():
            self.assertIsInstance(t, Target)
            self.assertEqual(t.proposal_id, proposal_id)
            self.assertEqual(t.sort_order, i)
            self.assertEqual(t.name, 'Obj {0}'.format(i))
            i += 1

    def test_category(self):
        facility_id = self.db.ensure_facility('cat test facility')
        records = ResultCollection()
        records[1] = Category(1, None, 'Category A', False)
        records[2] = Category(2, None, 'Category B', True)

        (n_insert, n_update, n_delete) = self.db.sync_facility_category(
            facility_id, records)

        self.assertEqual(n_insert, 2)
        self.assertEqual(n_update, 0)
        self.assertEqual(n_delete, 0)

        result = self.db.search_category(facility_id=facility_id, hidden=False)
        self.assertIsInstance(result, ResultCollection)

        self.assertEqual([x.name for x in result.values()], ['Category A'])
        category_id_a = list(result.keys())[0]
        self.assertIsInstance(category_id_a, int)

        result = self.db.search_category(facility_id=facility_id, hidden=True)
        self.assertIsInstance(result, ResultCollection)

        self.assertEqual([x.name for x in result.values()], ['Category B'])
        category_id_b = list(result.keys())[0]
        self.assertIsInstance(category_id_b, int)
        self.assertNotEqual(category_id_a, category_id_b)

        (call_id, affiliation_id) = self._create_test_call(
            's 1', 'q 1', facility_id=facility_id)

        person_id = self.db.add_person('Person 1')
        proposal_id = self.db.add_proposal(call_id, person_id,
                                           affiliation_id, 'Proposal 1')
        self.assertIsInstance(proposal_id, int)

        proposal_categories = ResultCollection()
        proposal_categories[1] = ProposalCategory(1, proposal_id,
                                                  category_id_a, None)

        (n_insert, n_update, n_delete) = self.db.sync_proposal_category(
            proposal_id, proposal_categories)

        self.assertEqual(n_insert, 1)
        self.assertEqual(n_update, 0)
        self.assertEqual(n_delete, 0)

        result = self.db.search_proposal_category(proposal_id=proposal_id)
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(len(result), 1)
        proposal_cat = list(result.values())[0]
        self.assertIsInstance(proposal_cat, ProposalCategory)
        self.assertEqual(proposal_cat.category_name, 'Category A')

        proposal_categories = ResultCollection()
        proposal_categories[2] = ProposalCategory(2, proposal_id,
                                                  category_id_b, None)

        (n_insert, n_update, n_delete) = self.db.sync_proposal_category(
            proposal_id, proposal_categories)

        self.assertEqual(n_insert, 1)
        self.assertEqual(n_update, 0)
        self.assertEqual(n_delete, 1)

        result = self.db.search_proposal_category(proposal_id=proposal_id)
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(len(result), 1)
        proposal_cat = list(result.values())[0]
        self.assertIsInstance(proposal_cat, ProposalCategory)
        self.assertEqual(proposal_cat.category_name, 'Category B')

    def _create_test_call(self, semester_name, queue_name, facility_id=None):
        if facility_id is None:
            facility_id = self.db.ensure_facility('my_tel')
            self.assertIsInstance(facility_id, int)

        semester_id = self.db.add_semester(
            facility_id, semester_name, semester_name,
            datetime(2000, 1, 1), datetime(2000, 6, 30))
        self.assertIsInstance(semester_id, int)
        queue_id = self.db.add_queue(facility_id, queue_name, queue_name)
        self.assertIsInstance(queue_id, int)

        call_id = self.db.add_call(semester_id, queue_id,
                                   datetime(1999, 9, 1), datetime(1999, 9, 30),
                                   100, 1000, 0, 1, 2000, 4, 3, 100, 100,
                                   '', '', '', FormatType.PLAIN)
        self.assertIsInstance(call_id, int)

        affiliations = self.db.search_affiliation(queue_id=queue_id)
        if affiliations:
            affiliation_id = affiliations.values()[0].id
        else:
            affiliation_id = self.db.add_affiliation(queue_id, 'test aff/n')
        self.assertIsInstance(affiliation_id, int)

        return (call_id, affiliation_id)


def _member_person_set(member_collection):
    return map(lambda x: x.person_id, member_collection.values())
