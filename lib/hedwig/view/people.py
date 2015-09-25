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

from datetime import datetime

from ..email.format import render_email_template
from ..error import ConsistencyError, Error, MultipleRecords, NoSuchRecord, \
    UserError
from ..type import Email, EmailCollection, Institution, Person, null_tuple
from ..util import get_countries
from ..web.util import flash, mangle_email_address, session, url_for, \
    ErrorPage, HTTPError, HTTPForbidden, HTTPNotFound, HTTPRedirect
from .util import organise_collection
from . import auth


def log_in(db, args, form, referrer):
    message = None

    user_name = args.get('user_name', '')

    if form is not None:
        try:
            user_name = form['user_name']
            user_id = db.authenticate_user(user_name, form['password'])

            if user_id is None:
                raise UserError('User name or password not recognised.')
            else:
                # Extract this session entry, if it exists, before clearing
                # the session on log-in.  (Not worth generally exempting
                # this entry from session clearning.)
                register_user_for = session.pop('register_user_for', None)

                _update_session_user(user_id)
                flash('You have been logged in.')

                try:
                    person = db.search_person(user_id=user_id).get_single()
                except NoSuchRecord:
                    if register_user_for is not None:
                        # The user has no profile, but we specifically only
                        # wanted them to have a user account.  Redirect
                        # to the specified URL.
                        raise HTTPRedirect(register_user_for)

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

                if register_user_for is not None:
                    # If we have this parameter, redirect there now.  (This
                    # entry will have been cleared from the session on log-in
                    # so do not redirect via any other pages first!)
                    raise HTTPRedirect(register_user_for)

                if person.institution_id is None:
                    # If the user has no institution, take them to the
                    # institution selection page.
                    flash('It appears your registration was not complete. '
                          'If convenient, please select your institution.')
                    raise HTTPRedirect(url_for('.person_edit_institution',
                                               person_id=person.id))
                raise HTTPRedirect(
                    session.pop('log_in_for', url_for('home_page')))

        except UserError as e:
            message = e.message

    elif ((referrer is not None) and
            ('log_in_for' not in session) and
            ('register_user_for' not in session)):
        session['log_in_for'] = referrer

    return {
        'title': 'Log in',
        'message':  message,
        'user_name': user_name,
        'without_links': False,
    }


def log_out():
    session.clear()
    flash('You have been logged out.')
    raise HTTPRedirect(url_for('home_page'))


def register_user(db, form, remote_addr):
    message = None

    user_name = ''

    if form is not None:
        try:
            user_name = form['user_name']
            password = form['password']
            if password != form['password_check']:
                raise UserError('The passwords did not match.')
            user_id = db.add_user(user_name, password, remote_addr=remote_addr)

            # Extract this session entry, if it exists, before logging in.
            register_user_for = session.pop('register_user_for', None)
            _update_session_user(user_id)
            flash('Your user account has been created.')

            # If we only wanted them to make a user account, go to the
            # next URL, otherwise go to the profile creation page.
            if register_user_for is not None:
                raise HTTPRedirect(register_user_for)
            raise HTTPRedirect(url_for('.register_person'))

        except UserError as e:
            message = e.message

    return {
        'title': 'Register',
        'message':  message,
        'user_name': user_name,
    }


def change_user_name(db, form, remote_addr):
    message = None
    user_id = session['user_id']

    if form is not None:
        try:
            user_name = form['user_name']
            password = form['password']
            if db.authenticate_user(None, form['password'],
                                    user_id=user_id) is None:
                raise UserError(
                    'Your current password was entered incorrectly.')

            db.update_user_name(user_id, user_name,
                                remote_addr=remote_addr)
            flash('Your user name has been changed.')
            if 'person' in session:
                raise HTTPRedirect(url_for('.person_view',
                                           person_id=session['person']['id']))
            else:
                raise HTTPRedirect(url_for('home_page'))

        except UserError as e:
            message = e.message

    else:
        user_name = db.get_user_name(user_id)

    return {
        'title': 'Change User Name',
        'message': message,
        'user_name': user_name,
    }


def change_password(db, form, remote_addr):
    message = None

    if form is not None:
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
            db.update_user_password(user_id, password_new,
                                    remote_addr=remote_addr)
            flash('Your password has been changed.')

            if 'person' in session:
                raise HTTPRedirect(url_for('.person_view',
                                           person_id=session['person']['id']))
            else:
                raise HTTPRedirect(url_for('home_page'))

        except UserError as e:
            message = e.message

    return {
        'title': 'Change Password',
        'message': message,
    }


