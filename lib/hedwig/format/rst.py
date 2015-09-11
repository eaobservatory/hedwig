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

import re
from threading import Lock

from docutils import nodes
from docutils.core import publish_parts
from docutils.parsers.rst import Directive, roles, directives
from docutils.readers.standalone import Reader
from docutils.transforms.frontmatter import DocTitle

from ..config import get_home
from ..web.util import HTTPError


rst_publish_lock = Lock()


def rst_to_html(text, extract_title, start_heading):
    settings = {
        'file_insertion_enabled': False,
        'raw_enabled': False,
        '_disable_config': True,
        'input_encoding': 'UTF-8',
        'output_encoding': 'UTF-8',
        'initial_header_level': start_heading,
        'smart_quotes': True,
        'doctitle_xform': extract_title,
        'sectsubtitle_xform': False,
    }

    with rst_publish_lock:
        del HedwigTocTree.toc_items[:]

        parts = publish_parts(
            source=text,
            reader=HedwigDocReader(),
            writer_name='html',
            settings_overrides=settings)

        return (parts['body'], parts['title'], list(HedwigTocTree.toc_items))


class HedwigDocReader(Reader):
    def get_transforms(self):
        transforms = list(Reader.get_transforms(self))
        transforms[transforms.index(DocTitle)] = DocTitleNoSubtitle
        return transforms


class DocTitleNoSubtitle(DocTitle):
    def promote_subtitle(self, *args, **kwargs):
        pass


class HedwigTocTree(Directive):
    has_content = True
    option_spec = {
        'maxdepth': int,
    }

    toc_items = []

    def run(self):
        for line in self.content:
            line = line.strip()
            if line:
                self.toc_items.append(line)

        return []


directives.register_directive('toctree', HedwigTocTree)


named_link = re.compile('^(.*) +<(.*)>$')


def doc_reference_role(role, rawtext, text, lineno, inliner,
                       options={}, context=[]):
    m = named_link.match(text)

    if m:
        (text, url) = m.groups()
    else:
        url = text

    return [nodes.reference(rawtext, text, refuri=url, **options)], []


roles.register_local_role('doc', doc_reference_role)
