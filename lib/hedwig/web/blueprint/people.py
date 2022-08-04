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
from ..util import require_admin, require_auth, require_not_auth, \
    templated, with_current_user
from ...compat import str_to_unicode
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
            str_to_unicode(request.remote_addr),
            str_to_unicode(request.environ.get('HTTP_USER_AGENT')),
            request.referrer)

    @bp.route('/user/log_in/done')
    @with_current_user
    @templated('people/log_in_post_done.html')
    def log_in_post_done(current_user):
        return {'title': 'Reauthentication Complete'}

    @bp.route('/user/log_out')
    @with_current_user
    def log_out(current_user):
        view.log_out(current_user, db)

    @bp.route('/user/register', methods=['GET', 'POST'])
    @require_not_auth
    @templated('people/register_user.html')
    def register_user():
        return view.register_user(
            db, request.args,
            (request.form if request.method == 'POST' else None),
            str_to_unicode(request.remote_addr),
            str_to_unicode(request.environ.get('HTTP_USER_AGENT')))

    @bp.route('/user/name', methods=['GET', 'POST'])
    @require_auth(require_person=False)
    @templated('people/change_user_name.html')
    def change_user_name(current_user):
        return view.change_user_name(
            current_user, db,
            (request.form if request.method == 'POST' else None),
            str_to_unicode(request.remote_addr))

    @bp.route('/user/password', methods=['GET', 'POST'])
    @require_auth(require_person=False)
    @templated('people/change_password.html')
    def change_password(current_user):
        return view.change_password(
            current_user, db,
            (request.form if request.method == 'POST' else None),
            str_to_unicode(request.remote_addr))

    @bp.route('/user/password/reset', methods=['GET', 'POST'])
    @require_not_auth
    @templated('people/password_reset_token_get.html')
    def password_reset_token_get():
        return view.password_reset_token_get(
            db, request.args,
            (request.form if request.method == 'POST' else None),
            str_to_unicode(request.remote_addr))

    @bp.route('/user/password/reset/token', methods=['GET', 'POST'])
    @require_not_auth
    @templated('people/password_reset_token_use.html')
    def password_reset_token_use():
        return view.password_reset_token_use(
            db, request.args,
            (request.form if request.method == 'POST' else None),
            str_to_unicode(request.remote_addr))

    @bp.route('/user/admin/take')
    @require_auth(require_person_admin=True, record_referrer=True)
    def take_admin(current_user):
        return view.take_admin(
            current_user, db, request.args, request.referrer)

    @bp.route('/user/admin/drop')
    @with_current_user
    def drop_admin(current_user):
        return view.drop_admin(current_user, request.referrer)

    @bp.route('/user/log/<int:user_id>')
    @require_admin
    @templated('people/user_log.html')
    def user_log(current_user, user_id):
        return view.user_log(current_user, db, user_id, request.args)

    @bp.route('/user/session/')
    @require_admin
    @templated('people/user_session_list.html')
    def user_session_list(current_user):
        return view.user_session_list(current_user, db)

    @bp.route(
        '/user/session/log_out/',
        methods=['GET', 'POST'])
    @require_admin
    @templated('confirm.html')
    def user_session_log_out_all(current_user):
        return view.user_session_log_out(
            current_user, db, None,
            (request.form if request.method == 'POST' else None))

    @bp.route(
        '/user/session/log_out/<int:auth_token_id>',
        methods=['GET', 'POST'])
    @require_admin
    @templated('confirm.html')
    def user_session_log_out(current_user, auth_token_id):
        return view.user_session_log_out(
            current_user, db, auth_token_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/person/register', methods=['GET', 'POST'])
    @require_auth(require_person=False)
    @templated('people/person_edit.html')
    def register_person(current_user):
        return view.register_person(
            current_user, db, request.args,
            (request.form if request.method == 'POST' else None),
            str_to_unicode(request.remote_addr))

    @bp.route('/person/')
    @require_auth()
    @templated('people/person_list.html')
    def person_list(current_user):
        return view.person_list(current_user, db, request.args)

    @bp.route('/person/<int:person_id>')
    @require_auth()
    @templated('people/person_view.html')
    def person_view(current_user, person_id):
        return view.person_view(current_user, db, person_id, facilities)

    @bp.route('/person/<int:person_id>/invite', methods=['GET', 'POST'])
    @require_admin
    @templated('confirm.html')
    def person_invite(current_user, person_id):
        return view.person_invite(
            current_user, db, person_id, request.args,
            (request.form if request.method == 'POST' else None))

    @bp.route('/person/<int:person_id>/edit', methods=['GET', 'POST'])
    @require_auth()
    @templated('people/person_edit.html')
    def person_edit(current_user, person_id):
        return view.person_edit(
            current_user, db, person_id, request.args,
            (request.form if request.method == 'POST' else None))

    @bp.route('/person/<int:person_id>/institution', methods=['GET', 'POST'])
    @require_auth()
    @templated('people/person_edit_institution.html')
    def person_edit_institution(current_user, person_id):
        return view.person_edit_institution(
            current_user, db, person_id, request.args,
            (request.form if request.method == 'POST' else None))

    @bp.route('/user/email/edit', methods=['GET', 'POST'])
    @require_auth(allow_unverified=True)
    @templated('people/person_edit_email.html')
    def person_edit_email_own(current_user):
        return view.person_edit_email_own(
            current_user, db, request.args,
            (request.form if request.method == 'POST' else None))

    @bp.route('/person/<int:person_id>/email', methods=['GET', 'POST'])
    @require_auth()
    @templated('people/person_edit_email.html')
    def person_edit_email(current_user, person_id):
        return view.person_edit_email(
            current_user, db, person_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/user/email/verify', methods=['GET', 'POST'])
    @require_auth(allow_unverified=True)
    @templated('people/person_email_verify_get.html')
    def person_email_verify_primary(current_user):
        return view.person_email_verify_get_primary(
            current_user, db, request.args,
            (request.form if request.method == 'POST' else None),
            str_to_unicode(request.remote_addr))

    @bp.route('/person/<int:person_id>/email/verify/<int:email_id>',
              methods=['GET', 'POST'])
    @require_auth(allow_unverified=True)
    @templated('people/person_email_verify_get.html')
    def person_email_verify_get(current_user, person_id, email_id):
        return view.person_email_verify_get(
            current_user, db, person_id, email_id,
            (request.form if request.method == 'POST' else None),
            str_to_unicode(request.remote_addr))

    @bp.route('/verify', methods=['GET', 'POST'])
    @require_auth(allow_unverified=True)
    @templated('people/person_email_verify_use.html')
    def person_email_verify_use(current_user):
        return view.person_email_verify_use(
            current_user, db, request.args,
            (request.form if request.method == 'POST' else None),
            str_to_unicode(request.remote_addr))

    @bp.route('/proposals')
    @require_auth()
    @templated('person_proposals.html')
    def person_proposals(current_user):
        return view.person_proposals_own(current_user, db, facilities)

    @bp.route('/person/<int:person_id>/proposals')
    @require_auth()
    @templated('person_proposals.html')
    def person_view_proposals(current_user, person_id):
        return view.person_proposals_other(
            current_user, db, person_id, facilities)

    @bp.route('/reviews')
    @require_auth()
    @templated('person_reviews.html')
    def person_reviews(current_user):
        return view.person_reviews_own(current_user, db, facilities)

    @bp.route('/person/<int:person_id>/reviews')
    @require_auth()
    @templated('person_reviews.html')
    def person_view_reviews(current_user, person_id):
        return view.person_reviews_other(
            current_user, db, person_id, facilities, request.args)

    @bp.route('/person/<int:person_id>/subsume',
              methods=['GET', 'POST'])
    @require_admin
    @templated('people/person_subsume.html')
    def person_subsume(current_user, person_id):
        return view.person_subsume(
            current_user, db, person_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/person/<int:person_id>/log')
    @require_admin
    @templated('people/person_log.html')
    def person_log(current_user, person_id):
        return view.person_log(
            current_user, db, person_id, request.args)

    @bp.route('/institution/')
    @require_auth()
    @templated('people/institution_list.html')
    def institution_list(current_user):
        return view.institution_list(current_user, db)

    @bp.route('/institution/<int:institution_id>')
    @require_auth()
    @templated('people/institution_view.html')
    def institution_view(current_user, institution_id):
        return view.institution_view(current_user, db, institution_id)

    @bp.route('/institution/<int:institution_id>/edit',
              methods=['GET', 'POST'])
    @require_auth()
    @templated('people/institution_edit.html')
    def institution_edit(current_user, institution_id):
        return view.institution_edit(
            current_user, db, institution_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/institution/<int:institution_id>/log', methods=['GET', 'POST'])
    @require_admin
    @templated('people/institution_log.html')
    def institution_log(current_user, institution_id):
        return view.institution_log(
            current_user, db, institution_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/institution/log_approval', methods=['GET', 'POST'])
    @require_admin
    @templated('people/institution_log.html')
    def institution_log_approval(current_user):
        return view.institution_log_approval(
            current_user, db,
            (request.form if request.method == 'POST' else None))

    @bp.route('/institution/<int:institution_id>/subsume',
              methods=['GET', 'POST'])
    @require_admin
    @templated('people/institution_subsume.html')
    def institution_subsume(current_user, institution_id):
        return view.institution_subsume(
            current_user, db, institution_id,
            (request.form if request.method == 'POST' else None))

    @bp.route('/invitation')
    @with_current_user
    @templated('people/invitation_token_enter.html')
    def invitation_token_enter(current_user):
        return view.invitation_token_enter(current_user, db, request.args)

    @bp.route('/invitation/accept', methods=['GET', 'POST'])
    @require_auth(require_person=False, register_user_only=True)
    @templated('people/invitation_token_accept.html')
    def invitation_token_accept(current_user):
        return view.invitation_token_accept(
            current_user, db, facilities, request.args,
            (request.form if request.method == 'POST' else None),
            str_to_unicode(request.remote_addr))

    return bp