def password_reset_token_get(db, form, remote_addr):
    message = None

    if form is not None:
        user_name = form['user_name']
        email_address = form['email']

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
                    person = db.search_person(
                        email_address=email_address, user_id=user_id,
                        registered=True
                    ).get_single()

                    user_id = person.user_id

                    show_email_address = email_address

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

                show_email_address = 'your primary address'

            else:
                raise UserError(
                    'Please enter either a user name or email address.')

            (token, expiry) = db.get_password_reset_token(
                user_id, remote_addr=remote_addr)
            db.add_message(
                'Password reset code',
                render_email_template('password_reset.txt', {
                    'recipient_name': person.name,
                    'token': token,
                    'expiry': expiry,
                    'target_url': url_for('.password_reset_token_use',
                                          token=token, _external=True),
                }),
                [person.id],
                email_addresses=[email_address])
            flash('Your password reset code has been sent by email '
                  ' to {0}.'.format(show_email_address))
            raise HTTPRedirect(url_for('.password_reset_token_use'))

        except UserError as e:
            message = e.message

    else:
        user_name = ''
        email_address = ''

    return {
        'title': 'Reset Password',
        'message': message,
        'user_name': user_name,
        'email': email_address,
    }


def password_reset_token_use(db, args, form, remote_addr):
    message = None
    token = args.get('token', '')

    if form is not None:
        try:
            token = form['token']
            password = form['password']
            if password != form['password_check']:
                raise UserError('The passwords did not match.')
            try:
                user_id = db.use_password_reset_token(token,
                                                      remote_addr=remote_addr)
            except NoSuchRecord:
                raise UserError('Your reset code was not recognised. '
                                'It may have expired or been superceded by '
                                'a newer reset code.')
            db.update_user_password(user_id, password, remote_addr=remote_addr)
            flash('Your password has been changed.'
                  ' You may now log in using your new password.')
            user_name = db.get_user_name(user_id)
            db.delete_auth_failure(user_name=user_name)
            raise HTTPRedirect(url_for('.log_in', user_name=user_name))

        except UserError as e:
            message = e.message

    return {
        'title': 'Use Password Reset Code',
        'message': message,
        'token': token,
    }


def take_admin(db, referrer):
    if 'person' not in session or not session['person']['admin']:
        raise HTTPForbidden('Permission denied.')

    # Double-check the user still has administrative privileges.
    if not auth.can_be_admin(db):
        raise HTTPForbidden('Permission denied.')

    session['is_admin'] = True
    flash('You have taken administrative privileges.')

    target = session.pop('log_in_referrer', None)
    if target is None:
        target = referrer if referrer else url_for('home_page')
    raise HTTPRedirect(target)


def drop_admin(referrer):
    session.pop('is_admin', None)
    flash('You have dropped administrative privileges.')
    raise HTTPRedirect(referrer if referrer else url_for('home_page'))


def register_person(db, form, remote_addr):
    if 'person' in session:
        raise ErrorPage('You have already created a profile')

    message = None

    person = null_tuple(Person)._replace(name='', public=False)

    if form is not None:
        person = person._replace(
            name=form['person_name'],
            public=('person_public' in form))
        email = form['single_email']

        try:
            if not person.name:
                raise UserError('Please enter your full name.')
            elif not email:
                raise UserError('Please enter your email address.')

            user_id = session['user_id']
            person_id = db.add_person(person.name, public=person.public,
                                      user_id=user_id, remote_addr=remote_addr)
            db.add_email(person_id, email, primary=True)
            flash('Your user profile has been saved.')
            _update_session_person(db.get_person(person_id))
            raise HTTPRedirect(url_for('.person_edit_institution',
                                       person_id=person_id))

        except UserError as e:
            message = e.message

    else:
        email = ''

    return {
        'title': 'Create Profile',
        'target': url_for('.register_person'),
        'message': message,
        'person': person,
        'single_email': email
    }


def person_list(db):
    # Only show public members unless the user is has administrative
    # privileges.
    public = True
    if session.get('is_admin', False) and auth.can_be_admin(db):
        public = None
    persons = db.search_person(registered=True, public=public,
                               with_institution=True)

    countries = get_countries()

    return {
        'title': 'Directory of Users',
        'persons': [
            p._replace(institution_country=countries.get(
                p.institution_country, 'Unknown country'))
            for p in persons.values()],
    }


