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

from datetime import datetime, timedelta
from time import sleep

from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_, exists, not_
from sqlalchemy.sql.functions import count

from ... import auth
from ...auth import check_password_hash, create_password_hash, generate_token
from ...config import get_countries
from ...email.util import is_valid_email
from ...error import ConsistencyError, DatabaseIntegrityError, \
    Error, NoSuchRecord, UserError
from ...type.collection import EmailCollection, ResultCollection, \
    SiteGroupMemberCollection
from ...type.enum import PersonTitle, SiteGroupType, UserLogEvent
from ...type.simple import AuthTokenInfo, Email, \
    Institution, InstitutionInfo, InstitutionLog, OAuthCode, OAuthToken, \
    Person, PersonInfo, SiteGroupMember, UserInfo, UserLog
from ...util import is_list_like
from ..meta import auth_failure, auth_token, email, group_member, \
    institution, institution_log, \
    invitation, member, message_recipient, \
    oauth_code, oauth_token, person, \
    proposal_fig, proposal_pdf, proposal_text, \
    request_prop_copy, \
    reset_token, reviewer, site_group_member, user, user_log, verify_token
from ..util import require_not_none

auth_token_expiry = timedelta(hours=24)

rate_limit_period = timedelta(minutes=120)
rate_limit_verify = 5
rate_limit_password_reset = 3


