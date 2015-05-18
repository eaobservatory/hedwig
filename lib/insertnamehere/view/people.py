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


def log_in(db, args, form, is_post, referrer):
    message = None

    if is_post:
        try:
            user_id = db.authenticate_user(form['user_name'], form['password'])

            if user_id is None:
                raise UserError('User name or password not recognised.')
            else:
                session['user_id'] = user_id
                flash('You have been logged in.')

                persons = db.search_person(user_id=user_id)
                if not persons:
                    # If the user has no profile, take them to the profile
                    # registration page.
                    flash('It appears your registration was not complete. '
                          'If convenient, please complete your profile.')
                    raise HTTPRedirect(url_for('.register_person'))
                elif len(persons) == 1:
                    person = list(persons.values())[0]
                    _update_session_person(person)
                    if person.institution_id is None:
                        # If the user has no institution, take them to the
                        # institution selection page.
                        flash('It appears your registration was not complete. '
                              'If convenient, please select your institution.')
                        raise HTTPRedirect(url_for('.edit_person_institution',
                                                   person_id=person.id))
                    raise HTTPRedirect(
                        session.pop('log_in_for', url_for('home_page')))
                else:
                    raise ErrorPage(
                        'Your account is associated with multiple profiles.')

        except UserError as e:
            message = e.message

    elif (referrer is not None) and ('log_in_for' not in session):
        session['log_in_for'] = referrer

    return {
        'title': 'Log in',
        'message':  message,
        'user_name': form.get('user_name', args.get('user_name', '')),
    }


def log_out():
    session.pop('user_id', None)
    session.pop('person', None)
    flash('You have been logged out.')
    raise HTTPRedirect(url_for('home_page'))


def register_user(db, form, is_post):
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
            raise HTTPRedirect(url_for('.register_person'))

        except UserError as e:
            message = e.message

    return {
        'title': 'Register',
        'message':  message,
        'user_name': form.get('user_name', ''),
    }


def change_password(db, form, is_post):
    message = None

    if is_post:
        try:
            user_id = session['user_id']
            password = form['password']
            password_new = form['password_new']
            if password_new != form['password_check']:
                raise UserError('The new passwords did not match.')
            if password_new == password:
                raise UserError(
                    'The new password is the same as the current password')
            if db.authenticate_user(None, form['password'],
                                    user_id=user_id) is None:
                raise UserError(
                    'Your current password was entered incorrectly.')
            db.update_user_password(user_id, password_new)
            flash('Your password has been changed.')
            raise HTTPRedirect(url_for('home_page'))

        except UserError as e:
            message = e.message

    return {
        'title': 'Change Password',
        'message': message,
    }


def get_password_reset_token(db, form, is_post):
    message = None

    if is_post:
        user_name = form.get('user_name', None)
        address = form.get('email', None)

        if user_name:
            message = 'Searching by user name is not yet implemented.'
        elif address:
            person = db.search_person(email_address=address, registered=True)
            if not person:
                message = 'No registered users found with this email address'
            elif len(person) > 1:
                message = 'There are multiple registered users with this' \
                    ' email address.  Please specify your user name.'
            else:
                user_id = person.values()[0].user_id
                token = db.get_password_reset_token(user_id)
                flash('Your password reset code has been sent by email.')
                raise HTTPRedirect(url_for('.use_password_reset_token'))
        else:
            message = 'Please enter either a user name or email address.'

    return {
        'title': 'Reset Password',
        'message': message,
    }


def use_password_reset_token(db, form, is_post):
    message = None

    if is_post:
        try:
            token = form['token']
            password = form['password']
            if password != form['password_check']:
                raise UserError('The passwords did not match.')
            user_id = db.use_password_reset_token(token)
            if user_id is None:
                raise UserError('Your reset code was not recognised. '
                                'It may have expired or been superceded by '
                                'a newer reset code.')
            db.update_user_password(user_id, password)
            flash('Your password has been changed.'
                  ' You may now log in using your new password.')
            raise HTTPRedirect(url_for(
                '.log_in', user_name=db.get_user_name(user_id)))

        except UserError as e:
            message = e.message

    return {
        'title': 'Use Password Reset Code',
        'message': message,
    }


def register_person(db, form, is_post):
    if 'person' in session:
        raise ErrorPage('You have already created a profile')

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
            _update_session_person(db.get_person(person_id))
            raise HTTPRedirect(url_for('.edit_person_institution',
                                       person_id=person_id))

    return {
        'title': 'Create Profile',
        'target': '.register_person',
        'message': message,
        'person_name': name,
        'person_public': public,
        'single_email': email
    }


def view_person(db, person_id):
    try:
        person = db.get_person(person_id,
                               with_institution=True, with_email=True)
    except NoSuchRecord:
        raise HTTPNotFound('Person profile not found.')

    is_current_user = person.user_id == session['user_id']

    if not is_current_user and not person.public:
        raise HTTPForbidden('Permission denied for this person profile.')

    person = person._replace(email=filter(
        (lambda x: x.public or is_current_user), person.email.values()))

    return {
        'title': 'Profile',
        'is_current_user': is_current_user,
        'person': person,
    }


def edit_person_institution(db, person_id, form, is_post):
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
            _update_session_person(db.get_person(person_id))
            flash('Your institution has been selected.')
            raise HTTPRedirect(session.pop(
                'log_in_for',
                url_for('.view_person', person_id=person_id)))

        elif 'submit_add' in form:
            if not name:
                message = 'Please enter the institution name.'
            else:
                institution_id = db.add_institution(name)
                db.update_person(person_id, institution_id=institution_id)
                _update_session_person(db.get_person(person_id))
                flash('Your new institution has been recorded.')
                raise HTTPRedirect(session.pop(
                    'log_in_for',
                    url_for('.view_person', person_id=person_id)))

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


def view_institution(db, institution_id):
    try:
        institution = db.get_institution(institution_id)
    except NoSuchRecord:
        raise HTTPNotFound('Institution not found.')

    if 'person' in session:
        user_institution_id = session['person']['institution_id']
    else:
        user_institution_id = None

    return {
        'title': 'Institution',
        'institution': institution,
        'can_edit': (user_institution_id is not None and
                     user_institution_id == institution_id),
    }


def edit_institution(db, institution_id, form, is_post):
    try:
        institution = db.get_institution(institution_id)
    except NoSuchRecord:
        raise HTTPNotFound('Institution not found.')

    if 'person' in session:
        user_institution_id = session['person']['institution_id']
    else:
        user_institution_id = None

    if user_institution_id is None or user_institution_id != institution_id:
        raise HTTPForbidden('Permission denied for editing this institution.')

    show_confirm_prompt = True
    message = None

    if is_post:
        if 'submit-confirm' in form:
            show_confirm_prompt = False
        elif 'submit-edit' in form:
            name = form['name']

            try:
                if not name:
                    raise UserError('Please enter the institution name.')
                db.update_institution(institution_id, name=name)
                flash('The institution\'s record has been updated.')
                raise HTTPRedirect(url_for('.view_institution',
                                           institution_id=institution_id))
            except UserError as e:
                message = e.message
                show_confirm_prompt = False
        else:
            raise ErrorPage('Unknown action.')

    return {
        'title': 'Edit Institution',
        'show_confirm_prompt': show_confirm_prompt,
        'message': message,
        'institution_id': institution_id,
        'institution': institution,
    }


def _update_session_person(person):
    session['person'] = person._asdict()
