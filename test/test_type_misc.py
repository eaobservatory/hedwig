# Copyright (C) 2016 East Asian Observatory
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

from unittest import TestCase

from hedwig.type.misc import SectionedList, SectionedListSection


class MiscTypeTestCase(TestCase):
    def test_sectioned_list(self):
        # Construct empty list.
        sl = SectionedList()

        self.assertIsInstance(sl, SectionedList)
        self.assertEqual(len(sl), 0)
        self.assertEqual(list(sl), [])
        self.assertEqual(sl.list_sections(), [])
        self.assertEqual(sl.list_sections(include_empty=True), [None])
        self.assertEqual(sl.get_section(None), [])
        self.assertEqual(sl.get_section_name(None), None)
        with self.assertRaises(KeyError):
            sl.get_section('alpha')
        with self.assertRaises(KeyError):
            sl.get_section_name('alpha')
        self.assertEqual(list(sl.by_section()), [])
        self.assertEqual(list(sl.by_section(include_empty=True)), [
            SectionedListSection(None, None, [])])

        # Add items to default section.
        sl.append('x')
        self.assertEqual(len(sl), 1)
        self.assertEqual(list(sl), ['x'])
        self.assertEqual(sl.list_sections(), [None])
        self.assertEqual(sl.get_section(None), ['x'])
        self.assertEqual(list(sl.by_section()), [
            SectionedListSection(None, None, ['x'])])

        sl.extend(['y', 'z'])
        self.assertEqual(len(sl), 3)
        self.assertEqual(list(sl), ['x', 'y', 'z'])
        self.assertEqual(sl.get_section(None), ['x', 'y', 'z'])
        self.assertEqual(list(sl.by_section()), [
            SectionedListSection(None, None, ['x', 'y', 'z'])])

        # Add items to more sections.
        sl.append('a', section='alpha', section_name='Alphanumeric')
        sl.extend(['1', '2', '3'], section='num', section_name='Numbers')

        self.assertEqual(len(sl), 7)
        self.assertEqual(list(sl), ['x', 'y', 'z', 'a', '1', '2', '3'])
        self.assertEqual(sl.list_sections(), [None, 'alpha', 'num'])

        self.assertEqual(sl.get_section(None), ['x', 'y', 'z'])
        self.assertEqual(sl.get_section('alpha'), ['a'])
        self.assertEqual(sl.get_section('num'), ['1', '2', '3'])

        self.assertEqual(sl.get_section_name('alpha'), 'Alphanumeric')
        self.assertEqual(sl.get_section_name('num'), 'Numbers')

        self.assertEqual(list(sl.by_section()), [
            SectionedListSection(None, None, ['x', 'y', 'z']),
            SectionedListSection('alpha', 'Alphanumeric', ['a']),
            SectionedListSection('num', 'Numbers', ['1', '2', '3']),
        ])

        # Try indexing operations.
        self.assertEqual(sl[0], 'x')
        self.assertEqual(sl[1], 'y')
        self.assertEqual(sl[2], 'z')
        self.assertEqual(sl[3], 'a')
        self.assertEqual(sl[4], '1')
        self.assertEqual(sl[5], '2')
        self.assertEqual(sl[6], '3')
        self.assertEqual(sl[-1], '3')
        self.assertEqual(sl[-2], '2')
        self.assertEqual(sl[-3], '1')
        self.assertEqual(sl[-4], 'a')
        self.assertEqual(sl[-5], 'z')
        self.assertEqual(sl[-6], 'y')
        self.assertEqual(sl[-7], 'x')

        with self.assertRaises(IndexError):
            sl[7]

        with self.assertRaises(IndexError):
            sl[-8]

        sl[1] = 'yyy'
        sl[3] = 'aaa'
        sl[5] = '222'

        self.assertEqual(list(sl), ['x', 'yyy', 'z', 'aaa', '1', '222', '3'])

        del sl[5]
        del sl[3]
        del sl[1]

        self.assertEqual(list(sl), ['x', 'z', '1', '3'])
        self.assertEqual(len(sl), 4)
        self.assertEqual(sl.list_sections(), [None, 'num'])
        self.assertEqual(sl.list_sections(include_empty=True),
                         [None, 'alpha', 'num'])

        # Try section manipulation methods.
        sl.add_section('new_1', 'New section one')
        sl.add_section('new_2', 'New section two')
        self.assertEqual(sl.list_sections(include_empty=True),
                         [None, 'alpha', 'num', 'new_1', 'new_2'])

        sl.append('t', section='new_2')
        self.assertEqual(sl.list_sections(), [None, 'num', 'new_2'])
        sl.extend(['u', 'v'], section='new_1')
        self.assertEqual(sl.list_sections(), [None, 'num', 'new_1', 'new_2'])

        self.assertEqual(list(sl), ['x', 'z', '1', '3', 'u', 'v', 't'])

        with self.assertRaises(KeyError):
            sl.delete_section('new_3')

        sl.delete_section('num')
        sl.delete_section(None)
        self.assertEqual(sl.list_sections(), ['new_1', 'new_2'])
        self.assertEqual(list(sl), ['u', 'v', 't'])

        self.assertEqual(sl.list_sections(include_empty=True),
                         [None, 'alpha', 'new_1', 'new_2'])

        sl.append('xxx')
        self.assertEqual(list(sl), ['xxx', 'u', 'v', 't'])

        self.assertEqual(list(sl.by_section()), [
            SectionedListSection(None, None, ['xxx']),
            SectionedListSection('new_1', 'New section one', ['u', 'v']),
            SectionedListSection('new_2', 'New section two', ['t']),
        ])
