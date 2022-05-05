# Copyright (C) 2015-2022 East Asian Observatory
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

from hedwig.type.enum import FormatType
from hedwig.type.simple import ProposalText
from hedwig.web.format import format_text, \
    format_text_plain, format_text_plain_inline
from hedwig.web.util import HTTPError
from hedwig.type.util import null_tuple

from .compat import TestCase


class TextFormatTest(TestCase):
    def test_format(self):
        self.assertEqual(format_text('text'), '<p>text</p>')
        self.assertEqual(format_text('text', FormatType.PLAIN), '<p>text</p>')

        with self.assertRaises(HTTPError):
            format_text('text', 999)

        with self.assertRaises(HTTPError):
            format_text(null_tuple(ProposalText)._replace(
                text='text', format=999))

        self.assertEqual(
            format_text(null_tuple(ProposalText)._replace(
                text='hello', format=FormatType.PLAIN)),
            '<p>hello</p>')

        # Test email-style formatting.
        self.assertEqual(
            format_text(null_tuple(ProposalText)._replace(
                text='a\nb\n\nc\nd', format=FormatType.PLAIN),
                as_email=True),
            '<pre>a b\n\nc d</pre>')

        self.assertTrue(
            format_text(null_tuple(ProposalText)._replace(
                text='rst', format=FormatType.RST),
                as_email=True).startswith(
                    '<p class="warning">Format is not plain text.</p>'))

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

    def test_format_plain_inline(self):
        # Empty input should give no output.
        self.assertEqual(format_text_plain_inline(''), '')

        # Check escaping of characters.
        self.assertEqual(format_text_plain_inline('<i>'), '&lt;i&gt;')
        self.assertEqual(format_text_plain_inline('&nbsp;'), '&amp;nbsp;')

        # Check processing of line feeds.
        self.assertEqual(format_text_plain_inline('a\nb'), 'a<br />b')
        self.assertEqual(format_text_plain_inline('a\r\nb'), 'a<br />b')
        self.assertEqual(format_text_plain_inline('\na\n\nb\n'), 'a<br />b')
        self.assertEqual(format_text_plain_inline('a\r\n\r\nb'), 'a<br />b')
