# Copyright (C) 2015-2017 East Asian Observatory
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

from ..config import get_countries
from ..email.format import render_email_template
from ..error import ConsistencyError, Error, MultipleRecords, NoSuchRecord, \
    UserError
from ..type.collection import EmailCollection, \
    ProposalCollection, ReviewerCollection
from ..type.enum import PermissionType, PersonTitle, ProposalState
from ..type.simple import Email, \
    Institution, InstitutionLog, Person, ProposalWithCode
from ..type.util import null_tuple
from ..web.util import flash, session, url_for, \
    ErrorPage, HTTPError, HTTPForbidden, HTTPNotFound, HTTPRedirect
from .util import organise_collection, with_institution, with_person, \
    with_verified_admin
from . import auth


InstitutionLogExtra = namedtuple(
    'InstitutionLogExtra',
    InstitutionLog._fields + ('new',))

ProposalsByFacility = namedtuple(
    'ProposalsByFacility',
    ('name', 'code', 'type_class', 'proposals'))

ReviewsByFacility = namedtuple(
    'ReviewsByFacility',
    ('name', 'code', 'role_class', 'proposals'))


class PeopleView(object):
    def log_in(self, db, args, form, referrer):
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
                            'Your account is associated with multiple '
                            'profiles.')

                    _update_session_person(person)

                    if register_user_for is not None:
                        # If we have this parameter, redirect there now.
                        # (This entry will have been cleared from the session
                        # on log-in so do not redirect via any other pages
                        # first!)
                        raise HTTPRedirect(register_user_for)

                    if person.institution_id is None:
                        # If the user has no institution, take them to the
                        # institution selection page.
                        flash('It appears your registration was not complete. '
                              'If convenient, please select your institution.')
                        raise HTTPRedirect(url_for('.person_edit_institution',
                                                   person_id=person.id))
                    raise HTTPRedirect(
                        session.pop('log_in_for', url_for('home.home_page')))

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
        }

    def log_out(self):
        session.clear()
        flash('You have been logged out.')
        raise HTTPRedirect(url_for('home.home_page'))

    def register_user(self, db, form, remote_addr):
        message = None

        user_name = ''

        if form is not None:
            try:
                user_name = form['user_name']
                password = form['password']
                if password != form['password_check']:
                    raise UserError('The passwords did not match.')
                user_id = db.add_user(user_name, password,
                                      remote_addr=remote_addr)

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

    def change_user_name(self, db, form, remote_addr):
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
                    raise HTTPRedirect(url_for(
                        '.person_view', person_id=session['person']['id']))
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

    def change_password(self, db, form, remote_addr):
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
                    raise HTTPRedirect(url_for(
                        '.person_view', person_id=session['person']['id']))
                else:
                    raise HTTPRedirect(url_for('home.home_page'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Change Password',
            'message': message,
        }

    def password_reset_token_get(self, db, form, remote_addr):
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
                    except KeyError:
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

    def password_reset_token_use(self, db, args, form, remote_addr):
        message = None
        token = args.get('token', '')

        if form is not None:
            try:
                token = form['token'].strip()
                password = form['password']

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

                raise HTTPRedirect(url_for('.log_in', user_name=user_name))

            except UserError as e:
                message = e.message

        return {
            'title': 'Use Password Reset Code',
            'message': message,
            'token': token,
        }

    @with_verified_admin
    def take_admin(self, db, referrer):
        session['is_admin'] = True
        flash('You have taken administrative privileges.')

        target = session.pop('log_in_referrer', None)
        if target is None:
            target = referrer if referrer else url_for('home.home_page')
        raise HTTPRedirect(target)

    def drop_admin(self, referrer):
        session.pop('is_admin', None)
        flash('You have dropped administrative privileges.')
        raise HTTPRedirect(referrer if referrer else url_for('home.home_page'))

    @with_verified_admin
    def user_log(self, db, user_id):
        try:
            user_name = db.get_user_name(user_id=user_id)
        except NoSuchRecord:
            user_name = None

        person = None
        try:
            person = db.search_person(user_id=user_id).get_single()
            name = person.name
        except NoSuchRecord:
            name = 'User {}'.format(user_id)

        events = db.search_user_log(user_id=user_id)

        return {
            'title': '{}: Account Log'.format(name),
            'user_name': user_name,
            'person': person,
            'events': events,
        }

    def register_person(self, db, form, remote_addr):
        if 'person' in session:
            raise ErrorPage('You have already created a profile.')

        # Check if the user already created a profile in another session.
        user_id = session['user_id']
        try:
            person = db.search_person(user_id=user_id).get_single()
            _update_session_person(person)
            raise ErrorPage(
                'You have already created a profile in another session.')
        except NoSuchRecord:
            pass

        message = None

        person = null_tuple(Person)._replace(name='', public=False)

        if form is not None:
            person = person._replace(
                name=form['person_name'].strip(),
                title=(None if (form['person_title'] == '')
                       else int(form['person_title'])),
                public=('person_public' in form))
            email = form['single_email'].strip()

            try:
                if not person.name:
                    raise UserError('Please enter your full name.')
                elif not email:
                    raise UserError('Please enter your email address.')

                person_id = db.add_person(
                    person.name, title=person.title, public=person.public,
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
            'single_email': email,
            'titles': PersonTitle.get_options(),
        }

    def person_list(self, db):
        # Only show public members unless the user is has administrative
        # privileges.
        public = True
        if session.get('is_admin', False) and auth.can_be_admin(db):
            public = None
        persons = db.search_person(registered=True, public=public,
                                   with_institution=True)

        return {
            'title': 'Directory of Users',
            'persons': persons,
        }

    @with_person(permission=PermissionType.VIEW)
    def person_view(self, db, person, can):
        is_current_user = person.user_id == session['user_id']

        # Show all email addresses if:
        # * It's your own profile.
        # * You're an administrator. (Not double-checked here but
        #   "auth.for_person" would have.)
        # * The user is unregistered but you can edit. (You're a co-member
        #   editor.)
        view_all_email = (
            is_current_user or
            session.get('is_admin', False) or
            ((person.user_id is None) and can.edit))

        person = person._replace(
            email=[x for x in person.email.values()
                   if x.public or view_all_email])

        return {
            'title': '{}: Profile'.format(person.name),
            'is_current_user': is_current_user,
            'can_edit': can.edit,
            'person': person,
        }

    @with_person(permission=PermissionType.EDIT)
    def person_edit(self, db, person, can, form):
        message = None

        if form is not None:
            person = person._replace(
                name=form['person_name'].strip(),
                title=(None if (form['person_title'] == '')
                       else int(form['person_title'])),
                public=('person_public' in form))

            try:
                if not person.name:
                    raise UserError('Please enter your full name.')
                db.update_person(
                    person.id, name=person.name, title=person.title,
                    public=(person.public and person.user_id is not None))

                if session['user_id'] == person.user_id:
                    flash('Your user profile has been saved.')
                    _update_session_person(db.get_person(person.id))
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
        }

    @with_person(permission=PermissionType.EDIT)
    def person_edit_institution(self, db, person, can, form):
        message = None

        is_current_user = person.user_id == session['user_id']
        institutions = db.search_institution()

        # Prepare blank record for an institution to potentially be
        # added to the database.
        institution = Institution(
            id=None, name='', department='', organization='',
            address='', country='')

        if form is not None:
            try:
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
                        institution.address, institution.country)
                    db.update_person(person.id, institution_id=institution_id)
                    action = 'recorded'

                else:
                    raise ErrorPage('Unknown action')

                if is_current_user:
                    _update_session_person(db.get_person(person.id))
                    flash('Your institution has been {}.', action)
                else:
                    flash('The institution has been {}.', action)

                # If an explicit "next page" has been set, go there now.
                if 'next_page' in session:
                    raise HTTPRedirect(session.pop('next_page'))

                raise HTTPRedirect(session.pop(
                    'log_in_for',
                    url_for('.person_view', person_id=person.id)))

            except UserError as e:
                message = e.message

        return {
            'title': '{}: Select Institution'.format(person.name),
            'message': message,
            'person': person,
            'institution': institution,
            'institution_id': person.institution_id,
            'institutions': institutions,
            'countries': get_countries(),
            'is_current_user': is_current_user,
        }

    @with_person(permission=PermissionType.EDIT)
    def person_edit_email(self, db, person, can, form):
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
                            email_id, person.id, form[param].strip(),
                            is_primary, False, is_public)

                    else:
                        # Convert to integer so that it matches existing
                        # email records.
                        email_id = int(id_)

                        verified = False
                        if email_id in person.email:
                            verified = person.email[email_id].verified

                        updated_records[email_id] = Email(
                            email_id, person.id, form[param].strip(),
                            is_primary, verified, is_public)

                # Create new record collection: overwrite "records" variable
                # name so that, in case of failure, the form will display the
                # new records again for correction.
                records = organise_collection(EmailCollection, updated_records,
                                              added_records)

                db.sync_person_email(person.id, records)

                if is_current_user:
                    flash('Your email addresses have been updated.')
                    _update_session_person(db.get_person(person.id))
                else:
                    flash('The email addresses have been updated.')
                raise HTTPRedirect(url_for(
                    '.person_view', person_id=person.id))

            except UserError as e:
                message = e.message

        return {
            'title': '{}: Edit Email Addresses'.format(person.name),
            'message': message,
            'person': person,
            'emails': records,
        }

    @with_person(permission=PermissionType.EDIT)
    def person_email_verify_get(self, db, person, can, email_id, form):
        try:
            email = person.email[email_id]
        except KeyError:
            raise HTTPNotFound('Email address record not found.')

        if email.verified:
            raise ErrorPage('The email address {} has already been verified.',
                            email.address)

        if form:
            (token, expiry) = db.issue_email_verify_token(
                person.id, email.address)
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
            raise HTTPRedirect(url_for('.person_email_verify_use'))

        return {
            'title': '{}: Verify Email Address'.format(person.name),
            'person': person,
            'email': email,
        }

    def person_email_verify_use(self, db, args, form):
        message = None
        token = args.get('token', '')
        person_id = session['person']['id']

        if form is not None:
            token = form['token'].strip()

            try:
                try:
                    email_address = db.use_email_verify_token(person_id, token)

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
                raise HTTPRedirect(url_for(
                    '.person_view', person_id=person_id))

            except UserError as e:
                message = e.message

        return {
            'title': 'Enter Email Verification Code',
            'message': message,
            'token': token,
        }

    def person_proposals_own(self, db, facilities):
        return self._person_proposals(
            db, session['person']['id'], facilities, None, 'Your Proposals')

    @with_verified_admin
    @with_person(permission=PermissionType.NONE)
    def person_proposals_other(self, db, person, facilities):
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

    def person_reviews_own(self, db, facilities):
        return self._person_reviews(
            db, session['person']['id'], facilities, None, 'Your Reviews',
            include_addable=True)

    @with_verified_admin
    @with_person(permission=PermissionType.NONE)
    def person_reviews_other(self, db, person, facilities):
        return self._person_reviews(
            db, person.id, facilities, person,
            '{}: Reviews'.format(person.name))

    def _person_reviews(self, db, person_id, facilities, person, title,
                        include_addable=False):
        auth_cache = {}

        # Get a list of proposals, in all review states, for which this
        # person has reviews.  (Will filter later to list only those
        # which are editable in each proposal's actual state.)
        all_proposals = db.search_proposal(
            reviewer_person_id=person_id,
            with_members=True, state=ProposalState.review_states())

        if include_addable:
            all_addable = auth.find_addable_reviews(
                db, facilities, auth_cache=auth_cache)
        else:
            all_addable = None

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
                if auth.for_review(
                        role_class, db, proposal.reviewer, proposal,
                        auth_cache=auth_cache).edit:
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
                        proposal.reviewer

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
                        proposal_reviewers['addable_{}'.format(i)] = reviewer

            # If, after filtering, no proposals are left, skip this facility.
            if not facility_proposals:
                continue

            proposals.append(ReviewsByFacility(
                facility.name, facility.code, role_class, facility_proposals))

        return {
            'title': title,
            'proposals': proposals,
            'person': person,
        }

    @with_verified_admin
    @with_person(permission=PermissionType.NONE)
    def person_subsume(self, db, person, form):
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
                db.merge_person_records(
                    main_person_id=person.id,
                    duplicate_person_id=duplicate.id,
                    duplicate_person_registered=True)

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

    def institution_list(self, db):
        return {
            'title': 'Institutions',
            'institutions': db.search_institution(),
        }

    @with_institution(permission=PermissionType.VIEW)
    def institution_view(self, db, institution, can):
        # Only show public, registered members unless the user has
        # administrative privileges.
        public = True
        registered = True
        if session.get('is_admin', False) and auth.can_be_admin(db):
            public = None
            registered = None

        persons = db.search_person(institution_id=institution.id,
                                   registered=registered, public=public)

        return {
            'title': 'Institution: {}'.format(institution.name),
            'institution': institution,
            'can_edit': can.edit,
            'persons': persons,
        }

    @with_institution(permission=PermissionType.EDIT)
    def institution_edit(self, db, institution, can, form):
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
                    log_approved = (session.get('is_admin', False) and
                                    auth.can_be_admin(db))

                    db.update_institution(
                        institution.id,
                        updater_person_id=session['person']['id'],
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
                if person.id == session['person']['id']:
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
            'countries': get_countries(),
        }

    @with_verified_admin
    def institution_log(self, db, institution_id, form):
        return self._display_institution_log(db, institution_id, form)

    @with_verified_admin
    def institution_log_approval(self, db, form):
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

    @with_verified_admin
    def institution_subsume(self, db, institution_id, form):
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

    def invitation_token_enter(self, db, args):
        return {
            'title': 'Enter Invitation Code',
            'token': args.get('token', ''),
        }

    def invitation_token_accept(self, db, args, form, remote_addr):
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
                # Re-fetch the current user's profile, in case they registered
                # a profile in another session.  We need to be sure we know
                # whether they are registered or not.
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

                # Attempt to determine where to redirect: ideally there will
                # only be one proposal or review associated with the old
                # person record.
                target = None
                try:
                    member = old_person_record.proposals.get_single()
                    proposal_id = member.proposal_id
                    code = db.get_proposal_facility_code(proposal_id)
                    target = url_for(
                        '{}.proposal_view'.format(code),
                        proposal_id=proposal_id, first_view='true')
                except NoSuchRecord:
                    pass
                except MultipleRecords:
                    pass

                if target is None:
                    try:
                        reviewer = old_person_record.reviews.get_single()
                        code = db.get_proposal_facility_code(
                            reviewer.proposal_id)
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
