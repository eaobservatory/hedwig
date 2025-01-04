# Copyright (C) 2019-2025 East Asian Observatory
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

from hedwig.email.format import wrap_email_text, unwrap_email_text

from .compat import TestCase


class EmailFormatTestCase(TestCase):
    def test_wrap_email(self):
        self.assertEqual(
            wrap_email_text(''),
            '')

        self.assertEqual(
            wrap_email_text('a '),
            'a')

        self.assertEqual(
            wrap_email_text('a b\nc d\n\ne f\ng h'),
            'a b\nc d\n\ne f\ng h')

        self.assertEqual(
            wrap_email_text(
                '123456789 123456789 123456789 123456789 '
                '123456789 123456789 123456789 123456789 '
                '\n\n'
                '123456789 123456789 123456789 123456789 '
                '123456789 123456789 123456789 123456789 '),
            '123456789 123456789 123456789 123456789 '
            '123456789 123456789 123456789 \n'
            '123456789\n\n'
            '123456789 123456789 123456789 123456789 '
            '123456789 123456789 123456789 \n'
            '123456789')

    def test_text_unwrap(self):
        """Test the `unwrap_email_text` function."""

        self.assertEqual(
            unwrap_email_text('a \na \na\nb \nb \nb'),
            'a a a\nb b b')

        self.assertEqual(
            unwrap_email_text('a \na\nb \nb\nc \nc\nd \nd\n'),
            'a a\nb b\nc c\nd d')

        self.assertEqual(
            unwrap_email_text('a\nb \nb \nb \nb \nb \nb \nb\nc'),
            'a\nb b b b b b b\nc')
