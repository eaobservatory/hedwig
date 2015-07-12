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

from ..util import require_admin, require_auth, require_not_auth, templated
from ...view.home import prepare_dashboard
from ...view import people as view


def create_people_blueprint(db, facilities):
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

    @bp.route('/user/name', methods=['GET', 'POST'])
    @templated('people/change_user_name.html')
    @require_auth()
    def change_user_name():
        return view.change_user_name(db, request.form,
                                     request.method == 'POST')

    @bp.route('/user/password', methods=['GET', 'POST'])
    @templated('people/change_password.html')
    @require_auth()
    def change_password():
        return view.change_password(db, request.form, request.method == 'POST')

    @bp.route('/user/password/reset', methods=['GET', 'POST'])
    @templated('people/password_reset_token_get.html')
    @require_not_auth
    def password_reset_token_get():
        return view.password_reset_token_get(db, request.form,
                                             request.method == 'POST')

    @bp.route('/user/password/reset/token', methods=['GET', 'POST'])
    @templated('people/password_reset_token_use.html')
    @require_not_auth
    def password_reset_token_use():
        return view.password_reset_token_use(db, request.args, request.form,
                                             request.method == 'POST')

    @bp.route('/user/admin/take')
    @require_auth()
    def take_admin():
        return view.take_admin(db, request.referrer)

    @bp.route('/user/admin/drop')
    def drop_admin():
        return view.drop_admin(request.referrer)

    @bp.route('/person/register', methods=['GET', 'POST'])
    @templated('people/person_edit.html')
    @require_auth()
    def register_person():
        return view.register_person(db, request.form, request.method == 'POST')

    @bp.route('/person/')
    @templated('people/person_list.html')
    @require_auth()
    def person_list():
        return view.person_list(db)

    @bp.route('/person/<int:person_id>')
    @templated('people/person_view.html')
    @require_auth()
    def person_view(person_id):
        return view.person_view(db, person_id)

    @bp.route('/person/<int:person_id>/edit', methods=['GET', 'POST'])
    @templated('people/person_edit.html')
    @require_auth()
    def person_edit(person_id):
        return view.person_edit(db, person_id, request.form,
                                request.method == 'POST')

    @bp.route('/person/<int:person_id>/institution', methods=['GET', 'POST'])
    @templated('people/person_edit_institution.html')
    @require_auth()
    def person_edit_institution(person_id):
        return view.person_edit_institution(db, person_id, request.form,
                                            request.method == 'POST')

    @bp.route('/person/<int:person_id>/email', methods=['GET', 'POST'])
    @templated('people/person_edit_email.html')
    @require_auth()
    def person_edit_email(person_id):
        return view.person_edit_email(db, person_id, request.form,
                                      request.method == 'POST')

    @bp.route('/person/<int:person_id>/email/verify/<int:email_id>',
              methods=['GET', 'POST'])
    @templated('people/person_email_verify_get.html')
    @require_auth(require_person=True)
    def person_email_verify_get(person_id, email_id):
        return view.person_email_verify_get(
            db, person_id, email_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/verify', methods=['GET', 'POST'])
    @templated('people/person_email_verify_use.html')
    @require_auth(require_person=True)
    def person_email_verify_use():
        return view.person_email_verify_use(
            db, request.args,
            (request.form if request.method == 'POST' else None))

    @bp.route('/person/<int:person_id>/dashboard')
    @templated('dashboard.html')
    @require_admin
    def person_view_dashboard(person_id):
        return prepare_dashboard(db, person_id, facilities,
                                 administrative=True)

    @bp.route('/institution/')
    @templated('people/institution_list.html')
    @require_auth()
    def institution_list():
        return view.institution_list(db)

    @bp.route('/institution/<int:institution_id>')
    @templated('people/institution_view.html')
    @require_auth()
    def institution_view(institution_id):
        return view.institution_view(db, institution_id)

    @bp.route('/institution/<int:institution_id>/edit',
              methods=['GET', 'POST'])
    @templated('people/institution_edit.html')
    @require_auth()
    def institution_edit(institution_id):
        return view.institution_edit(db, institution_id, request.form,
                                     request.method == 'POST')

    @bp.route('/invitation')
    @templated('people/invitation_token_enter.html')
    def invitation_token_enter():
        return view.invitation_token_enter(db, request.args)

    @bp.route('/invitation/accept', methods=['GET', 'POST'])
    @templated('people/invitation_token_accept.html')
    @require_auth(register_user_only=True)
    def invitation_token_accept():
        return view.invitation_token_accept(db, request.args, request.form,
                                            request.method == 'POST')

    return bp
