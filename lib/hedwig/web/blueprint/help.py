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

import os.path
import re

from collections import namedtuple, OrderedDict

from flask import Blueprint, send_from_directory

from ...config import get_home
from ..format import format_text_rst
from ..util import HTTPError, HTTPNotFound, require_admin, templated


valid_page_name = re.compile('^([-_a-z0-9]+)$')


TOCEntry = namedtuple('TOCEntry', ('mtime', 'title'))


def create_help_blueprint():
    bp = Blueprint('help', __name__)

    user_doc_root = os.path.join(get_home(), 'doc', 'user')
    user_image_root = os.path.join(user_doc_root, 'image')
    user_toc_cache = {}

    admin_doc_root = os.path.join(get_home(), 'doc', 'admin')
    admin_image_root = os.path.join(user_doc_root, 'image')
    admin_toc_cache = {}

    @bp.route('/')
    @templated('help/index.html')
    def help_index():
        return {'title': 'Help'}

    @bp.route('/about')
    @templated('help/about.html')
    def help_about():
        return {'title': 'About this System'}

    @bp.route('/user/')
    @templated('help/help_page.html')
    def user_index():
        return prepare_help_page(user_doc_root, None, user_toc_cache)

    @bp.route('/user/<page_name>')
    @templated('help/help_page.html')
    def user_page(page_name):
        return prepare_help_page(user_doc_root, page_name, user_toc_cache)

    @bp.route('/user/image/<path:file_name>')
    def user_image(file_name):
        return send_from_directory(user_image_root, file_name)

    @bp.route('/admin/')
    @templated('help/help_page.html')
    @require_admin
    def admin_index():
        return prepare_help_page(admin_doc_root, None, admin_toc_cache)

    @bp.route('/admin/<page_name>')
    @templated('help/help_page.html')
    @require_admin
    def admin_page(page_name):
        return prepare_help_page(admin_doc_root, page_name, admin_toc_cache)

    @bp.route('/admin/image/<path:file_name>')
    @require_admin
    def admin_image(file_name):
        return send_from_directory(admin_image_root, file_name)

    return bp


def prepare_help_page(doc_root, page_name, toc_cache):
    """
    Prepare template context information for viewing a help page.
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
