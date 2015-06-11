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

from unittest import TestCase

from insertnamehere.type import FormatType, ProposalText
from insertnamehere.web.format import format_text, format_text_plain
from insertnamehere.web.util import HTTPError


class TextFormatTest(TestCase):
    def test_format(self):
        self.assertEqual(format_text('text'), '<p>text</p>')
        self.assertEqual(format_text('text', FormatType.PLAIN), '<p>text</p>')

        with self.assertRaises(HTTPError):
            format_text('text', 999)

        with self.assertRaises(HTTPError):
            format_text(ProposalText('text', 999))

        self.assertEqual(format_text(ProposalText('hello', FormatType.PLAIN)),
                         '<p>hello</p>')

    def test_format_plain(self):
        # Empty input should give no output.
        self.assertEqual(format_text_plain(''), '')

        # Check escaping of characters.
        self.assertEqual(format_text_plain('<i>'), '<p>&lt;i&gt;</p>')
        self.assertEqual(format_text_plain('&nbsp;'), '<p>&amp;nbsp;</p>')

        # Check processing of line feeds.
        self.assertEqual(format_text_plain('a\nb'), '<p>a<br />b</p>')
        self.assertEqual(format_text_plain('a\r\nb'), '<p>a<br />b</p>')
        self.assertEqual(format_text_plain('a\n\nb'), '<p>a</p><p>b</p>')
        self.assertEqual(format_text_plain('a\r\n\r\nb'), '<p>a</p><p>b</p>')

        # Combined test.
        self.assertEqual(format_text_plain(
            '&ldquo;a\n<i>b</i>\n\nc\nd'),
            '<p>&amp;ldquo;a<br />&lt;i&gt;b&lt;/i&gt;</p><p>c<br />d</p>')
