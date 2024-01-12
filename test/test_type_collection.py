# Copyright (C) 2015-2024 East Asian Observatory
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

from hedwig.error import MultipleRecords, NoSuchRecord, NoSuchValue, UserError
from hedwig.type.base import CollectionByProposal, CollectionOrdered, \
    CollectionSortable
from hedwig.type.collection import \
    AffiliationCollection, AnnotationCollection, \
    CallCollection, CallPreambleCollection, \
    EmailCollection, GroupMemberCollection, MemberCollection, \
    ResultCollection, ReviewDeadlineCollection, \
    PrevProposalCollection, \
    ProposalCollection, ProposalFigureCollection, \
    RequestCollection, ReviewerCollection, \
    SiteGroupMemberCollection
from hedwig.type.enum import AnnotationType, BaseAffiliationType, \
    BaseReviewerRole, BaseTextRole, \
    CallState, GroupType, \
    RequestState, ReviewState, SiteGroupType
from hedwig.type.simple import \
    Affiliation, Annotation, Call, CallPreamble, Email, GroupMember, Member, \
    PrevProposal, \
    Proposal, ProposalFigureInfo, \
    RequestPropPDF, Reviewer, ReviewDeadline, SiteGroupMember
from hedwig.type.util import null_tuple

from .compat import TestCase


