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

from datetime import datetime, timedelta

from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_, not_
from sqlalchemy.sql.functions import count

from ...auth import check_password_hash, create_password_hash, generate_token
from ...error import ConsistencyError, Error, NoSuchRecord, UserError
from ...type import Email, EmailCollection, Institution, InstitutionInfo, \
    Person, ResultCollection
from ..meta import email, institution, invitation, member, person, \
    reset_token, user
from ..util import require_not_none


class PeoplePart(object):
    def add_email(self, person_id, address, primary=False, verified=False,
                  public=False, _test_skip_check=False):
        """
        Add an email address record to the databae.

        Returns the email_id number.
        """

        with self._transaction() as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, person, person_id)):
                raise ConsistencyError(
                    'person does not exist with id={0}', person_id)

            result = conn.execute(email.insert().values({
                email.c.person_id: person_id,
                email.c.address: address,
                email.c.primary: primary,
                email.c.verified: verified,
                email.c.public: public,
            }))

        return result.inserted_primary_key[0]

    def add_institution(self, name):
        """
        Add an institution to the database.

        Returns the new institution_id number.
        """

        with self._transaction() as conn:
            result = conn.execute(institution.insert().values({
                institution.c.name: name,
            }))

        return result.inserted_primary_key[0]

    def add_invitation(self, person_id, _test_skip_check=False):
        """
        Creates an invitation token to allow someone to register as the
        given person and adds it to the database.

        Deletes existing tokens to register as this person.

        Returns the new token.
        """

        token = generate_token()
        expiry = datetime.utcnow() + timedelta(days=30)

        with self._transaction() as conn:
            if not _test_skip_check:
                result = conn.execute(select([
                    person.c.user_id, person.c.admin
                ]).where(
                    person.c.id == person_id
                )).first()
                if result is None:
                    raise ConsistencyError('person does not exist with id={0}',
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

        return token

    def add_person(self, name, public=False, user_id=None,
                   _test_skip_check=False):
        """
        Add a person to the database.

        If the user_id for an existing user is provided, then the person
        includes a reference to that user.
        """

        with self._transaction() as conn:
            if user_id is not None and not _test_skip_check:
                if not self._exists_id(conn, user, user_id):
                    raise ConsistencyError(
                        'user does not exist with id={0}', user_id)
                if self._exists_person_user(conn, user_id):
                    raise ConsistencyError(
                        'person already exists with user_id={0}', user_id)

            result = conn.execute(person.insert().values({
                person.c.name: name,
                person.c.public: public,
                person.c.user_id: user_id,
                person.c.admin: False,
            }))

            person_id = result.inserted_primary_key[0]

        return person_id

    def add_user(self, name, password_raw, person_id=None,
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
                    'The user account name "{0}" already exists.',
                    name)

            result = conn.execute(user.insert().values({
                user.c.name: name,
                user.c.password: password_hash,
                user.c.salt: password_salt,
            }))

            user_id = result.inserted_primary_key[0]

            if person_id is not None:
                if not _test_skip_check and \
                        not self._exists_id(conn, person, person_id):
                    raise ConsistencyError(
                        'person does not exist with id={0}', person_id)

                result = conn.execute(person.update().where(and_(
                    person.c.id == person_id,
                    person.c.user_id.is_(None)
                )).values({
                    person.c.user_id: user_id,
                }))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched setting new user_id'
                        ' for person with id={0}',
                        person_id)

        return user_id

    def authenticate_user(self, name, password_raw, user_id=None):
        """
        Given a user name and raw password, try to authenitcate the user.

        Can take a user_id instead of a user name for re-authentication,
        e.g. before changing password.  In that case, name must be
        explicitly set to None (to prevent accidental use of this
        rare use-case).

        Returns the user_id on success, None otherwise.
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
            result = conn.execute(stmt).first()

        if result is None:
            # Spend time hashing the password so that the user can't tell
            # that the user name doesn't exist by this function returning fast.
            create_password_hash(password_raw)
            return None

        else:
            if check_password_hash(password_raw, result[user.c.password],
                                   result[user.c.salt]):
                return result[user.c.id]
            else:
                return None

    def get_institution(self, institution_id):
        """
        Get an institution record.
        """

        with self._transaction() as conn:
            return self._get_institution(conn, institution_id)

    def _get_institution(self, conn, institution_id):
        result = conn.execute(institution.select().where(
            institution.c.id == institution_id
        )).first()

        if result is None:
            raise NoSuchRecord('institution does not exist with id={0}',
                               institution_id)

        return Institution(**result)

    def get_person(self, person_id, user_id=None,
                   with_email=False, with_institution=False):
        """
        Get a person record.

        Can take a user_id instead of a person_id, but in that case,
        person_id must be explicitly set to None (to prevent accidental use
        of this rare use-case).

        Raises NoSuchRecord if the person_id doesn't exist.
        """

        email = None
        institution = None

        stmt = person.select()
        if person_id is not None:
            stmt = stmt.where(person.c.id == person_id)
        elif user_id is not None:
            stmt = stmt.where(person.c.user_id == user_id)
        else:
            raise Error('neither person_id nor user_id specified')

        with self._transaction() as conn:
            result = conn.execute(stmt).first()

            if result is None:
                raise NoSuchRecord('person does not exist')

            # If we weren't searching by person_id, we need to retrieve it
            # from the record.
            if person_id is None:
                person_id = result['id']

            if with_institution and result['institution_id'] is not None:
                institution = self._get_institution(conn, result['institution_id'])

            if with_email:
                email = self._search_email(conn, person_id=person_id)

        return Person(email=email, institution=institution, **result)

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
    def get_user_name(self, user_id):
        """
        Get the user name associated with the given user_id.
        """

        with self._transaction() as conn:
            return conn.execute(select([user.c.name]).where(
                user.c.id == user_id
            )).scalar()

    def list_institution(self):
        """
        Get a list of all institutions.

        Summary information is returned.
        """

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(select([institution.c.id,
                                            institution.c.name
                                            ]).order_by(institution.c.name)):
                ans[row['id']] = InstitutionInfo(**row)

        return ans

    def get_password_reset_token(self, user_id):
        """
        Create a password reset token for a given user.

        Deletes any existing tokens for this user and returns the new token.
        """

        token = generate_token()
        expiry = datetime.utcnow() + timedelta(hours=4)

        with self._transaction() as conn:
            conn.execute(reset_token.delete().where(
                reset_token.c.user_id == user_id))

            result = conn.execute(reset_token.insert().values({
                reset_token.c.token: token,
                reset_token.c.user_id: user_id,
                reset_token.c.expiry: expiry,
            }))

        return token

    def search_email(self, person_id):
        """
        Find email address records.
        """

        with self._transaction() as conn:
            return self._search_email(conn, person_id)

    def _search_email(self, conn, person_id):
        stmt = email.select()
        stmt = stmt.where(email.c.person_id == person_id)

        ans = EmailCollection()

        for row in conn.execute(stmt.order_by(email.c.id)):
            ans[row['id']] = Email(**row)

        return ans

    def search_person(self, user_id=None, email_address=None, registered=None):
        """
        Find person records.
        """

        stmt = person.select()

        if user_id is not None:
            stmt = stmt.where(person.c.user_id == user_id)

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

        ans = ResultCollection()

        with self._transaction() as conn:
            for row in conn.execute(stmt.order_by(person.c.name)):
                ans[row['id']] = Person(email=None, institution=None, **row)

        return ans

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
                    'person does not exist with id={0}', person_id)

            return self._sync_records(
                conn, email, email.c.person_id, person_id, records, [
                    email.c.address, email.c.primary, email.c.public,
                ], verified_columns=(email.c.address,))

    def update_institution(self, institution_id, name=None,
                           _test_skip_check=False):
        """
        Update an institution record.
        """

        values = {}

        if name is not None:
            values['name'] = name

        if not values:
            raise Error('no institution updates specified')

        with self._transaction() as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, institution, institution_id):
                raise ConsistencyError(
                    'institution does not exist with id={0}', institution_id)

            result = conn.execute(institution.update().where(
                institution.c.id == institution_id
            ).values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating institution with id={0}',
                    institution_id)

    def update_person(self, person_id,
                      name=None, public=None, institution_id=(),
                      admin=None,
                      _test_skip_check=False):
        """
        Update a person database record.
        """

        stmt = person.update().where(person.c.id == person_id)
        values = {}

        if name is not None:
            values['name'] = name
        if public is not None:
            values['public'] = public
        if institution_id != ():
            values['institution_id'] = institution_id
        if admin is not None:
            values['admin'] = admin
            # Don't allow setting of the admin flag for non-registered users.
            if admin and not _test_skip_check:
                stmt = stmt.where(not_(person.c.user_id.is_(None)))

        # The values dictionary is only empty if the caller specified
        # no parameters, i.e. everything was left at the default of ()
        # meaning do nothing.  In this case, raise an error.
        if not values:
            raise Error('no person updates specified')

        with self._transaction() as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, person, person_id)):
                raise ConsistencyError(
                    'person does not exist with id={0}', person_id)

            result = conn.execute(stmt.values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating person with id={0}',
                    person_id)

    def update_user_name(self, user_id, name, _test_skip_check=False):
        if not name:
            raise UserError('The new user name can not be blank.')

        with self._transaction() as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, user, user_id)):
                raise ConsistencyError(
                    'user does not exist with id={0}', user_id)

            if not _test_skip_check and self._exists_user_name(conn, name):
                raise UserError(
                    'The user account name "{0}" already exists.',
                    name)

            result = conn.execute(user.update().where(
                user.c.id == user_id
            ).values({
                user.c.name: name,
            }))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating user with id={0}',
                    user_id)

    def update_user_password(self, user_id, password_raw,
                             _test_skip_check=False):
        if not password_raw:
            raise UserError('The password can not be blank.')

        (password_hash, password_salt) = create_password_hash(password_raw)

        with self._transaction() as conn:
            if (not _test_skip_check and
                    not self._exists_id(conn, user, user_id)):
                raise ConsistencyError(
                    'user does not exist with id={0}', user_id)

            result = conn.execute(user.update().where(
                user.c.id == user_id
            ).values({
                user.c.password: password_hash,
                user.c.salt: password_salt,
            }))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating user with id={0}',
                    user_id)

    def use_password_reset_token(self, token):
        """
        Tries to use the given password reset token.

        If successful returns the user_id.  Otherwise returns None.
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

            # If we found it, consider it used and delete it.
            conn.execute(reset_token.delete().where(
                reset_token.c.token == token))

        return result['user_id']

    def use_invitation(self, token, user_id=None, new_person_id=None,
                       _test_skip_check=False):
        """
        Uses the invitation token to link the given user_id to the
        person record associated with the invitation.
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
                            'user does not exist with id={0}', user_id)
                if new_person_id is not None:
                    if not self._exists_id(conn, person, new_person_id):
                        raise ConsistencyError(
                            'person does not exist with id={0}', new_person_id)

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

            # Remove the token.  (Must do first otherwise it has a foreign
            # key which references the person record and prevents its
            # deletion, but this should be OK as any exceptions should
            # abort the whole transaction.)
            conn.execute(invitation.delete().where(
                invitation.c.token == token))

            if user_id is not None:
                # They have registered a new user account to link to the
                # invited person record.  Simply set the user_id there.
                result = conn.execute(person.update().where(and_(
                    person.c.id == old_person_id,
                    person.c.user_id.is_(None),
                    not_(person.c.admin)
                )).values({
                    person.c.user_id: user_id,
                }))

                if result.rowcount != 1:
                    raise ConsistencyError(
                        'no rows matched setting new user_id'
                        ' for person with id={0}',
                        old_person_id)

            elif new_person_id is not None:
                # They already have a person record, so swap out the
                # record linked to the invitation and delete it.
                for table in (member,):
                    conn.execute(table.update().where(
                        table.c.person_id == old_person_id
                    ).values({
                        table.c.person_id: new_person_id,
                    }))

                result = conn.execute(person.delete().where(
                    person.c.id == old_person_id))

            else:
                # They were there at the start of the method so this
                # shouldn't happen.
                raise Error('user_id or new_person_id vanished')

    def _exists_person_user(self, conn, user_id):
        """Test whether a person exists with the given user_id."""
        return 0 < conn.execute(select([count(person.c.id)]).where(
            person.c.user_id == user_id,
        )).scalar()

    def _exists_user_name(self, conn, name):
        """Test whether a user exists by name."""
        return 0 < conn.execute(select([count(user.c.id)]).where(
            user.c.name == name,
        )).scalar()
