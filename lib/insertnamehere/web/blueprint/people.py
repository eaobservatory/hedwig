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

from ..util import require_auth, require_not_auth, templated

from ...view.people import do_login, do_logout, do_register_user, \
    do_change_password, get_password_reset_token, use_password_reset_token, \
    do_register_person, do_edit_person_institution, do_view_person, \
    do_view_institution, do_edit_institution


def create_people_blueprint(db):
    bp = Blueprint('people', __name__)

    @bp.route('/user/login', methods=['GET', 'POST'])
    @templated('people/login.html')
    @require_not_auth
    def login():
        return do_login(db, request.args, request.form,
                        request.method == 'POST')

    @bp.route('/user/logout')
    def logout():
        do_logout()

    @bp.route('/user/register', methods=['GET', 'POST'])
    @templated('people/register_user.html')
    @require_not_auth
    def register():
        return do_register_user(db, request.form, request.method == 'POST')

    @bp.route('/user/password', methods=['GET', 'POST'])
    @templated('people/change_password.html')
    @require_auth
    def change_password():
        return do_change_password(db, request.form, request.method == 'POST')

    @bp.route('/user/password/reset', methods=['GET', 'POST'])
    @templated('people/reset_password.html')
    @require_not_auth
    def reset_password():
        return get_password_reset_token(db, request.form,
                                        request.method == 'POST')

    @bp.route('/user/password/token', methods=['GET', 'POST'])
    @templated('people/reset_password_token.html')
    @require_not_auth
    def reset_password_token():
        return use_password_reset_token(db, request.form,
                                        request.method == 'POST')

    @bp.route('/person/register', methods=['GET', 'POST'])
    @templated('people/edit_person.html')
    @require_auth
    def register_person():
        return do_register_person(db, request.form, request.method == 'POST')

    @bp.route('/person/<int:person_id>')
    @templated('people/view_person.html')
    @require_auth
    def view_person(person_id):
        return do_view_person(db, person_id)

    @bp.route('/person/<int:person_id>/institution', methods=['GET', 'POST'])
    @templated('people/edit_person_institution.html')
    @require_auth
    def edit_person_institution(person_id):
        return do_edit_person_institution(db, person_id, request.form,
                                          request.method == 'POST')

    @bp.route('/institution/<int:institution_id>')
    @templated('people/view_institution.html')
    @require_auth
    def view_institution(institution_id):
        return do_view_institution(db, institution_id)

    @bp.route('/institution/<int:institution_id>/edit',
              methods=['GET', 'POST'])
    @templated('people/edit_institution.html')
    @require_auth
    def edit_institution(institution_id):
        return do_edit_institution(db, institution_id, request.form,
                                   request.method == 'POST')

    return bp
