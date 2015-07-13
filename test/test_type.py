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

from collections import namedtuple
from unittest import TestCase

from hedwig.error import MultipleRecords, NoSuchRecord
from hedwig.type import OrderedResultCollection, ResultCollection, \
    ProposalState


class TypeTestCase(TestCase):
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
