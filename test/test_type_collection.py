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

from collections import namedtuple
import itertools
from unittest import TestCase

from hedwig.error import MultipleRecords, NoSuchRecord, UserError
from hedwig.type.base import CollectionByProposal, CollectionOrdered
from hedwig.type.collection import \
    CallCollection, EmailCollection, GroupMemberCollection, MemberCollection, \
    ResultCollection, \
    ProposalCollection, ProposalFigureCollection, ReviewerCollection
from hedwig.type.enum import BaseReviewerRole, BaseTextRole, \
    CallState, GroupType, \
    ReviewState
from hedwig.type.simple import \
    Call, Email, GroupMember, Member, \
    Proposal, ProposalFigureInfo, Reviewer
from hedwig.type.util import null_tuple


class CollectionTypeTestCase(TestCase):
    def test_by_proposal_collection(self):
        class BPCollection(ResultCollection, CollectionByProposal):
            pass

        BP = namedtuple('BP', ('id', 'proposal_id'))

        c = BPCollection()
        c[101] = BP(101, 1)
        c[102] = BP(102, 1)
        c[103] = BP(103, 1)
        c[201] = BP(201, 2)
        c[202] = BP(202, 2)

        # Test get_proposal method.

        r = c.get_proposal(1)
        self.assertEqual(r, BP(101, 1))

        r = c.get_proposal(2)
        self.assertEqual(r, BP(201, 2))

        with self.assertRaises(KeyError):
            c.get_proposal(3)

        r = c.get_proposal(3, default=None)
        self.assertIsNone(r)

        # Test subset_by_proposal method.

        s = c.subset_by_proposal(1)
        self.assertIsInstance(s, BPCollection)
        self.assertEqual(len(s), 3)

        self.assertEqual(list(s.keys()), [101, 102, 103])
        self.assertEqual(list(s.values()),
                         [BP(101, 1), BP(102, 1), BP(103, 1)])

        s = c.subset_by_proposal(2)
        self.assertIsInstance(s, BPCollection)
        self.assertEqual(len(s), 2)

        self.assertEqual(list(s.keys()), [201, 202])
        self.assertEqual(list(s.values()), [BP(201, 2), BP(202, 2)])

        s = c.subset_by_proposal(3)
        self.assertIsInstance(s, BPCollection)
        self.assertEqual(len(s), 0)

    def test_call_collection(self):
        c = CallCollection()

        c[1] = null_tuple(Call)._replace(
            id=1, queue_id=11, state=CallState.OPEN)
        c[2] = null_tuple(Call)._replace(
            id=2, queue_id=12, state=CallState.OPEN)
        c[3] = null_tuple(Call)._replace(
            id=3, queue_id=13, state=CallState.UNOPENED)
        c[4] = null_tuple(Call)._replace(
            id=4, queue_id=13, state=CallState.CLOSED)

        self.assertEqual([x.id for x in c.values_by_state(CallState.OPEN)],
                         [1, 2])

        self.assertEqual([x.id for x in c.values_by_state(CallState.UNOPENED)],
                         [3])

        self.assertEqual([x.id for x in c.values_by_state(CallState.CLOSED)],
                         [4])

        self.assertEqual([x.id for x in c.values_by_queue(11)],
                         [1])

        self.assertEqual([x.id for x in c.values_by_queue(12)],
                         [2])

        self.assertEqual([x.id for x in c.values_by_queue(13)],
                         [3, 4])

        self.assertEqual([x.id for x in c.values_by_queue((11, 12))],
                         [1, 2])

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

        self.assertIsNone(c.get_pi(default=None))

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

        self.assertTrue(c.has_person(9001))
        self.assertFalse(c.has_person(999999))

    def test_proposal_figure_collection(self):
        fc = ProposalFigureCollection()

        fc[1001] = null_tuple(ProposalFigureInfo)._replace(
            id=1001, role=BaseTextRole.TECHNICAL_CASE)
        fc[1002] = null_tuple(ProposalFigureInfo)._replace(
            id=1002, role=BaseTextRole.TECHNICAL_CASE)
        fc[1003] = null_tuple(ProposalFigureInfo)._replace(
            id=1003, role=BaseTextRole.SCIENCE_CASE)
        fc[1004] = null_tuple(ProposalFigureInfo)._replace(
            id=1004, role=BaseTextRole.SCIENCE_CASE)

        tech = set((x.id for x in fc.values_by_role(
            BaseTextRole.TECHNICAL_CASE)))
        sci = set((x.id for x in fc.values_by_role(
            BaseTextRole.SCIENCE_CASE)))

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
        class OrderedResultCollection(ResultCollection, CollectionOrdered):
            pass

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

    def test_group_member_collection(self):
        c = GroupMemberCollection()

        c[101] = null_tuple(GroupMember)._replace(
            id=101, group_type=GroupType.CTTEE, facility_id=1)
        c[102] = null_tuple(GroupMember)._replace(
            id=102, group_type=GroupType.TECH, facility_id=1)
        c[103] = null_tuple(GroupMember)._replace(
            id=103, group_type=GroupType.TECH, facility_id=1)
        c[104] = null_tuple(GroupMember)._replace(
            id=104, group_type=GroupType.COORD, facility_id=2)

        self.assertEqual(
            sorted([x.id for x in c.values_by_group_type(GroupType.CTTEE)]),
            [101])

        self.assertEqual(
            sorted([x.id for x in c.values_by_group_type(GroupType.TECH)]),
            [102, 103])

        self.assertEqual(
            sorted([x.id for x in c.values_by_group_type(GroupType.COORD)]),
            [104])

        self.assertTrue(c.has_entry(group_type=GroupType.CTTEE))
        self.assertTrue(c.has_entry(group_type=(GroupType.TECH,
                                                GroupType.COORD)))
        self.assertFalse(c.has_entry(group_type=999))

        self.assertTrue(c.has_entry(facility_id=1))
        self.assertTrue(c.has_entry(facility_id=2))
        self.assertFalse(c.has_entry(facility_id=3))

        self.assertTrue(c.has_entry(group_type=GroupType.CTTEE,
                                    facility_id=1))
        self.assertFalse(c.has_entry(group_type=GroupType.CTTEE,
                                     facility_id=2))

        self.assertTrue(c.has_entry(group_type=GroupType.COORD,
                                    facility_id=2))
        self.assertFalse(c.has_entry(group_type=GroupType.COORD,
                                     facility_id=1))

    def test_proposal_collection(self):
        c = ProposalCollection()

        c[101] = null_tuple(Proposal)._replace(id=101, facility_id=1)
        c[102] = null_tuple(Proposal)._replace(id=102, facility_id=1)
        c[103] = null_tuple(Proposal)._replace(id=103, facility_id=1)
        c[201] = null_tuple(Proposal)._replace(id=201, facility_id=2)
        c[202] = null_tuple(Proposal)._replace(id=202, facility_id=2)
        c[203] = null_tuple(Proposal)._replace(id=203, facility_id=2)

        fl = list(c.values_by_facility(facility_id=1))
        self.assertEqual([x.id for x in fl], [101, 102, 103])

        fl = list(c.values_by_facility(facility_id=2))
        self.assertEqual([x.id for x in fl], [201, 202, 203])

        fl = list(c.values_by_facility(facility_id=3))
        self.assertEqual(fl, [])

    def test_reviewer_collection(self):
        c = ReviewerCollection()

        c[201] = null_tuple(Reviewer)._replace(id=201, person_id=2001,
                                               role=BaseReviewerRole.TECH)
        c[202] = null_tuple(Reviewer)._replace(id=202, person_id=2002,
                                               role=BaseReviewerRole.EXTERNAL)

        self.assertFalse(c.has_person(9999))

        self.assertTrue(c.has_person(2001))

        self.assertFalse(c.has_person(2001, roles=[BaseReviewerRole.EXTERNAL]))

        self.assertTrue(c.has_person(2001, roles=[BaseReviewerRole.TECH]))

        self.assertEqual(c.person_id_by_role(BaseReviewerRole.EXTERNAL),
                         [2002])

        self.assertFalse(c.has_role(BaseReviewerRole.FEEDBACK))

        self.assertTrue(c.has_role(BaseReviewerRole.EXTERNAL))

        self.assertEqual(c.role_by_person_id(2001),
                         [BaseReviewerRole.TECH])

        self.assertEqual(c.role_by_person_id(2002),
                         [BaseReviewerRole.EXTERNAL])

        reviewers = c.values_by_role(BaseReviewerRole.EXTERNAL)
        self.assertIsInstance(reviewers, list)
        self.assertEqual(len(reviewers), 1)
        self.assertIsInstance(reviewers[0], Reviewer)
        self.assertEqual(reviewers[0].id, 202)

    def test_reviewer_collection_rating(self):
        c = ReviewerCollection()

        rr = BaseReviewerRole

        def rwf_inc_unweighted(reviewer):
            if reviewer.review_weight is None:
                if rr.get_info(reviewer.role).weight:
                    return (None, None)
                return (reviewer.review_rating, 1.0)
            return (reviewer.review_rating, reviewer.review_weight / 100.0)

        def rwf_exc_unweighted(reviewer):
            if reviewer.review_weight is None:
                return (None, None)
            return (reviewer.review_rating, reviewer.review_weight / 100.0)

        rating = c.get_overall_rating(rwf_inc_unweighted,
                                      with_std_dev=False)
        self.assertIsNone(rating)
        rating = c.get_overall_rating(rwf_inc_unweighted,
                                      with_std_dev=True)
        self.assertIsInstance(rating, tuple)
        self.assertEqual(len(rating), 2)
        self.assertIsNone(rating[0])
        self.assertIsNone(rating[1])

        # Add some simple review ratings.
        rs = [
            dict(role=rr.TECH),
            dict(role=rr.EXTERNAL),
            dict(role=rr.EXTERNAL, review_rating=20),
            dict(role=rr.CTTEE_PRIMARY),
            dict(role=rr.CTTEE_PRIMARY, review_rating=10),
            dict(role=rr.CTTEE_PRIMARY, review_rating=80, review_weight=100),
        ]

        for (r, n) in zip(rs, itertools.count(100)):
            c[n] = null_tuple(Reviewer)._replace(
                review_state=ReviewState.DONE, **r)

        self.assertEqual(c.get_overall_rating(rwf_inc_unweighted,
                                              with_std_dev=False), 50)
        self.assertEqual(c.get_overall_rating(rwf_exc_unweighted,
                                              with_std_dev=False), 80)

        # Repeat test above, including calculation of standard deviation.
        rating = c.get_overall_rating(rwf_exc_unweighted,
                                      with_std_dev=True)
        self.assertIsInstance(rating, tuple)
        self.assertEqual(len(rating), 2)
        self.assertEqual(rating[0], 80.0)
        self.assertEqual(rating[1], 0.0)

        (rating, std_dev) = c.get_overall_rating(rwf_inc_unweighted,
                                                 with_std_dev=True)
        self.assertEqual(rating, 50.0)
        self.assertEqual(std_dev, 30.0)

        # Add some more reviews with non-100% weights.
        rs = [
            dict(role=rr.CTTEE_SECONDARY, review_rating=20, review_weight=50),
            dict(role=rr.CTTEE_SECONDARY, review_rating=40, review_weight=50),
        ]

        for (r, n) in zip(rs, itertools.count(200)):
            c[n] = null_tuple(Reviewer)._replace(
                review_state=ReviewState.DONE, **r)

        self.assertEqual(c.get_overall_rating(rwf_exc_unweighted,
                                              with_std_dev=False), 55)

        (rating, std_dev) = c.get_overall_rating(rwf_exc_unweighted,
                                                 with_std_dev=True)
        self.assertEqual(rating, 55.0)
        self.assertAlmostEqual(std_dev, 25.981, places=3)