def person_view(db, person_id):
    try:
        person = db.get_person(person_id,
                               with_institution=True, with_email=True)
    except NoSuchRecord:
        raise HTTPNotFound('Person profile not found.')

    can = auth.for_person(db, person)

    if not can.view:
        raise HTTPForbidden('Permission denied for this person profile.')

    is_current_user = person.user_id == session['user_id']

    # Show all email addresses if:
    # * It's your own profile.
    # * You're an administrator. (Not double-checked here but "auth.for_person"
    #   would have.)
    # * The user is unregistered but you can edit. (You're a co-member editor.)
    view_all_email = (
        is_current_user or
        session.get('is_admin', False) or
        ((person.user_id is None) and can.edit))

    person = person._replace(
        email=[x._replace(address=mangle_email_address(x.address))
               for x in person.email.values()
               if x.public or view_all_email])

    if person.institution is not None:
        person = person._replace(
            institution=person.institution._replace(
                country=get_countries().get(person.institution.country,
                                            'Unknown country')))

    return {
        'title': '{0}: Profile'.format(person.name),
        'is_current_user': is_current_user,
        'can_edit': can.edit,
        'person': person,
    }


def person_edit(db, person_id, form):
    try:
        person = db.get_person(person_id)
    except NoSuchRecord:
        raise HTTPNotFound('Person profile not found.')
    if not auth.for_person(db, person).edit:
        raise HTTPForbidden('Permission denied for this person profile.')

    message = None

    if form is not None:
        person = person._replace(
            name=form['person_name'],
            public=('person_public' in form))

        try:
            if not person.name:
                raise UserError('Please enter your full name.')
            db.update_person(
                person_id, name=person.name,
                public=(person.public and person.user_id is not None))

            if session['user_id'] == person.user_id:
                flash('Your user profile has been saved.')
                _update_session_person(db.get_person(person_id))
            else:
                flash('The user profile has been saved.')
            raise HTTPRedirect(url_for('.person_view', person_id=person_id))

        except UserError as e:
            message = e.message

    return {
        'title': '{0}: Edit Profile'.format(person.name),
        'target': url_for('.person_edit', person_id=person_id),
        'message': message,
        'person': person,
    }


def person_edit_institution(db, person_id, form):
    try:
        person = db.get_person(person_id)
    except NoSuchRecord:
        raise HTTPNotFound('Person profile not found.')
    if not auth.for_person(db, person).edit:
        raise HTTPForbidden('Permission denied for this person profile.')

    message = None

    is_current_user = person.user_id == session['user_id']
    institutions = db.list_institution()

    # Prepare blank record for an institution to potentially be
    # added to the database.
    institution = Institution(id=None, name='', department='', organization='',
                              address='', country='')

    if form is not None:
        try:
            if 'submit_select' in form:
                institution_id = int(form['institution_id'])
                if institution_id not in institutions:
                    raise HTTPError('Institution not found.')
                db.update_person(person_id, institution_id=institution_id)
                action = 'selected'

            elif 'submit_add' in form:
                institution = institution._replace(
                    name=form['institution_name'],
                    department=form['department'],
                    organization=form['organization'],
                    address=form['address'],
                    country=form['country_code'])
                if not institution.name:
                    raise UserError('Please enter the institution name.')
                if not institution.country:
                    raise UserError('Please select the institution country.')

                institution_id = db.add_institution(
                    institution.name, institution.department,
                    institution.organization,
                    institution.address, institution.country)
                db.update_person(person_id, institution_id=institution_id)
                action = 'recorded'

            else:
                raise ErrorPage('Unknown action')

            if is_current_user:
                _update_session_person(db.get_person(person_id))
                flash('Your institution has been {0}.', action)
            else:
                flash('The institution has been {0}.', action)

            # If an explicit "next page" has been set, go there now.
            if 'next_page' in session:
                raise HTTPRedirect(session.pop('next_page'))

            raise HTTPRedirect(session.pop(
                'log_in_for',
                url_for('.person_view', person_id=person_id)))

        except UserError as e:
            message = e.message

    return {
        'title': '{0}: Select Institution'.format(person.name),
        'message': message,
        'person': person,
        'institution': institution,
        'institution_id': person.institution_id,
        'institutions': [i._replace(
            country=get_countries().get(i.country, 'Unknown country'))
            for i in institutions.values()],
        'countries': get_countries(),
        'is_current_user': is_current_user,
    }


