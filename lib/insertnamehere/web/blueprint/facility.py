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

from ..util import require_admin, require_auth, templated


def create_facility_blueprint(db, facility):
    """
    Create Flask blueprint for a facility.
    """

    code = facility.get_code()
    name = facility.get_name()

    bp = Blueprint(code, __name__)

    def facility_template(template):
        """
        Decorator which uses the template from the facility's directory if it
        exists, otherwise the generic template.  It does this by providing a
        list of alternative templates, from which Flask's "render_template"
        method will pick the first which exists.
        """

        def decorator(f):
            return templated((code + '/' + template, 'generic/' + template))(f)
        return decorator

    @bp.route('/')
    @facility_template('facility_home.html')
    def facility_home():
        return facility.view_facility_home(db)

    @bp.route('/semester/<int:semester_id>')
    @facility_template('semester_calls.html')
    def semester_calls(semester_id):
        return facility.view_semester_calls(db, semester_id)

    @bp.route('/call/<int:call_id>/new_proposal',
              methods=['GET', 'POST'])
    @facility_template('proposal_new.html')
    @require_auth(require_institution=True)
    def proposal_new(call_id):
        return facility.view_proposal_new(
            db, call_id, request.form, request.method == 'POST')

    @bp.route('/proposal/<int:proposal_id>')
    @facility_template('proposal_view.html')
    @require_auth(require_person=True)
    def proposal_view(proposal_id):
        return facility.view_proposal_view(db, proposal_id)

    @bp.route('/proposal/<int:proposal_id>/member', methods=['GET', 'POST'])
    @facility_template('member_edit.html')
    @require_auth(require_person=True)
    def member_edit(proposal_id):
        return facility.view_member_edit(
            db, proposal_id, request.form, request.method == 'POST')

    @bp.route('/proposal/<int:proposal_id>/member/add',
              methods=['GET', 'POST'])
    @facility_template('member_add.html')
    @require_auth(require_person=True)
    def member_add(proposal_id):
        return facility.view_member_add(
            db, proposal_id, request.form, request.method == 'POST')

    @bp.route('/admin')
    @facility_template('facility_admin.html')
    @require_admin
    def facility_admin():
        return facility.view_facility_admin(db)

    @bp.route('/admin/semester/')
    @facility_template('semester_list.html')
    @require_admin
    def semester_list():
        return facility.view_semester_list(db)

    @bp.route('/admin/semester/new', methods=['GET', 'POST'])
    @facility_template('semester_edit.html')
    @require_admin
    def semester_new():
        return facility.view_semester_edit(db, None, request.form,
                                           request.method == 'POST')

    @bp.route('/admin/semester/<int:semester_id>')
    @facility_template('semester_view.html')
    @require_admin
    def semester_view(semester_id):
        return facility.view_semester_view(db, semester_id)

    @bp.route('/admin/semester/<int:semester_id>/edit',
              methods=['GET', 'POST'])
    @facility_template('semester_edit.html')
    @require_admin
    def semester_edit(semester_id):
        return facility.view_semester_edit(db, semester_id, request.form,
                                           request.method == 'POST')

    @bp.route('/admin/queue/')
    @facility_template('queue_list.html')
    @require_admin
    def queue_list():
        return facility.view_queue_list(db)

    @bp.route('/admin/queue/new', methods=['GET', 'POST'])
    @facility_template('queue_edit.html')
    @require_admin
    def queue_new():
        return facility.view_queue_edit(db, None, request.form,
                                        request.method == 'POST')

    @bp.route('/admin/queue/<int:queue_id>')
    @facility_template('queue_view.html')
    @require_admin
    def queue_view(queue_id):
        return facility.view_queue_view(db, queue_id)

    @bp.route('/admin/queue/<int:queue_id>/edit',
              methods=['GET', 'POST'])
    @facility_template('queue_edit.html')
    @require_admin
    def queue_edit(queue_id):
        return facility.view_queue_edit(db, queue_id, request.form,
                                        request.method == 'POST')

    @bp.route('/admin/queue/<int:queue_id>/affiliation',
              methods=['GET', 'POST'])
    @facility_template('affiliation_edit.html')
    @require_admin
    def affiliation_edit(queue_id):
        return facility.view_affiliation_edit(db, queue_id, request.form,
                                              request.method == 'POST')

    @bp.route('/admin/call/')
    @facility_template('call_list.html')
    @require_admin
    def call_list():
        return facility.view_call_list(db)

    @bp.route('/admin/call/new', methods=['GET', 'POST'])
    @facility_template('call_edit.html')
    @require_admin
    def call_new():
        return facility.view_call_edit(db, None, request.form,
                                       request.method == 'POST')

    @bp.route('/admin/call/<int:call_id>')
    @facility_template('call_view.html')
    @require_admin
    def call_view(call_id):
        return facility.view_call_view(db, call_id)

    @bp.route('/admin/call/<int:call_id>/edit', methods=['GET', 'POST'])
    @facility_template('call_edit.html')
    @require_admin
    def call_edit(call_id):
        return facility.view_call_edit(db, call_id, request.form,
                                       request.method == 'POST')

    @bp.context_processor
    def add_to_context():
        return {
            'facility_name': name,
        }

    return bp
