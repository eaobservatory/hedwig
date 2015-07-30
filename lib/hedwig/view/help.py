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

from collections import namedtuple, OrderedDict
import os.path
import re

from ..web.format import format_text_rst
from ..web.util import HTTPError, HTTPNotFound


valid_page_name = re.compile('^([-_a-z0-9]+)$')


TOCEntry = namedtuple('TOCEntry', ('mtime', 'title'))


def prepare_help_page(doc_root, page_name, toc_cache):
    """
    Prepare template context information for viewing a help page.

    The toc_cache argument is a dictionary in which we can store
    information about other pages for use in generating tables
    of contents.
    """

    if page_name is None:
        file_name = 'index'

    else:
        m = valid_page_name.match(page_name)

        if not m:
            raise HTTPError('Invalid help page name.')

        file_name = m.group(1)

    path_name = os.path.join(doc_root, file_name + '.rst')

    if not os.path.exists(path_name):
        raise HTTPNotFound('Help page  not found.')

    with open(os.path.join(path_name)) as f:
        text = f.read()

    (body, title, toc) = format_text_rst(text, extract_title_toc=True,
                                         start_heading=2)

    toc_entries = OrderedDict()

    for toc_entry in toc:
        path_name = os.path.join(doc_root, toc_entry + '.rst')
        if not os.path.exists(path_name):
            continue

        mtime = os.path.getmtime(path_name)

        if toc_entry not in toc_cache or toc_cache[toc_entry].mtime < mtime:
            with open(path_name) as f:
                # Assume that the first line of the file is the title.  This
                # should be more efficient than parsing the whole file as RST.
                toc_entry_title = f.readline().strip()

            toc_cache[toc_entry] = TOCEntry(mtime, toc_entry_title)

        else:
            toc_entry_title = toc_cache[toc_entry].title

        toc_entries[toc_entry] = toc_entry_title

    return {
        'title': title,
        'help_text': body,
        'toc': toc_entries,
    }