def person_edit_email(db, person_id, form):
    try:
        person = db.get_person(person_id, with_email=True)
    except NoSuchRecord:
        raise HTTPNotFound('Person profile not found.')
    if not auth.for_person(db, person).edit:
        raise HTTPForbidden('Permission denied for this person profile.')

    message = None
    is_current_user = person.user_id == session['user_id']
    records = person.email

    if form is not None:
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
            records = organise_collection(EmailCollection, updated_records,
                                          added_records)

            db.sync_person_email(person_id, records)

            if is_current_user:
                flash('Your email addresses have been updated.')
                _update_session_person(db.get_person(person_id))
            else:
                flash('The email addresses have been updated.')
            raise HTTPRedirect(url_for('.person_view', person_id=person_id))

        except UserError as e:
            message = e.message

    return {
        'title': '{0}: Edit Email Addresses'.format(person.name),
        'message': message,
        'person': person,
        'emails': records.values(),
    }


def person_email_verify_get(db, person_id, email_id, form):
    try:
        person = db.get_person(person_id, with_email=True)
    except NoSuchRecord:
        raise HTTPNotFound('Person profile not found.')
    if not auth.for_person(db, person).edit:
        raise HTTPForbidden('Permission denied for this person profile.')

    try:
        email = person.email[email_id]
    except KeyError:
        raise HTTPNotFound('Email address record not found.')

    if email.verified:
        raise ErrorPage('The email address {} has already been verified.',
                        email.address)

    if form:
        (token, expiry) = db.get_email_verify_token(person_id, email.address)
        db.add_message(
            'Email verification code',
            render_email_template('email_verify.txt', {
                'recipient_name': person.name,
                'token': token,
                'expiry': expiry,
                'target_url': url_for('.person_email_verify_use',
                                      token=token, _external=True),
            }),
            [person.id],
            email_addresses=[email.address])
        flash('Your address verification code has been sent by email to {}.',
              email.address)
        raise HTTPRedirect(url_for('.person_email_verify_use'))

    return {
        'title': '{}: Verify Email Address'.format(person.name),
        'person': person,
        'email': email,
    }


def person_email_verify_use(db, args, form):
    message = None
    token = args.get('token', '')
    person_id = session['person']['id']

    if form is not None:
        token = form['token']

        try:
            try:
                email_address = db.use_email_verify_token(person_id, token)

            except NoSuchRecord:
                raise UserError('Your verification code was not recognised. '
                                'It may have expired or been superceded by '
                                'a newer verification code.')

            except ConsistencyError:
                raise UserError('The email address to which this verification '
                                'code relates could not be found.  It may '
                                'have been changed or removed.')

            flash('Your email address {} has been verified.', email_address)
            raise HTTPRedirect(url_for('.person_view', person_id=person_id))

        except UserError as e:
            message = e.message

    return {
        'title': 'Enter Email Verification Code',
        'message': message,
        'token': token,
    }


def institution_list(db):
    countries = get_countries()

    return {
        'title': 'Institutions',
        'institutions': [
            x._replace(country=countries.get(x.country, 'Unknown country'))
            for x in db.list_institution().values()],
    }


def institution_view(db, institution_id):
    try:
        institution = db.get_institution(institution_id)
    except NoSuchRecord:
        raise HTTPNotFound('Institution not found.')

    can = auth.for_institution(db, institution)

    if not can.view:
        raise HTTPForbidden('Permission denied for this institution.')

    # Only show public members unless the user is has administrative
    # privileges.
    public = True
    if session.get('is_admin', False) and auth.can_be_admin(db):
        public = None
    persons = db.search_person(institution_id=institution_id,
                               registered=True, public=public)

    return {
        'title': 'Institution: {0}'.format(institution.name),
        'institution': institution._replace(
            country=get_countries().get(institution.country,
                                        'Unknown country')),
        'can_edit': can.edit,
        'persons': persons.values(),
    }


