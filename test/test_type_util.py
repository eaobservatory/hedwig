# Copyright (C) 2016-2026 East Asian Observatory
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

from hedwig.error import Error
from hedwig.type.collection import ResultCollection
from hedwig.type.enum import SyncOperation
from hedwig.type.util import compare_collections, insert_after, \
    with_can_edit, with_can_view, \
    with_can_view_edit, with_can_view_edit_rating, \
    with_proposals, with_sync_operation

from .compat import TestCase


class TypeUtilTestCase(TestCase):
    def test_insert_after(self):
        d = OrderedDict((
            (1, 'a'),
            (2, 'b'),
            (4, 'd'),
            (5, 'e'),
        ))

        insert_after(d, 2, 3, 'c')

        self.assertEqual(list(d.items()), [
            (1, 'a'),
            (2, 'b'),
            (3, 'c'),
            (4, 'd'),
            (5, 'e'),
        ])

        with self.assertRaises(KeyError):
            insert_after(d, 2, 3, 'c')

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

    def test_with_can_view(self):
        TestTuple = namedtuple('TestTuple', ('x', 'y'))

        t = TestTuple(1, 2)

        t_t = with_can_view(t, True)
        t_f = with_can_view(t, False)

        self.assertEqual(t_t.can_view, True)
        self.assertEqual(t_f.can_view, False)

        for t_x in (t_t, t_f):
            self.assertEqual(type(t_x).__name__, 'TestTupleWithCV')
            self.assertEqual(t_x._fields, ('x', 'y', 'can_view'))
            self.assertEqual(t_x.x, 1)
            self.assertEqual(t_x.y, 2)

    def test_with_can_view_edit(self):
        TestTuple = namedtuple('TestTuple', ('x', 'y'))

        t = TestTuple(1, 2)

        t_t = with_can_view_edit(t, True, False)
        t_f = with_can_view_edit(t, False, True)

        self.assertEqual(t_t.can_view, True)
        self.assertEqual(t_f.can_view, False)

        self.assertEqual(t_t.can_edit, False)
        self.assertEqual(t_f.can_edit, True)

        for t_x in (t_t, t_f):
            self.assertEqual(type(t_x).__name__, 'TestTupleWithCVE')
            self.assertEqual(t_x._fields, ('x', 'y', 'can_view', 'can_edit'))
            self.assertEqual(t_x.x, 1)
            self.assertEqual(t_x.y, 2)

    def test_with_can_view_edit_rating(self):
        TestTuple = namedtuple('TestTuple', ('x', 'y'))

        t = TestTuple(1, 2)

        t_1 = with_can_view_edit_rating(t, True, True, False)
        t_2 = with_can_view_edit_rating(t, False, False, True)

        self.assertEqual(t_1.can_view, True)
        self.assertEqual(t_2.can_view, False)

        self.assertEqual(t_1.can_edit, True)
        self.assertEqual(t_2.can_edit, False)

        self.assertEqual(t_1.can_view_rating, False)
        self.assertEqual(t_2.can_view_rating, True)

        for t_x in (t_1, t_2):
            self.assertEqual(type(t_x).__name__, 'TestTupleWithCVER')
            self.assertEqual(t_x._fields, (
                'x', 'y', 'can_view', 'can_edit', 'can_view_rating'))
            self.assertEqual(t_x.x, 1)
            self.assertEqual(t_x.y, 2)

    def test_with_proposals(self):
        TestTuple = namedtuple('TestTuple', ('x', 'y'))
        TestProposal = namedtuple('TestProposal', ('id',))

        t = TestTuple(1, 2)

        t_1 = with_proposals(t)

        self.assertIsInstance(t_1.proposals, list)
        self.assertEqual(len(t_1.proposals), 0)

        t_2 = with_proposals(t, TestProposal(999))

        self.assertIsInstance(t_2.proposals, list)
        self.assertEqual(len(t_2.proposals), 1)
        self.assertEqual(t_2.proposals[0].id, 999)

        for t_x in (t_1, t_2):
            self.assertEqual(t_x.x, 1)
            self.assertEqual(t_x.y, 2)

    def test_with_sync_operation(self):
        TestTuple = namedtuple('TestTuple', ('x', 'y'))

        t = TestTuple(1, 2)

        t_1 = with_sync_operation(t, SyncOperation.DELETE)

        self.assertEqual(t_1.x, 1)
        self.assertEqual(t_1.y, 2)
        self.assertEqual(t_1.sync_operation, SyncOperation.DELETE)
        self.assertEqual(t_1.sync_update, ())

        t_2 = with_sync_operation(t, SyncOperation.INSERT, ('z', 'w'))

        self.assertEqual(t_2.x, 1)
        self.assertEqual(t_2.y, 2)
        self.assertEqual(t_2.sync_operation, SyncOperation.INSERT)
        self.assertEqual(t_2.sync_update, ('z', 'w'))

    def test_compare_collections(self):
        TestTuple = namedtuple('TestTuple', (
            'id', 'x', 'y', 'hidden'))
        TestTupleWithSO = namedtuple('TestTupleWithSO', (
            'id', 'x', 'y', 'hidden', 'sync_operation', 'sync_update'))

        original = ResultCollection((
            (11, TestTuple(11, 'a', 'A', False)),
            (12, TestTuple(12, 'b', 'B', False)),
            (13, TestTuple(13, 'c', 'C', False)),
        ))

        other = ResultCollection((
            (21, TestTuple(21, 'a', 'AA', False)),
            (22, TestTuple(22, 'c', 'C', False)),
            (23, TestTuple(23, 'd', 'D', False)),
        ))

        comparison = compare_collections(
            original, other,
            match_attrs=('x',),
            sort_attrs=('x',),
            update_attrs=('y',))

        self.assertIsInstance(comparison, ResultCollection)
        self.assertEqual(list(comparison.keys()), [11, 12, 13, 14])

        self.assertEqual(comparison[11], TestTupleWithSO(
            11, 'a', 'AA', False, SyncOperation.UPDATE, ('y',)))
        self.assertEqual(comparison[12], TestTupleWithSO(
            12, 'b', 'B', False, SyncOperation.DELETE, ()))
        self.assertEqual(comparison[13], TestTupleWithSO(
            13, 'c', 'C', False, SyncOperation.UNCHANGED, ()))
        self.assertEqual(comparison[14], TestTupleWithSO(
            None, 'd', 'D', False, SyncOperation.INSERT, ()))

        # Do the same again, but with "hide_deleted".
        with self.assertRaisesRegex(Error, 'hidden not among'):
            compare_collections(
                original, other,
                match_attrs=('x',),
                sort_attrs=('x',),
                update_attrs=('y',),
                hide_deleted=True)

        comparison = compare_collections(
            original, other,
            match_attrs=('x',),
            sort_attrs=('x',),
            update_attrs=('y', 'hidden'),
            hide_deleted=True)

        self.assertIsInstance(comparison, ResultCollection)
        self.assertEqual(list(comparison.keys()), [11, 12, 13, 14])

        self.assertEqual(comparison[11], TestTupleWithSO(
            11, 'a', 'AA', False, SyncOperation.UPDATE, ('y',)))
        self.assertEqual(comparison[12], TestTupleWithSO(
            12, 'b', 'B', True, SyncOperation.UPDATE, ('hidden',)))
        self.assertEqual(comparison[13], TestTupleWithSO(
            13, 'c', 'C', False, SyncOperation.UNCHANGED, ()))
        self.assertEqual(comparison[14], TestTupleWithSO(
            None, 'd', 'D', False, SyncOperation.INSERT, ()))

        # The same comparison again, but "b" is already hidden.
        original[12] = original[12]._replace(hidden=True)

        comparison = compare_collections(
            original, other,
            match_attrs=('x',),
            sort_attrs=('x',),
            update_attrs=('y', 'hidden'),
            hide_deleted=True)

        self.assertIsInstance(comparison, ResultCollection)
        self.assertEqual(list(comparison.keys()), [11, 12, 13, 14])

        self.assertEqual(comparison[11], TestTupleWithSO(
            11, 'a', 'AA', False, SyncOperation.UPDATE, ('y',)))
        self.assertEqual(comparison[12], TestTupleWithSO(
            12, 'b', 'B', True, SyncOperation.UNCHANGED, ()))
        self.assertEqual(comparison[13], TestTupleWithSO(
            13, 'c', 'C', False, SyncOperation.UNCHANGED, ()))
        self.assertEqual(comparison[14], TestTupleWithSO(
            None, 'd', 'D', False, SyncOperation.INSERT, ()))

        # Check that the multiple values exception is trapped
        # and re-raised correctly.
        with self.assertRaisesRegex(
                Error, r'Multiple matches found for key \(False,\) '
                'comparing collections'):
            compare_collections(
                original, other,
                match_attrs=('hidden',),
                sort_attrs=('x',),
                update_attrs=('y',))
