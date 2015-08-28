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

from hedwig.error import ConsistencyError, DatabaseIntegrityError, Error, \
    NoSuchRecord, UserError
from hedwig.type import Assessment, FormatType, \
    GroupMember, GroupMemberCollection, GroupType, \
    NoteRole, ProposalNote, Review, Reviewer, ReviewerCollection, ReviewerRole

from .dummy_db import DBTestCase


class DBReviewTest(DBTestCase):
    def test_group(self):
        facility_id = self.db.ensure_facility('Test Facility')
        queue_id = self.db.add_queue(facility_id, 'Test Queue', 'T')
        queue_id_2 = self.db.add_queue(facility_id, 'Another Test Queue', 'U')

        person_id_1 = self.db.add_person('Person One')
        person_id_2 = self.db.add_person('Person Two')

        # Check null search result.
        result = self.db.search_group_member(queue_id, GroupType.CTTEE)
        self.assertIsInstance(result, GroupMemberCollection)
        self.assertEqual(len(result), 0)

        # Check member add constraints.
        with self.assertRaisesRegexp(ConsistencyError, 'queue does not exist'):
            self.db.add_group_member(1999999, GroupType.CTTEE, person_id_1)
        with self.assertRaisesRegexp(ConsistencyError, 'person does not'):
            self.db.add_group_member(queue_id, GroupType.TECH, 1999999)
        with self.assertRaisesRegexp(Error, 'invalid group type'):
            self.db.add_group_member(queue_id, 999, person_id_1)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_group_member(1999999, GroupType.CTTEE, person_id_1,
                                     _test_skip_check=True)
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_group_member(queue_id, GroupType.TECH, 1999999,
                                     _test_skip_check=True)

        # Add two members.
        self.db.add_group_member(queue_id, GroupType.CTTEE, person_id_1)
        self.db.add_group_member(queue_id, GroupType.CTTEE, person_id_2)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_group_member(queue_id, GroupType.CTTEE, person_id_2)

        # Check we don't find them when searching another queue / group.
        result = self.db.search_group_member(queue_id, GroupType.TECH)
        self.assertEqual(len(result), 0)
        result = self.db.search_group_member(queue_id_2, GroupType.CTTEE)
        self.assertEqual(len(result), 0)

        # Check the search results.
        result = self.db.search_group_member(queue_id, GroupType.CTTEE)
        self.assertIsInstance(result, GroupMemberCollection)
        self.assertEqual(len(result), 2)

        for ((k, v), person_id) in zip(result.items(),
                                       (person_id_1, person_id_2)):
            self.assertIsInstance(k, int)
            self.assertIsInstance(v, GroupMember)
            self.assertEqual(k, v.id)
            self.assertEqual(v.queue_id, queue_id)
            self.assertEqual(v.group_type, GroupType.CTTEE)
            self.assertEqual(v.person_id, person_id)

        # Remove members via sync.
        records = GroupMemberCollection()
        self.db.sync_group_member(queue_id, GroupType.CTTEE, records)
        result = self.db.search_group_member(queue_id, GroupType.CTTEE)
        self.assertEqual(len(result), 0)

    def test_note(self):
        proposal_id = self._create_test_proposal()

        # Try null search.
        with self.assertRaises(NoSuchRecord):
            self.db.get_proposal_note(proposal_id, NoteRole.FEEDBACK)

        # Set and retrieve a note.
        with self.assertRaisesRegexp(ConsistencyError, 'note does not exist'):
            self.db.set_proposal_note(proposal_id, NoteRole.FEEDBACK,
                                      '', FormatType.PLAIN, True)

        self.db.set_proposal_note(proposal_id, NoteRole.FEEDBACK,
                                  'Test note...', FormatType.PLAIN, False)

        note = self.db.get_proposal_note(proposal_id, NoteRole.FEEDBACK)

        self.assertIsInstance(note, ProposalNote)

        self.assertIsInstance(note.id, int)
        self.assertEqual(note.proposal_id, proposal_id)
        self.assertEqual(note.role, NoteRole.FEEDBACK)
        self.assertEqual(note.text, 'Test note...')
        self.assertEqual(note.format, FormatType.PLAIN)
        self.assertIsInstance(note.edited, datetime)

        # Update the note.
        with self.assertRaisesRegexp(ConsistencyError, 'note already exists'):
            self.db.set_proposal_note(proposal_id, NoteRole.FEEDBACK,
                                      '', FormatType.PLAIN, False)

        self.db.set_proposal_note(proposal_id, NoteRole.FEEDBACK,
                                  'Updated note!', FormatType.PLAIN, True)
        note = self.db.get_proposal_note(proposal_id, NoteRole.FEEDBACK)
        self.assertEqual(note.text, 'Updated note!')

        # Check constraints.
        with self.assertRaisesRegexp(ConsistencyError, 'proposal does not'):
            self.db.set_proposal_note(1999999, NoteRole.FEEDBACK,
                                      '', FormatType.PLAIN, False)
        with self.assertRaisesRegexp(Error, 'invalid note role'):
            self.db.set_proposal_note(proposal_id, 999,
                                      '', FormatType.PLAIN, False)

    def test_review(self):
        proposal_id = self._create_test_proposal()

        person_id_1 = self.db.add_person('Reviewer One')
        person_id_2 = self.db.add_person('Reviewer Two')
        person_id_3 = self.db.add_person('Reviewer Three')

        # Try null search.
        result = self.db.search_reviewer(proposal_id)
        self.assertIsInstance(result, ReviewerCollection)
        self.assertEqual(len(result), 0)

        # Try adding reviewers.
        reviewer_id_1 = self.db.add_reviewer(proposal_id, person_id_1,
                                             ReviewerRole.CTTEE_PRIMARY)
        self.assertIsInstance(reviewer_id_1, int)

        with self.assertRaisesRegexp(UserError, '^There is already'):
            self.db.add_reviewer(proposal_id, person_id_2,
                                 ReviewerRole.CTTEE_PRIMARY)

        reviewer_id_2 = self.db.add_reviewer(proposal_id, person_id_2,
                                             ReviewerRole.CTTEE_SECONDARY)
        self.assertIsInstance(reviewer_id_2, int)

        reviewer_id_3 = self.db.add_reviewer(proposal_id, person_id_3,
                                             ReviewerRole.CTTEE_SECONDARY)
        self.assertIsInstance(reviewer_id_3, int)

        # Try searching for reviewers.
        result = self.db.search_reviewer(proposal_id=proposal_id)
        self.assertEqual(len(result), 3)

        for ((k, v), ref) in zip(result.items(), (
                (person_id_1, ReviewerRole.CTTEE_PRIMARY),
                (person_id_2, ReviewerRole.CTTEE_SECONDARY),
                (person_id_3, ReviewerRole.CTTEE_SECONDARY))):
            self.assertIsInstance(k, int)
            self.assertIsInstance(v, Reviewer)
            self.assertEqual(k, v.id)
            self.assertEqual(v.person_id, ref[0])
            self.assertEqual(v.role, ref[1])

        # Try removing a reviewer.
        self.db.delete_reviewer(reviewer_id=reviewer_id_1)

        result = self.db.search_reviewer(proposal_id=proposal_id)
        self.assertEqual(len(result), 2)

        self.assertFalse(reviewer_id_1 in result.keys())

        # Try specifying a review.
        with self.assertRaisesRegexp(ConsistencyError, '^review does not'):
            self.db.set_review(
                reviewer_id=reviewer_id_2,
                text='A review', format_=FormatType.PLAIN,
                assessment=None, rating=50, weight=50, is_update=True)

        self.db.set_review(
            reviewer_id=reviewer_id_2,
            text='A review', format_=FormatType.PLAIN,
            assessment=None, rating=50, weight=50, is_update=False)

        # Try updating a review.
        with self.assertRaisesRegexp(ConsistencyError, '^review already'):
            self.db.set_review(
                reviewer_id=reviewer_id_2,
                text='An updated review', format_=FormatType.PLAIN,
                assessment=None, rating=51, weight=51, is_update=False)

        self.db.set_review(
            reviewer_id=reviewer_id_2,
            text='An updated review', format_=FormatType.PLAIN,
            assessment=None, rating=52, weight=52, is_update=True)

        # Try deleting a reviewer with a review present: should need the
        # "delete_review" argument.
        with self.assertRaises(DatabaseIntegrityError):
            self.db.delete_reviewer(reviewer_id=reviewer_id_2)

        self.db.delete_reviewer(reviewer_id=reviewer_id_2, delete_review=True)

        # Test review constraints.
        with self.assertRaisesRegexp(Error, 'The rating should be specified'):
            self.db.set_review(
                reviewer_id=reviewer_id_3,
                text='Another review', format_=FormatType.PLAIN,
                assessment=None, rating=None, weight=None, is_update=False)

        with self.assertRaisesRegexp(Error, 'Text format not specified'):
            self.db.set_review(
                reviewer_id=reviewer_id_3,
                text='Another review', format_=None,
                assessment=None, rating=25, weight=75, is_update=False)

        with self.assertRaisesRegexp(Error, 'Text format not recognised'):
            self.db.set_review(
                reviewer_id=reviewer_id_3,
                text='Another review', format_=999,
                assessment=None, rating=25, weight=75, is_update=False)

        with self.assertRaisesRegexp(Error, 'The assessment should not'):
            self.db.set_review(
                reviewer_id=reviewer_id_3,
                text='Another review', format_=FormatType.PLAIN,
                assessment=Assessment.PROBLEM, rating=25, weight=75,
                is_update=False)

        person_id_4 = self.db.add_person('Reviewer Four')
        reviewer_id_4 = self.db.add_reviewer(proposal_id, person_id_4,
                                             ReviewerRole.TECH)
        self.assertIsInstance(reviewer_id_4, int)

        with self.assertRaisesRegexp(Error, 'Assessment value not recognised'):
            self.db.set_review(
                reviewer_id=reviewer_id_4,
                text='Technical review', format_=FormatType.PLAIN,
                assessment=999, rating=None, weight=None,
                is_update=False)

    def _create_test_proposal(self):
        facility_id = self.db.ensure_facility('test facility')
        semester_id = self.db.add_semester(
            facility_id, 'test', 'test',
            datetime(2000, 1, 1), datetime(2000, 6, 30))
        queue_id = self.db.add_queue(facility_id, 'test', 'test')
        call_id = self.db.add_call(
            semester_id, queue_id,
            datetime(1999, 9, 1), datetime(1999, 9, 30),
            100, 1000, 0, 1, 2000, 4, 3, 100, 100, '', '', '',
            FormatType.PLAIN)
        affiliation_id = self.db.add_affiliation(queue_id, 'test')
        person_id = self.db.add_person('Test Person')
        return self.db.add_proposal(
            call_id, person_id, affiliation_id, 'Test Title')
