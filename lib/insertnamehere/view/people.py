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

from ..error import MultipleRecords, NoSuchRecord, UserError
from ..type import Email, EmailCollection
from ..web.util import flash, session, url_for, \
    ErrorPage, HTTPError, HTTPForbidden, HTTPNotFound, HTTPRedirect
from . import auth


def log_in(db, args, form, is_post, referrer):
    message = None

    if is_post:
        try:
            user_id = db.authenticate_user(form['user_name'], form['password'])

            if user_id is None:
                raise UserError('User name or password not recognised.')
            else:
                _update_session_user(user_id)
                flash('You have been logged in.')

                try:
                    person = db.search_person(user_id=user_id).get_single()
                except NoSuchRecord:
                    # If the user has no profile, take them to the profile
                    # registration page.
                    flash('It appears your registration was not complete. '
                          'If convenient, please complete your profile.')
                    raise HTTPRedirect(url_for('.register_person'))
                except MultipleRecords:
                    # Mutliple results should not be possible.
                    raise ErrorPage(
                        'Your account is associated with multiple profiles.')

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
    session.clear()
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
            _update_session_user(user_id)
            flash('Your user account has been created.')
            raise HTTPRedirect(url_for('.register_person'))

        except UserError as e:
            message = e.message

    return {
        'title': 'Register',
        'message':  message,
        'user_name': form.get('user_name', ''),
    }


