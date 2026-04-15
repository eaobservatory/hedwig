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

from hedwig.format.markdown import markdown_to_html

from .compat import TestCase


class MarkdownFormatTest(TestCase):
    def test_format_markdown(self):
        # Test a heading and both types of HTML passthrough removal
        # plus application of "smarty" extension to quotes and em dash.
        self.assertRegex(
            markdown_to_html(
                '# Heading'
                '\n\n<blockquote>Q</blockquote>'
                '\n\nP<i>ar</i>a --- "graph"',
                start_heading=3),
            r'^<h3>Heading</h3>'
            r'\s*<p>&lt;blockquote&gt;Q&lt;/blockquote&gt;</p>'
            r'\s*<p>P&lt;i&gt;ar&lt;/i&gt;a &mdash; &ldquo;graph&rdquo;</p>'
            r'\s*$')

        # Test limits on range of heading levels.
        self.assertRegex(
            markdown_to_html('# Heading', start_heading=-10),
            r'<h1>Heading</h1>')

        self.assertRegex(
            markdown_to_html('# Heading', start_heading=10),
            r'<h6>Heading</h6>')

        # Test with multiple levels.
        self.assertRegex(
            markdown_to_html(
                '# H1'
                '\n\n## H2'
                '\n\n### H3',
                start_heading=5),
            r'<h5>H1</h5>'
            r'\s*<h6>H2</h6>'
            r'\s*<h6>H3</h6>')
