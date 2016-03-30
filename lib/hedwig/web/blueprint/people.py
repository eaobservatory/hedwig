# Copyright (C) 2015-2016 East Asian Observatory
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
from ...view.people import PeopleView


def create_people_blueprint(db, facilities):
    """
    Create Flask Blueprint for pages related to users, personal profiles
    and institutions.
    """

    bp = Blueprint('people', __name__)
    view = PeopleView()

    @bp.route('/user/log_in', methods=['GET', 'POST'])
    @require_not_auth
    @templated('people/log_in.html')
    def log_in():
        return view.log_in(
            db, request.args,
            (request.form if request.method == 'POST' else None),
            request.referrer)

    @bp.route('/user/log_in/done')
    @templated('people/log_in_post_done.html')
    def log_in_post_done():
        return {'title': 'Reauthentication Complete'}

    @bp.route('/user/log_out')
    def log_out():
        view.log_out()

    @bp.route('/user/register', methods=['GET', 'POST'])
    @require_not_auth
    @templated('people/register_user.html')
    def register_user():
        return view.register_user(
            db, (request.form if request.method == 'POST' else None),
            request.remote_addr)

    @bp.route('/user/name', methods=['GET', 'POST'])
    @require_auth()
    @templated('people/change_user_name.html')
    def change_user_name():
        return view.change_user_name(
            db, (request.form if request.method == 'POST' else None),
            request.remote_addr)

    @bp.route('/user/password', methods=['GET', 'POST'])
    @require_auth()
    @templated('people/change_password.html')
    def change_password():
        return view.change_password(
            db, (request.form if request.method == 'POST' else None),
            request.remote_addr)

    @bp.route('/user/password/reset', methods=['GET', 'POST'])
    @require_not_auth
    @templated('people/password_reset_token_get.html')
    def password_reset_token_get():
        return view.password_reset_token_get(
            db, (request.form if request.method == 'POST' else None),
            request.remote_addr)

    @bp.route('/user/password/reset/token', methods=['GET', 'POST'])
    @require_not_auth
    @templated('people/password_reset_token_use.html')
    def password_reset_token_use():
        return view.password_reset_token_use(
            db, request.args,
            (request.form if request.method == 'POST' else None),
            request.remote_addr)

    @bp.route('/user/admin/take')
    @require_auth(require_person_admin=True, record_referrer=True)
    def take_admin():
        return view.take_admin(db, request.referrer)

    @bp.route('/user/admin/drop')
    def drop_admin():
        return view.drop_admin(request.referrer)

    @bp.route('/user/log/<int:user_id>')
    @require_admin
    @templated('people/user_log.html')
    def user_log(user_id):
        return view.user_log(db, user_id)

    @bp.route('/person/register', methods=['GET', 'POST'])
    @require_auth()
    @templated('people/person_edit.html')
    def register_person():
        return view.register_person(
            db, (request.form if request.method == 'POST' else None),
            request.remote_addr)

    @bp.route('/person/')
    @require_auth()
    @templated('people/person_list.html')
    def person_list():
        return view.person_list(db)

    @bp.route('/person/<int:person_id>')
    @require_auth()
    @templated('people/person_view.html')
    def person_view(person_id):
        return view.person_view(db, person_id)

    @bp.route('/person/<int:person_id>/edit', methods=['GET', 'POST'])
    @require_auth()
    @templated('people/person_edit.html')
    def person_edit(person_id):
        return view.person_edit(
            db, person_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/person/<int:person_id>/institution', methods=['GET', 'POST'])
    @require_auth()
    @templated('people/person_edit_institution.html')
    def person_edit_institution(person_id):
        return view.person_edit_institution(
            db, person_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/person/<int:person_id>/email', methods=['GET', 'POST'])
    @require_auth()
    @templated('people/person_edit_email.html')
    def person_edit_email(person_id):
        return view.person_edit_email(
            db, person_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/person/<int:person_id>/email/verify/<int:email_id>',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @templated('people/person_email_verify_get.html')
    def person_email_verify_get(person_id, email_id):
        return view.person_email_verify_get(
            db, person_id, email_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/verify', methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @templated('people/person_email_verify_use.html')
    def person_email_verify_use():
        return view.person_email_verify_use(
            db, request.args,
            (request.form if request.method == 'POST' else None))

    @bp.route('/proposals')
    @require_auth(require_person=True)
    @templated('person_proposals.html')
    def person_proposals():
        return view.person_proposals_own(db, facilities)

    @bp.route('/person/<int:person_id>/proposals')
    @require_admin
    @templated('person_proposals.html')
    def person_view_proposals(person_id):
        return view.person_proposals_other(db, person_id, facilities)

    @bp.route('/reviews')
    @require_auth(require_person=True)
    @templated('person_reviews.html')
    def person_reviews():
        return view.person_reviews_own(db, facilities)

    @bp.route('/person/<int:person_id>/reviews')
    @require_admin
    @templated('person_reviews.html')
    def person_view_reviews(person_id):
        return view.person_reviews_other(db, person_id, facilities)

    @bp.route('/institution/')
    @require_auth()
    @templated('people/institution_list.html')
    def institution_list():
        return view.institution_list(db)

    @bp.route('/institution/<int:institution_id>')
    @require_auth()
    @templated('people/institution_view.html')
    def institution_view(institution_id):
        return view.institution_view(db, institution_id)

    @bp.route('/institution/<int:institution_id>/edit',
              methods=['GET', 'POST'])
    @require_auth(require_person=True)
    @templated('people/institution_edit.html')
    def institution_edit(institution_id):
        return view.institution_edit(
            db, institution_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/institution/<int:institution_id>/log', methods=['GET', 'POST'])
    @require_admin
    @templated('people/institution_log.html')
    def institution_log(institution_id):
        return view.institution_log(
            db, institution_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/institution/log_approval', methods=['GET', 'POST'])
    @require_admin
    @templated('people/institution_log.html')
    def institution_log_approval():
        return view.institution_log_approval(
            db, (request.form if request.method == 'POST' else None))

    @bp.route('/institution/<int:institution_id>/subsume',
              methods=['GET', 'POST'])
    @require_admin
    @templated('people/institution_subsume.html')
    def institution_subsume(institution_id):
        return view.institution_subsume(
            db, institution_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/invitation')
    @templated('people/invitation_token_enter.html')
    def invitation_token_enter():
        return view.invitation_token_enter(db, request.args)

    @bp.route('/invitation/accept', methods=['GET', 'POST'])
    @require_auth(register_user_only=True)
    @templated('people/invitation_token_accept.html')
    def invitation_token_accept():
        return view.invitation_token_accept(
            db, request.args,
            (request.form if request.method == 'POST' else None),
            request.remote_addr)

    return bp