def change_user_name(db, form, is_post):
    message = None
    user_id = session['user_id']

    if is_post:
        try:
            password = form['password']
            if db.authenticate_user(None, form['password'],
                                    user_id=user_id) is None:
                raise UserError(
                    'Your current password was entered incorrectly.')

            db.update_user_name(user_id, form['user_name'])
            flash('Your user name has been changed.')
            if 'person' in session:
                raise HTTPRedirect(url_for('.view_person',
                                           person_id=session['person']['id']))
            else:
                raise HTTPRedirect(url_for('home_page'))

        except UserError as e:
            message = e.message

    return {
        'title': 'Change User Name',
        'message': message,
        'user_name': form.get('user_name', db.get_user_name(user_id)),
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

    user_name = form.get('user_name', '')
    email_address = form.get('email', '')

    if is_post:
        try:
            user_id = None

            if user_name:
                try:
                    user_id = db.get_user_id(user_name)
                except NoSuchRecord:
                    # TODO: delay or rate-check before showing this?
                    raise UserError(
                        'No user account was found matching the information '
                        'you provided.')

            if email_address:
                # Look up person by email address.  If this succeeds then
                # we know the email address belongs to their account,
                # so we can send the token to it.
                try:
                    user_id = db.search_person(
                        email_address=email_address, user_id=user_id,
                        registered=True
                    ).get_single().user_id

                except NoSuchRecord:
                    raise UserError(
                        'No user account was found matching the information '
                        'you provided.')

                except MultipleRecords:
                    # This shouldn't happen if they did enter a user name,
                    # so there is no need to check whether they did to decide
                    # what to suggest.
                    raise UserError(
                        'Your account could not be uniquely identified from '
                        'the information you have entered.  Please try to '
                        'be more specific: include your user name if you '
                        'remember it, or use an email address which is not '
                        'used by other accounts.')

            elif user_id is not None:
                # They did specify a user name, so try to look up their
                # primary email address.
                try:
                    person = db.get_person(person_id=None, user_id=user_id,
                                           with_email=True)
                except NoSuchRecord:
                    raise ErrorPage(
                        'There is no email address associated with your '
                        'account, so it is not currently possible to '
                        'send you a password reset code.')

                try:
                    email_address = person.email.get_primary().address
                except KeyError:
                    raise HTTPError('Could not get primary email.')

            else:
                raise UserError(
                    'Please enter either a user name or email address.')

            token = db.get_password_reset_token(user_id)
            # TODO: email the token to: email_address
            flash('Your password reset code has been sent by email '
                  ' to "{0}".'.format(email_address))
            raise HTTPRedirect(url_for('.use_password_reset_token'))

        except UserError as e:
            message = e.message

    return {
        'title': 'Reset Password',
        'message': message,
        'user_name': user_name,
        'email': email_address,
    }


def use_password_reset_token(db, form, is_post):
    message = None

    if is_post:
        try:
            token = form['token']
            password = form['password']
            if password != form['password_check']:
                raise UserError('The passwords did not match.')
            try:
                user_id = db.use_password_reset_token(token)
            except NoSuchRecord:
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


def take_admin(db, referrer):
    if 'person' not in session or not session['person']['admin']:
        raise HTTPForbidden('Permission denied.')

    # Double-check the user still has administrative privileges.
    if not auth.can_be_admin(db):
        raise HTTPForbidden('Permission denied.')

    session['is_admin'] = True
    flash('You have taken administrative privileges.')
    raise HTTPRedirect(referrer if referrer else url_for('home_page'))


def drop_admin(referrer):
    session.pop('is_admin', None)
    flash('You have dropped administrative privileges.')
    raise HTTPRedirect(referrer if referrer else url_for('home_page'))


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
        'target': url_for('.register_person'),
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

    can = auth.for_person(db, person)

    if not can.view:
        raise HTTPForbidden('Permission denied for this person profile.')

    is_current_user = person.user_id == session['user_id']
    person = person._replace(email=filter(
        (lambda x: x.public or is_current_user), person.email.values()))

    return {
        'title': 'Profile',
        'is_current_user': is_current_user,
        'can_edit': can.edit,
        'person': person,
    }


def edit_person(db, person_id, form, is_post):
    try:
        person = db.get_person(person_id)
    except NoSuchRecord:
        raise HTTPNotFound('Person profile not found.')
    if not auth.for_person(db, person).edit:
        raise HTTPForbidden('Permission denied for this person profile.')

    message = None

    name = form.get('person_name', person.name)
    public = ('person_public' in form) if is_post else person.public

    if is_post:
        name = form['person_name']
        try:
            if not name:
                raise UserError('Please enter your full name.')
            db.update_person(person_id, name=name, public=public)

            if session['user_id'] == person.user_id:
                flash('Your user profile has been saved.')
                _update_session_person(db.get_person(person_id))
            else:
                flash('The user profile has been saved.')
            raise HTTPRedirect(url_for('.view_person', person_id=person_id))

        except UserError as e:
            message = e.message

    return {
        'title': 'Edit Profile',
        'target': url_for('.edit_person', person_id=person_id),
        'message': message,
        'person_name': name,
        'person_public': public,
    }


def edit_person_institution(db, person_id, form, is_post):
    try:
        person = db.get_person(person_id)
    except NoSuchRecord:
        raise HTTPNotFound('Person profile not found.')
    if not auth.for_person(db, person).edit:
        raise HTTPForbidden('Permission denied for this person profile.')

    message = None

    is_current_user = person.user_id == session['user_id']
    name = form.get('institution_name', '')
    institutions = db.list_institution()

    if is_post:
        if 'submit_select' in form:
            institution_id = int(form['institution_id'])
            if institution_id not in institutions:
                raise HTTPError('Institution not found.')
            db.update_person(person_id, institution_id=institution_id)
            action = 'selected'

        elif 'submit_add' in form:
            if not name:
                message = 'Please enter the institution name.'
            else:
                institution_id = db.add_institution(name)
                db.update_person(person_id, institution_id=institution_id)
                action = 'recorded'

        else:
            raise ErrorPage('Unknown action')

        if is_current_user:
            _update_session_person(db.get_person(person_id))
            flash('Your institution has been {0}.'.format(action))
        else:
            flash('The institution has been {0}.'.format(action))

        raise HTTPRedirect(session.pop(
            'log_in_for',
            url_for('.view_person', person_id=person_id)))

    return {
        'title': 'Select Institution',
        'message': message,
        'person_id': person_id,
        'institution_name': name,
        'institution_id': person.institution_id,
        'institutions': institutions.values(),
    }


def edit_person_email(db, person_id, form, is_post):
    try:
        person = db.get_person(person_id, with_email=True)
    except NoSuchRecord:
        raise HTTPNotFound('Person profile not found.')
    if not auth.for_person(db, person).edit:
        raise HTTPForbidden('Permission denied for this person profile.')

    message = None
    is_current_user = person.user_id == session['user_id']
    records = person.email

    if is_post:
        try:
            # Temporary (unsorted) dictionaries for new records.
            updated_records = {}
            added_records = {}

            # Which is the primary address?
            primary = form['primary']

            for param in form:
                if not param.startswith('email_'):
                    continue
                id_ = param[6:]

                is_primary = primary == id_
                is_public = ('public_' + id_) in form

                if id_.startswith('new_'):
                    # Temporarily use the "new" number.
                    email_id = int(id_[4:])
                    added_records[email_id] = Email(
                        email_id, person_id, form[param],
                        is_primary, False, is_public)

                else:
                    # Convert to integer so that it matches existing
                    # email records.
                    email_id = int(id_)

                    verified = False
                    if email_id in person.email:
                        verified = person.email[email_id].verified

                    updated_records[email_id] = Email(
                        email_id, person_id, form[param],
                        is_primary, verified, is_public)

            # Create new record collection: overwrite "records" variable
            # name so that, in case of failure, the form will display the
            # new records again for correction.
            records = EmailCollection(map((lambda x: (x, updated_records[x])),
                                          sorted(updated_records.keys())))
            # Number the newly-added addresses upwards from the existing max.
            max_record = max(records.keys()) if records else 0
            for email_id in sorted(added_records.keys()):
                new_email_id = max_record + email_id
                records[new_email_id] = \
                    added_records[email_id]._replace(id=new_email_id)

            db.sync_person_email(person_id, records)

            if is_current_user:
                flash('Your email addresses have been updated.')
                _update_session_person(db.get_person(person_id))
            else:
                flash('The email addresses have been updated.')
            raise HTTPRedirect(url_for('.view_person', person_id=person_id))

        except UserError as e:
            message = e.message

    return {
        'title': 'Edit Email Addresses',
        'message': message,
        'person_id': person_id,
        'emails': records.values(),
    }


def view_institution(db, institution_id):
    try:
        institution = db.get_institution(institution_id)
    except NoSuchRecord:
        raise HTTPNotFound('Institution not found.')

    can = auth.for_institution(db, institution)

    if not can.view:
        raise HTTPForbidden('Permission denied for this institution.')

    return {
        'title': 'Institution',
        'institution': institution,
        'can_edit': can.edit,
    }


def edit_institution(db, institution_id, form, is_post):
    try:
        institution = db.get_institution(institution_id)
    except NoSuchRecord:
        raise HTTPNotFound('Institution not found.')

    if not auth.for_institution(db, institution).edit:
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


def _update_session_user(user_id):
    """
    Clears the session and inserts the given user identifier.

    This should be done on log in to ensure that nothing from a
    previous session remains.

    Certain (white-listed) session entries are preserved, e.g.
    "log_in_for", which needs to persist through the log in process.
    """

    # Save the white-listed session entries.
    saved = {}
    for key in ('log_in_for',):
        if key in session:
            saved[key] = session[key]

    # Clear the session, restore saved entries, and log in.
    session.clear()
    session.update(saved)
    session['user_id'] = user_id


def _update_session_person(person):
    session['person'] = person._asdict()
