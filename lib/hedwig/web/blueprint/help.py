# Copyright (C) 2015-2018 East Asian Observatory
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

from flask import Blueprint, send_from_directory

from ...config import get_home
from ...type.enum import FigureType
from ...view.help import HelpView
from ..util import send_file, templated


def create_help_blueprint(db):
    """
    Create Flask Blueprint for the online help system.
    """

    bp = Blueprint('help', __name__)
    view = HelpView()

    doc_root = os.path.join(get_home(), 'doc')

    about_doc_root = os.path.join(doc_root, 'about')

    user_doc_root = os.path.join(doc_root, 'user')
    user_image_root = os.path.join(user_doc_root, 'image')
    user_toc_cache = {}

    review_doc_root = os.path.join(doc_root, 'review')
    review_image_root = os.path.join(review_doc_root, 'image')
    review_toc_cache = {}

    admin_doc_root = os.path.join(doc_root, 'admin')
    admin_image_root = os.path.join(admin_doc_root, 'image')
    admin_toc_cache = {}

    @bp.route('/')
    @templated('help/index.html')
    def help_index():
        return view.help_home(db)

    @bp.route('/about')
    @templated('help/help_page.html')
    def help_about():
        return view.help_page(about_doc_root, None, {})

    @bp.route('/user/')
    @templated('help/help_page.html')
    def user_index():
        return view.help_page(user_doc_root, None, user_toc_cache)

    @bp.route('/user/<page_name>')
    @templated('help/help_page.html')
    def user_page(page_name):
        return view.help_page(user_doc_root, page_name, user_toc_cache)

    @bp.route('/user/image/<path:file_name>')
    def user_image(file_name):
        return send_from_directory(user_image_root, file_name)

    @bp.route('/review/')
    @templated('help/help_page.html')
    def review_index():
        return view.help_page(review_doc_root, None, review_toc_cache)

    @bp.route('/review/<page_name>')
    @templated('help/help_page.html')
    def review_page(page_name):
        return view.help_page(review_doc_root, page_name, review_toc_cache)

    @bp.route('/review/image/<path:file_name>')
    def review_image(file_name):
        return send_from_directory(review_image_root, file_name)

    @bp.route('/admin/')
    @templated('help/help_page.html')
    def admin_index():
        return view.help_page(admin_doc_root, None, admin_toc_cache)

    @bp.route('/admin/<page_name>')
    @templated('help/help_page.html')
    def admin_page(page_name):
        return view.help_page(admin_doc_root, page_name, admin_toc_cache)

    @bp.route('/admin/image/<path:file_name>')
    def admin_image(file_name):
        return send_from_directory(admin_image_root, file_name)

    @bp.route('/admin/graph/<path:file_name>')
    @send_file(fixed_type=FigureType.PNG)
    def admin_graph(file_name):
        return view.help_graph(admin_doc_root, file_name)

    return bp
