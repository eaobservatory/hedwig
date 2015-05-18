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

from ...view import people as view


def create_people_blueprint(db):
    bp = Blueprint('people', __name__)

    @bp.route('/user/log_in', methods=['GET', 'POST'])
    @templated('people/log_in.html')
    @require_not_auth
    def log_in():
        return view.log_in(db, request.args, request.form,
                           request.method == 'POST', request.referrer)

    @bp.route('/user/log_out')
    def log_out():
        view.log_out()

    @bp.route('/user/register', methods=['GET', 'POST'])
    @templated('people/register_user.html')
    @require_not_auth
    def register_user():
        return view.register_user(db, request.form, request.method == 'POST')

    @bp.route('/user/password', methods=['GET', 'POST'])
    @templated('people/change_password.html')
    @require_auth()
    def change_password():
        return view.change_password(db, request.form, request.method == 'POST')

    @bp.route('/user/password/reset', methods=['GET', 'POST'])
    @templated('people/get_password_reset_token.html')
    @require_not_auth
    def get_password_reset_token():
        return view.get_password_reset_token(db, request.form,
                                             request.method == 'POST')

    @bp.route('/user/password/reset/token', methods=['GET', 'POST'])
    @templated('people/use_password_reset_token.html')
    @require_not_auth
    def use_password_reset_token():
        return view.use_password_reset_token(db, request.form,
                                             request.method == 'POST')

    @bp.route('/person/register', methods=['GET', 'POST'])
    @templated('people/edit_person.html')
    @require_auth()
    def register_person():
        return view.register_person(db, request.form, request.method == 'POST')

    @bp.route('/person/<int:person_id>')
    @templated('people/view_person.html')
    @require_auth()
    def view_person(person_id):
        return view.view_person(db, person_id)

    @bp.route('/person/<int:person_id>/edit', methods=['GET', 'POST'])
    @templated('people/edit_person.html')
    @require_auth()
    def edit_person(person_id):
        return view.edit_person(db, person_id, request.form,
                                request.method == 'POST')

    @bp.route('/person/<int:person_id>/institution', methods=['GET', 'POST'])
    @templated('people/edit_person_institution.html')
    @require_auth()
    def edit_person_institution(person_id):
        return view.edit_person_institution(db, person_id, request.form,
                                            request.method == 'POST')

    @bp.route('/institution/<int:institution_id>')
    @templated('people/view_institution.html')
    @require_auth()
    def view_institution(institution_id):
        return view.view_institution(db, institution_id)

    @bp.route('/institution/<int:institution_id>/edit',
              methods=['GET', 'POST'])
    @templated('people/edit_institution.html')
    @require_auth()
    def edit_institution(institution_id):
        return view.edit_institution(db, institution_id, request.form,
                                     request.method == 'POST')

    return bp
