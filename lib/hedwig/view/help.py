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
from ..web.util import HTTPError, HTTPNotFound, url_for


valid_page_name = re.compile('^([-_a-z0-9]+)$')

NavLink = namedtuple(
    'NavLink', ('up', 'up_title', 'prev', 'prev_title', 'next', 'next_title'))

TOCEntry = namedtuple('TOCEntry', ('mtime', 'title'))

TreeEntry = namedtuple('TreeEntry', ('mtime', 'title', 'toc'))


def prepare_help_page(doc_root, page_name, toc_cache):
    """
    Prepare template context information for viewing a help page.

    The toc_cache argument is a dictionary in which we can store
    information about other pages for use in generating tables
    of contents.
    """

    title_cache = toc_cache.get('_title')
    if title_cache is None:
        title_cache = {}
        toc_cache['_title'] = title_cache

    tree_cache = toc_cache.get('_tree')
    if tree_cache is None:
        tree_cache = {}
        toc_cache['_tree'] = tree_cache

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

    (body, title, toc) = _read_rst_file(doc_root, path_name)

    toc_entries = OrderedDict()

    for toc_entry in toc:
        toc_entry_title = _get_page_title(doc_root, toc_entry, title_cache)

        if toc_entry_title is None:
            continue

        toc_entries[toc_entry] = toc_entry_title

    if page_name is None:
        nav_link = NavLink(url_for('.help_index'), 'Help',
                           None, None, None, None)

    else:
        nav_link = _find_nav_link(doc_root, page_name, 'index',
                                  title_cache, tree_cache)

    return {
        'title': title,
        'help_text': body,
        'toc': toc_entries,
        'nav_link': nav_link,
    }


def _read_rst_file(doc_root, path_name):
    """
    Read a file and return the body, title and toc.
    """

    with open(os.path.join(path_name)) as f:
        text = f.read()

    return format_text_rst(text, extract_title_toc=True, start_heading=2)


def _get_page_title(doc_root, page_name, title_cache):
    """
    Get the title of a page, using the cache if possible.
    """

    path_name = os.path.join(doc_root, page_name + '.rst')

    if not os.path.exists(path_name):
        return None

    mtime = os.path.getmtime(path_name)

    toc_entry = title_cache.get(page_name)

    if (toc_entry is not None) and not (toc_entry.mtime < mtime):
        return toc_entry.title

    with open(path_name) as f:
        # Assume that the first line of the file is the title.  This
        # should be more efficient than parsing the whole file as RST.
        toc_entry_title = f.readline().strip()

    title_cache[page_name] = TOCEntry(mtime, toc_entry_title)

    return toc_entry_title


def _find_nav_link(doc_root, target_name, page_name, title_cache, tree_cache):
    """
    Find navigation links for the given page.

    This is called recursively, starting with page_name='index'.
    """

    path_name = os.path.join(doc_root, page_name + '.rst')

    if not os.path.exists(path_name):
        return None

    mtime = os.path.getmtime(path_name)

    tree_entry = tree_cache.get(page_name)

    if tree_entry is None or tree_entry.mtime < mtime:
        (body, title, toc) = _read_rst_file(doc_root, path_name)
        sub_tree_cache = OrderedDict(((x, None) for x in toc))
        tree_cache[page_name] = TreeEntry(mtime, title, sub_tree_cache)

    else:
        title = tree_entry.title
        sub_tree_cache = tree_entry.toc
        toc = list(sub_tree_cache.keys())

    try:
        toc_i = toc.index(target_name)
    except ValueError:
        toc_i = None

    if toc_i is not None:
        # The target page was in this TOC.  Create the NavLink object.
        nl = NavLink(('./' if page_name == 'index' else page_name),
                     title, None, None, None, None)

        if toc_i > 0:
            prev = toc[toc_i - 1]
            prev_title = _get_page_title(doc_root, prev, title_cache)
            if prev_title is not None:
                nl = nl._replace(prev=prev, prev_title=prev_title)

        if toc_i < (len(toc) - 1):
            next_ = toc[toc_i + 1]
            next_title = _get_page_title(doc_root, next_, title_cache)
            if next_title is not None:
                nl = nl._replace(next=next_, next_title=next_title)

        return nl

    else:
        # Recurse through the TOC entries looking for a match.
        for toc_entry in toc:
            ans = _find_nav_link(doc_root, target_name, toc_entry,
                                 title_cache, sub_tree_cache)

            if ans is not None:
                return ans

    # If we didn't find anything, return None.
    return None
