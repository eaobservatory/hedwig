# Copyright (C) 2015-2016 East Asian Observatory
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
from hedwig.type.collection import GroupMemberCollection, ReviewerCollection
from hedwig.type.enum import Assessment, BaseCallType, BaseReviewerRole, \
    FormatType, GroupType, ReviewState
from hedwig.type.simple import GroupMember, Reviewer

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
        with self.assertRaisesRegex(ConsistencyError, 'queue does not exist'):
            self.db.add_group_member(1999999, GroupType.CTTEE, person_id_1)
        with self.assertRaisesRegex(ConsistencyError, 'person does not'):
            self.db.add_group_member(queue_id, GroupType.TECH, 1999999)
        with self.assertRaisesRegex(Error, 'invalid group type'):
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

        # Check the search results (without and then with person info).
        result = self.db.search_group_member(queue_id, GroupType.CTTEE)
        self.assertIsInstance(result, GroupMemberCollection)
        self.assertEqual(len(result), 2)

        for v in result.values():
            self.assertIsInstance(v, GroupMember)
            self.assertIsNone(v.person_name)

        result = self.db.search_group_member(queue_id, GroupType.CTTEE,
                                             with_person=True)
        self.assertIsInstance(result, GroupMemberCollection)
        self.assertEqual(len(result), 2)

        for ((k, v), person_id, person_name) in zip(
                result.items(),
                (person_id_1, person_id_2),
                ('Person One', 'Person Two')):
            self.assertIsInstance(k, int)
            self.assertIsInstance(v, GroupMember)
            self.assertEqual(k, v.id)
            self.assertEqual(v.queue_id, queue_id)
            self.assertEqual(v.group_type, GroupType.CTTEE)
            self.assertEqual(v.person_id, person_id)
            self.assertEqual(v.person_name, person_name)
            self.assertEqual(v.facility_id, facility_id)

        # Check additional search criteria.
        result = self.db.search_group_member(person_id=person_id_1)
        self.assertEqual(len(result), 1)

        result = self.db.search_group_member(person_id=1999999)
        self.assertEqual(len(result), 0)

        result = self.db.search_group_member(facility_id=facility_id)
        self.assertEqual(len(result), 2)

        result = self.db.search_group_member(facility_id=1999999)
        self.assertEqual(len(result), 0)

        # Remove members via sync.
        records = GroupMemberCollection()
        self.db.sync_group_member(queue_id, GroupType.CTTEE, records)
        result = self.db.search_group_member(queue_id, GroupType.CTTEE)
        self.assertEqual(len(result), 0)

    def test_review(self):
        proposal_id = self._create_test_proposal()

        person_id_1 = self.db.add_person('Reviewer 1')
        person_id_2 = self.db.add_person('Reviewer 2')
        person_id_3 = self.db.add_person('Reviewer 3')

        # Try null search.
        result = self.db.search_reviewer(proposal_id)
        self.assertIsInstance(result, ReviewerCollection)
        self.assertEqual(len(result), 0)

        # Try adding reviewers.
        reviewer_id_1 = self.db.add_reviewer(
            BaseReviewerRole, proposal_id, person_id_1,
            BaseReviewerRole.CTTEE_PRIMARY)
        self.assertIsInstance(reviewer_id_1, int)

        with self.assertRaisesRegex(UserError, '^There is already'):
            self.db.add_reviewer(
                BaseReviewerRole, proposal_id, person_id_2,
                BaseReviewerRole.CTTEE_PRIMARY)

        reviewer_id_2 = self.db.add_reviewer(
            BaseReviewerRole, proposal_id, person_id_2,
            BaseReviewerRole.CTTEE_SECONDARY)
        self.assertIsInstance(reviewer_id_2, int)

        reviewer_id_3 = self.db.add_reviewer(
            BaseReviewerRole, proposal_id, person_id_3,
            BaseReviewerRole.CTTEE_SECONDARY)
        self.assertIsInstance(reviewer_id_3, int)

        # Try searching for reviewers.
        result = self.db.search_reviewer(proposal_id=proposal_id)
        self.assertEqual(len(result), 3)

        for ((k, v), ref) in zip(result.items(), (
                (person_id_1, 'Reviewer 1', BaseReviewerRole.CTTEE_PRIMARY),
                (person_id_2, 'Reviewer 2', BaseReviewerRole.CTTEE_SECONDARY),
                (person_id_3, 'Reviewer 3', BaseReviewerRole.CTTEE_SECONDARY))):
            self.assertIsInstance(k, int)
            self.assertIsInstance(v, Reviewer)
            self.assertEqual(k, v.id)
            self.assertEqual(v.person_id, ref[0])
            self.assertEqual(v.person_name, ref[1])
            self.assertEqual(v.person_public, False)
            self.assertEqual(v.person_registered, False)
            self.assertEqual(v.role, ref[2])
            self.assertIsNone(v.institution_name)
            self.assertIsNone(v.institution_department)
            self.assertIsNone(v.institution_organization)
            self.assertIsNone(v.institution_country)
            self.assertIsNone(v.review_state)
            self.assertIsNone(v.review_text)
            self.assertIsNone(v.review_format)

        institution_id = self.db.add_institution(
            'Inst', 'Dept', 'Org', '', 'AX')
        self.db.update_person(person_id=person_id_3,
                              institution_id=institution_id)

        result = self.db.search_reviewer(
            reviewer_id=reviewer_id_3,
            with_review=True, with_review_text=True).get_single()

        self.assertEqual(result.institution_name, 'Inst')
        self.assertEqual(result.institution_department, 'Dept')
        self.assertEqual(result.institution_organization, 'Org')
        self.assertEqual(result.institution_country, 'AX')
        self.assertEqual(result.review_state, ReviewState.NOT_DONE)
        self.assertIsNone(result.review_text)
        self.assertIsNone(result.review_format)

        # Test call and queue query parameters.
        result = self.db.search_reviewer(call_id=1999999)
        self.assertEqual(len(result), 0)

        result = self.db.search_reviewer(queue_id=1999999)
        self.assertEqual(len(result), 0)

        # Try removing a reviewer.
        self.db.delete_reviewer(reviewer_id=reviewer_id_1)

        result = self.db.search_reviewer(proposal_id=proposal_id)
        self.assertEqual(len(result), 2)

        self.assertFalse(reviewer_id_1 in result.keys())

        result = self.db.search_reviewer(proposal_id=proposal_id,
                                         person_id=person_id_2)

        self.assertEqual(list(result.keys()), [reviewer_id_2])

        # Try specifying a review.
        with self.assertRaisesRegex(ConsistencyError, '^review does not'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_2,
                text='A review', format_=FormatType.PLAIN,
                assessment=None, rating=50, weight=50,
                note='A note', note_format=FormatType.PLAIN, note_public=False,
                is_update=True)

        self.db.set_review(
            BaseReviewerRole,
            reviewer_id=reviewer_id_2,
            text='A review', format_=FormatType.PLAIN,
            assessment=None, rating=50, weight=50,
            note='A note', note_format=FormatType.PLAIN, note_public=False,
            is_update=False)

        # Try updating a review.
        with self.assertRaisesRegex(ConsistencyError, '^review already'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_2,
                text='An updated review', format_=FormatType.PLAIN,
                assessment=None, rating=51, weight=51,
                note='A note', note_format=FormatType.PLAIN, note_public=False,
                is_update=False)

        self.db.set_review(
            BaseReviewerRole,
            reviewer_id=reviewer_id_2,
            text='An updated review', format_=FormatType.PLAIN,
            assessment=None, rating=52, weight=52,
            note='A note', note_format=FormatType.PLAIN, note_public=False,
            is_update=True)

        # Retrieve the review.
        result = self.db.search_reviewer(
            reviewer_id=reviewer_id_2, with_review=True).get_single()
        self.assertEqual(result.review_state, ReviewState.DONE)
        self.assertIsNone(result.review_text)
        self.assertEqual(result.review_format, FormatType.PLAIN)
        self.assertIsNone(result.review_assessment)
        self.assertEqual(result.review_rating, 52)
        self.assertEqual(result.review_weight, 52)
        self.assertEqual(result.review_note_format, FormatType.PLAIN)
        self.assertEqual(result.review_note_public, False)

        result = self.db.search_reviewer(
            reviewer_id=reviewer_id_2, with_review=True,
            with_review_text=True).get_single()
        self.assertEqual(result.review_text, 'An updated review')

        # Try deleting a reviewer with a review present: should need the
        # "delete_review" argument.
        with self.assertRaises(DatabaseIntegrityError):
            self.db.delete_reviewer(reviewer_id=reviewer_id_2)

        self.db.delete_reviewer(reviewer_id=reviewer_id_2, delete_review=True)

        # Test review constraints.
        with self.assertRaisesRegex(Error, 'The rating should be specified'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_3,
                text='Another review', format_=FormatType.PLAIN,
                assessment=None, rating=None, weight=None,
                note='A note', note_format=FormatType.PLAIN, note_public=False,
                is_update=False)

        with self.assertRaisesRegex(Error, 'Text format not specified'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_3,
                text='Another review', format_=None,
                assessment=None, rating=25, weight=75,
                note='A note', note_format=FormatType.PLAIN, note_public=False,
                is_update=False)

        with self.assertRaisesRegex(Error, 'Text format not recognised'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_3,
                text='Another review', format_=999,
                assessment=None, rating=25, weight=75,
                note='A note', note_format=FormatType.PLAIN, note_public=False,
                is_update=False)

        with self.assertRaisesRegex(Error, 'The assessment should not'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_3,
                text='Another review', format_=FormatType.PLAIN,
                assessment=Assessment.PROBLEM, rating=25, weight=75,
                note='A note', note_format=FormatType.PLAIN, note_public=False,
                is_update=False)

        with self.assertRaisesRegex(Error, 'Note format not recognised'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_3,
                text='Another review', format_=FormatType.PLAIN,
                assessment=None, rating=25, weight=75,
                note='A note', note_format=999, note_public=False,
                is_update=False)

        with self.assertRaisesRegex(Error, 'The note should be specified'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_3,
                text='Another review', format_=FormatType.PLAIN,
                assessment=None, rating=25, weight=75,
                note=None, note_format=None, note_public=None,
                is_update=False)

        person_id_4 = self.db.add_person('Reviewer Four')
        reviewer_id_4 = self.db.add_reviewer(
            BaseReviewerRole, proposal_id, person_id_4,
            BaseReviewerRole.TECH)
        self.assertIsInstance(reviewer_id_4, int)

        with self.assertRaisesRegex(Error, 'Assessment value not recognised'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_4,
                text='Technical review', format_=FormatType.PLAIN,
                assessment=999, rating=None, weight=None,
                note='A note', note_format=FormatType.PLAIN, note_public=False,
                is_update=False)

    def test_decision(self):
        proposal_id = self._create_test_proposal()

        # Initially get null decision values.
        proposal = self.db.get_proposal(
            facility_id=None, proposal_id=proposal_id, with_decision=True)

        self.assertEqual(proposal.id, proposal_id)
        self.assertFalse(proposal.has_decision)
        self.assertIsNone(proposal.decision_accept)
        self.assertIsNone(proposal.decision_exempt)
        self.assertIsNone(proposal.decision_ready)

        # Try creating a decision record.
        with self.assertRaisesRegex(
                ConsistencyError, 'decision does not already exist'):
            self.db.set_decision(proposal_id, False, False, False,
                                 note='', note_format=FormatType.PLAIN,
                                 is_update=True)

        self.db.set_decision(proposal_id, False, False, False, note='A note.',
                             note_format=FormatType.PLAIN, is_update=False)

        proposal = self.db.get_proposal(
            facility_id=None, proposal_id=proposal_id,
            with_decision=True, with_decision_note=True)

        self.assertEqual(proposal.id, proposal_id)
        self.assertTrue(proposal.has_decision)
        self.assertIsNotNone(proposal.decision_accept)
        self.assertIsNotNone(proposal.decision_exempt)
        self.assertIsNotNone(proposal.decision_ready)
        self.assertFalse(proposal.decision_accept)
        self.assertFalse(proposal.decision_exempt)
        self.assertFalse(proposal.decision_ready)
        self.assertEqual(proposal.decision_note, 'A note.')
        self.assertEqual(proposal.decision_note_format, FormatType.PLAIN)

        # Try updating a decision record.
        with self.assertRaisesRegex(
                ConsistencyError, 'decision already exists'):
            self.db.set_decision(proposal_id, True, True, True,
                                 note='', note_format=FormatType.PLAIN,
                                 is_update=False)

        self.db.set_decision(proposal_id, True, True, True,
                             note='Edited note.', note_format=FormatType.PLAIN,
                             is_update=True)

        proposal = self.db.get_proposal(
            facility_id=None, proposal_id=proposal_id,
            with_decision=True, with_decision_note=True)

        self.assertEqual(proposal.id, proposal_id)
        self.assertIsNotNone(proposal.decision_accept)
        self.assertIsNotNone(proposal.decision_exempt)
        self.assertIsNotNone(proposal.decision_ready)
        self.assertTrue(proposal.decision_accept)
        self.assertTrue(proposal.decision_exempt)
        self.assertTrue(proposal.decision_ready)
        self.assertEqual(proposal.decision_note, 'Edited note.')
        self.assertEqual(proposal.decision_note_format, FormatType.PLAIN)

        # Try deleting a decision record
        self.db.set_decision(proposal_id, accept=None, is_update=True)

        proposal = self.db.get_proposal(
            facility_id=None, proposal_id=proposal_id, with_decision=True)

        self.assertEqual(proposal.id, proposal_id)
        self.assertIsNone(proposal.decision_accept)

    def _create_test_proposal(self):
        facility_id = self.db.ensure_facility('test facility')
        semester_id = self.db.add_semester(
            facility_id, 'test', 'test',
            datetime(2000, 1, 1), datetime(2000, 6, 30))
        queue_id = self.db.add_queue(facility_id, 'test', 'test')
        call_id = self.db.add_call(
            BaseCallType, semester_id, queue_id, BaseCallType.STANDARD,
            datetime(1999, 9, 1), datetime(1999, 9, 30),
            100, 1000, 0, 1, 2000, 4, 3, 100, 100, '', '', '',
            FormatType.PLAIN)
        affiliation_id = self.db.add_affiliation(queue_id, 'test')
        person_id = self.db.add_person('Test Person')
        return self.db.add_proposal(
            call_id, person_id, affiliation_id, 'Test Title')
