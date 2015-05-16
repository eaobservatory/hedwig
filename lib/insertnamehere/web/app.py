# Copyright (C) 2014 Science and Technology Facilities Council.
# Copyright (C) 2015 East Asian Observatory.
# All Rights Reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import datetime
from flask import Flask, request
import os

from ..config import get_config, get_database, get_home
from ..view.people import do_login, do_logout, do_register_user, \
    do_reset_password, do_register_person, do_edit_person_institution
from ..view.home import prepare_home
from .util import require_auth, require_not_auth, templated


def create_web_app():
    """
    Function to prepare the Flask web application.
    """

    home = get_home()
    config = get_config()
    db = get_database()

    application_name = config.get('application', 'name')

    app = Flask(
        application_name,
        static_folder=os.path.join(home, 'data', 'web', 'static'),
        template_folder=os.path.join(home, 'data', 'web', 'template'),
    )

    # Try to read the secret key from the configuration file, but if
    # there isn't one, generate a temporary key.
    secret_key = config.get('application', 'secret_key')
    if not secret_key:
        # TODO: issue warning: generating temporary secret key
        secret_key = os.urandom(32)
    app.secret_key = secret_key

    @app.route('/')
    @templated('home.html')
    def home_page():
        return prepare_home()

    @app.route('/user/login', methods=['GET', 'POST'])
    @templated('login.html')
    @require_not_auth
    def login():
        return do_login(db, request.form, request.method == 'POST')

    @app.route('/user/logout')
    def logout():
        do_logout()

    @app.route('/user/register', methods=['GET', 'POST'])
    @templated('register.html')
    @require_not_auth
    def register():
        return do_register_user(db, request.form, request.method == 'POST')

    @app.route('/user/password/reset', methods=['GET', 'POST'])
    @templated('reset_password.html')
    @require_not_auth
    def reset_password():
        return do_reset_password(db, request.form, request.method == 'POST')

    @app.route('/person/register', methods=['GET', 'POST'])
    @templated('edit_person.html')
    @require_auth
    def register_person():
        return do_register_person(db, request.form, request.method == 'POST')

    @app.route('/person/<int:person_id>/institution', methods=['GET', 'POST'])
    @templated('edit_person_institution.html')
    @require_auth
    def edit_person_institution(person_id):
        return do_edit_person_institution(db, person_id, request.form,
                                          request.method == 'POST')

    @app.context_processor
    def add_to_context():
        return {
            'application_name': application_name,
        }

    return app
