# Copyright (C) 2015-2022 East Asian Observatory
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
    """
    Create Flask Blueprint for the site-wide administrative interface.
    """

    bp = Blueprint('admin', __name__)
    view = AdminView()

    @bp.route('/')
    @templated('admin/home.html')
    @require_admin
    def admin_home(current_user):
        return view.home(current_user, facilities)

    @bp.route('/message/', methods=['GET', 'POST'])
    @templated('admin/message_list.html')
    @require_admin
    def message_list(current_user):
        return view.message_list(
            current_user, db, request.args,
            (request.form if request.method == 'POST' else None))

    @bp.route('/message/<int:message_id>')
    @templated('admin/message_view.html')
    @require_admin
    def message_view(current_user, message_id):
        return view.message_view(current_user, db, message_id)

    @bp.route('/message/<int:message_id>/alter_state',
              methods=['GET', 'POST'])
    @templated('admin/message_alter_state.html')
    @require_admin
    def message_alter_state(current_user, message_id):
        return view.message_alter_state(
            current_user, db, message_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/message_thread/<hedwig_thread:thread_type>/<int:thread_id>')
    @templated('admin/message_thread.html')
    @require_admin
    def message_thread(current_user, thread_type, thread_id):
        return view.message_thread(
            current_user, db, facilities, thread_type, thread_id)

    @bp.route('/processing', methods=['GET', 'POST'])
    @templated('admin/processing_status.html')
    @require_admin
    def processing_status(current_user):
        return view.processing_status(
            current_user, db, facilities,
            (request.form if request.method == 'POST' else None))

    @bp.route('/request', methods=['GET', 'POST'])
    @templated('admin/request_status.html')
    @require_admin
    def request_status(current_user):
        return view.request_status(
            current_user, db, facilities,
            (request.form if request.method == 'POST' else None))

    @bp.route('/user_unregistered', methods=['GET', 'POST'])
    @templated('admin/user_unregistered.html')
    @require_admin
    def user_unregistered(current_user):
        return view.user_unregistered(
            current_user, db,
            (request.form if request.method == 'POST' else None))

    @bp.route('/group/<hedwig_site_group:site_group_type>')
    @templated('admin/site_group_view.html')
    @require_admin
    def site_group_view(current_user, site_group_type):
        return view.site_group_view(current_user, db, site_group_type)

    @bp.route('/group/<hedwig_site_group:site_group_type>/add',
              methods=['GET', 'POST'])
    @templated('person_select.html')
    @require_admin
    def site_group_member_add(current_user, site_group_type):
        return view.site_group_member_add(
            current_user, db, site_group_type,
            (request.form if request.method == 'POST' else None))

    @bp.route('/group/<hedwig_site_group:site_group_type>/edit',
              methods=['GET', 'POST'])
    @templated('admin/site_group_member_edit.html')
    @require_admin
    def site_group_member_edit(current_user, site_group_type):
        return view.site_group_member_edit(
            current_user, db, site_group_type,
            (request.form if request.method == 'POST' else None))

    @bp.route(
        '/group/<hedwig_site_group:site_group_type>/reinvite/<int:member_id>',
        methods=['GET', 'POST'])
    @templated('confirm.html')
    @require_admin
    def site_group_member_reinvite(current_user, site_group_type, member_id):
        return view.site_group_member_reinvite(
            current_user, db, site_group_type, member_id,
            (request.form if request.method == 'POST' else None))

    return bp