class PeoplePart(object):
    def add_email(self, person_id, address, primary=False, verified=False,
                  public=False, _conn=None, _test_skip_check=False):
        """
        Add an email address record to the databae.

        Returns the email_id number.
        """

        if not is_valid_email(address):
            raise UserError(
                'The email address "{}" does not appear to be valid.', address)

        with self._transaction(_conn=_conn) as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, person, person_id)):
                raise ConsistencyError(
                    'person does not exist with id={}', person_id)

            result = conn.execute(email.insert().values({
                email.c.person_id: person_id,
                email.c.address: address,
                email.c.primary: primary,
                email.c.verified: verified,
                email.c.public: public,
            }))

        return result.inserted_primary_key[0]

    def add_institution(self, name, department, organization,
                        address, country):
        """
        Add an institution to the database.

        Returns the new institution_id number.
        """

        if country not in get_countries():
            raise UserError('Country code not recognised')

        with self._transaction() as conn:
            result = conn.execute(institution.insert().values({
                institution.c.name: name,
                institution.c.department: department,
                institution.c.organization: organization,
                institution.c.address: address,
                institution.c.country: country,
            }))

        return result.inserted_primary_key[0]

    def add_person(self, name, title=None, public=False,
                   user_id=None, remote_addr=None,
                   primary_email=None, institution_id=None,
                   _test_skip_check=False):
        """
        Add a person to the database.

        If the user_id for an existing user is provided, then the person
        includes a reference to that user.

        If a `primary_email` address is given, it is added as the
        person's primary email address.
        """

        if not ((title is None) or PersonTitle.is_valid(title)):
            raise UserError('Invalid title selection.')

        values = {
            person.c.name: name,
            person.c.title: title,
            person.c.public: public,
            person.c.user_id: user_id,
            person.c.admin: False,
        }

        if institution_id is not None:
            values[person.c.institution_id] = institution_id

        with self._transaction() as conn:
            if user_id is not None and not _test_skip_check:
                if not self._exists_id(conn, user, user_id):
                    raise ConsistencyError(
                        'user does not exist with id={}', user_id)
                if self._exists_person_user(conn, user_id):
                    raise ConsistencyError(
                        'person already exists with user_id={}', user_id)

            result = conn.execute(person.insert().values(values))

            person_id = result.inserted_primary_key[0]

            if user_id is not None:
                self._add_user_log_entry(
                    conn, user_id, UserLogEvent.LINK_PROFILE, remote_addr)

            if primary_email is not None:
                self.add_email(
                    person_id, primary_email, primary=True, _conn=conn)

        return person_id

    def add_oauth_code(
            self, code, redirect_uri, response_type, nonce,
            client_id, scope, person_id):
        values = {
            oauth_code.c.code: code,
            oauth_code.c.redirect_uri: redirect_uri,
            oauth_code.c.response_type: response_type,
            oauth_code.c.nonce: nonce,
            oauth_code.c.client_id: client_id,
            oauth_code.c.scope: scope,
            oauth_code.c.person_id: person_id,
            oauth_code.c.issued: datetime.utcnow(),
            oauth_code.c.expiry: datetime.utcnow() + timedelta(minutes=10),
        }

        with self._transaction() as conn:
            result = conn.execute(oauth_code.insert().values(values))

        return result.inserted_primary_key[0]

    def add_oauth_token(
            self, token_type, access_token, refresh_token,
            client_id, scope, person_id, expires_in):
        values = {
            oauth_token.c.token_type: token_type,
            oauth_token.c.access_token: access_token,
            oauth_token.c.refresh_token: refresh_token,
            oauth_token.c.client_id: client_id,
            oauth_token.c.scope: scope,
            oauth_token.c.person_id: person_id,
            oauth_token.c.issued: datetime.utcnow(),
            oauth_token.c.expiry: datetime.utcnow() + timedelta(
                seconds=expires_in),
        }

        with self._transaction() as conn:
            result = conn.execute(oauth_token.insert().values(values))

        return result.inserted_primary_key[0]

    def add_site_group_member(
            self, site_group_type, person_id,
            _conn=None, _test_skip_check=False):
        if not SiteGroupType.is_valid(site_group_type):
            raise Error('invalid site group type')

        with self._transaction(_conn=_conn) as conn:
            if not _test_skip_check:
                if not self._exists_id(conn, person, person_id):
                    raise ConsistencyError('person does not exist with id={}',
                                           person_id)

            result = conn.execute(site_group_member.insert().values({
                site_group_member.c.site_group_type: site_group_type,
                site_group_member.c.person_id: person_id,
            }))

        return result.inserted_primary_key[0]

    def add_user(self, name, password_raw, person_id=None, remote_addr=None,
                 _test_skip_check=False):
        """
        Add a user to the database.

        The given raw password is used to generate a salted password
        hash which is then stored in the database.  If a person_id
        for an existing person is given, then that person's record
        is updated to contain a reference to this user.
        """

        if not name:
            raise UserError('The user account name can not be blank.')
        if not password_raw:
            raise UserError('The password can not be blank.')

        (password_hash, password_salt) = create_password_hash(password_raw)

        with self._transaction() as conn:
            if not _test_skip_check and self._exists_user_name(conn, name):
                raise UserError(
                    'The user account name "{}" already exists.', name)

            result = conn.execute(user.insert().values({
                user.c.name: name,
                user.c.password: password_hash,
                user.c.salt: password_salt,
            }))

            user_id = result.inserted_primary_key[0]

            self._add_user_log_entry(
                conn, user_id, UserLogEvent.CREATE, remote_addr)

            if person_id is not None:
                if not _test_skip_check and \
                        not self._exists_id(conn, person, person_id):
                    raise ConsistencyError(
                        'person does not exist with id={}', person_id)

                result = conn.execute(person.update().where(and_(
                    person.c.id == person_id,
                    person.c.user_id.is_(None)
                )).values({
                    person.c.user_id: user_id,
                }))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched setting new user_id'
                        ' for person with id={}',
                        person_id)

                self._add_user_log_entry(
                    conn, user_id, UserLogEvent.LINK_PROFILE, remote_addr)

        return user_id

    def authenticate_user(self, name, password_raw, user_id=None):
        """
        Given a user name and raw password, try to authenitcate the user.

        Can take a user_id instead of a user name for re-authentication,
        e.g. before changing password.  In that case, name must be
        explicitly set to None (to prevent accidental use of this
        rare use-case).

        Returns the user_id on success, None otherwise.

        Attempts to protect against multiple authentication attempts, but only
        if "name" is given.  (I.e. not in user_id re-authentication mode.)
        """

        stmt = user.select()

        if user_id is not None:
            if name is not None:
                raise Error('name and user_id both given')
            stmt = stmt.where(user.c.id == user_id)
        elif name is None:
            raise Error('neither name nor user_id given')
        elif not name:
            raise UserError('The user account name can not be blank.')
        else:
            stmt = stmt.where(user.c.name == name)
        if not password_raw:
            raise UserError('The password can not be blank.')

        with self._transaction() as conn:
            if name is not None:
                # Removed any expired auth_failure records.
                conn.execute(auth_failure.delete().where(
                    auth_failure.c.expiry < datetime.utcnow()))

                # Check for excessive authentication failures.
                attempts = conn.execute(select([
                    auth_failure.c.attempts
                ]).where(auth_failure.c.user_name == name)).scalar()

                # Current limit: more that 5 (i.e. 6 or more failures).
                if (attempts is not None) and (attempts >= 5):
                    raise UserError(
                        'Too many authentication attempts for this user name.')

            result = conn.execute(stmt).first()

        if result is None:
            if name is not None:
                self._record_auth_failure(name)

            # Spend time as if we were hashing the password so that the user
            # can't tell that the user name doesn't exist by this function
            # returning fast.
            sleep(auth.password_hash_delay)
            return None

        else:
            if check_password_hash(password_raw, result[user.c.password],
                                   result[user.c.salt]):
                return result[user.c.id]
            else:
                if name is not None:
                    self._record_auth_failure(name)

                return None

    def _record_auth_failure(self, name):
        """
        Record an authentication failure.
        """

        # Note the try .. except outside the with block: this is because
        # our context manager detects and raises  DatabaseIntegrityError
        # so we can only catch it after the block.

        try:
            expiry = datetime.utcnow() + timedelta(minutes=30)

            with self._transaction() as conn:
                conn.execute(auth_failure.insert().values({
                    auth_failure.c.user_name: name,
                    auth_failure.c.attempts: 1,
                    auth_failure.c.expiry: expiry,
                }))

        except DatabaseIntegrityError:
            with self._transaction() as conn:
                conn.execute(auth_failure.update().where(
                    auth_failure.c.user_name == name
                ).values({
                    auth_failure.c.attempts: auth_failure.c.attempts + 1,
                }))

    def _delete_auth_failure(self, user_name, _conn=None):
        """
        Delete authentication failure records for a given user name.

        This can be used, for example, after a user has reset their password
        via the password reset system.
        """

        with self._transaction(_conn=_conn) as conn:
            conn.execute(auth_failure.delete().where(
                auth_failure.c.user_name == user_name))

    def authenticate_token(self, token):
        """
        If the given token is valid, return the corresponding user.

        Expired token are automatically deleted before the search
        is performed.  Additionally if more that 10 minutes of the
        token's duration has elapsed, its expiry date is refreshed.
        """

        select_columns = [
            user.c.id,
            user.c.name,
            auth_token.c.id.label('token_id'),
            auth_token.c.expiry,
        ]
        select_from = user.join(auth_token)

        stmt = select(select_columns).select_from(select_from).where(
            auth_token.c.token == token)

        with self._transaction() as conn:
            self._delete_auth_expired(conn)

            result = conn.execute(stmt).first()

            if result is not None:
                expiry = result['expiry']

                time_left = expiry - datetime.utcnow()

                time_gone = (
                    auth_token_expiry.total_seconds()
                    - time_left.total_seconds())

                if time_gone > 600:
                    expiry = datetime.utcnow() + auth_token_expiry

                    refresh_result = conn.execute(auth_token.update().where(
                        auth_token.c.id == result['token_id']
                    ).values({
                        auth_token.c.expiry: expiry,
                    }))

                    if refresh_result.rowcount != 1:
                        raise ConsistencyError('could not refresh token')

        if result is None:
            raise NoSuchRecord('token not found')

        return UserInfo(id=result['id'], name=result['name'])

    def _delete_auth_expired(self, conn):
        conn.execute(auth_token.delete().where(
            auth_token.c.expiry < datetime.utcnow()))

    def delete_auth_token(
            self, token=None, user_id=None, auth_token_id=None):
        stmt = auth_token.delete()

        if token is not None:
            stmt = stmt.where(auth_token.c.token == token)

        if user_id is not None:
            stmt = stmt.where(auth_token.c.user_id == user_id)

        if auth_token_id is not None:
            stmt = stmt.where(auth_token.c.id == auth_token_id)

        with self._transaction() as conn:
            conn.execute(stmt)

    def delete_oauth_code(self, code_id):
        """
        Delete the given authorization code.
        """

        with self._transaction() as conn:
            conn.execute(oauth_code.delete().where(
                oauth_code.c.id == code_id))

    def _delete_oauth_expired(self, conn):
        """
        Delete expired OAuth data.

        This removes authorization codes and, since refresh is not
        implemented, access tokens.
        """

        conn.execute(oauth_code.delete().where(
            oauth_code.c.expiry < datetime.utcnow()))

        conn.execute(oauth_token.delete().where(
            oauth_token.c.expiry < datetime.utcnow()))

    def get_institution(self, institution_id, _conn=None):
        """
        Get an institution record.
        """

        with self._transaction(_conn=_conn) as conn:
            result = conn.execute(institution.select().where(
                institution.c.id == institution_id
            )).first()

        if result is None:
            raise NoSuchRecord('institution does not exist with id={}',
                               institution_id)

        return Institution(**result)

    def get_invitation_person(self, token, *args, **kwargs):
        """
        Get the person record associated with an invitation.

        Any additional "args" and "kwargs" are passed to the "get_person"
        method.

        NoSuchRecord is raised if the token does not exist and RecordExpired
        is raised if it does exist but has expired.

        Simply returns the Person record from "get_person" since there
        is no other useful information associated with an invitation.
        """

        with self._transaction() as conn:
            # Removed any expired invitations, as for password reset tokens.
            conn.execute(invitation.delete().where(
                invitation.c.expiry < datetime.utcnow()))

            # Fetch the requested invitation.
            result = conn.execute(invitation.select().where(
                invitation.c.token == token
            )).first()

            if result is None:
                raise NoSuchRecord('invitation token expired or non-existant')

        return self.get_person(person_id=result['person_id'],
                               *args, **kwargs)

    def get_person(self, person_id, user_id=None,
                   with_email=False, with_institution=False,
                   with_proposals=False, with_reviews=False,
                   _conn=None):
        """
        Get a person record.

        Can take a user_id instead of a person_id, but in that case,
        person_id must be explicitly set to None (to prevent accidental use
        of this rare use-case).

        Raises NoSuchRecord if the person_id doesn't exist.
        """

        email = None
        institution = None
        proposals = None
        reviews = None

        stmt = person.select()
        if person_id is not None:
            stmt = stmt.where(person.c.id == person_id)
        elif user_id is not None:
            stmt = stmt.where(person.c.user_id == user_id)
        else:
            raise Error('neither person_id nor user_id specified')

        with self._transaction(_conn=_conn) as conn:
            result = conn.execute(stmt).first()

            if result is None:
                raise NoSuchRecord('person does not exist')

            # If we weren't searching by person_id, we need to retrieve it
            # from the record.
            if person_id is None:
                person_id = result['id']

            if with_institution and result['institution_id'] is not None:
                institution = self.get_institution(result['institution_id'],
                                                   _conn=conn)

            if with_email:
                email = self.search_email(person_id=person_id, _conn=conn)

            if with_proposals:
                proposals = self.search_member(person_id=person_id, _conn=conn)

            if with_reviews:
                reviews = self.search_reviewer(person_id=person_id, _conn=conn)

        return Person(email=email, institution=institution,
                      proposals=proposals, reviews=reviews, **result)

    @require_not_none
    def get_user_id(self, user_name):
        """
        Get the user_id for the given user name.
        """

        with self._transaction() as conn:
            return conn.execute(select([user.c.id]).where(
                user.c.name == user_name
            )).scalar()

    @require_not_none
    def get_user_name(self, user_id, _conn=None):
        """
        Get the user name associated with the given user_id.
        """

        with self._transaction(_conn=_conn) as conn:
            return conn.execute(select([user.c.name]).where(
                user.c.id == user_id
            )).scalar()

    def issue_auth_token(
            self, user_id, remote_addr, remote_agent):
        """
        Create a user authentication token.
        """

        token = generate_token(32)
        expiry = datetime.utcnow() + auth_token_expiry

        with self._transaction() as conn:
            result = conn.execute(auth_token.insert().values({
                auth_token.c.token: token,
                auth_token.c.user_id: user_id,
                auth_token.c.expiry: expiry,
                auth_token.c.remote_addr: remote_addr,
                auth_token.c.remote_agent: remote_agent,
            }))

        return (token, expiry)

    def issue_email_verify_token(
            self, person_id, email_address, user_id, remote_addr=None):
        """
        Create a email address verification token.

        Stores the person_id along with the generated token in the database
        so that we can ensure only one token is issued per person and
        address.
        """

        token = generate_token()
        expiry = datetime.utcnow() + timedelta(hours=24)

        with self._transaction() as conn:
            if user_id is not None:
                self._check_rate_limit(
                    conn, user_id, UserLogEvent.GET_EMAIL_TOKEN,
                    rate_limit_verify)

            conn.execute(verify_token.delete().where(and_(
                verify_token.c.email_address == email_address,
                verify_token.c.person_id == person_id)))

            result = conn.execute(verify_token.insert().values({
                verify_token.c.token: token,
                verify_token.c.person_id: person_id,
                verify_token.c.email_address: email_address,
                verify_token.c.expiry: expiry,
            }))

            if user_id is not None:
                self._add_user_log_entry(
                    conn, user_id, UserLogEvent.GET_EMAIL_TOKEN, remote_addr)

        return (token, expiry)

    def issue_invitation(self, person_id, days_valid=30,
                         _test_skip_check=False):
        """
        Creates an invitation token to allow someone to register as the
        given person and adds it to the database.

        Deletes existing tokens to register as this person.

        Returns a tuple of the new token and its expiry.
        """

        token = generate_token()
        expiry = datetime.utcnow() + timedelta(days_valid)

        with self._transaction() as conn:
            if not _test_skip_check:
                result = conn.execute(select([
                    person.c.user_id, person.c.admin
                ]).where(
                    person.c.id == person_id
                )).first()
                if result is None:
                    raise ConsistencyError('person does not exist with id={}',
                                           person_id)
                elif result['user_id'] is not None:
                    raise ConsistencyError('person is already registered')
                elif result['admin']:
                    raise UserError('person has administrative privileges')

            conn.execute(invitation.delete().where(
                invitation.c.person_id == person_id))

            conn.execute(invitation.insert().values({
                invitation.c.token: token,
                invitation.c.person_id: person_id,
                invitation.c.expiry: expiry,
            }))

        return (token, expiry)

    def issue_password_reset_token(
            self, user_id, remote_addr, _test_skip_check=False):
        """
        Create a password reset token for a given user.

        Deletes any existing tokens for this user and returns a tuple of
        the new token and its expiry date.
        """

        token = generate_token()
        expiry = datetime.utcnow() + timedelta(hours=4)

        with self._transaction() as conn:
            if not _test_skip_check:
                self._check_rate_limit(
                    conn, user_id, UserLogEvent.GET_TOKEN,
                    rate_limit_password_reset)

            conn.execute(reset_token.delete().where(
                reset_token.c.user_id == user_id))

            result = conn.execute(reset_token.insert().values({
                reset_token.c.token: token,
                reset_token.c.user_id: user_id,
                reset_token.c.expiry: expiry,
            }))

            self._add_user_log_entry(
                conn, user_id, UserLogEvent.GET_TOKEN, remote_addr)

        return (token, expiry)

    def merge_institution_records(self, main_institution_id,
                                  duplicate_institution_id,
                                  _test_skip_check=False):
        """
        Merge the two given institutions.

        Deletes all log entries corresponding to the duplicate and then
        changes references to the duplicate to point at the main
        record before deleting it.
        """

        with self._transaction() as conn:
            if not _test_skip_check:
                if not self._exists_id(conn, institution,
                                       main_institution_id):
                    raise ConsistencyError(
                        'main institution {} does not exist for merge',
                        main_institution_id)
                if not self._exists_id(conn, institution,
                                       duplicate_institution_id):
                    raise ConsistencyError(
                        'duplicate institution {} does not exist for merge',
                        duplicate_institution_id)

            conn.execute(institution_log.delete().where(
                institution_log.c.institution_id == duplicate_institution_id))

            # Swap out references in other tables.
            for table in (member, person):
                conn.execute(table.update().where(
                    table.c.institution_id == duplicate_institution_id
                ).values({
                    table.c.institution_id: main_institution_id,
                }))

            conn.execute(institution.delete().where(
                institution.c.id == duplicate_institution_id))

    def merge_person_records(self, main_person_id, duplicate_person_id,
                             duplicate_person_registered=None,
                             _conn=None, _test_skip_check=False):
        """
        Merge the two given person records.
        """

        with self._transaction(_conn=_conn) as conn:
            if not _test_skip_check:
                if not self._exists_id(conn, person, main_person_id):
                    raise ConsistencyError(
                        'main person ID {} does not exist for merge',
                        main_person_id)
                if not self._exists_id(conn, person, duplicate_person_id):
                    raise ConsistencyError(
                        'duplicate person ID {} does not exist for merge',
                        duplicate_person_id)

            # Check if the main person is registered.
            main_user_id = conn.execute(select([person.c.user_id]).where(
                person.c.id == main_person_id
            )).scalar()

            # Check if the duplicate person is registered.
            duplicate_user_id = conn.execute(select([person.c.user_id]).where(
                person.c.id == duplicate_person_id
            )).scalar()

            # Apply constraint on duplicate person being registered.
            if duplicate_person_registered is None:
                pass

            elif duplicate_person_registered:
                if duplicate_user_id is None:
                    raise ConsistencyError(
                        'duplicate person {} is not already registered',
                        duplicate_person_id)

            else:
                if duplicate_user_id is not None:
                    raise ConsistencyError(
                        'duplicate person {} is already registered as user {}',
                        duplicate_person_id, duplicate_user_id)

            # Swap out references in other tables.
            for (table, column_name) in (
                    (group_member, 'person_id'),
                    (institution_log, 'person_id'),
                    (member, 'person_id'),
                    (message_recipient, 'person_id'),
                    (proposal_fig, 'uploader'),
                    (proposal_pdf, 'uploader'),
                    (proposal_text, 'editor'),
                    (reviewer, 'person_id'),
                    (request_prop_copy, 'requester'),
                    (site_group_member, 'person_id')):
                column = getattr(table.c, column_name)
                conn.execute(table.update().where(
                    column == duplicate_person_id
                ).values({
                    column: main_person_id,
                }))

            # Delete references which are no longer relevant.
            # Note: email table entries are deleted with the person by cascade.
            for table in (invitation, verify_token):
                conn.execute(table.delete().where(
                    table.c.person_id == duplicate_person_id))

            # Remove duplicate person record.
            conn.execute(person.delete().where(
                person.c.id == duplicate_person_id))

            # Remove duplicate user record, if present.
            if duplicate_user_id is not None:
                # Remove entries which refer to the old user_id.
                for table in (reset_token, user_log):
                    conn.execute(table.delete().where(
                        table.c.user_id == duplicate_user_id))

                # Remove the old user record itself.
                conn.execute(user.delete().where(
                    user.c.id == duplicate_user_id))

            # Add a log entry to for the main person, if registered.
            if main_user_id is not None:
                self._add_user_log_entry(
                    conn, main_user_id, UserLogEvent.MERGED)

    def search_auth_token(self):
        """
        Find authentication token records.
        """

        stmt = select([
            auth_token.c.id,
            auth_token.c.user_id,
            auth_token.c.expiry,
            auth_token.c.remote_addr,
            auth_token.c.remote_agent,
            user.c.name.label('user_name'),
            person.c.id.label('person_id'),
            person.c.name.label('person_name'),
        ]).select_from(auth_token.join(user).outerjoin(person))

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(auth_token.c.id)):
                ans[row['id']] = AuthTokenInfo(**row)

        return ans

    def search_email(self, person_id, address=None, _conn=None):
        """
        Find email address records.
        """

        stmt = email.select()

        if person_id is not None:
            stmt = stmt.where(email.c.person_id == person_id)

        if address is not None:
            if is_list_like(address):
                stmt = stmt.where(email.c.address.in_(address))
            else:
                stmt = stmt.where(email.c.address == address)

        ans = EmailCollection()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt.order_by(email.c.id)):
                ans[row['id']] = Email(**row)

        return ans

    def search_institution(self, has_registered_person=None):
        """
        Search institution records.

        Summary information is returned.
        """

        stmt = select([
            institution.c.id,
            institution.c.name,
            institution.c.department,
            institution.c.organization,
            institution.c.country,
        ])

        if has_registered_person is not None:
            condition = exists().select_from(person).where(and_(
                person.c.user_id.isnot(None),
                person.c.institution_id == institution.c.id
            ))

            if has_registered_person:
                stmt = stmt.where(condition)

            else:
                stmt = stmt.where(not_(condition))

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(
                    institution.c.name, institution.c.department)):
                ans[row['id']] = InstitutionInfo(**row)

        return ans

    def search_institution_log(self, institution_id=None, approved=None,
                               has_unapproved=None):
        """
        Search for records in the institution edit log.

        Note that the web interface
        (hedwig.view.people._display_institution_log) needs the values
        in descending order as it works backwards from the current
        version of each institution record.

        Note also that if you want to see the history of edits to an
        institution, you should probably not filter by the "approved"
        status.  Instead use the "has_unapproved" argument to select
        only those institutions which have unapproved changes and
        filter out already approved changes for display.  This will
        allow you to see the 'before' and 'after' of each change since
        the log only stores the 'before' -- you need to next log entry,
        or current record, to get the 'after' values.
        """

        select_columns = [institution_log, person.c.name.label('person_name')]
        select_from = institution_log.join(person)
        default = {}

        if institution_id is None:
            select_columns.append(institution.c.name.label('institution_name'))
            select_from = select_from.join(
                institution,
                institution_log.c.institution_id == institution.c.id)
        else:
            default = {'institution_name': None}

        stmt = select(select_columns).select_from(select_from)

        if approved is not None:
            if approved:
                stmt = stmt.where(institution_log.c.approved)
            else:
                stmt = stmt.where(not_(institution_log.c.approved))

        if has_unapproved is not None:
            log_alias = institution_log.alias()

            unapproved_institutions = select([
                log_alias.c.institution_id,
            ]).where(
                not_(log_alias.c.approved)
            ).distinct()

            if has_unapproved:
                stmt = stmt.where(institution_log.c.institution_id.in_(
                    unapproved_institutions))
            else:
                stmt = stmt.where(institution_log.c.institution_id.notin_(
                    unapproved_institutions))

        if institution_id is not None:
            stmt = stmt.where(
                institution_log.c.institution_id == institution_id
            ).order_by(
                institution_log.c.id.desc())
        else:
            stmt = stmt.order_by(
                institution.c.name.asc(),
                institution.c.id.asc(),
                institution_log.c.id.desc())

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt):
                values = default.copy()
                values.update(**row)

                prev = Institution(
                    id=values['institution_id'],
                    name=values.pop('prev_name'),
                    department=values.pop('prev_department'),
                    organization=values.pop('prev_organization'),
                    address=values.pop('prev_address'),
                    country=values.pop('prev_country'),
                )

                ans[values['id']] = InstitutionLog(prev=prev, **values)

        return ans

    def search_oauth_code(self, client_id, code=None, nonce=None):
        ans = ResultCollection()

        stmt = oauth_code.select()

        if client_id is not None:
            stmt = stmt.where(oauth_code.c.client_id == client_id)
        if code is not None:
            stmt = stmt.where(oauth_code.c.code == code)
        if nonce is not None:
            stmt = stmt.where(oauth_code.c.nonce == nonce)

        with self._transaction() as conn:
            self._delete_oauth_expired(conn)

            for row in conn.execute(stmt):
                ans[row['id']] = OAuthCode(**row)

        return ans

    def search_oauth_token(self, client_id, access_token=None):
        ans = ResultCollection()

        stmt = oauth_token.select().where(not_(oauth_token.c.revoked))

        if client_id is not None:
            stmt = stmt.where(oauth_token.c.client_id == client_id)
        if access_token is not None:
            stmt = stmt.where(oauth_token.c.access_token == access_token)

        with self._transaction() as conn:
            self._delete_oauth_expired(conn)

            for row in conn.execute(stmt):
                ans[row['id']] = OAuthToken(**row)

        return ans

    def search_person(self, person_id=None, user_id=None, email_address=None,
                      registered=None, public=None, admin=None,
                      institution_id=None,
                      with_institution=False):
        """
        Find person records.
        """

        if not with_institution:
            default = {
                'institution_name': None,
                'institution_department': None,
                'institution_organization': None,
                'institution_country': None,
            }

            stmt = person.select()
        else:
            default = {}

            stmt = select([
                person,
                institution.c.name.label('institution_name'),
                institution.c.department.label('institution_department'),
                institution.c.organization.label('institution_organization'),
                institution.c.country.label('institution_country'),
            ]).select_from(person.outerjoin(institution))

        if person_id is not None:
            stmt = stmt.where(person.c.id == person_id)

        if user_id is not None:
            stmt = stmt.where(person.c.user_id == user_id)

        if institution_id is not None:
            stmt = stmt.where(person.c.institution_id == institution_id)

        if email_address is not None:
            stmt = stmt.where(person.c.id.in_(
                select([email.c.person_id]).where(
                    email.c.address == email_address
                )))

        if registered is not None:
            if registered:
                stmt = stmt.where(person.c.user_id.isnot(None))
            else:
                stmt = stmt.where(person.c.user_id.is_(None))

        if public is not None:
            if public:
                stmt = stmt.where(person.c.public)
            else:
                stmt = stmt.where(not_(person.c.public))

        if admin is not None:
            if admin:
                stmt = stmt.where(person.c.admin)
            else:
                stmt = stmt.where(not_(person.c.admin))

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(person.c.name)):
                values = default.copy()
                values.update(**row)
                ans[row['id']] = PersonInfo(**values)

        return ans

    def search_site_group_member(
            self, site_group_type=None, person_id=None,
            site_group_member_id=None, with_person=False, _conn=None):
        select_from = site_group_member

        select_columns = [
            site_group_member,
        ]

        if with_person:
            select_columns.extend([
                person.c.name.label('person_name'),
                person.c.public.label('person_public'),
                (person.c.user_id.isnot(None)).label('person_registered'),
                person.c.institution_id,
                institution.c.name.label('institution_name'),
                institution.c.department.label('institution_department'),
                institution.c.organization.label('institution_organization'),
                institution.c.country.label('institution_country'),
            ])

            select_from = select_from.join(person).outerjoin(institution)

            default = None
        else:
            default = {
                'person_name': None,
                'person_public': None,
                'person_registered': None,
                'institution_id': None,
                'institution_name': None,
                'institution_department': None,
                'institution_organization': None,
                'institution_country': None,
            }

        stmt = select(select_columns).select_from(select_from)

        if site_group_type is not None:
            if is_list_like(site_group_type):
                stmt = stmt.where(
                    site_group_member.c.site_group_type.in_(site_group_type))
            else:
                stmt = stmt.where(
                    site_group_member.c.site_group_type == site_group_type)

        if person_id is not None:
            stmt = stmt.where(site_group_member.c.person_id == person_id)

        if site_group_member_id is not None:
            stmt = stmt.where(site_group_member.c.id == site_group_member_id)

        if with_person:
            stmt = stmt.order_by(person.c.name.asc())
        else:
            stmt = stmt.order_by(site_group_member.c.id.asc())

        ans = SiteGroupMemberCollection()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt):
                if default is not None:
                    values = default.copy()
                    values.update(**row)
                else:
                    values = row

                ans[row['id']] = SiteGroupMember(**values)

        return ans

    def search_user(self, registered=None):
        """
        Search for user accounts.
        """

        select_columns = [user.c.id, user.c.name]
        select_from = user

        if registered is not None:
            select_from = select_from.outerjoin(person)

        stmt = select(select_columns).select_from(select_from)

        if registered is not None:
            if registered:
                stmt = stmt.where(person.c.id.isnot(None))
            else:
                stmt = stmt.where(person.c.id.is_(None))

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(user.c.name.asc())):
                ans[row['id']] = UserInfo(**row)

        return ans

    def search_user_log(
            self, user_id, event=None, date_after=None, _conn=None):
        """
        Search for user log entries.
        """

        stmt = user_log.select().where(user_log.c.user_id == user_id)

        if event is not None:
            stmt = stmt.where(user_log.c.event == event)

        if date_after is not None:
            stmt = stmt.where(user_log.c.date > date_after)

        ans = ResultCollection()

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt.order_by(user_log.c.id.desc())):
                ans[row['id']] = UserLog(**row)

        return ans

    def sync_institution_log_approval(self, records):
        """
        Update the approval status for some institution edit log entries.

        Takes a dictionary of log entry identifiers where the values
        are booleans indicating whether the entry is approved or not.

        This method works in terms of log entries rather than individual
        institutions so that it could be used for log entries for
        multiple institutions.
        """

        n_update = 0

        with self._transaction() as conn:
            # Determine which log entries are or are not already approved.
            # Do this by retrieving the identifiers of the (hopefully smaller)
            # subset of entries which are not approved.
            stmt = select([
                institution_log.c.id,
            ]).where(
                not_(institution_log.c.approved))

            not_approved = set()
            for row in conn.execute(stmt):
                not_approved.add(row['id'])

            # Now update the records which changed.
            for (id_, approved) in records.items():
                # Skip entries which didn't change.
                if id_ in not_approved:
                    if not approved:
                        continue
                elif approved:
                    continue

                # Apply update.
                result = conn.execute(institution_log.update().where(
                    institution_log.c.id == id_
                ).values({
                    institution_log.c.approved: approved,
                }))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows updated with new approval status for id={}',
                        id_)

                n_update += 1

        return n_update

    def sync_person_email(self, person_id, records):
        """
        Update the email records for a person to match those
        given in "records".

        The "verified" column is not updated.
        """

        records.validate()

        with self._transaction() as conn:
            if not self._exists_id(conn, person, person_id):
                raise ConsistencyError(
                    'person does not exist with id={}', person_id)

            return self._sync_records(
                conn, email, email.c.person_id, person_id, records,
                update_columns=(
                    email.c.address, email.c.primary, email.c.public,
                ), verified_columns=(email.c.address,),
                unique_columns=(email.c.address,))

    def sync_site_group_member(self, site_group_type, records):
        """
        Update the member records of the given site group.

        Currently this just allows removing members of the group,
        but could be extended if group members gain extra attributes.
        """

        if not SiteGroupType.is_valid(site_group_type):
            raise Error('invalid site group type')

        with self._transaction() as conn:
            self._sync_records(
                conn, site_group_member,
                key_column=site_group_member.c.site_group_type,
                key_value=site_group_type,
                records=records,
                update_columns=(),
                forbid_add=True)

    def update_institution(self, institution_id, updater_person_id=None,
                           name=None, department=None,
                           organization=None, address=None, country=None,
                           log_approved=False,
                           _test_skip_log=False):
        """
        Update an institution record.
        """

        values = {}

        if name is not None:
            values['name'] = name

        if department is not None:
            values['department'] = department

        if organization is not None:
            values['organization'] = organization

        if address is not None:
            values['address'] = address

        if country is not None:
            if country not in get_countries():
                raise UserError('Country code not recognised')
            values['country'] = country

        if not values:
            raise Error('no institution updates specified')

        with self._transaction() as conn:
            if not _test_skip_log:
                try:
                    prev = self.get_institution(institution_id, _conn=conn)
                except NoSuchRecord:
                    raise ConsistencyError(
                        'institution does not exist with id={}',
                        institution_id)

                conn.execute(institution_log.insert().values({
                    institution_log.c.institution_id: institution_id,
                    institution_log.c.date: datetime.utcnow(),
                    institution_log.c.person_id: updater_person_id,
                    institution_log.c.prev_name: prev.name,
                    institution_log.c.prev_department: prev.department,
                    institution_log.c.prev_organization: prev.organization,
                    institution_log.c.prev_address: prev.address,
                    institution_log.c.prev_country: prev.country,
                    institution_log.c.approved: log_approved,
                }))

            result = conn.execute(institution.update().where(
                institution.c.id == institution_id
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating institution with id={}',
                    institution_id)

    def update_person(self, person_id,
                      name=None, title=(), public=None, institution_id=(),
                      admin=None, verified=None,
                      _conn=None, _test_skip_check=False):
        """
        Update a person database record.
        """

        stmt = person.update().where(person.c.id == person_id)
        values = {}
        require_registered = False

        if name is not None:
            values['name'] = name
        if title != ():
            if not ((title is None) or PersonTitle.is_valid(title)):
                raise UserError('Invalid title selection.')
            values['title'] = title
        if public is not None:
            values['public'] = public
        if institution_id != ():
            values['institution_id'] = institution_id
        if admin is not None:
            values['admin'] = admin
            require_registered = (require_registered or admin)
        if verified is not None:
            values['verified'] = verified
            require_registered = (require_registered or verified)

        # The values dictionary is only empty if the caller specified
        # no parameters, i.e. everything was left at the default of ()
        # meaning do nothing.  In this case, raise an error.
        if not values:
            raise Error('no person updates specified')

        # Don't allow setting admin / verified flags for non-registered users.
        if require_registered and not _test_skip_check:
            stmt = stmt.where(not_(person.c.user_id.is_(None)))

        with self._transaction(_conn=_conn) as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, person, person_id)):
                raise ConsistencyError(
                    'person does not exist with id={}', person_id)

            result = conn.execute(stmt.values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating person with id={}', person_id)

    def update_user_name(self, user_id, name, remote_addr=None,
                         _test_skip_check=False):
        if not name:
            raise UserError('The new user name can not be blank.')

        with self._transaction() as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, user, user_id)):
                raise ConsistencyError(
                    'user does not exist with id={}', user_id)

            if not _test_skip_check and self._exists_user_name(conn, name):
                raise UserError(
                    'The user account name "{}" already exists.', name)

            result = conn.execute(user.update().where(
                user.c.id == user_id
            ).values({
                user.c.name: name,
            }))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating user with id={}', user_id)

            self._add_user_log_entry(
                conn, user_id, UserLogEvent.CHANGE_NAME, remote_addr)

    def update_user_password(self, user_id, password_raw, remote_addr=None,
                             _test_skip_check=False, _skip_log=False,
                             _conn=None):
        """
        Update a user's password.

        :raises UserError: if the password is blank.
        """

        if not password_raw:
            raise UserError('The password can not be blank.')

        (password_hash, password_salt) = create_password_hash(password_raw)

        with self._transaction(_conn=_conn) as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, user, user_id)):
                raise ConsistencyError(
                    'user does not exist with id={}', user_id)

            result = conn.execute(user.update().where(
                user.c.id == user_id
            ).values({
                user.c.password: password_hash,
                user.c.salt: password_salt,
            }))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating user with id={}', user_id)

            if not _skip_log:
                self._add_user_log_entry(
                    conn, user_id, UserLogEvent.CHANGE_PASS, remote_addr)

    def use_email_verify_token(
            self, person_id, token, user_id, remote_addr=None):
        """
        Tries to use the given email verification token.

        Also ensures the person record is marked as verified.
        """

        with self._transaction() as conn:
            # Remove any expired tokens.
            conn.execute(verify_token.delete().where(
                verify_token.c.expiry < datetime.utcnow()))

            # Try to fetch this token.
            result = conn.execute(verify_token.select().where(
                verify_token.c.token == token)).first()

            if result is None:
                raise NoSuchRecord('verify token expired or non-existant')

            email_address = result['email_address']
            if person_id != result['person_id']:
                raise UserError('This verification code appears to have been '
                                'issued to someone else.')

            # If we found it, go ahead and verify the email address.
            result = conn.execute(email.update().where(and_(
                email.c.person_id == person_id,
                email.c.address == email_address)).values({
                    'verified': True,
                }))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched verifying email address')

            # Ensure the person profile is marked as verified.
            self.update_person(person_id, verified=True, _conn=conn)

            # Finally delete the token (which has now been used).
            conn.execute(verify_token.delete().where(
                verify_token.c.token == token))

            if user_id is not None:
                self._add_user_log_entry(
                    conn, user_id, UserLogEvent.USE_EMAIL_TOKEN, remote_addr)

        return email_address

    def use_password_reset_token(self, token, password_raw, remote_addr):
        """
        Tries to use the given password reset token.

        :return: the user_name corresponding to the given token, if successful.

        :raises NoSuchRecord: if the token is not found.
        """

        with self._transaction() as conn:
            # Remove any expired tokens to keep the reset_token
            # table tidy.
            conn.execute(reset_token.delete().where(
                reset_token.c.expiry < datetime.utcnow()))

            # Try to fetch this token.
            result = conn.execute(reset_token.select().where(
                reset_token.c.token == token
            )).first()

            if result is None:
                raise NoSuchRecord('reset token expired or non-existant')

            user_id = result['user_id']

            # Log the usage of this token.
            self._add_user_log_entry(
                conn, user_id, UserLogEvent.USE_TOKEN, remote_addr)

            # Apply the password change, without adding another log entry.
            self.update_user_password(user_id, password_raw, remote_addr,
                                      _skip_log=True, _conn=conn)

            # Delete the used password reset token.
            conn.execute(reset_token.delete().where(
                reset_token.c.token == token))

            # Clear the auth failure record for this user.
            user_name = self.get_user_name(user_id, _conn=conn)

            self._delete_auth_failure(user_name=user_name, _conn=conn)

        return user_name

    def use_invitation(self, token, user_id=None, new_person_id=None,
                       remote_addr=None, _test_skip_check=False):
        """
        Uses the invitation token to link the given user_id to the
        person record associated with the invitation.

        Also ensures the person record is marked as verified.

        Returns the person record to which the invitation refers as it was
        before the invitation was accepted.
        """

        if user_id is None and new_person_id is None:
            raise Error('one of user_id and new_person_id must be specified')
        if not (user_id is None or new_person_id is None):
            raise Error('user_id and new_person_id can not both be specified')

        with self._transaction() as conn:
            # Check the user or person exist.
            if not _test_skip_check:
                if user_id is not None:
                    if not self._exists_id(conn, user, user_id):
                        raise ConsistencyError(
                            'user does not exist with id={}', user_id)
                if new_person_id is not None:
                    if not self._exists_id(conn, person, new_person_id):
                        raise ConsistencyError(
                            'person does not exist with id={}', new_person_id)

            # Removed any expired invitations, as for password reset tokens.
            conn.execute(invitation.delete().where(
                invitation.c.expiry < datetime.utcnow()))

            # Fetch the requested invitation.
            result = conn.execute(invitation.select().where(
                invitation.c.token == token
                )).first()

            if result is None:
                raise NoSuchRecord('invitation token expired or non-existant')

            old_person_id = result['person_id']
            old_person_record = self.get_person(old_person_id,
                                                with_proposals=True,
                                                with_reviews=True,
                                                _conn=conn)

            if user_id is not None:
                # Remove the token.
                conn.execute(invitation.delete().where(
                    invitation.c.token == token))

                # They have registered a new user account to link to the
                # invited person record.  Simply set the user_id there
                # and mark as verified.
                result = conn.execute(person.update().where(and_(
                    person.c.id == old_person_id,
                    person.c.user_id.is_(None),
                    not_(person.c.admin)
                )).values({
                    person.c.user_id: user_id,
                    person.c.verified: True,
                }))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched setting new user_id'
                        ' for person with id={}',
                        old_person_id)

                self._add_user_log_entry(
                    conn, user_id, UserLogEvent.USE_INVITE, remote_addr)

            elif new_person_id is not None:
                # Merge the person records, treating the "old_person_id"
                # from the invitation as a duplicate, applying a constraint
                # to ensure the "old_person_id" profile wasn't already
                # registered.
                self.merge_person_records(
                    main_person_id=new_person_id,
                    duplicate_person_id=old_person_id,
                    duplicate_person_registered=False,
                    _conn=conn)

                # Ensure the "new" profile is marked as verified.
                self.update_person(new_person_id, verified=True, _conn=conn)

            else:
                # They were there at the start of the method so this
                # shouldn't happen.
                raise Error('user_id or new_person_id vanished')

        return old_person_record

    def _add_user_log_entry(self, conn, user_id, event, remote_addr=None):
        """
        Adds an entry to the user log table.
        """

        if not UserLogEvent.is_valid(event):
            raise Error('Invalid user account action log event type')

        conn.execute(user_log.insert().values({
            user_log.c.user_id: user_id,
            user_log.c.date: datetime.utcnow(),
            user_log.c.event: event,
            user_log.c.remote_addr: remote_addr,
        }))

    def _check_rate_limit(self, conn, user_id, event, limit):
        """
        Checks the number of user log entries for the given event type
        against the specified limit.

        :raises: UserError if excess entries present.
        """

        events = self.search_user_log(
            user_id=user_id,
            event=event,
            date_after=(datetime.utcnow() - rate_limit_period),
            _conn=conn)

        if len(events) >= limit:
            raise UserError('Excess requests of this type.')

    def _exists_person_user(self, conn, user_id):
        """Test whether a person exists with the given user_id."""
        return 0 < conn.execute(select([count(person.c.id)]).where(
            person.c.user_id == user_id
        )).scalar()

    def _exists_user_name(self, conn, name):
        """Test whether a user exists by name."""
        return 0 < conn.execute(select([count(user.c.id)]).where(
            user.c.name == name
        )).scalar()
