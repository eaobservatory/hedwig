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
from flask import Flask, flash, request, session, url_for
import os

from ..config import get_config, get_database, get_home
from ..error import UserError
from .util import require_auth, require_not_auth, templated, HTTPRedirect


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
        return {
        }

    @app.route('/user/login', methods=['GET', 'POST'])
    @templated('login.html')
    @require_not_auth
    def login():
        message = None

        if request.method == 'POST':
            user_id = db.authenticate_user(request.form['user_name'],
                                           request.form['password'])

            if user_id is None:
                message = 'User name or password not recognised.'
            else:
                session['user_id'] = user_id
                flash('You have been logged in.')
                raise HTTPRedirect(url_for('home_page'))

        return {
            'title': 'Log in',
            'message':  message,
            'user_name': request.form.get('user_name', ''),
        }

    @app.route('/user/logout')
    def logout():
        session.pop('user_id', None)
        flash('You have been logged out.')
        raise HTTPRedirect(url_for('home_page'))

    @app.route('/user/register', methods=['GET', 'POST'])
    @templated('register.html')
    @require_not_auth
    def register():
        message = None

        if request.method == 'POST':
            try:
                user_name = request.form['user_name']
                password = request.form['password']
                if password != request.form['password_check']:
                    raise UserError('The passwords did not match.')
                user_id = db.add_user(user_name, password)
                session['user_id'] = user_id
                flash('Your user account has been created.')
                raise HTTPRedirect(url_for('register_person'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Register',
            'message':  message,
            'user_name': request.form.get('user_name', ''),
        }

    @app.route('/user/password/reset', methods=['GET', 'POST'])
    @templated('reset_password.html')
    @require_not_auth
    def reset_password():
        return {
            'title': 'Reset password',
        }

    @app.route('/person/register', methods=['GET', 'POST'])
    @templated('edit_person.html')
    @require_auth
    def register_person():
        message = None

        name = request.form.get('person_name', '')
        email = request.form.get('single_email', '')
        public = 'person_public' in request.form

        if request.method == 'POST':
            name = request.form['person_name']
            email = request.form['single_email']
            if not name:
                message = 'Please enter your full name.'
            elif not email:
                message = 'Please enter your email address.'
            else:
                user_id = session['user_id']
                person_id = db.add_person(name, public=public, user_id=user_id)
                db.add_email(person_id, email, primary=True)
                flash('Your user profile has been saved.')
                raise HTTPRedirect(url_for('edit_person_institution',
                                           person_id=person_id))

        return {
            'title': 'Create Profile',
            'target': 'register_person',
            'message': message,
            'person_name': name,
            'person_public': public,
            'single_email': email
        }

    @app.route('/person/<int:person_id>/institution')
    @templated('edit_person_institution.html')
    @require_auth
    def edit_person_institution(person_id):
        return {
            'title': 'Select Institution',
        }

    @app.context_processor
    def add_to_context():
        return {
            'application_name': application_name,
        }

    return app
