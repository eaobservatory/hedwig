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

from ..error import NoSuchRecord, UserError
from ..web.util import flash, session, url_for, \
    ErrorPage, HTTPError, HTTPForbidden, HTTPNotFound, HTTPRedirect


def do_login(db, form, is_post):
    message = None

    if is_post:
        user_id = db.authenticate_user(form['user_name'], form['password'])

        if user_id is None:
            message = 'User name or password not recognised.'
        else:
            session['user_id'] = user_id
            flash('You have been logged in.')
            raise HTTPRedirect(url_for('home_page'))

    return {
        'title': 'Log in',
        'message':  message,
        'user_name': form.get('user_name', ''),
    }


def do_logout():
    session.pop('user_id', None)
    flash('You have been logged out.')
    raise HTTPRedirect(url_for('home_page'))


def do_register_user(db, form, is_post):
    message = None

    if is_post:
        try:
            user_name = form['user_name']
            password = form['password']
            if password != form['password_check']:
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
        'user_name': form.get('user_name', ''),
    }


def do_reset_password(db, form, is_post):
    return {
        'title': 'Reset password',
    }


def do_register_person(db, form, is_post):
    message = None

    name = form.get('person_name', '')
    email = form.get('single_email', '')
    public = 'person_public' in form

    if is_post:
        name = form['person_name']
        email = form['single_email']
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


def do_edit_person_institution(db, person_id, form, is_post):
    try:
        person = db.get_person(person_id)
    except NoSuchRecord:
        raise HTTPNotFound('Person profile not found.')
    if person.user_id != session['user_id']:
        raise HTTPForbidden('Permission denied for this person profile.')

    message = None

    name = form.get('institution_name', '')
    institutions = db.list_institution()

    if is_post:
        if 'submit_select' in form:
            institution_id = int(form['institution_id'])
            if institution_id not in institutions:
                raise HTTPError('Institution not found.')
            db.update_person(person_id, institution_id=institution_id)
            raise HTTPRedirect(url_for('home_page'))

        elif 'submit_add' in form:
            if not name:
                message = 'Please enter the institution name.'
            else:
                institution_id = db.add_institution(name)
                db.update_person(person_id, institution_id=institution_id)
                raise HTTPRedirect(url_for('home_page'))

        else:
            raise ErrorPage('Unknown action')

    return {
        'title': 'Select Institution',
        'message': message,
        'person_id': person_id,
        'institution_name': name,
        'institution_id': person.institution_id,
        'institutions': institutions.values(),
    }
