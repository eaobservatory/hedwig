# Copyright (C) 2015-2025 East Asian Observatory
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

from hedwig.type.enum import FormatType, MessageFormatType
from hedwig.type.simple import Message, ProposalText
from hedwig.web.format import format_message_text, format_text, \
    format_text_plain, format_text_plain_inline, format_title_markup
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

    def test_format_message(self):
        with self.assertRaises(HTTPError):
            format_message_text(null_tuple(Message)._replace(
                    body='...', format=999))

        with self.assertRaises(HTTPError):
            format_message_text('...', format=999)

        self.assertEqual(
            format_message_text(null_tuple(Message)._replace(
                body='a\nb\n\nc\nd', format=MessageFormatType.PLAIN_FLOWED)),
            '<pre>a\nb\n\nc\nd</pre>')

        self.assertEqual(
            format_message_text(null_tuple(Message)._replace(
                body='a\nb\n\nc\nd', format=MessageFormatType.PLAIN)),
            '<p>a<br />b</p><p>c<br />d</p>')

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

    def test_format_title_markup(self):
        for (text, expect) in [[
                'Plain title with <b>unwanted</b> formatting',
                'Plain title with &lt;b&gt;unwanted&lt;/b&gt; formatting',
                ], [
                'Molecules <SUP>13</SUP>CO and H<SUB>2</SUB>O',
                'Molecules <sup>13</sup>CO and H<sub>2</sub>O',
                ], [
                'LaTeX for molecules ^{13}CO and H_2O',
                'LaTeX for molecules <sup>13</sup>CO and H<sub>2</sub>O',
                ], [
                'LaTeX with {\\sc small} and {\\bf bold} and {\\it italic} text',
                'LaTeX with <span class="smallcaps">small</span> and <b>bold</b> and <i>italic</i> text',
                ], [
                '\\textsc{text} \\textbf{command} \\textit{alternative}',
                '<span class="smallcaps">text</span> <b>command</b> <i>alternative</i>',
                ], [
                'H\,{\sc ii} region and cloud at 20 km s^{-1} velocity',
                'H <span class="smallcaps">ii</span> region and cloud at 20 km s<sup>-1</sup> velocity',
                ], [
                '<SUP>HTML</SUP> format mixed with LaTeX _{format}',
                '<sup>HTML</sup> format mixed with LaTeX <sub>format</sub>',
                ]]:
            self.assertEqual(format_title_markup(text), expect)
