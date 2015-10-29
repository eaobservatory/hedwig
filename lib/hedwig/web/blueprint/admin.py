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

from flask import Blueprint, request

from ..util import require_admin, templated
from ...view.admin import AdminView


def create_admin_blueprint(db, facilities):
    bp = Blueprint('admin', __name__)
    view = AdminView()

    @bp.route('/')
    @templated('admin/home.html')
    @require_admin
    def admin_home():
        return view.home(facilities)

    @bp.route('/message/')
    @templated('admin/message_list.html')
    @require_admin
    def message_list():
        return view.message_list(db, request.args)

    @bp.route('/message/<int:message_id>')
    @templated('admin/message_view.html')
    @require_admin
    def message_view(message_id):
        return view.message_view(db, message_id)

    @bp.route('/processing', methods=['GET', 'POST'])
    @templated('admin/processing_status.html')
    @require_admin
    def processing_status():
        return view.processing_status(
            db, facilities,
            (request.form if request.method == 'POST' else None))

    @bp.route('/user_unregistered')
    @templated('admin/user_unregistered.html')
    @require_admin
    def user_unregistered():
        return view.user_unregistered(db)

    return bp
