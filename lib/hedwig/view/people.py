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

from collections import OrderedDict, namedtuple
from datetime import datetime

have_user_agents = False
try:
    from user_agents import parse as user_agents_parse
    have_user_agents = True
except ImportError:
    pass

from ..config import get_config
from ..email.format import render_email_template
from ..error import ConsistencyError, DatabaseIntegrityError, Error, \
    MultipleRecords, NoSuchRecord, NoSuchValue, \
    UserError
from ..type.collection import EmailCollection, GroupMemberCollection, \
    ProposalCollection, ReviewerCollection
from ..type.enum import LogEventLevel, \
    PermissionType, PersonLogEvent, PersonTitle, ProposalState, \
    ReviewState, UserLogEvent
from ..type.simple import Email, \
    Institution, InstitutionLog, Person, ProposalWithCode
from ..type.util import null_tuple, with_deadline
from ..view.util import int_or_none
from ..web.util import flash, session, url_for, url_add_args, url_relative, \
    ErrorPage, HTTPError, HTTPForbidden, HTTPNotFound, HTTPRedirect
from .util import with_institution, with_person, with_user
from . import auth


InstitutionLogExtra = namedtuple(
    'InstitutionLogExtra',
    InstitutionLog._fields + ('new',))

GroupsByFacility = namedtuple(
    'GroupsByFacility',
    ('name', 'code', 'groups'))

ProposalsByFacility = namedtuple(
    'ProposalsByFacility',
    ('name', 'code', 'type_class', 'proposals'))

ReviewsByFacility = namedtuple(
    'ReviewsByFacility',
    ('name', 'code', 'role_class', 'proposals'))


