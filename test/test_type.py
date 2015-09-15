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

from collections import namedtuple, OrderedDict
import itertools
from unittest import TestCase

from hedwig.error import MultipleRecords, NoSuchRecord
from hedwig.type import Assessment, GroupType, \
    Member, MemberCollection, \
    OrderedResultCollection, \
    ResultCollection, \
    ProposalState, Reviewer, ReviewerRole, ReviewerCollection, \
    null_tuple


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

    def test_reviewer_collection_rating(self):
        c = ReviewerCollection()

        rating = c.get_overall_rating(include_unweighted=True)
        self.assertIsNone(rating)

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

        self.assertEqual(c.get_overall_rating(include_unweighted=True), 50)
        self.assertEqual(c.get_overall_rating(include_unweighted=False), 80)

        # Add some more reviews with non-100% weights.
        rs = [
            dict(role=rr.CTTEE_SECONDARY, review_rating=20, review_weight=50),
            dict(role=rr.CTTEE_SECONDARY, review_rating=40, review_weight=50),
        ]

        for (r, n) in zip(rs, itertools.count(200)):
            c[n] = null_tuple(Reviewer)._replace(review_present=True, **r)

        self.assertEqual(c.get_overall_rating(include_unweighted=False), 55)

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