def institution_edit(db, institution_id, form):
    try:
        institution = db.get_institution(institution_id)
    except NoSuchRecord:
        raise HTTPNotFound('Institution not found.')

    if not auth.for_institution(db, institution).edit:
        raise HTTPForbidden('Permission denied for editing this institution.')

    show_confirm_prompt = True
    message = None

    if form is not None:
        if 'submit-confirm' in form:
            show_confirm_prompt = False
        elif 'submit_cancel' in form:
            raise HTTPRedirect(url_for('.institution_view',
                                       institution_id=institution_id))
        elif 'submit-edit' in form:
            try:
                institution = institution._replace(
                    name=form['institution_name'],
                    department=form['department'],
                    organization=form['organization'],
                    address=form['address'],
                    country=form['country_code'])
                if not institution.name:
                    raise UserError('Please enter the institution name.')
                if not institution.country:
                    raise UserError('Please select the institution country.')

                db.update_institution(
                    institution_id,
                    updater_person_id=session['person']['id'],
                    name=institution.name,
                    department=institution.department,
                    organization=institution.organization,
                    address=institution.address,
                    country=institution.country)
                flash('The institution\'s record has been updated.')
                raise HTTPRedirect(url_for('.institution_view',
                                           institution_id=institution_id))
            except UserError as e:
                message = e.message
                show_confirm_prompt = False
        else:
            raise ErrorPage('Unknown action.')

    return {
        'title': 'Edit Institution: {0}'.format(institution.name),
        'show_confirm_prompt': show_confirm_prompt,
        'message': message,
        'institution_id': institution_id,
        'institution': institution,
        'countries': get_countries(),
    }


def invitation_token_enter(db, args):
    return {
        'title': 'Enter Invitation Code',
        'token': args.get('token', ''),
    }


def invitation_token_accept(db, args, form, remote_addr):
    token = (form.get('token', None) if (form is not None)
             else args.get('token', None))

    if token is None:
        # Token was lost somehow: redirect back to entry page.
        flash('Your invitation code was not received.  Please enter it again.')
        raise HTTPRedirect(url_for('.invitation_token_enter'))

    try:
        if form is not None:
            # Re-fetch the current user's profile, in case they registered a
            # profile in another session.  We need to be sure we know whether
            # they are registered or not.
            user_id = session['user_id']
            try:
                person = db.get_person(person_id=None, user_id=user_id)
                kwargs = {'new_person_id': person.id}
            except NoSuchRecord:
                kwargs = {'user_id': user_id}

            old_person_record = db.use_invitation(
                token, remote_addr=remote_addr, **kwargs)
            flash('The invitation has been accepted successfully.')
            person = db.get_person(person_id=None, user_id=user_id)
            _update_session_person(person)

            # Attempt to determine where to redirect: ideally there will only
            # be one proposal or review associated with the old person record.
            target = None
            try:
                member = old_person_record.proposals.get_single()
                proposal_id = member.proposal_id
                code = db.get_proposal_facility_code(proposal_id)
                target = url_for('{0}.proposal_view'.format(code),
                                 proposal_id=proposal_id, first_view='true')
            except NoSuchRecord:
                pass
            except MultipleRecords:
                pass

            if target is None:
                try:
                    reviewer = old_person_record.reviews.get_single()
                    code = db.get_proposal_facility_code(reviewer.proposal_id)
                    target = url_for('{}.review_info'.format(code),
                                     reviewer_id=reviewer.id)

                except NoSuchRecord:
                    pass
                except MultipleRecords:
                    pass

            if person.institution_id is None:
                # If the user has no institution, take them to the
                # institution selection page.
                if target is not None:
                    session['next_page'] = target

                flash('Please select your institution.')
                raise HTTPRedirect(url_for('.person_edit_institution',
                                           person_id=person.id))

            # Redirect to the proposal/review, if we determined it, otherwise
            # the user profile page, which has links to their proposal and
            # review lists.
            raise HTTPRedirect(target if target is not None else
                               url_for('.person_view', person_id=person.id))

        person = db.get_invitation_person(
            token, with_email=True, with_institution=True)

    except NoSuchRecord:
        raise ErrorPage('Your invitation code was not recognised. '
                        'It may have expired or been superceded by '
                        'a newer code.')

    except Error as e:
        # TODO: detect the "already a member" error specifically and avoid
        # it.  For now adding the note that this is a possible cause of this
        # error will have to suffice.
        raise ErrorPage('An error occurred while attempting to process '
                        'the invitation.  Perhaps you have been invited '
                        'to a proposal of which you are already a member?')

    return {
        'title': 'Accept Invitation',
        'token': token,
        'person': person._replace(email=person.email.values())
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
    for key in ('log_in_for', 'log_in_referrer'):
        if key in session:
            saved[key] = session[key]

    # Clear the session, restore saved entries, and log in.
    session.clear()
    session.update(saved)
    session['user_id'] = user_id
    session['date_set'] = datetime.utcnow()


def _update_session_person(person):
    session['person'] = person._asdict()
