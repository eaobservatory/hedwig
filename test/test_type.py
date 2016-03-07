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

from collections import namedtuple, OrderedDict
import itertools
from unittest import TestCase

from hedwig.error import Error, MultipleRecords, NoSuchRecord, UserError
from hedwig.type import Assessment, AttachmentState, CallState, \
    Email, EmailCollection, GroupType, GroupMember, GroupMemberCollection,  \
    Member, MemberCollection, \
    OrderedResultCollection, \
    ResultCollection, ProposalFigureInfo, ProposalFigureCollection, \
    ProposalState, Reviewer, ReviewerRole, ReviewerCollection, \
    TextRole, \
    null_tuple, with_can_edit


class TypeTestCase(TestCase):
    def test_assessment(self):
        self.assertTrue(Assessment.is_valid(Assessment.PROBLEM))
        self.assertFalse(Assessment.is_valid(999))

        name = Assessment.get_name(Assessment.FEASIBLE)
        self.assertIsInstance(name, unicode)

        options = Assessment.get_options()
        self.assertIsInstance(options, OrderedDict)

        for (k, v) in options.items():
            self.assertIsInstance(k, int)
            self.assertIsInstance(v, unicode)

    def test_attachment_state(self):
        # Get list of all states for subsequent tests.
        states = list(AttachmentState._info.keys())

        self.assertFalse(AttachmentState.is_valid(999))

        unready = AttachmentState.unready_states()
        self.assertIsInstance(unready, list)

        for state in states:
            self.assertTrue(AttachmentState.is_valid(state))
            self.assertIsInstance(AttachmentState.get_name(state), unicode)

            if state == AttachmentState.READY:
                self.assertNotIn(state, unready)
                self.assertTrue(AttachmentState.is_ready(state))
            else:
                self.assertIn(state, unready)
                self.assertFalse(AttachmentState.is_ready(state))

            if state == AttachmentState.ERROR:
                self.assertTrue(AttachmentState.is_error(state))
            else:
                self.assertFalse(AttachmentState.is_error(state))

    def test_call_state(self):
        states = [CallState.UNOPENED, CallState.OPEN, CallState.CLOSED]

        self.assertEqual(CallState.get_name(CallState.OPEN), 'Open')

        for state in states:
            self.assertIsInstance(CallState.get_name(state), unicode)

    def test_email_collection(self):
        c = EmailCollection()

        c[1] = null_tuple(Email)._replace(address='a@b', primary=False)

        with self.assertRaisesRegexp(UserError, 'There is no primary'):
            c.validate()

        c[2] = null_tuple(Email)._replace(address='c@d', primary=True)

        c.validate()

        c[3] = null_tuple(Email)._replace(address='e@f', primary=True)

        with self.assertRaisesRegexp(UserError, 'more than one primary'):
            c.validate()

        c[3] = null_tuple(Email)._replace(address='a@b', primary=False)

        with self.assertRaisesRegexp(UserError, 'appears more than once'):
            c.validate()

    def test_member_collection(self):
        c = MemberCollection()

        c[101] = null_tuple(Member)._replace(
            id=101, person_id=9001, pi=False, person_name='Person One')

        with self.assertRaises(KeyError):
            c.get_pi()

        c[102] = null_tuple(Member)._replace(
            id=102, person_id=9002, pi=True, person_name='Person Two')

        c[103] = null_tuple(Member)._replace(
            id=103, person_id=9003, pi=False, person_name='Person Three')

        result = c.get_pi()
        self.assertEqual(result.person_id, 9002)

        result = c.get_person(9003)
        self.assertEqual(result.id, 103)

        # hedwig.view.auth.for_proposal relies on this exception being
        # raised when the current user isn't a member of the proposal.
        with self.assertRaises(KeyError):
            c.get_person(999999)

    def test_proposal_state(self):
        states = set()
        for state in (
                ProposalState.PREPARATION,
                ProposalState.SUBMITTED,
                ProposalState.WITHDRAWN,
                ProposalState.REVIEW,
                ProposalState.ACCEPTED,
                ProposalState.REJECTED,
                ):
            # Check state is an integer.
            self.assertIsInstance(state, int)
            self.assertNotIn(state, states)

            # Check state is unique.
            states.add(state)

            # State should be considered valid.
            self.assertTrue(ProposalState.is_valid(state))

            # State should have a name.
            self.assertIsInstance(ProposalState.get_name(state), unicode)

            # State should have boolean "can_edit" property.
            self.assertIn(ProposalState.can_edit(state), (True, False))

        self.assertFalse(ProposalState.is_valid(999))

        states = ProposalState.editable_states()
        self.assertIsInstance(states, list)
        self.assertIn(ProposalState.PREPARATION, states)
        self.assertNotIn(ProposalState.REVIEW, states)

        states = ProposalState.submitted_states()
        self.assertIsInstance(states, list)
        self.assertNotIn(ProposalState.PREPARATION, states)
        self.assertIn(ProposalState.REVIEW, states)

        states = ProposalState.reviewed_states()
        self.assertIsInstance(states, list)
        self.assertNotIn(ProposalState.PREPARATION, states)
        self.assertNotIn(ProposalState.SUBMITTED, states)
        self.assertNotIn(ProposalState.ABANDONED, states)
        self.assertIn(ProposalState.ACCEPTED, states)
        self.assertIn(ProposalState.REJECTED, states)
        self.assertTrue(ProposalState.is_reviewed(ProposalState.ACCEPTED))
        self.assertTrue(ProposalState.is_reviewed(ProposalState.REJECTED))
        self.assertFalse(ProposalState.is_reviewed(ProposalState.REVIEW))
        self.assertFalse(ProposalState.is_reviewed(ProposalState.ABANDONED))

        self.assertEqual(ProposalState.by_name('accepted'),
                         ProposalState.ACCEPTED)
        self.assertIsNone(ProposalState.by_name('not a real state'))

    def test_proposal_figure_collection(self):
        fc = ProposalFigureCollection()

        fc[1001] = null_tuple(ProposalFigureInfo)._replace(
            id=1001, role=TextRole.TECHNICAL_CASE)
        fc[1002] = null_tuple(ProposalFigureInfo)._replace(
            id=1002, role=TextRole.TECHNICAL_CASE)
        fc[1003] = null_tuple(ProposalFigureInfo)._replace(
            id=1003, role=TextRole.SCIENCE_CASE)
        fc[1004] = null_tuple(ProposalFigureInfo)._replace(
            id=1004, role=TextRole.SCIENCE_CASE)

        tech = set((x.id for x in fc.values_by_role(TextRole.TECHNICAL_CASE)))
        sci = set((x.id for x in fc.values_by_role(TextRole.SCIENCE_CASE)))

        self.assertEqual(tech, set((1001, 1002)))
        self.assertEqual(sci, set((1003, 1004)))

    def test_result_collection(self):
        rc = ResultCollection()
        r = 'test result'

        with self.assertRaises(NoSuchRecord):
            rc.get_single()

        rc[0] = r

        self.assertIs(rc.get_single(), r)

        rc[1] = 'another result'

        with self.assertRaises(MultipleRecords):
            rc.get_single()

    def test_ordered_result_collection(self):
        SortOrdered = namedtuple('SortOrdered', ('id', 'sort_order'))

        rc = OrderedResultCollection()
        rc[1] = SortOrdered(1, 1)
        rc[2] = SortOrdered(2, None)
        rc[3] = SortOrdered(3, 2)
        rc[4] = SortOrdered(4, None)

        rc.ensure_sort_order()

        self.assertEqual(list(rc.values()), [
            SortOrdered(1, 1),
            SortOrdered(2, 3),
            SortOrdered(3, 2),
            SortOrdered(4, 4),
        ])

    def test_group_type(self):
        options = GroupType.get_options()
        self.assertIsInstance(options, OrderedDict)

        for (k, v) in options.items():
            self.assertIsInstance(k, int)
            self.assertTrue(GroupType.is_valid(k))

            self.assertIsInstance(v, unicode)

            i = GroupType.get_info(k)
            self.assertIsInstance(i, tuple)
            self.assertIsInstance(i.name, unicode)
            self.assertIsInstance(i.view_all_prop, bool)
            self.assertIsInstance(i.private_moc, bool)
            self.assertEqual(i.name, v)

        self.assertFalse(GroupType.is_valid(999999))

        self.assertIsInstance(GroupType.view_all_groups(), list)
        self.assertIsInstance(GroupType.private_moc_groups(), list)
        self.assertIsInstance(GroupType.review_coord_groups(), list)

    def test_group_member_collection(self):
        c = GroupMemberCollection()

        c[101] = null_tuple(GroupMember)._replace(
            id=101, group_type=GroupType.CTTEE)
        c[102] = null_tuple(GroupMember)._replace(
            id=102, group_type=GroupType.TECH)
        c[103] = null_tuple(GroupMember)._replace(
            id=103, group_type=GroupType.TECH)
        c[104] = null_tuple(GroupMember)._replace(
            id=104, group_type=GroupType.COORD)

        self.assertEqual(
            sorted([x.id for x in c.values_by_group_type(GroupType.CTTEE)]),
            [101])

        self.assertEqual(
            sorted([x.id for x in c.values_by_group_type(GroupType.TECH)]),
            [102, 103])

        self.assertEqual(
            sorted([x.id for x in c.values_by_group_type(GroupType.COORD)]),
            [104])

    def test_reviewer_collection(self):
        c = ReviewerCollection()

        c[201] = null_tuple(Reviewer)._replace(id=201, person_id=2001,
                                               role=ReviewerRole.TECH)
        c[202] = null_tuple(Reviewer)._replace(id=202, person_id=2002,
                                               role=ReviewerRole.EXTERNAL)

        # hedwig.view.auth.for_proposal relies on this exception being
        # raised when the current user isn't a reviewer of the proposal.
        with self.assertRaises(KeyError):
            c.get_person(9999)

        self.assertEqual(c.get_person(2001).id, 201)

        with self.assertRaises(KeyError):
            c.get_person(2001, roles=[ReviewerRole.EXTERNAL])

        self.assertEqual(c.get_person(2001, roles=[ReviewerRole.TECH]).id, 201)

        self.assertEqual(c.person_id_by_role(ReviewerRole.EXTERNAL), [2002])

        reviewers = c.values_by_role(ReviewerRole.EXTERNAL)
        self.assertIsInstance(reviewers, list)
        self.assertEqual(len(reviewers), 1)
        self.assertIsInstance(reviewers[0], Reviewer)
        self.assertEqual(reviewers[0].id, 202)

    def test_reviewer_collection_rating(self):
        c = ReviewerCollection()

        rating = c.get_overall_rating(include_unweighted=True,
                                      with_std_dev=False)
        self.assertIsNone(rating)
        rating = c.get_overall_rating(include_unweighted=True,
                                      with_std_dev=True)
        self.assertIsInstance(rating, tuple)
        self.assertEqual(len(rating), 2)
        self.assertIsNone(rating[0])
        self.assertIsNone(rating[1])

        # Add some simple review ratings.
        rr = ReviewerRole
        rs = [
            dict(role=rr.TECH),
            dict(role=rr.EXTERNAL),
            dict(role=rr.EXTERNAL, review_rating=20),
            dict(role=rr.CTTEE_PRIMARY),
            dict(role=rr.CTTEE_PRIMARY, review_rating=10),
            dict(role=rr.CTTEE_PRIMARY, review_rating=80, review_weight=100),
        ]

        for (r, n) in zip(rs, itertools.count(100)):
            c[n] = null_tuple(Reviewer)._replace(review_present=True, **r)

        self.assertEqual(c.get_overall_rating(include_unweighted=True,
                                              with_std_dev=False), 50)
        self.assertEqual(c.get_overall_rating(include_unweighted=False,
                                              with_std_dev=False), 80)

        # Repeat test above, including calculation of standard deviation.
        rating = c.get_overall_rating(include_unweighted=False,
                                      with_std_dev=True)
        self.assertIsInstance(rating, tuple)
        self.assertEqual(len(rating), 2)
        self.assertEqual(rating[0], 80.0)
        self.assertEqual(rating[1], 0.0)

        (rating, std_dev) = c.get_overall_rating(include_unweighted=True,
                                                 with_std_dev=True)
        self.assertEqual(rating, 50.0)
        self.assertEqual(std_dev, 30.0)

        # Add some more reviews with non-100% weights.
        rs = [
            dict(role=rr.CTTEE_SECONDARY, review_rating=20, review_weight=50),
            dict(role=rr.CTTEE_SECONDARY, review_rating=40, review_weight=50),
        ]

        for (r, n) in zip(rs, itertools.count(200)):
            c[n] = null_tuple(Reviewer)._replace(review_present=True, **r)

        self.assertEqual(c.get_overall_rating(include_unweighted=False,
                                              with_std_dev=False), 55)

        (rating, std_dev) = c.get_overall_rating(include_unweighted=False,
                                                 with_std_dev=True)
        self.assertEqual(rating, 55.0)
        self.assertAlmostEqual(std_dev, 25.981, places=3)

    def test_reviewer_role(self):
        for role in [
                ReviewerRole.TECH,
                ReviewerRole.EXTERNAL,
                ReviewerRole.CTTEE_PRIMARY,
                ReviewerRole.CTTEE_SECONDARY,
                ReviewerRole.CTTEE_OTHER]:
            self.assertTrue(ReviewerRole.is_valid(role))

            info = ReviewerRole.get_info(role)

            self.assertIsInstance(info, tuple)
            self.assertIsInstance(info.name, unicode)
            self.assertIsInstance(info.unique, bool)
            self.assertIsInstance(info.text, bool)
            self.assertIsInstance(info.assessment, bool)
            self.assertIsInstance(info.rating, bool)
            self.assertIsInstance(info.weight, bool)

        self.assertFalse(ReviewerRole.is_valid(999999))

        self.assertEqual(ReviewerRole.get_cttee_roles(), [
            ReviewerRole.CTTEE_PRIMARY,
            ReviewerRole.CTTEE_SECONDARY,
            ReviewerRole.CTTEE_OTHER,
        ])

        self.assertEqual(ReviewerRole.get_feedback_roles(), [
            ReviewerRole.CTTEE_PRIMARY,
            ReviewerRole.CTTEE_SECONDARY,
        ])

    def test_with_can_edit(self):
        TestTuple = namedtuple('TestTuple', ('x', 'y'))

        t = TestTuple(1, 2)

        t_t = with_can_edit(t, True)
        t_f = with_can_edit(t, False)

        self.assertEqual(t_t.can_edit, True)
        self.assertEqual(t_f.can_edit, False)

        for t_x in (t_t, t_f):
            self.assertEqual(type(t_x).__name__, 'TestTupleWithCE')
            self.assertEqual(t_x._fields, ('x', 'y', 'can_edit'))
            self.assertEqual(t_x.x, 1)
            self.assertEqual(t_x.y, 2)

    def test_text_role(self):
        self.assertTrue(TextRole.is_valid(TextRole.ABSTRACT))
        self.assertFalse(TextRole.is_valid(999))

        self.assertIsInstance(TextRole.get_name(TextRole.TECHNICAL_CASE),
                              unicode)

        self.assertIsInstance(TextRole.short_name(TextRole.SCIENCE_CASE),
                              unicode)

        self.assertIsInstance(TextRole.url_path(TextRole.TECHNICAL_CASE),
                              unicode)

        self.assertIsNone(TextRole.url_path(TextRole.TOOL_NOTE))

        self.assertEqual(TextRole.get_url_paths(), ['technical', 'scientific'])

        self.assertEqual(TextRole.by_url_path('scientific'),
                         TextRole.SCIENCE_CASE)
        self.assertEqual(TextRole.by_url_path('technical'),
                         TextRole.TECHNICAL_CASE)

        with self.assertRaisesRegexp(Error, 'path .* not recognised'):
            TextRole.by_url_path('something_else')

        self.assertIsNone(TextRole.by_url_path('something_else', None))
