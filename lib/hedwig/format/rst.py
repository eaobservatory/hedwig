# Copyright (C) 2015-2016 East Asian Observatory
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
import sys
from threading import Lock

from docutils import nodes
from docutils.core import publish_parts
from docutils.parsers.rst import Directive, roles, directives
from docutils.readers.standalone import Reader
from docutils.transforms.frontmatter import DocTitle

from ..config import get_home
from ..web.util import HTTPError


rst_publish_lock = Lock()

named_link = re.compile(r'^(.*) +<(.*)>$')
graph_path = re.compile(r'^graph\/([-_a-z0-9]+)\.dot$')


def rst_to_html(text, extract_title, start_heading):
    """
    Convert RST to HTML.

    :param extract_title: whether to extract a document title
    :param start_heading: initial heading level

    :return: a tuple containing the body, title and a list of TOC items
    """

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
    """
    RST reader sub-class which replaces the `DocTitle` transform with
    our `DocTitleNoSubtitle` class.
    """

    def get_transforms(self):
        """
        Returns the standard `Reader` transforms with `DocTitle` replaced.
        """

        transforms = list(Reader.get_transforms(self))
        transforms[transforms.index(DocTitle)] = DocTitleNoSubtitle
        return transforms


class DocTitleNoSubtitle(DocTitle):
    """
    Sub-class of the `DocTitle` transform which does not process a
    sub-title.
    """

    def promote_subtitle(self, *args, **kwargs):
        """Does nothing."""

        pass


class HedwigTocTree(Directive):
    """
    Handler for the `toctree` directive.

    This allows the use of TOC trees in the Hedwig online help system.
    """

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


class HedwigGraphviz(Directive):
    """
    Handler for the `graphviz` directive.

    This only supports references to external `.dot` files in a graph
    directory, e.g.::

        .. graphviz:: graph/a_graph.dot
    """

    required_arguments = 1

    def run(self):
        m = graph_path.match(self.arguments[0])

        if not m:
            raise self.error('Did not understand reference to Graphviz file.')

        return [nodes.image(uri='graph/{}'.format(m.group(1)))]


def doc_reference_role(role, rawtext, text, lineno, inliner,
                       options={}, context=[]):
    """
    Handler for the `:doc:` reference role.

    This allows the Sphinx cross-reference syntax to be used in document
    served though Hedwig's online help system.
    """

    m = named_link.match(text)

    if m:
        (text, url) = m.groups()
    else:
        url = text

    return [nodes.reference(rawtext, text, refuri=url, **options)], []


# Do not register our Sphinx-emulation directives/roles if the module
# is being imported by Sphinx to build the software documentation.
if 'sphinx' not in sys.modules:
    directives.register_directive('toctree', HedwigTocTree)
    directives.register_directive('graphviz', HedwigGraphviz)
    roles.register_local_role('doc', doc_reference_role)