class PeopleView(object):
    def log_in(self, db, args, form, remote_addr, remote_agent, referrer):
        if get_config().getboolean('status', 'disable_log_in'):
            raise ErrorPage(
                'Account log in is not available at this time.')

        message = None

        user_name = args.get('user_name', '')
        log_in_for = args.get('log_in_for', None)
        log_in_referrer = args.get('log_in_referrer', None)
        register_only = ('register_only' in args)

        if form is not None:
            try:
                user_name = form['user_name']
                log_in_for = form.get('log_in_for', None)
                log_in_referrer = form.get('log_in_referrer', None)
                register_only = ('register_only' in form)

                user_id = db.authenticate_user(
                    user_name, form['password'], remote_addr=remote_addr)

                if user_id is None:
                    raise UserError('User name or password not recognised.')
                else:
                    _update_session_user(
                        db, user_id, remote_addr=remote_addr,
                        remote_agent=remote_agent)
                    flash('You have been logged in.')

                    redirect_kwargs = {}
                    if register_only:
                        redirect_kwargs['register_only'] = 1
                    if log_in_for is None:
                        target = url_for('home.home_page')
                    else:
                        redirect_kwargs['log_in_for'] = log_in_for
                        target = log_in_for

                        if log_in_referrer is not None:
                            target = url_add_args(
                                target, log_in_referrer=log_in_referrer)

                    try:
                        person = db.search_person(user_id=user_id).get_single()
                    except NoSuchRecord:
                        if register_only:
                            # The user has no profile, but we specifically only
                            # wanted them to have a user account.  Redirect
                            # to the specified URL.
                            raise HTTPRedirect(target)

                        # If the user has no profile, take them to the profile
                        # registration page.
                        flash('It appears your registration was not complete. '
                              'Please complete your profile.')
                        raise HTTPRedirect(url_for(
                            '.register_person', **redirect_kwargs))
                    except MultipleRecords:
                        # Mutliple results should not be possible.
                        raise ErrorPage(
                            'Your account is associated with multiple '
                            'profiles.')

                    if not register_only:
                        if not person.verified:
                            # If the user is not verified, take them to the
                            # primary address verification page.
                            flash(
                                'It appears your registration was not complete. '
                                'Please verify your email address.')
                            raise HTTPRedirect(url_for(
                                '.person_email_verify_primary',
                                **redirect_kwargs))

                        if person.institution_id is None:
                            # If the user has no institution, take them to the
                            # institution selection page.
                            flash(
                                'It appears your registration was not complete. '
                                'Please select your institution.')
                            raise HTTPRedirect(url_for(
                                '.person_edit_institution',
                                person_id=person.id, **redirect_kwargs))

                    raise HTTPRedirect(target)

            except UserError as e:
                message = e.message

        elif (referrer is not None) and (log_in_for is None):
            log_in_for = url_relative(referrer)

        return {
            'title': 'Log in',
            'message':  message,
            'user_name': user_name,
            'log_in_for': log_in_for,
            'log_in_referrer': log_in_referrer,
            'register_only': register_only,
        }

    def log_out(self, current_user, db):
        token = session.get('token')
        if token is not None:
            db.delete_auth_token(token=token)

        session.clear()

        flash('You have been logged out.')
        raise HTTPRedirect(url_for('home.home_page'))

    def register_user(self, db, args, form, remote_addr, remote_agent):
        if get_config().getboolean('status', 'disable_register'):
            raise ErrorPage(
                'Account registration is not available at this time.')

        message = None

        user_name = ''
        log_in_for = args.get('log_in_for', None)
        register_only = ('register_only' in args)

        if form is not None:
            try:
                log_in_for = form.get('log_in_for', None)
                register_only = ('register_only' in form)

                user_name = form['user_name']
                password = form['password']
                if password != form['password_check']:
                    raise UserError('The passwords did not match.')
                user_id = db.add_user(user_name, password,
                                      remote_addr=remote_addr)

                _update_session_user(
                    db, user_id, remote_addr=remote_addr,
                    remote_agent=remote_agent)

                flash('Your user account has been created.')

                # If we only wanted them to make a user account, go to the
                # next URL, otherwise go to the profile creation page.
                if register_only and (log_in_for is not None):
                    raise HTTPRedirect(log_in_for)

                raise HTTPRedirect(url_for(
                    '.register_person', log_in_for=log_in_for))

            except UserError as e:
                message = e.message

        return {
            'title': 'Register',
            'message':  message,
            'user_name': user_name,
            'log_in_for': log_in_for,
            'register_only': register_only,
        }

    def change_user_name(self, current_user, db, form, remote_addr):
        message = None
        user_id = current_user.user.id

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
                if current_user.person is not None:
                    raise HTTPRedirect(url_for(
                        '.person_view', person_id=current_user.person.id))
                else:
                    raise HTTPRedirect(url_for('home.home_page'))

            except UserError as e:
                message = e.message

        else:
            user_name = db.get_user_name(user_id)

        return {
            'title': 'Change User Name',
            'message': message,
            'user_name': user_name,
        }

    def change_password(self, current_user, db, form, remote_addr):
        message = None

        if form is not None:
            try:
                user_id = current_user.user.id
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

                if current_user.person is not None:
                    raise HTTPRedirect(url_for(
                        '.person_view', person_id=current_user.person.id))
                else:
                    raise HTTPRedirect(url_for('home.home_page'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Change Password',
            'message': message,
        }

    def password_reset_token_get(self, db, args, form, remote_addr):
        if get_config().getboolean('status', 'disable_reset_password'):
            raise ErrorPage(
                'Password reset is not available at this time.')

        message = None

        log_in_for = args.get('log_in_for', None)

        if form is not None:
            user_name = form['user_name']
            email_address = form['email']
            log_in_for = form.get('log_in_for', None)

            try:
                user_id = None

                if user_name:
                    try:
                        user_id = db.get_user_id(user_name)
                    except NoSuchRecord:
                        # TODO: delay or rate-check before showing this?
                        raise UserError(
                            'No user account was found matching the '
                            'information you provided.')

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
                            'No user account was found matching the '
                            'information you provided.')

                    except MultipleRecords:
                        # This shouldn't happen if they did enter a user name,
                        # so there is no need to check whether they did to
                        # decide what to suggest.
                        raise UserError(
                            'Your account could not be uniquely identified '
                            'from the information you have entered.  Please '
                            'try to be more specific: include your user name '
                            'if you remember it, or use an email address '
                            'which is not used by other accounts.')

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
                    except NoSuchValue:
                        raise HTTPError('Could not get primary email.')

                    show_email_address = 'your primary address'

                else:
                    raise UserError(
                        'Please enter either a user name or email address.')

                (token, expiry) = db.issue_password_reset_token(
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
                      ' to {}.'.format(show_email_address))
                raise HTTPRedirect(url_for(
                    '.password_reset_token_use', log_in_for=log_in_for))

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
            'log_in_for': log_in_for,
        }

    def password_reset_token_use(self, db, args, form, remote_addr):
        if get_config().getboolean('status', 'disable_reset_password'):
            raise ErrorPage(
                'Password reset is not available at this time.')

        message = None
        token = args.get('token', '')
        log_in_for = args.get('log_in_for', None)

        if form is not None:
            try:
                token = form['token'].strip()
                password = form['password']
                log_in_for = form.get('log_in_for', None)

                if password != form['password_check']:
                    raise UserError('The passwords did not match.')

                try:
                    user_name = db.use_password_reset_token(
                        token, password, remote_addr=remote_addr)
                except NoSuchRecord:
                    raise UserError('Your reset code was not recognised. '
                                    'It may have expired or been superceded '
                                    'by a newer reset code.')

                flash('Your password has been changed.'
                      ' You may now log in using your new password.')

                raise HTTPRedirect(url_for(
                    '.log_in', user_name=user_name, log_in_for=(
                        log_in_for if log_in_for is not None else
                        url_for('home.home_page'))))

            except UserError as e:
                message = e.message

        return {
            'title': 'Use Password Reset Code',
            'message': message,
            'token': token,
            'log_in_for': log_in_for,
        }

    def take_admin(self, current_user, db, args, referrer):
        session['is_admin'] = True
        flash('You have taken administrative privileges.')

        target = args.get('log_in_referrer', None)
        if target is None:
            target = referrer if referrer else url_for('home.home_page')
        raise HTTPRedirect(target)

    def drop_admin(self, current_user, referrer):
        session.pop('is_admin', None)
        flash('You have dropped administrative privileges.')
        raise HTTPRedirect(referrer if referrer else url_for('home.home_page'))

    @with_user()
    def user_log(self, current_user, db, user, person, name, args):
        level = (
            int(args['level']) if 'level' in args
            else LogEventLevel.INTERMEDIATE)

        events = db.search_user_log(
            user_id=user.id, event=UserLogEvent.events_of_level(level))

        return {
            'title': '{}: Account Log'.format(name),
            'user': user,
            'person': person,
            'events': events,
            'level': level,
            'levels': LogEventLevel.get_options(),
        }

    @with_user()
    def user_enable_disable(
            self, current_user, db, user, person, name, disabled, form):
        if disabled:
            action = 'disable'
            if user.disabled:
                raise ErrorPage('Account already disabled.')

        else:
            action = 'enable'
            if not user.disabled:
                raise ErrorPage('Account already enabled.')

        if form is not None:
            if 'submit_confirm' in form:
                db.update_user(user_id=user.id, disabled=disabled)

                flash('Account {}d.'.format(action))

            raise HTTPRedirect(url_for('.user_log', user_id=user.id))

        return {
            'title': '{}: {} Account'.format(name, action.title()),
            'message': 'Are you sure you wish to {} this account?'.format(action),
            'target': url_for(
                ('.user_disable' if disabled else '.user_enable'),
                user_id=user.id),
        }

    def user_session_list(self, current_user, db):
        sessions = db.search_auth_token()

        return {
            'title': 'Log in sessions',
            'sessions': sessions.map_values(
                lambda x: x._replace(remote_agent=(
                    user_agents_parse(x.remote_agent)
                    if have_user_agents else None))
            ),
        }

    def user_session_log_out(self, current_user, db, auth_token_id, form):
        if form:
            if 'submit_confirm' in form:
                if auth_token_id is None:
                    db.delete_auth_token(
                        auth_token_id_not=current_user.auth_token_id)
                else:
                    db.delete_auth_token(auth_token_id=auth_token_id)

            raise HTTPRedirect(url_for('.user_session_list'))

        if auth_token_id is None:
            return {
                'title': 'Log out sessions',
                'message': 'Log out all other sessions?',
            }
        else:
            return {
                'title': 'Log out session',
                'message': 'Log out user session?',
            }

    def register_person(self, current_user, db, args, form, remote_addr):
        if current_user.person is not None:
            raise ErrorPage('You have already created a profile.')

        message = None

        person = null_tuple(Person)._replace(name='', public=False)

        log_in_for = args.get('log_in_for', None)

        if form is not None:
            log_in_for = form.get('log_in_for', None)

            person = person._replace(
                name=form['person_name'].strip(),
                title=int_or_none(form['person_title']),
                public=('person_public' in form))
            email = form['single_email'].strip()

            try:
                if not person.name:
                    raise UserError('Please enter your full name.')
                elif not email:
                    raise UserError('Please enter your email address.')

                person_id = db.add_person(
                    person.name, title=person.title, public=person.public,
                    user_id=current_user.user.id, remote_addr=remote_addr,
                    primary_email=email)
                flash('Your user profile has been saved.')

                raise HTTPRedirect(url_for(
                    '.person_email_verify_primary',
                    log_in_for=log_in_for))

            except UserError as e:
                message = e.message

        else:
            email = ''

        return {
            'title': 'Create Profile',
            'target': url_for('.register_person'),
            'message': message,
            'person': person,
            'single_email': email,
            'titles': PersonTitle.get_options(),
            'log_in_for': log_in_for,
        }

    def person_list(self, current_user, db, args):
        # Only show public, registered members unless the user has
        # suitable authorization.
        public = True
        can_view_unregistered = False
        registered = True
        if auth.for_person(current_user, db, None).view:
            public = None
            can_view_unregistered = True
            registered = int_or_none(args.get('registered', '1'))

        persons = db.search_person(registered=registered, public=public,
                                   with_institution=True)

        return {
            'title': 'Directory of Users',
            'persons': persons,
            'can_view_unregistered': can_view_unregistered,
            'registered': registered,
        }

    @with_person(permission=PermissionType.VIEW)
    def person_view(self, current_user, db, person, can, facilities):
        is_admin = current_user.is_admin
        is_current_user = (person.user_id == current_user.user.id)

        # Show all email addresses if:
        # * It's your own profile.
        # * You're an administrator. (Not double-checked here but
        #   "auth.for_person" would have.)
        # * The user is unregistered but you can edit. (You're a co-member
        #   editor.)
        view_all_email = (
            is_current_user
            or is_admin
            or ((person.user_id is None) and can.edit))

        person = person._replace(
            email=[x for x in person.email.values()
                   if x.public or view_all_email])

        site_group_membership = None
        review_group_membership = []
        if is_admin:
            site_group_membership = db.search_site_group_member(
                person_id=person.id)
            all_review_group_membership = db.search_group_member(
                person_id=person.id, with_queue=True)

            for facility in facilities.values():
                facility_members = all_review_group_membership.map_values(
                    filter_value=(lambda x: x.facility_id == facility.id))

                if not facility_members:
                    continue

                review_group_membership.append(GroupsByFacility(
                    facility.name, facility.code, facility_members))

        return {
            'title': '{}: Profile'.format(person.name),
            'is_current_user': is_current_user,
            'can_edit': can.edit,
            'person': person,
            'show_admin_links': is_admin,
            'show_viewer_links': auth.for_person(
                current_user, db, None, auth_cache=can.cache).view,
            'site_group_membership': site_group_membership,
            'review_group_membership': review_group_membership,
        }

    @with_person(permission=PermissionType.NONE)
    def person_invite(self, current_user, db, person, args, form):
        if person.user_id is not None:
            raise ErrorPage('This user is already registered.')

        if form:
            if 'submit_confirm' in form:
                application_name = get_config().get('application', 'name')

                (token, expiry) = db.issue_invitation(person.id)

                db.add_message(
                    'Invitation to register with {}'.format(application_name),
                    render_email_template('administrative_invitation.txt', {
                        'recipient_name': person.name,
                        'inviter_name': current_user.person.name,
                        'token': token,
                        'expiry': expiry,
                        'target_url': url_for(
                            'people.invitation_token_enter', token=token,
                            _external=True),
                        'target_plain': url_for(
                            'people.invitation_token_enter',
                            _external=True),
                    }),
                    [person.id])

                flash('{} has been invited to register.', person.name)

            raise HTTPRedirect(url_for('.person_view', person_id=person.id))

        return {
            'title': '{}: Invite to Register'.format(person.name),
            'message': 'Would you like to send an administrative invitation '
            'to register to {}?'.format(person.name),
        }

    @with_person(permission=PermissionType.EDIT)
    def person_edit(self, current_user, db, person, can, args, form):
        message = None

        if form is not None:
            person = person._replace(
                name=form['person_name'].strip(),
                title=int_or_none(form['person_title']),
                public=('person_public' in form))

            try:
                if not person.name:
                    raise UserError('Please enter your full name.')
                db.update_person(
                    person.id, name=person.name, title=person.title,
                    public=(person.public and person.user_id is not None))

                if current_user.user.id == person.user_id:
                    flash('Your user profile has been saved.')
                else:
                    flash('The user profile has been saved.')
                raise HTTPRedirect(url_for(
                    '.person_view', person_id=person.id))

            except UserError as e:
                message = e.message

        return {
            'title': '{}: Edit Profile'.format(person.name),
            'target': url_for('.person_edit', person_id=person.id),
            'message': message,
            'person': person,
            'titles': PersonTitle.get_options(),
            'log_in_for': None,
        }

    @with_person(permission=PermissionType.EDIT)
    def person_edit_institution(
            self, current_user, db, person, can, args, form):
        message = None

        # Accept either query argument "log_in_for" or "next_page"
        # to be used for subsequent navigation.
        next_page = args.get('next_page', args.get('log_in_for', None))

        is_current_user = (person.user_id == current_user.user.id)
        institutions = db.search_institution()

        # Prepare blank record for an institution to potentially be
        # added to the database.
        institution = Institution(
            id=None, name='', department='', organization='',
            address='', country='')

        if form is not None:
            try:
                next_page = form.get('next_page', None)

                if 'submit_select' in form:
                    institution_id = int(form['institution_id'])
                    if institution_id not in institutions:
                        raise HTTPError('Institution not found.')
                    db.update_person(person.id, institution_id=institution_id)
                    action = 'selected'

                elif 'submit_add' in form:
                    institution = institution._replace(
                        name=form['institution_name'].strip(),
                        department=form['department'].strip(),
                        organization=form['organization'].strip(),
                        address=form['address'],
                        country=form['country_code'])
                    if not institution.name:
                        raise UserError('Please enter the institution name.')
                    if not institution.country:
                        raise UserError(
                            'Please select the institution country.')

                    institution_id = db.add_institution(
                        institution.name, institution.department,
                        institution.organization,
                        institution.address, institution.country,
                        adder_person_id=current_user.person.id)
                    db.update_person(person.id, institution_id=institution_id)
                    action = 'recorded'

                else:
                    raise ErrorPage('Unknown action')

                if is_current_user:
                    flash('Your institution has been {}.', action)
                else:
                    flash('The institution has been {}.', action)

                # If an explicit "next page" has been set, go there now.
                if next_page is not None:
                    raise HTTPRedirect(next_page)

                raise HTTPRedirect(url_for(
                    '.person_view', person_id=person.id))

            except UserError as e:
                message = e.message

        title = 'Select Institution'

        if not (is_current_user and (person.institution_id is None)):
            title = '{}: {}'.format(person.name, title)

        return {
            'title': title,
            'message': message,
            'person': person,
            'institution': institution,
            'institution_id': person.institution_id,
            'institutions': institutions,
            'is_current_user': is_current_user,
            'next_page': next_page,
        }

    def person_edit_email_own(self, current_user, db, args, form):
        return self._person_edit_email(
            current_user, db, current_user.person, args, form)

    @with_person(permission=PermissionType.EDIT)
    def person_edit_email(self, current_user, db, person, can, form):
        return self._person_edit_email(
            current_user, db, person, None, form)

    def _person_edit_email(self, current_user, db, person, args, form):
        message = None
        is_current_user = True
        is_registration = False
        log_in_for = None

        if args is not None:
            is_registration = True
            log_in_for = args.get('log_in_for', None)
            records = db.search_email(person_id=person.id)

        else:
            is_current_user = (person.user_id == current_user.user.id)
            records = person.email

        if form is not None:
            try:
                log_in_for = form.get('log_in_for', None)

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
                            email_id, person.id, form[param].strip(),
                            is_primary, False, is_public)

                    else:
                        # Convert to integer so that it matches existing
                        # email records.
                        email_id = int(id_)

                        verified = False
                        if email_id in records:
                            verified = records[email_id].verified

                        updated_records[email_id] = Email(
                            email_id, person.id, form[param].strip(),
                            is_primary, verified, is_public)

                # Create new record collection: overwrite "records" variable
                # name so that, in case of failure, the form will display the
                # new records again for correction.
                records = EmailCollection.organize_collection(
                    updated_records, added_records)

                db.sync_person_email(person.id, records)

                if is_current_user:
                    flash('Your email addresses have been updated.')
                else:
                    flash('The email addresses have been updated.')

                if not is_registration:
                    raise HTTPRedirect(url_for(
                        '.person_view', person_id=person.id))
                else:
                    raise HTTPRedirect(url_for(
                        '.person_email_verify_primary', log_in_for=log_in_for))

            except UserError as e:
                message = e.message

        title = 'Edit Email Addresses'
        if not is_registration:
            title = '{}: {}'.format(person.name, title)

        return {
            'title': title,
            'message': message,
            'person': person,
            'emails': records,
            'target': (
                url_for('.person_edit_email_own') if is_registration else
                url_for('.person_edit_email', person_id=person.id)),
            'log_in_for': log_in_for,
        }

    def person_email_verify_get_primary(
            self, current_user, db, args, form, remote_addr):
        try:
            email = db.search_email(
                person_id=current_user.person.id).get_primary()
        except NoSuchValue:
            raise ErrorPage('No primary email address found.')

        return self._person_email_verify_get(
            current_user, db, current_user.person, email,
            args, form, remote_addr)

    @with_person(permission=PermissionType.EDIT)
    def person_email_verify_get(
            self, current_user, db, person, can, email_id, form, remote_addr):
        try:
            email = person.email[email_id]
        except KeyError:
            raise HTTPNotFound('Email address record not found.')

        if email.verified:
            raise ErrorPage(
                'The email address {} has already been verified.',
                email.address)

        return self._person_email_verify_get(
            current_user, db, person, email,
            None, form, remote_addr)

    def _person_email_verify_get(
            self, current_user, db, person, email, args, form, remote_addr):
        # Is this an automated request (args not None) as would be triggered
        # during registration or via require_auth?
        is_registration = False
        log_in_for = None

        if args is not None:
            is_registration = True
            log_in_for = args.get('log_in_for', None)

        if form is not None:
            log_in_for = form.get('log_in_for', None)

            try:
                (token, expiry) = db.issue_email_verify_token(
                    person.id, email.address, user_id=person.user_id,
                    remote_addr=remote_addr)

            except UserError as e:
                raise ErrorPage(e.message)

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
            flash('Your address verification code has been sent by email '
                  'to {}.', email.address)
            raise HTTPRedirect(url_for(
                '.person_email_verify_use', log_in_for=log_in_for))

        title = 'Verify Email Address'
        if not is_registration:
            title = '{}: {}'.format(person.name, title)

        return {
            'title': title,
            'person': person,
            'email': email,
            'is_registration': is_registration,
            'target': (
                url_for('.person_email_verify_primary')
                if is_registration else
                url_for(
                    '.person_email_verify_get',
                    person_id=person.id, email_id=email.id)),
            'log_in_for': log_in_for,
        }

    def person_email_verify_use(
            self, current_user, db, args, form, remote_addr):
        message = None
        token = args.get('token', '')
        log_in_for = args.get('log_in_for', None)

        person_id = current_user.person.id
        user_id = current_user.user.id

        if form is not None:
            log_in_for = form.get('log_in_for', None)
            token = form['token'].strip()

            try:
                try:
                    email_address = db.use_email_verify_token(
                        person_id, token, user_id=user_id,
                        remote_addr=remote_addr)

                except NoSuchRecord:
                    raise UserError(
                        'Your verification code was not recognised. '
                        'It may have expired or been superceded by '
                        'a newer verification code.')

                except ConsistencyError:
                    raise UserError(
                        'The email address to which this verification '
                        'code relates could not be found.  It may '
                        'have been changed or removed.')

                flash('Your email address {} has been verified.',
                      email_address)

                if current_user.person.institution_id is None:
                    raise HTTPRedirect(url_for(
                        '.person_edit_institution',
                        person_id=person_id, log_in_for=log_in_for))

                if log_in_for is not None:
                    raise HTTPRedirect(log_in_for)

                raise HTTPRedirect(url_for(
                    '.person_view', person_id=person_id))

            except UserError as e:
                message = e.message

        return {
            'title': 'Enter Email Verification Code',
            'message': message,
            'token': token,
            'log_in_for': log_in_for,
        }

    def person_proposals_own(self, current_user, db, facilities):
        return self._person_proposals(
            db, current_user.person.id, facilities, None, 'Your Proposals')

    @with_person(permission=PermissionType.UNIVERSAL_VIEW)
    def person_proposals_other(
            self, current_user, db, person, can, facilities):
        return self._person_proposals(
            db, person.id, facilities, person,
            '{}: Proposals'.format(person.name))

    def _person_proposals(self, db, person_id, facilities, person, title):
        all_proposals = db.search_proposal(person_id=person_id)

        proposals = []

        for facility in facilities.values():
            facility_proposals = ProposalCollection((
                (p.id, ProposalWithCode(
                    *p, code=facility.view.make_proposal_code(db, p)))
                for p in all_proposals.values_by_facility(facility.id)))

            if not facility_proposals:
                continue

            proposals.append(ProposalsByFacility(
                facility.name, facility.code, facility.view.get_call_types(),
                facility_proposals))

        return {
            'title': title,
            'proposals': proposals,
            'person': person,
        }

    def person_reviews_own(self, current_user, db, facilities):
        return self._person_reviews(
            current_user, db, current_user.person.id, facilities, None)

    @with_person(permission=PermissionType.UNIVERSAL_VIEW)
    def person_reviews_other(
            self, current_user, db, person, can, facilities, args):
        return self._person_reviews(
            current_user, db, person.id, facilities, person, as_admin=True,
            view_all=int_or_none(args.get('view_all', '0')),
            auth_cache=can.cache)

    def _person_reviews(self, current_user, db, person_id, facilities, person,
                        as_admin=False, view_all=None, auth_cache={}):
        # Get a list of proposals, in all review states, for which this
        # person has reviews.  (Will filter later to list only those
        # which are editable in each proposal's actual state.)
        all_proposals = db.search_proposal(
            reviewer_person_id=person_id,
            with_members=True,
            state=(None if view_all else ProposalState.review_states()))
        calls = set((x.call_id for x in all_proposals.values()))

        if as_admin:
            all_addable = None
        else:
            all_addable = auth.find_addable_reviews(
                current_user, db, facilities, auth_cache=auth_cache)
            calls.update((x.call_id for x in all_addable.values()))

        # Get the review deadlines for the calls of interest.
        deadlines = db.search_review_deadline(call_id=calls)

        # Organize proposals by facility and attach extra information
        # as necessary.  Note that we re-assemble the reviewers for each
        # proposal into a ReviewerCollection reviewers attribute, rather
        # than having multiple entries for each proposal with a single
        # reviewer attribute.  Conversely we switch from a MemberCollection
        # members attribute to a single member attribute (the PI).
        proposals = []

        for facility in facilities.values():
            role_class = facility.view.get_reviewer_roles()

            facility_proposals = ProposalCollection()

            for proposal in all_proposals.values_by_facility(facility.id):
                # Filter reviews by edit permission.  But show all reviews
                # when viewing the administrative version of this page,
                # and exclude rejected reviews otherwise.
                if as_admin or (auth.for_review(
                        role_class, current_user, db,
                        proposal.reviewer, proposal,
                        auth_cache=auth_cache,
                        allow_unaccepted=True).edit
                        and (proposal.reviewer.review_state
                             != ReviewState.REJECTED)):
                    if proposal.id in facility_proposals:
                        proposal_reviewers = \
                            facility_proposals[proposal.id].reviewers
                    else:
                        proposal_reviewers = ReviewerCollection()
                        facility_proposals[proposal.id] = ProposalWithCode(
                            *proposal,
                            code=facility.view.make_proposal_code(
                                db, proposal))._replace(
                            member=proposal.members.get_pi(default=None),
                            reviewers=proposal_reviewers,
                            members=None, reviewer=None)

                    proposal_reviewers[proposal.reviewer.id] = \
                        with_deadline(proposal.reviewer, deadlines.get_role(
                            proposal.reviewer.role, call_id=proposal.call_id,
                            default=None))

            if all_addable is not None:
                for proposal in all_addable.values_by_facility(facility.id):
                    if proposal.id in facility_proposals:
                        proposal_reviewers = \
                            facility_proposals[proposal.id].reviewers
                    else:
                        proposal_reviewers = ReviewerCollection()
                        facility_proposals[proposal.id] = ProposalWithCode(
                            *proposal,
                            code=facility.view.make_proposal_code(
                                db, proposal))._replace(
                            member=proposal.members.get_pi(default=None),
                            reviewers=proposal_reviewers,
                            members=None, reviewer=None)

                    for (i, reviewer) in enumerate(
                            proposal.reviewers.values()):
                        proposal_reviewers['addable_{}'.format(i)] = \
                            with_deadline(reviewer, deadlines.get_role(
                                reviewer.role, call_id=proposal.call_id,
                                default=None))

            # If, after filtering, no proposals are left, skip this facility.
            if not facility_proposals:
                continue

            proposals.append(ReviewsByFacility(
                facility.name, facility.code, role_class, facility_proposals))

        return {
            'title': ('Your Reviews' if (person is None)
                      else '{}: Reviews'.format(person.name)),
            'proposals': proposals,
            'person': person,
            'view_all': view_all,
        }

    @with_person(permission=PermissionType.NONE)
    def person_log(self, current_user, db, person, args):
        level = (
            int(args['level']) if 'level' in args
            else LogEventLevel.INTERMEDIATE)

        events = db.search_person_log(
            person_id=person.id, event=PersonLogEvent.events_of_level(level))

        return {
            'title': '{}: Action Log'.format(person.name),
            'person': person,
            'events': events,
            'level': level,
            'levels': LogEventLevel.get_options(),
        }

    @with_person(permission=PermissionType.NONE)
    def person_subsume(self, current_user, db, person, form):
        ctx = {
            'title': '{}: Subsume Duplicate'.format(person.name),
            'person': person,
        }

        if form is None:
            ctx.update({
                'show_confirm_prompt': False,
                'persons': [
                    p for p in db.search_person(
                        registered=True, with_institution=True).values()
                    if p.id != person.id],
            })

        else:
            duplicate_id = int(form['duplicate_id'])

            if duplicate_id == person.id:
                raise ErrorPage('Main and duplicate identifiers are the same.')

            try:
                duplicate = db.get_person(
                    person_id=duplicate_id,
                    with_institution=True, with_email=True)
            except NoSuchRecord:
                raise HTTPError('Duplicate person profile not found.')

            assert duplicate.id == duplicate_id

            if 'submit_cancel' in form:
                raise HTTPRedirect(url_for('.person_view',
                                           person_id=person.id))

            elif 'submit_confirm' in form:
                try:
                    db.merge_person_records(
                        main_person_id=person.id,
                        duplicate_person_id=duplicate.id,
                        duplicate_person_registered=True)
                except DatabaseIntegrityError:
                    raise ErrorPage(
                        'The profiles could not be merged. They may be '
                        'members/reviewers of the same proposal or '
                        'members of the same review group.')

                flash('The person profiles have been merged.')

                raise HTTPRedirect(url_for('.person_view',
                                           person_id=person.id))

            else:
                user_name = None
                if person.user_id is not None:
                    try:
                        user_name = db.get_user_name(user_id=person.user_id)
                    except NoSuchRecord:
                        pass

                duplicate_user_name = None
                if duplicate.user_id is not None:
                    try:
                        duplicate_user_name = db.get_user_name(
                            user_id=duplicate.user_id)
                    except NoSuchRecord:
                        pass

                ctx.update({
                    'show_confirm_prompt': True,
                    'duplicate': duplicate,
                    'duplicate_user_name': duplicate_user_name,
                    'user_name': user_name,
                })

        return ctx

    def institution_list(self, current_user, db):
        return {
            'title': 'Institutions',
            'institutions': db.search_institution(),
        }

    @with_institution(permission=PermissionType.VIEW)
    def institution_view(self, current_user, db, institution, can):
        # Only show public, registered members unless the user has
        # suitable authorization.
        public = True
        registered = True
        is_admin = current_user.is_admin
        if auth.for_person(current_user, db, None, auth_cache=can.cache).view:
            public = None
            registered = None

        persons = db.search_person(institution_id=institution.id,
                                   registered=registered, public=public)

        return {
            'title': 'Institution: {}'.format(institution.name),
            'institution': institution,
            'can_edit': can.edit,
            'persons': persons,
            'show_admin_links': is_admin,
        }

    @with_institution(permission=PermissionType.EDIT)
    def institution_edit(self, current_user, db, institution, can, form):
        show_confirm_prompt = True
        message = None
        person_affected_list = []
        person_affected_other = 0

        if form is not None:
            if 'submit_confirm' in form:
                show_confirm_prompt = False
            elif 'submit_cancel' in form:
                raise HTTPRedirect(url_for('.institution_view',
                                           institution_id=institution.id))
            elif 'submit_edit' in form:
                try:
                    institution = institution._replace(
                        name=form['institution_name'].strip(),
                        department=form['department'].strip(),
                        organization=form['organization'].strip(),
                        address=form['address'],
                        country=form['country_code'])
                    if not institution.name:
                        raise UserError('Please enter the institution name.')
                    if not institution.country:
                        raise UserError(
                            'Please select the institution country.')

                    # If the user is making the update as an administrator,
                    # mark the update as already approved in the edit log.
                    log_approved = current_user.is_admin

                    db.update_institution(
                        institution.id,
                        updater_person_id=current_user.person.id,
                        name=institution.name,
                        department=institution.department,
                        organization=institution.organization,
                        address=institution.address,
                        country=institution.country,
                        log_approved=log_approved)
                    flash('The institution\'s record has been updated.')
                    raise HTTPRedirect(url_for('.institution_view',
                                               institution_id=institution.id))
                except UserError as e:
                    message = e.message
                    show_confirm_prompt = False
            else:
                raise ErrorPage('Unknown action.')

        if show_confirm_prompt:
            # Get information to show about the people who will be affected.
            # Fetch all users for the institution and then split into
            # public, registered people and a simple count of the others.
            for person in db.search_person(
                    institution_id=institution.id).values():
                if person.id == current_user.person.id:
                    continue

                if person.public and (person.user_id is not None):
                    person_affected_list.append(person)
                else:
                    person_affected_other += 1

        return {
            'title': 'Edit Institution: {}'.format(institution.name),
            'show_confirm_prompt': show_confirm_prompt,
            'message': message,
            'person_affected_list': person_affected_list,
            'person_affected_other': person_affected_other,
            'institution_id': institution.id,
            'institution': institution,
        }

    def institution_log(self, current_user, db, institution_id, form):
        return self._display_institution_log(db, institution_id, form)

    def institution_log_approval(self, current_user, db, form):
        return self._display_institution_log(db, None, form)

    def _display_institution_log(self, db, institution_id, form):
        if form is not None:
            approved = {}

            for param in form:
                if param.startswith('entry_'):
                    id_ = int(param[6:])
                    approved[id_] = ('approved_{}'.format(id_) in form)

            n_update = db.sync_institution_log_approval(approved)
            if n_update:
                flash(
                    'The institution edit log approval status has been saved.')

            if institution_id is None:
                raise HTTPRedirect(url_for('admin.admin_home'))
            else:
                raise HTTPRedirect(url_for('.institution_view',
                                           institution_id=int(institution_id)))

        current = {}

        if institution_id is None:
            institution = None

            raw_entries = db.search_institution_log(has_unapproved=True)

            title = 'Approve Institution Edits'

        else:
            try:
                institution = db.get_institution(institution_id)
            except NoSuchRecord:
                raise HTTPNotFound('Institution not found.')

            raw_entries = db.search_institution_log(
                institution_id=institution_id)

            current[institution_id] = institution

            title = 'Institution Edit Log: {}'.format(institution.name)

        entries = OrderedDict()

        for entry in raw_entries.values():
            if entry.institution_id in current:
                new = current[entry.institution_id]
            else:
                try:
                    new = db.get_institution(entry.institution_id)
                except NoSuchRecord:
                    raise HTTPError('Institution {} not found',
                                    entry.institution_id)

            # Only display non-approved entries if we are not displaying an
            # institution-specific log.
            if not (entry.approved and (institution_id is None)):
                if entry.institution_id in entries:
                    entry_list = entries[entry.institution_id]
                else:
                    entry_list = []
                    entries[entry.institution_id] = entry_list
                entry_list.append(InstitutionLogExtra(*entry, new=new))

            current[entry.institution_id] = entry.prev

        return {
            'title': title,
            'institution': institution,
            'entries': entries,
        }

    def institution_subsume(self, current_user, db, institution_id, form):
        try:
            institution = db.get_institution(institution_id)
        except NoSuchRecord:
            raise HTTPNotFound('Institution not found.')

        ctx = {
            'title': 'Subsume Duplicate: {}'.format(institution.name),
            'institution': institution,
        }

        if form is None:
            ctx.update({
                'show_confirm_prompt': False,
                'institutions': [
                    i for i in db.search_institution().values()
                    if i.id != institution_id]
            })

        else:
            duplicate_id = int(form['duplicate_id'])

            if duplicate_id == institution_id:
                raise ErrorPage('Main and duplicate identifiers are the same.')

            try:
                duplicate = db.get_institution(duplicate_id)
            except NoSuchRecord:
                raise HTTPError('Duplicate institution not found.')

            if 'submit_cancel' in form:
                raise HTTPRedirect(url_for('.institution_view',
                                           institution_id=institution_id))

            elif 'submit_confirm' in form:
                db.merge_institution_records(
                    main_institution_id=institution_id,
                    duplicate_institution_id=duplicate_id)

                flash('The institution records have been merged.')

                raise HTTPRedirect(url_for('.institution_view',
                                           institution_id=institution_id))

            else:
                ctx.update({
                    'show_confirm_prompt': True,
                    'duplicate_id': duplicate_id,
                    'duplicate': duplicate,
                })

        return ctx

    def invitation_token_enter(self, current_user, db, args):
        return {
            'title': 'Enter Invitation Code',
            'token': args.get('token', ''),
        }

    def invitation_token_accept(
            self, current_user, db, facilities, args, form, remote_addr):
        token = (form.get('token', None) if (form is not None)
                 else args.get('token', None))

        if token is None:
            # Token was lost somehow: redirect back to entry page.
            flash('Your invitation code was not received.  '
                  'Please enter it again.')
            raise HTTPRedirect(url_for('.invitation_token_enter'))

        token = token.strip()

        try:
            if form is not None:
                user_id = current_user.user.id
                if current_user.person is not None:
                    kwargs = {'new_person_id': current_user.person.id}
                else:
                    kwargs = {'user_id': user_id}

                old_person_record = db.use_invitation(
                    token, remote_addr=remote_addr, **kwargs)
                flash('The invitation has been accepted successfully.')
                person = db.search_person(user_id=user_id).get_single()

                target = self._determine_invitee_target(
                    db, facilities, old_person_record)

                if person.institution_id is None:
                    # If the user has no institution, take them to the
                    # institution selection page.
                    flash('Please select your institution.')
                    raise HTTPRedirect(url_for(
                        '.person_edit_institution',
                        person_id=person.id, log_in_for=target))

                # Redirect to the proposal/review, if we determined it,
                # otherwise the user profile page, which has links to
                # their proposal and review lists.
                raise HTTPRedirect(
                    target if target is not None else
                    url_for('.person_view', person_id=person.id))

            person = db.get_invitation_person(
                token, with_email=True, with_institution=True)

        except NoSuchRecord:
            raise ErrorPage('Your invitation code was not recognised. '
                            'It may have expired or been superceded by '
                            'a newer code.')

        except Error as e:
            # TODO: detect the "already a member" error specifically and avoid
            # it.  For now adding the note that this is a possible cause of
            # this error will have to suffice.
            raise ErrorPage('An error occurred while attempting to process '
                            'the invitation.  Perhaps you have been invited '
                            'to a proposal of which you are already a member?')

        return {
            'title': 'Accept Invitation',
            'token': token,
            'person': person,
        }

    def _determine_invitee_target(self, db, facilities, person):
        """
        Attempt to determine where to redirect, based on the "old"
        person record (from before invitation acceptance).

        Ideally there will only be one proposal or review associated
        with this person record.  If there are multiple proposals or
        multiple reviews, the person proposals / reviews page is returned.
        If there is a mixture of proposals or reviews (or none of either)
        then None is returned.
        """

        targets = []

        try:
            member = person.proposals.get_single()
            proposal_id = member.proposal_id
            code = facilities[db.get_proposal(
                None, proposal_id).facility_id].code
            targets.append(url_for(
                '{}.proposal_view'.format(code), proposal_id=proposal_id))

        except NoSuchRecord:
            pass
        except KeyError:
            pass
        except MultipleRecords:
            targets.append(url_for('.person_proposals'))

        try:
            reviewer = person.reviews.get_single()
            code = facilities[db.get_proposal(
                None, reviewer.proposal_id).facility_id].code
            targets.append(url_for(
                '{}.review_info'.format(code), reviewer_id=reviewer.id))

        except NoSuchRecord:
            pass
        except KeyError:
            pass
        except MultipleRecords:
            targets.append(url_for('.person_reviews'))

        # If we found a unique target, return it, otherwise return None.
        if len(targets) == 1:
            return targets[0]

        return None


def _update_session_user(
        db, user_id, sess=session, remote_addr=None, remote_agent=None):
    """
    Clears the session and inserts a token for the given user identifier.

    This should be done on log in to ensure that nothing from a
    previous session remains.
    """

    (token, expiry) = db.issue_auth_token(
        user_id, remote_addr=remote_addr, remote_agent=remote_agent)

    sess.clear()
    sess['token'] = token
