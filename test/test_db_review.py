# Copyright (C) 2015-2025 East Asian Observatory
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

from hedwig.compat import first_value
from hedwig.error import ConsistencyError, DatabaseIntegrityError, Error, \
    NoSuchRecord, UserError
from hedwig.type.collection import GroupMemberCollection, \
    ReviewerCollection, ReviewerAcceptanceCollection, \
    ReviewDeadlineCollection, ReviewFigureCollection
from hedwig.type.enum import Assessment, AttachmentState, BaseReviewerRole, \
    FigureType, FormatType, GroupType, ReviewState
from hedwig.type.simple import GroupMember, Note, \
    Reviewer, ReviewerAcceptance, \
    ReviewDeadline, ReviewFigureInfo
from hedwig.type.util import null_tuple

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
        person_id_4 = self.db.add_person('Reviewer 4')
        person_id_5 = self.db.add_person('Reviewer 5')

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

        reviewer_id_4 = self.db.add_reviewer(
            BaseReviewerRole, proposal_id, person_id_4,
            BaseReviewerRole.PEER)
        self.assertIsInstance(reviewer_id_4, int)

        reviewer_id_5 = self.db.add_reviewer(
            BaseReviewerRole, proposal_id, person_id_5,
            BaseReviewerRole.EXTERNAL)
        self.assertIsInstance(reviewer_id_5, int)

        # Try searching for reviewers.
        result = self.db.search_reviewer(
            proposal_id=proposal_id, with_note=True)
        self.assertEqual(len(result), 5)

        for ((k, v), ref) in zip(result.items(), (
                (person_id_5, 'Reviewer 5', BaseReviewerRole.EXTERNAL, reviewer_id_5),
                (person_id_1, 'Reviewer 1', BaseReviewerRole.CTTEE_PRIMARY, reviewer_id_1),
                (person_id_2, 'Reviewer 2', BaseReviewerRole.CTTEE_SECONDARY, reviewer_id_2),
                (person_id_3, 'Reviewer 3', BaseReviewerRole.CTTEE_SECONDARY, reviewer_id_3),
                (person_id_4, 'Reviewer 4', BaseReviewerRole.PEER, reviewer_id_4))):
            self.assertIsInstance(k, int)
            self.assertEqual(k, ref[3])
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
            self.assertFalse(v.notified)
            self.assertIsNone(v.accepted)
            self.assertIsNone(v.note)
            self.assertIsNone(v.note_format)
            self.assertFalse(v.thanked)

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

        # Try updating the reviewer flags.
        self.db.update_reviewer(
            BaseReviewerRole, reviewer_id_1, notified=True)
        result = self.db.search_reviewer(
            reviewer_id=reviewer_id_1).get_single()
        self.assertTrue(result.notified)

        with self.assertRaisesRegex(Error, 'role is not accepted'):
            self.db.update_reviewer(
                BaseReviewerRole, reviewer_id_1, accepted=True)

        with self.assertRaisesRegex(ConsistencyError, 'reviewer does not'):
            self.db.update_reviewer(
                BaseReviewerRole, 1999999, notified=False)

        self.db.update_reviewer(
                BaseReviewerRole, reviewer_id_4, accepted=False)
        result = self.db.search_reviewer(
            reviewer_id=reviewer_id_4).get_single()
        self.assertIs(result.accepted, False)

        self.db.update_reviewer(
                BaseReviewerRole, reviewer_id_4, accepted=True)
        result = self.db.search_reviewer(
            reviewer_id=reviewer_id_4).get_single()
        self.assertIs(result.accepted, True)

        self.assertEqual(len(self.db.search_reviewer(
            proposal_id=proposal_id, thanked=True)), 0)
        self.assertEqual(len(self.db.search_reviewer(
            proposal_id=proposal_id, thanked=False)), 5)

        with self.assertRaisesRegex(
                Error, 'reviewer role does not use thanked attribute'):
            self.db.update_reviewer(
                BaseReviewerRole, reviewer_id_1, thanked=True)

        self.db.update_reviewer(
            BaseReviewerRole, reviewer_id_5, thanked=True)
        result = self.db.search_reviewer(
            reviewer_id=reviewer_id_5).get_single()
        self.assertIs(result.thanked, True)

        self.assertEqual(len(self.db.search_reviewer(
            proposal_id=proposal_id, thanked=True)), 1)
        self.assertEqual(len(self.db.search_reviewer(
            proposal_id=proposal_id, thanked=False)), 4)

        # Test call and queue query parameters.
        result = self.db.search_reviewer(call_id=1999999)
        self.assertEqual(len(result), 0)

        result = self.db.search_reviewer(queue_id=1999999)
        self.assertEqual(len(result), 0)

        # Try removing a reviewer.
        self.db.delete_reviewer(reviewer_id=reviewer_id_1)

        result = self.db.search_reviewer(proposal_id=proposal_id)
        self.assertEqual(len(result), 4)

        self.assertFalse(reviewer_id_1 in result.keys())

        result = self.db.search_reviewer(proposal_id=proposal_id,
                                         person_id=person_id_2)

        self.assertEqual(list(result.keys()), [reviewer_id_2])

        # Try setting a note.
        with self.assertRaisesRegex(ConsistencyError, 'parent entry does not'):
            self.db.set_reviewer_note(1999999, 'a note', FormatType.PLAIN)

        self.db.set_reviewer_note(reviewer_id_2, 'a note', FormatType.PLAIN)

        result = self.db.search_reviewer(
            reviewer_id=reviewer_id_2).get_single()
        self.assertIsNone(result.note)
        self.assertIsNone(result.note_format)

        result = self.db.search_reviewer(
            reviewer_id=reviewer_id_2, with_note=True).get_single()
        self.assertEqual(result.note, 'a note')
        self.assertEqual(result.note_format, FormatType.PLAIN)

        self.db.set_reviewer_note(reviewer_id_2, 'b note', FormatType.PLAIN)
        result = self.db.search_reviewer(
            reviewer_id=reviewer_id_2, with_note=True).get_single()
        self.assertEqual(result.note, 'b note')
        self.assertEqual(result.note_format, FormatType.PLAIN)

        with self.assertRaises(ConsistencyError):
            self.db.delete_reviewer_note(1999999)

        self.db.delete_reviewer_note(reviewer_id_2)
        result = self.db.search_reviewer(
            reviewer_id=reviewer_id_2, with_note=True).get_single()
        self.assertIsNone(result.note)
        self.assertIsNone(result.note_format)

        # Try specifying a review.
        with self.assertRaisesRegex(Error, 'invalid review state'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_2,
                text='A review', format_=FormatType.PLAIN,
                assessment=None, rating=50, weight=50,
                note='A note', note_format=FormatType.PLAIN, note_public=False,
                state=ReviewState.ADDABLE)

        self.db.set_review(
            BaseReviewerRole,
            reviewer_id=reviewer_id_2,
            text='A review', format_=FormatType.PLAIN,
            assessment=None, rating=50, weight=50,
            note='A note', note_format=FormatType.PLAIN, note_public=False,
            state=ReviewState.DONE)

        result = self.db.search_reviewer(
            reviewer_id=reviewer_id_2, with_review=True,
            with_review_text=True, with_review_note=True).get_single()
        self.assertEqual(result.review_state, ReviewState.DONE)
        self.assertEqual(result.review_text, 'A review')
        self.assertEqual(result.review_format, FormatType.PLAIN)
        self.assertIsNone(result.review_assessment)
        self.assertEqual(result.review_rating, 50)
        self.assertEqual(result.review_weight, 50)
        self.assertEqual(result.review_note, 'A note')
        self.assertEqual(result.review_note_format, FormatType.PLAIN)
        self.assertEqual(result.review_note_public, False)

        # Try updating a review.
        self.db.set_review(
            BaseReviewerRole,
            reviewer_id=reviewer_id_2,
            text='An updated review', format_=FormatType.PLAIN,
            assessment=None, rating=52, weight=52,
            note='A note', note_format=FormatType.PLAIN, note_public=False,
            state=ReviewState.DONE)

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
                state=ReviewState.DONE)

        with self.assertRaisesRegex(Error, 'Text format not specified'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_3,
                text='Another review', format_=None,
                assessment=None, rating=25, weight=75,
                note='A note', note_format=FormatType.PLAIN, note_public=False,
                state=ReviewState.DONE)

        with self.assertRaisesRegex(Error, 'Text format not recognised'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_3,
                text='Another review', format_=999,
                assessment=None, rating=25, weight=75,
                note='A note', note_format=FormatType.PLAIN, note_public=False,
                state=ReviewState.DONE)

        with self.assertRaisesRegex(Error, 'The assessment should not'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_3,
                text='Another review', format_=FormatType.PLAIN,
                assessment=Assessment.PROBLEM, rating=25, weight=75,
                note='A note', note_format=FormatType.PLAIN, note_public=False,
                state=ReviewState.DONE)

        with self.assertRaisesRegex(Error, 'Note format not recognised'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_3,
                text='Another review', format_=FormatType.PLAIN,
                assessment=None, rating=25, weight=75,
                note='A note', note_format=999, note_public=False,
                state=ReviewState.DONE)

        with self.assertRaisesRegex(Error, 'The note should be specified'):
            self.db.set_review(
                BaseReviewerRole,
                reviewer_id=reviewer_id_3,
                text='Another review', format_=FormatType.PLAIN,
                assessment=None, rating=25, weight=75,
                note=None, note_format=None, note_public=None,
                state=ReviewState.DONE)

        # Same update as above allowed when state is not DONE.
        self.db.set_review(
            BaseReviewerRole,
            reviewer_id=reviewer_id_3,
            text='Another review', format_=FormatType.PLAIN,
            assessment=None, rating=25, weight=75,
            note=None, note_format=None, note_public=None,
            state=ReviewState.PREPARATION)

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
                state=ReviewState.DONE)

    def test_reviewer_acceptance(self):
        role = BaseReviewerRole.PEER
        proposal_id = self._create_test_proposal()
        person_id = self.db.add_person('Reviewer')
        reviewer_id = self.db.add_reviewer(
            BaseReviewerRole, proposal_id, person_id, role)
        self.assertIsInstance(reviewer_id, int)

        result = self.db.search_reviewer_acceptance(person_id=person_id)
        self.assertIsInstance(result, ReviewerAcceptanceCollection)
        self.assertFalse(result)

        acceptance_id = self.db.add_reviewer_acceptance(
            BaseReviewerRole, proposal_id=proposal_id,
            person_id=person_id, role=role,
            accepted=False, text='I know the PI', format_=FormatType.PLAIN)
        self.assertIsInstance(acceptance_id, int)

        result = self.db.search_reviewer_acceptance(
            person_id=person_id).get_single()

        self.assertIsInstance(result, ReviewerAcceptance)
        self.assertEqual(result.id, acceptance_id)
        self.assertEqual(result.proposal_id, proposal_id)
        self.assertEqual(result.person_id, person_id)
        self.assertEqual(result.role, role)
        self.assertFalse(result.accepted)
        self.assertIsNone(result.text)
        self.assertIsNone(result.format)

        result = self.db.search_reviewer_acceptance(
            person_id=person_id, with_text=True).get_single()

        self.assertIsInstance(result, ReviewerAcceptance)
        self.assertEqual(result.id, acceptance_id)
        self.assertEqual(result.proposal_id, proposal_id)
        self.assertEqual(result.person_id, person_id)
        self.assertEqual(result.role, role)
        self.assertFalse(result.accepted)
        self.assertEqual(result.text, 'I know the PI')
        self.assertEqual(result.format, FormatType.PLAIN)

        self.db.update_reviewer_acceptance(
            reviewer_acceptance_id=acceptance_id, accepted=True,
            text='I knew the PI', format_=FormatType.PLAIN)

        result = self.db.search_reviewer_acceptance(
            person_id=person_id, with_text=True).get_single()

        self.assertIsInstance(result, ReviewerAcceptance)
        self.assertEqual(result.id, acceptance_id)
        self.assertTrue(result.accepted)
        self.assertEqual(result.text, 'I knew the PI')
        self.assertEqual(result.format, FormatType.PLAIN)

        # Try a different review type -- without acceptance.
        reviewer_id = self.db.add_reviewer(
            BaseReviewerRole, proposal_id, person_id,
            BaseReviewerRole.TECH)
        self.assertIsInstance(reviewer_id, int)
        with self.assertRaisesRegex(Error, 'not require acceptance'):
            self.db.add_reviewer_acceptance(
                BaseReviewerRole, proposal_id=proposal_id,
                person_id=proposal_id, role=BaseReviewerRole.TECH,
                accepted=False, text='I know the PI', format_=FormatType.PLAIN)

        # Check we get no results for a non-existent record.
        result = self.db.search_reviewer_acceptance(person_id=1999999)
        self.assertFalse(result)

        # Try deleting a record.
        with self.assertRaises(ConsistencyError):
            self.db.delete_reviewer_acceptance(reviewer_acceptance_id=1999999)

        self.db.delete_reviewer_acceptance(reviewer_acceptance_id=acceptance_id)

        with self.assertRaises(NoSuchRecord):
            self.db.search_reviewer_acceptance(
                person_id=person_id).get_single()

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
        decision_id = self.db.set_decision(
            proposal_id, False, False, False, note='A note.',
            note_format=FormatType.PLAIN)
        self.assertIsInstance(decision_id, int)

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
        decision_id = self.db.set_decision(
            proposal_id, True, True, True,
            note='Edited note.', note_format=FormatType.PLAIN)
        self.assertIsNone(decision_id)

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
        decision_id = self.db.set_decision(proposal_id, accept=None)
        self.assertIsNone(decision_id)

        proposal = self.db.get_proposal(
            facility_id=None, proposal_id=proposal_id, with_decision=True)

        self.assertEqual(proposal.id, proposal_id)
        self.assertIsNone(proposal.decision_accept)

    def test_review_fig(self):
        facility_id = self.db.ensure_facility('my_tel')
        proposal_id = self._create_test_proposal(facility_id=facility_id)
        reviewer_id = self._create_test_reviewer(proposal_id)
        person_id = self.db.add_person('Person 1')

        fig = b'dummy figure'
        type_ = FigureType.PNG

        result = self.db.search_review_figure(reviewer_id=reviewer_id)
        self.assertIsInstance(result, ReviewFigureCollection)
        self.assertEqual(len(result), 0)

        (link_id, fig_id) = self.db.add_review_figure(
            reviewer_id, type_, fig, 'Figure caption.', 'test.png', person_id)
        self.assertIsInstance(link_id, int)
        self.assertIsInstance(fig_id, int)

        result = self.db.search_review_figure(reviewer_id=reviewer_id)
        self.assertIsInstance(result, ReviewFigureCollection)
        self.assertEqual(len(result), 1)
        self.assertIn(link_id, result)
        fig_info = result[link_id]
        self.assertIsInstance(fig_info, ReviewFigureInfo)
        self.assertEqual(fig_info.id, link_id)
        self.assertEqual(fig_info.fig_id, fig_id)
        self.assertEqual(fig_info.reviewer_id, reviewer_id)
        self.assertEqual(fig_info.sort_order, 1)
        self.assertEqual(fig_info.md5sum, 'b41faa148ef23d1ddfa46debb3b66f35')
        self.assertEqual(fig_info.type, type_)
        self.assertEqual(fig_info.state, AttachmentState.NEW)
        self.assertEqual(fig_info.caption, None)
        self.assertEqual(fig_info.filename, 'test.png')
        self.assertIsInstance(fig_info.uploaded, datetime)
        self.assertEqual(fig_info.uploader, person_id)
        self.assertEqual(fig_info.uploader_name, None)
        self.assertEqual(fig_info.has_preview, None)

        result = self.db.search_review_figure(
            fig_id=fig_id, with_has_preview=True).get_single()
        self.assertEqual(result.has_preview, False)

        with self.assertRaises(NoSuchRecord):
            self.db.search_review_figure(fig_id=1999999).get_single()

        self.assertEqual(
            self.db.search_review_figure(link_id=link_id).get_single().id,
            link_id)

        with self.assertRaises(NoSuchRecord):
            self.db.search_review_figure(link_id=1999999).get_single()

        self.assertEqual(
            self.db.get_review_figure(reviewer_id, link_id).data,
            fig)

        # Try previews and thumbnails.
        preview = b'dummy preview'
        thumbnail = b'dummy thumbnail'

        self.db.set_review_figure_preview(fig_id, preview)
        self.db.set_review_figure_thumbnail(fig_id, thumbnail)

        self.assertEqual(
            self.db.get_review_figure_preview(reviewer_id, link_id),
            preview)

        self.assertEqual(
            self.db.get_review_figure_thumbnail(reviewer_id, link_id),
            thumbnail)

        preview = b'dummy preview updated'
        thumbnail = b'dummy thumbnail updated'

        self.db.set_review_figure_preview(fig_id, preview)
        self.db.set_review_figure_thumbnail(fig_id, thumbnail)

        self.assertEqual(
            self.db.get_review_figure_preview(reviewer_id, link_id),
            preview)

        self.assertEqual(
            self.db.get_review_figure_thumbnail(reviewer_id, link_id),
            thumbnail)

        # Try updating the figure...
        # ... change figure state.
        result = self.db.update_review_figure(
            None, None, fig_id, state=AttachmentState.ERROR,
            state_prev=AttachmentState.NEW, state_is_system=True)
        self.assertIsNone(result)

        result = self.db.search_review_figure(
            reviewer_id=reviewer_id, with_has_preview=True)
        fig_info = result[link_id]
        self.assertEqual(fig_info.state, AttachmentState.ERROR)
        self.assertEqual(fig_info.has_preview, True)
        self.assertEqual(fig_info.fig_id, fig_id)

        # ... change figure image.
        fig = b'dummy figure updated'
        new_fig_id = self.db.update_review_figure(
            reviewer_id, link_id,
            figure=fig, type_=type_, filename='test2.png',
            uploader_person_id=person_id)
        self.assertIsInstance(new_fig_id, int)
        self.assertNotEqual(new_fig_id, fig_id)

        result = self.db.search_review_figure(
            reviewer_id=reviewer_id, with_caption=True)
        fig_info = result[link_id]
        self.assertEqual(fig_info.md5sum, 'b9e7dfbc36883c26e5d2aff8c80f34db')
        self.assertEqual(fig_info.state, AttachmentState.NEW)
        self.assertEqual(fig_info.filename, 'test2.png')
        self.assertEqual(fig_info.caption, 'Figure caption.')
        self.assertEqual(fig_info.fig_id, new_fig_id)
        fig_id = new_fig_id

        self.assertEqual(
            self.db.get_review_figure(reviewer_id, link_id).data,
            fig)

        # ... changing the image should have removed the preview/thumbnail.
        with self.assertRaises(NoSuchRecord):
            self.db.get_review_figure_preview(reviewer_id, link_id)

        with self.assertRaises(NoSuchRecord):
            self.db.get_review_figure_thumbnail(reviewer_id, link_id)

        # ... change the figure caption.
        result = self.db.update_review_figure(
            reviewer_id, link_id, caption='!')
        self.assertIsNone(result)

        result = self.db.search_review_figure(
            reviewer_id=reviewer_id, with_caption=True)
        fig_info = result[link_id]
        self.assertEqual(fig_info.caption, '!')

        # Add another figure to test syncing operations.
        (link_id2, fig_id2) = self.db.add_review_figure(
            reviewer_id, type_, fig, 'Figure caption.', 'test2.png', person_id)
        self.assertIsInstance(fig_id2, int)

        result = self.db.search_review_figure(reviewer_id=reviewer_id)
        self.assertEqual(list(result), [link_id, link_id2])
        self.assertEqual(
            [x.id for x in result.values()],
            [link_id, link_id2])
        self.assertEqual(
            [x.fig_id for x in result.values()],
            [fig_id, fig_id2])

        records = ReviewFigureCollection()
        records[link_id] = result[link_id]._replace(sort_order=2)
        records[link_id2] = result[link_id2]._replace(sort_order=1)

        # ... change the sort order.
        (n_insert, n_update, n_delete) = self.db.sync_review_figure(
            reviewer_id, records)
        self.assertEqual(n_insert, 0)
        self.assertEqual(n_update, 2)
        self.assertEqual(n_delete, 0)

        result = self.db.search_review_figure(reviewer_id=reviewer_id)
        self.assertEqual(list(result), [link_id2, link_id])
        self.assertEqual(
            [x.id for x in result.values()],
            [link_id2, link_id])

        # ... delete the second figure.
        del records[link_id2]

        (n_insert, n_update, n_delete) = self.db.sync_review_figure(
            reviewer_id, records)
        self.assertEqual(n_insert, 0)
        self.assertEqual(n_update, 0)
        self.assertEqual(n_delete, 1)

        result = self.db.search_review_figure(reviewer_id=reviewer_id)
        self.assertEqual(list(result), [link_id])
        self.assertEqual(
            [x.id for x in result.values()],
            [link_id])

        # Try deleting the first figure.
        self.db.delete_review_figure(reviewer_id, fig_id)

        result = self.db.search_review_figure(reviewer_id=reviewer_id)
        self.assertEqual(len(result), 0)

    def test_review_deadline(self):
        (call_id, affiliation_id) = self._create_test_call()
        self.assertIsInstance(call_id, int)

        result = self.db.search_review_deadline(call_id=call_id)
        self.assertIsInstance(result, ReviewDeadlineCollection)
        self.assertEqual(len(result), 0)

        records = ReviewDeadlineCollection((
            ('new_1', null_tuple(ReviewDeadline)._replace(
                role=BaseReviewerRole.TECH, date=datetime(2020, 2, 20))),
            ('new_2', null_tuple(ReviewDeadline)._replace(
                role=BaseReviewerRole.EXTERNAL, date=datetime(2020, 2, 10))),
        ))

        (n_insert, n_update, n_delete) = self.db.sync_call_review_deadline(
            BaseReviewerRole, call_id, records)

        self.assertEqual(n_insert, 2)
        self.assertEqual(n_update, 0)
        self.assertEqual(n_delete, 0)

        result = self.db.search_review_deadline(call_id=call_id)
        self.assertIsInstance(result, ReviewDeadlineCollection)
        self.assertEqual(len(result), 2)

        for (entry, date) in zip(
                result.values_in_role_order(BaseReviewerRole),
                ['2020-02-20T00:00:00', '2020-02-10T00:00:00']):
            self.assertIsInstance(entry, ReviewDeadline)
            self.assertEqual(entry.date.isoformat(), date)

        result = self.db.search_review_deadline(
            call_id=call_id, role=BaseReviewerRole.TECH)
        self.assertIsInstance(result, ReviewDeadlineCollection)
        self.assertEqual(len(result), 1)
        self.assertEqual(first_value(result).date, datetime(2020, 2, 20))

        (n_insert, n_update, n_delete) = self.db.sync_call_review_deadline(
            BaseReviewerRole, call_id, ReviewDeadlineCollection())

        self.assertEqual(n_insert, 0)
        self.assertEqual(n_update, 0)
        self.assertEqual(n_delete, 2)

        result = self.db.search_review_deadline(call_id=call_id)
        self.assertIsInstance(result, ReviewDeadlineCollection)
        self.assertEqual(len(result), 0)

    def test_review_notes(self):
        (call_id, affiliation_id) = self._create_test_call()
        with self.assertRaises(NoSuchRecord):
            self.db.get_affiliation_weight_note(call_id=call_id)

        self.db.set_affiliation_weight_note(
            call_id, 'note a', FormatType.PLAIN)

        note = self.db.get_affiliation_weight_note(call_id=call_id)
        self.assertIsInstance(note, Note)
        self.assertEqual(note.text, 'note a')
        self.assertEqual(note.format, FormatType.PLAIN)

        self.db.set_affiliation_weight_note(
            call_id, 'note b', FormatType.RST)

        note = self.db.get_affiliation_weight_note(call_id=call_id)
        self.assertIsInstance(note, Note)
        self.assertEqual(note.text, 'note b')
        self.assertEqual(note.format, FormatType.RST)

        with self.assertRaises(NoSuchRecord):
            self.db.get_available_note(call_id=call_id)

        self.db.set_available_note(
            call_id, 'note c', FormatType.PLAIN)

        note = self.db.get_available_note(call_id=call_id)
        self.assertIsInstance(note, Note)
        self.assertEqual(note.text, 'note c')
        self.assertEqual(note.format, FormatType.PLAIN)

        self.db.set_available_note(
            call_id, 'note d', FormatType.RST)

        note = self.db.get_available_note(call_id=call_id)
        self.assertIsInstance(note, Note)
        self.assertEqual(note.text, 'note d')
        self.assertEqual(note.format, FormatType.RST)

        self.db.delete_affiliation_weight_note(call_id)

        with self.assertRaises(NoSuchRecord):
            self.db.get_affiliation_weight_note(call_id=call_id)

        self.db.delete_available_note(call_id)

        with self.assertRaises(NoSuchRecord):
            self.db.get_available_note(call_id=call_id)
