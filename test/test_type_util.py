# Copyright (C) 2016-2017 East Asian Observatory
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

from hedwig.type.util import with_can_edit, with_can_view, with_can_view_edit

from .compat import TestCase


class TypeUtilTestCase(TestCase):
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
