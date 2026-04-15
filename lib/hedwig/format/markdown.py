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

from markdown import Markdown
from markdown.treeprocessors import Treeprocessor
from markdown.extensions import Extension
from markdown.extensions.smarty import SmartyExtension


class HeaderShift(Treeprocessor):
    def __init__(self, levels, *args):
        super(HeaderShift, self).__init__(*args)
        self.mapping = {
            'h{}'.format(x): 'h{}'.format(max(min(x + levels, 6), 1))
            for x in range(1, 7)}

    def run(self, root):
        for el in root.iter():
            replacement = self.mapping.get(el.tag)
            if replacement is not None:
                el.tag = replacement


class HedwigExtension(Extension):
    def __init__(self, start_heading):
        super(HedwigExtension, self).__init__()
        self.start_heading = start_heading

    def extendMarkdown(self, md):
        # Shift header levels in order to obtain the desired starting level.
        md.treeprocessors.register(
            HeaderShift(self.start_heading - 1, md),
            'hedwig_hdr_shift',
            50)

        # These are to prevent HTML being passed through.
        # From the Markdown documentation regarding deprecation of safe_mode.
        # (Note: Markdown documentation says to sanitize output if input
        # is untrusted, so configure this format with allow_user=False.)
        md.preprocessors.deregister('html_block')
        md.inlinePatterns.deregister('html')


def markdown_to_html(text, start_heading):
    """
    Convert Markdown to HTML.
    """

    md = Markdown(extensions=[
        HedwigExtension(start_heading=start_heading),
        SmartyExtension(),
    ])

    html = md.convert(text)

    return html