class CollectionTypeTestCase(TestCase):
    def test_organize_collection(self):
        TT = namedtuple('TT', ('id', 'x'))

        c = ResultCollection.organize_collection({}, {})
        self.assertIsInstance(c, ResultCollection)
        self.assertEqual(list(c.keys()), [])

        c = ResultCollection.organize_collection(
            OrderedDict(((20, TT(20, 'b')), (10, TT(10, 'a')))),
            OrderedDict(((2, TT(2, 'd')), (1, TT(1, 'c')))))

        self.assertIsInstance(c, ResultCollection)
        self.assertEqual(list(c.keys()), [10, 20, 21, 22])
        self.assertEqual(list(c.values()), [
            TT(10, 'a'), TT(20, 'b'), TT(21, 'c'), TT(22, 'd')])

    def test_group_by(self):
        TT = namedtuple('TT', ('id', 'flag'))

        c = ResultCollection()
        c[0] = TT(0, 1)
        c[1] = TT(1, 1)
        c[2] = TT(2, 2)
        c[3] = TT(3, 2)
        c[4] = TT(4, 1)
        c[5] = TT(5, 3)

        cc = OrderedDict(c.group_by('flag'))

        self.assertEqual(len(cc), 3)
        self.assertEqual(list(cc.keys()), [1, 2, 3])
        self.assertEqual(list(cc[1].keys()), [0, 1, 4])
        self.assertEqual(list(cc[2].keys()), [2, 3])
        self.assertEqual(list(cc[3].keys()), [5])
        self.assertEqual(list(cc[1].values()), [TT(0, 1), TT(1, 1), TT(4, 1)])
        self.assertEqual(list(cc[2].values()), [TT(2, 2), TT(3, 2)])
        self.assertEqual(list(cc[3].values()), [TT(5, 3)])

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

        with self.assertRaises(NoSuchValue):
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

    def test_sortable_collection(self):
        class TSCollection(ResultCollection, CollectionSortable):
            sort_attr = ((False, ('a', 'b')),)

        TS = namedtuple('TC', ('id', 'a', 'b'))

        c = TSCollection()

        c[101] = TS(101, 1, 3)
        c[102] = TS(102, 3, 2)
        c[103] = TS(103, 2, 1)
        c[104] = TS(104, 3, 1)
        c[105] = TS(105, 2, 3)
        c[106] = TS(106, 1, 1)
        c[107] = TS(107, 3, 3)
        c[108] = TS(108, 1, 2)
        c[109] = TS(109, 2, 2)

        c[201] = TS(201, 2, 1)
        c[202] = TS(202, 3, 1)
        c[203] = TS(203, 1, 3)
        c[204] = TS(204, 3, 2)
        c[205] = TS(205, 2, 3)
        c[206] = TS(206, 2, 2)
        c[207] = TS(207, 3, 3)
        c[208] = TS(208, 1, 2)
        c[209] = TS(209, 1, 1)

        expected = [
            106, 209, 108, 208, 101, 203,
            103, 201, 109, 206, 105, 205,
            104, 202, 102, 204, 107, 207]

        self.assertEqual(
            [x.id for x in c.values_in_sorted_order()], expected)

        sc = c.sorted()

        self.assertIsInstance(sc, TSCollection)

        self.assertEqual(list(sc.keys()), expected)

        self.assertEqual([x.id for x in sc.values()], expected)

    def test_affiliation_collection(self):
        affiliations = AffiliationCollection()

        id_ = 1

        for name in ['Aff. 1', 'Aff. 2', 'Aff. 3']:
            for (type_name, type_) in [
                    ('ex', BaseAffiliationType.EXCLUDED),
                    ('st', BaseAffiliationType.STANDARD),
                    ('sh', BaseAffiliationType.SHARED)]:
                affiliations[id_] = Affiliation(
                    id_, None, '{} ({})'.format(name, type_name),
                    hidden=False, type=type_, weight=None)
                id_ += 1

        self.assertEqual(
            list(x.name for x in affiliations.values()), [
                'Aff. 1 (ex)', 'Aff. 1 (st)', 'Aff. 1 (sh)',
                'Aff. 2 (ex)', 'Aff. 2 (st)', 'Aff. 2 (sh)',
                'Aff. 3 (ex)', 'Aff. 3 (st)', 'Aff. 3 (sh)'])

        self.assertEqual(
            list(x.name for x in affiliations.values_in_type_order(BaseAffiliationType)), [
                'Aff. 1 (st)', 'Aff. 2 (st)', 'Aff. 3 (st)',
                'Aff. 1 (sh)', 'Aff. 2 (sh)', 'Aff. 3 (sh)',
                'Aff. 1 (ex)', 'Aff. 2 (ex)', 'Aff. 3 (ex)'])

    def test_annotation_collection(self):
        c = AnnotationCollection()

        c[1] = null_tuple(Annotation)._replace(
            id=1, type=AnnotationType.PROPOSAL_COPY)

        self.assertTrue(c.has_type(AnnotationType.PROPOSAL_COPY))
        self.assertFalse(c.has_type(AnnotationType.PROPOSAL_CONTINUATION))

        self.assertEqual(
            [x.id for x in c.values_by_type(
                AnnotationType.PROPOSAL_COPY)],
            [1])

        self.assertEqual(
            [x.id for x in c.values_by_type(
                AnnotationType.PROPOSAL_CONTINUATION)],
            [])

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

        self.assertEqual(
            [x.id for x in c.values_matching(state=CallState.OPEN)],
            [1, 2])

        self.assertEqual(
            [x.id for x in c.values_matching(state=CallState.UNOPENED)],
            [3])

        self.assertEqual(
            [x.id for x in c.values_matching(state=CallState.CLOSED)],
            [4])

        self.assertEqual(
            [x.id for x in c.values_matching(queue_id=11)],
            [1])

        self.assertEqual(
            [x.id for x in c.values_matching(queue_id=12)],
            [2])

        self.assertEqual(
            [x.id for x in c.values_matching(queue_id=13)],
            [3, 4])

        self.assertEqual(
            [x.id for x in c.values_matching(queue_id=(11, 12))],
            [1, 2])

        cc = c.subset_separate()
        self.assertEqual(len(cc), 0)
        cc = c.subset_separate(separate=False)
        self.assertEqual(len(cc), 4)

        c[3] = c[3]._replace(separate=True)

        cc = c.subset_separate()
        self.assertEqual(len(cc), 1)
        self.assertEqual(list(cc.keys()), [3])
        cc = c.subset_separate(separate=False)
        self.assertEqual(len(cc), 3)
        self.assertEqual(list(cc.keys()), [1, 2, 4])

    def test_email_collection(self):
        c = EmailCollection()

        c[1] = null_tuple(Email)._replace(address='a@b', primary=False)

        with self.assertRaisesRegex(UserError, 'There is no primary'):
            c.validate()

        c[2] = null_tuple(Email)._replace(address='c@d', primary=True)

        c.validate()

        c[3] = null_tuple(Email)._replace(address='e@f', primary=True)

        with self.assertRaisesRegex(UserError, 'more than one primary'):
            c.validate()

        c[3] = null_tuple(Email)._replace(address='a@b', primary=False)

        with self.assertRaisesRegex(UserError, 'appears more than once'):
            c.validate()

        c[3] = null_tuple(Email)._replace(
            address='A B <a.b@c.d>', primary=False)
        with self.assertRaisesRegex(UserError, 'does not appear to be valid'):
            c.validate()

    def test_call_preamble_collection(self):
        c = CallPreambleCollection()

        c[101] = null_tuple(CallPreamble)._replace(id=101, type=1)
        c[102] = null_tuple(CallPreamble)._replace(id=102, type=2)

        v = c.get_type(1)
        self.assertIsInstance(v, CallPreamble)
        self.assertEqual(v.id, 101)

        with self.assertRaises(NoSuchValue):
            c.get_type(999)

        v = c.get_type(2, default=None)
        self.assertIsInstance(v, CallPreamble)
        self.assertEqual(v.id, 102)

        v = c.get_type(999, default=None)
        self.assertIsNone(v)

    def test_member_collection(self):
        c = MemberCollection()

        c[101] = null_tuple(Member)._replace(
            id=101, person_id=9001, pi=False, person_name='Person One')

        with self.assertRaises(NoSuchValue):
            c.get_pi()

        self.assertIsNone(c.get_pi(default=None))
        self.assertIsNone(c.get_reviewer(default=None))

        c[102] = null_tuple(Member)._replace(
            id=102, person_id=9002, pi=True, person_name='Person Two')

        c[103] = null_tuple(Member)._replace(
            id=103, person_id=9003, pi=False, person_name='Person Three',
            reviewer=True)

        result = c.get_pi()
        self.assertEqual(result.person_id, 9002)

        result = c.get_reviewer()
        self.assertEqual(result.person_id, 9003)

        result = c.get_person(9003)
        self.assertEqual(result.id, 103)

        # hedwig.view.auth.for_proposal relies on this exception being
        # raised when the current user isn't a member of the proposal.
        with self.assertRaises(NoSuchValue):
            c.get_person(999999)

        self.assertTrue(c.has_person(9001))
        self.assertFalse(c.has_person(999999))

        # Test validation.
        with self.assertRaisesRegex(UserError, 'no specified editors'):
            c.validate(9001)

        c[101] = c[101]._replace(editor=True)

        c[104] = null_tuple(Member)._replace(
            id=104, person_id=9004, pi=True, person_name='Person Four')

        with self.assertRaisesRegex(UserError, 'more than one PI'):
            c.validate(9001)

        c[104] = c[104]._replace(pi=False, reviewer=True)

        with self.assertRaisesRegex(UserError, 'more than one reviewer'):
            c.validate(9001)

        del c[104]
        c.validate(9001)

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

        mapped = rc.map_values(lambda x: x.upper())

        self.assertIsInstance(mapped, ResultCollection)
        self.assertEqual(list(mapped.keys()), [0, 1])
        self.assertEqual(mapped[0], 'TEST RESULT')
        self.assertEqual(mapped[1], 'ANOTHER RESULT')

        rc[2] = 'yet another result'

        mapped = rc.map_values(
            (lambda x: x.title()),
            filter_value=(lambda x: not x.startswith('another')))

        self.assertIsInstance(mapped, ResultCollection)
        self.assertEqual(list(mapped.keys()), [0, 2])
        self.assertEqual(mapped[0], 'Test Result')
        self.assertEqual(mapped[2], 'Yet Another Result')

        mapped = rc.map_values(
            (lambda x: x.rjust(20)),
            filter_key=(lambda x: x > 0))

        self.assertIsInstance(mapped, ResultCollection)
        self.assertEqual(list(mapped.keys()), [1, 2])
        self.assertEqual(mapped[1], '      another result')
        self.assertEqual(mapped[2], '  yet another result')

        mapped = rc.map_values(filter_value=(lambda x: x.startswith('test')))

        self.assertIsInstance(mapped, ResultCollection)
        self.assertEqual(list(mapped.keys()), [0])
        self.assertEqual(mapped[0], 'test result')

    def test_ordered_result_collection(self):
        class OrderedResultCollection(ResultCollection, CollectionOrdered):
            pass

        SortOrdered = namedtuple('SortOrdered', ('id', 'sort_order'))

        rc = OrderedResultCollection()
        rc[1] = SortOrdered(1, 1)
        rc[2] = SortOrdered(2, None)
        rc[3] = SortOrdered(3, 2)
        rc[4] = SortOrdered(4, None)
        rc[5] = SortOrdered(5, 0)

        self.assertEqual(rc.values_in_sorted_order(), [
            SortOrdered(5, 0),
            SortOrdered(1, 1),
            SortOrdered(3, 2),
            SortOrdered(2, None),
            SortOrdered(4, None),
        ])

        rc.ensure_sort_order()

        self.assertEqual(list(rc.values()), [
            SortOrdered(1, 1),
            SortOrdered(2, 3),
            SortOrdered(3, 2),
            SortOrdered(4, 4),
            SortOrdered(5, 0),
        ])

        self.assertEqual(rc.values_in_sorted_order(), [
            SortOrdered(5, 0),
            SortOrdered(1, 1),
            SortOrdered(3, 2),
            SortOrdered(2, 3),
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

        self.assertEqual(
            [x.person_id for x in c.values_by_role(BaseReviewerRole.EXTERNAL)],
            [2002])

        self.assertFalse(c.has_role(BaseReviewerRole.FEEDBACK))

        self.assertTrue(c.has_role(BaseReviewerRole.EXTERNAL))

        self.assertEqual([x.role for x in c.values_by_person_id(2001)],
                         [BaseReviewerRole.TECH])

        self.assertEqual([x.role for x in c.values_by_person_id(2002)],
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

        for (n, r) in enumerate(rs, 100):
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

        for (n, r) in enumerate(rs, 200):
            c[n] = null_tuple(Reviewer)._replace(
                review_state=ReviewState.DONE, **r)

        self.assertEqual(c.get_overall_rating(rwf_exc_unweighted,
                                              with_std_dev=False), 55)

        (rating, std_dev) = c.get_overall_rating(rwf_exc_unweighted,
                                                 with_std_dev=True)
        self.assertEqual(rating, 55.0)
        self.assertAlmostEqual(std_dev, 25.981, places=3)

    def test_review_deadline_collection(self):
        # Test validation.
        c = ReviewDeadlineCollection()

        c.validate(BaseReviewerRole)

        c[1] = null_tuple(ReviewDeadline)._replace(role=999999)

        with self.assertRaisesRegex(UserError, 'invalid role'):
            c.validate(BaseReviewerRole)

        c[1] = null_tuple(ReviewDeadline)._replace(
            role=BaseReviewerRole.CTTEE_PRIMARY)
        c[2] = null_tuple(ReviewDeadline)._replace(
            role=BaseReviewerRole.CTTEE_PRIMARY)

        with self.assertRaisesRegex(UserError, 'Multiple entries for role'):
            c.validate(BaseReviewerRole)

        c[2] = null_tuple(ReviewDeadline)._replace(
            role=BaseReviewerRole.CTTEE_SECONDARY)

        c.validate(BaseReviewerRole)

        # Test get_role method.
        c = ReviewDeadlineCollection((
            (1, null_tuple(ReviewDeadline)._replace(id=1, role=1, call_id=1)),
            (2, null_tuple(ReviewDeadline)._replace(id=2, role=2, call_id=1)),
            (3, null_tuple(ReviewDeadline)._replace(id=3, role=1, call_id=2)),
            (4, null_tuple(ReviewDeadline)._replace(id=4, role=2, call_id=2)),
        ))

        self.assertEqual(c.get_role(1).id, 1)
        self.assertEqual(c.get_role(2).id, 2)
        self.assertEqual(c.get_role(1, call_id=1).id, 1)
        self.assertEqual(c.get_role(2, call_id=1).id, 2)
        self.assertEqual(c.get_role(1, call_id=2).id, 3)
        self.assertEqual(c.get_role(2, call_id=2).id, 4)

        self.assertEqual(c.get_role(3, default="my default"), "my default")
        with self.assertRaises(NoSuchValue):
            c.get_role(3)

    def test_site_group_member_collection(self):
        c = SiteGroupMemberCollection()

        c[101] = null_tuple(SiteGroupMember)._replace(
            id=101, site_group_type=SiteGroupType.PROFILE_VIEWER)
        c[102] = null_tuple(SiteGroupMember)._replace(
            id=102, site_group_type=SiteGroupType.PROFILE_VIEWER)

        self.assertEqual(
            sorted([x.id for x in c.values_by_site_group_type(
                SiteGroupType.PROFILE_VIEWER)]),
            [101, 102])

        self.assertEqual(
            sorted([x.id for x in c.values_by_site_group_type(999)]),
            [])

        self.assertTrue(c.has_entry(site_group_type=SiteGroupType.PROFILE_VIEWER))
        self.assertFalse(c.has_entry(site_group_type=999))

    def test_request_collection(self):
        c = RequestCollection()

        c[1] = null_tuple(RequestPropPDF)._replace(
            id=1, state=RequestState.NEW)
        c[2] = null_tuple(RequestPropPDF)._replace(
            id=2, state=RequestState.PROCESSING)
        c[3] = null_tuple(RequestPropPDF)._replace(
            id=3, state=RequestState.ERROR)
        c[4] = null_tuple(RequestPropPDF)._replace(
            id=4, state=RequestState.EXPIRED)

        cc = c.subset_by_state(RequestState.NEW)
        self.assertEqual([x for x in cc.keys()], [1])
        self.assertEqual([x.id for x in cc.values()], [1])

        cc = c.subset_by_state(RequestState.pre_ready_states())
        self.assertEqual([x for x in cc.keys()], [1, 2])
        self.assertEqual([x.id for x in cc.values()], [1, 2])

    def test_prev_proposal_collection(self):
        c = PrevProposalCollection()

        c[1] = null_tuple(PrevProposal)._replace(id=1, continuation=False)
        c[2] = null_tuple(PrevProposal)._replace(id=2, continuation=False)

        with self.assertRaises(NoSuchValue):
            c.get_continuation()

        self.assertIsNone(c.get_continuation(default=None))

        c[3] = null_tuple(PrevProposal)._replace(id=3, continuation=True)

        pp = c.get_continuation()

        self.assertIsInstance(pp, PrevProposal)
        self.assertEqual(pp.id, 3)

        c[4] = null_tuple(PrevProposal)._replace(id=4, continuation=True)

        with self.assertRaises(MultipleRecords):
            c.get_continuation()
