# Copyright (C) 2026 East Asian Observatory
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

from hedwig.format.rst import rst_to_html

from .compat import TestCase


class MarkdownFormatTest(TestCase):
    def test_format_rst(self):
        text = (
            'AAA\n==='
            '\n\nBBB\n---'
            '\n\nPara'
            '\n\n.. toctree::'
            '\n    page1'
            '\n    page2')

        result = rst_to_html(text, False, 3)

        self.assertIsInstance(result, tuple)
        self.assertRegex(result[0], r'<h3>AAA</h3>')
        self.assertRegex(result[0], r'<h4>BBB</h4>')
        self.assertEqual(result[1], '')
        self.assertEqual(result[2], ['page1', 'page2'])

        result = rst_to_html(text, True, 2)

        self.assertIsInstance(result, tuple)
        self.assertRegex(result[0], r'<h2>BBB</h2>')
        self.assertEqual(result[1], 'AAA')
        self.assertEqual(result[2], ['page1', 'page2'])
