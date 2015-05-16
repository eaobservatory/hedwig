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

from collections import OrderedDict
from datetime import datetime, timedelta

from insertnamehere import auth
from insertnamehere.db.meta import reset_token
from insertnamehere.error import ConsistencyError, DatabaseIntegrityError, \
    Error, NoSuchRecord, UserError
from insertnamehere.type import Email, Institution, InstitutionInfo, Person
from .dummy_db import DBTestCase


class DBUserTest(DBTestCase):
    def setUp(self):
        DBTestCase.setUp(self)
        auth._rounds = 10

    def test_user(self):
        # Check that we can create a user and get an integer user_id.
        user_id = self.db.add_user('user1', 'pass1')
        self.assertIsInstance(user_id, int)

        user_name = self.db.get_user_name(user_id)
        self.assertEqual(user_name, 'user1')

        # Attempting to re-create the same user is an error.
        with self.assertRaises(UserError):
            self.db.add_user('user1', 'pass1')

        # Ensure that, even if we don't check for duplicate users,
        # the database traps the error.
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_user('user1', 'pass1', _test_skip_check=True)

        # Test successful authentication.
        self.assertEqual(self.db.authenticate_user('user1', 'pass1'), user_id)

        # Test unsuccessful authentication.
        self.assertIsNone(self.db.authenticate_user('user1', 'wrongpass'))
        self.assertIsNone(self.db.authenticate_user('user2', 'pass1'))

        # Test creation with reference to an existing person.
        person_id = self.db.add_person('User Three')
        user_id = self.db.add_user('user3', 'pass3', person_id=person_id)
        self.assertIsInstance(user_id, int)

        # Attempting to reference a non-existant person is an error.
        with self.assertRaisesRegexp(ConsistencyError,
                                     '^person does not exist'):
            user_id = self.db.add_user('user4', 'pass4', person_id=999)

        # Check that we also detects this error via.
        with self.assertRaisesRegexp(ConsistencyError, '^no rows matched'):
            user_id = self.db.add_user('user4', 'pass4', person_id=999,
                                       _test_skip_check=True)

        # Test changing a password.
        self.assertEqual(self.db.authenticate_user('user3', 'pass3'), user_id)
        self.db.update_user_password(user_id, '3ssap')
        self.assertIsNone(self.db.authenticate_user('user3', 'pass3'))
        self.assertEqual(self.db.authenticate_user('user3', '3ssap'), user_id)

    def test_user_person(self):
        # Check that we can create a person and get an integer person_id.
        person_id = self.db.add_person('User Zero')
        self.assertIsInstance(person_id, int)

        # Attempting to reference a non-existant user_id is an error.
        with self.assertRaisesRegexp(ConsistencyError, '^user does not exist'):
            self.db.add_person('User One', user_id=999)

        # Check that the database also traps this error.
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_person('User One', user_id=999,
                               _test_skip_check=True)

        # Create a person which references a valid user_id.
        user_id = self.db.add_user('user1', 'pass1')
        person_id = self.db.add_person('User One', user_id=user_id)
        self.assertIsInstance(person_id, int)

        # Check that we can't have two person records referencing the same
        # user.
        with self.assertRaisesRegexp(ConsistencyError,
                                     '^person already exists with user_id'):
            person_id = self.db.add_person('User Two', user_id=user_id)

        # Check that the database also recognises this error.
        with self.assertRaises(DatabaseIntegrityError):
            person_id = self.db.add_person('User Two', user_id=user_id,
                                           _test_skip_check=True)

    def test_email(self):
        # Check that we can add an email address.
        person_id = self.db.add_person('User One')
        email_id = self.db.add_email(person_id, 'one@users.net')

        self.assertIsInstance(email_id, int)

        # Test person_id existance checking.
        with self.assertRaisesRegexp(ConsistencyError,
                                     '^person does not exist'):
            email_id = self.db.add_email(999, 'zero@users.net')

        # Test that the database check for the same thing works.
        with self.assertRaises(DatabaseIntegrityError):
            email_id = self.db.add_email(999, 'zero@users.net',
                                         _test_skip_check=True)

        # Test that the database prevents duplicates for the same person.
        with self.assertRaises(DatabaseIntegrityError):
            email_id = self.db.add_email(person_id, 'one@users.net')

        # But we can have the same address for multiple person records.
        person_id = self.db.add_person('User One Duplicate')
        email_id = self.db.add_email(person_id, 'one@users.net')
        self.assertIsInstance(email_id, int)

        # Add a second address and try a search.
        email_id2 = self.db.add_email(person_id, 'one@another.name')
        result = self.db.search_email(person_id=person_id)

        self.assertIsInstance(result, OrderedDict)
        self.assertEqual(len(result), 2)

        for ((result_id, email), address, expected_id) in zip(
                result.items(),
                ['one@users.net', 'one@another.name'],
                [email_id, email_id2]):
            self.assertIsInstance(email, Email)
            self.assertEqual(email.id, result_id)
            self.assertEqual(email.id, expected_id)
            self.assertEqual(email.person_id, person_id)
            self.assertEqual(email.address, address)
            self.assertIs(email.primary, False)
            self.assertIs(email.validated, False)
            self.assertIs(email.public, False)

        # Try searching for people by email address.
        # TODO: check these results more thoroughly.
        result = self.db.search_person(email_address='one@users.net')
        self.assertEqual(len(result), 2)
        result = self.db.search_person(email_address='one@another.name')
        self.assertEqual(len(result), 1)
        result = self.db.search_person(email_address='one@another.name',
                                       registered=True)
        self.assertEqual(len(result), 0)

    def test_institution(self):
        # Try getting a non-existent institution record.
        with self.assertRaisesRegexp(NoSuchRecord,
                                     '^institution does not exist'):
            institution = self.db.get_institution(999)

        # Check that we can add an institution.
        institution_id = self.db.add_institution('Institution One')

        self.assertIsInstance(institution_id, int)

        # Try retrieving the institution.
        institution = self.db.get_institution(institution_id)
        self.assertIsInstance(institution, Institution)

        # Get a list of institutions.
        institution_id2 = self.db.add_institution('Institution Two')
        result = self.db.list_institution()
        self.assertIsInstance(result, OrderedDict)
        self.assertEqual(len(result), 2)

        for ((row_id, institution), name, expected_id) in zip(
                result.items(),
                ['Institution One', 'Institution Two'],
                [institution_id, institution_id2]):
            self.assertIsInstance(institution, InstitutionInfo)
            self.assertEqual(institution.id, row_id)
            self.assertEqual(institution.id, expected_id)
            self.assertEqual(institution.name, name)

    def test_person(self):
        # Try getting a non-existent person record.
        with self.assertRaisesRegexp(NoSuchRecord, '^person does not exist'):
            person = self.db.get_person(999)

        # Create a test person record.
        person_id = self.db.add_person('Person One')
        self.assertIsInstance(person_id, int)

        # Check starting state of the record.
        person = self.db.get_person(person_id)
        self.assertIsInstance(person, Person)
        self.assertIsNone(person.institution_id)

        # Create a test institution record.
        institution_id = self.db.add_institution('Institution One')
        self.assertIsInstance(institution_id, int)

        # Update the person to reference the new institution.
        self.db.update_person(person_id, institution_id=institution_id)

        # Get and inspect the updated record.
        person = self.db.get_person(person_id)
        self.assertIsInstance(person, Person)
        self.assertEqual(person.institution_id, institution_id)

        # Check that errors are trapped.
        with self.assertRaisesRegexp(Error, '^no person updates specified'):
            self.db.update_person(person_id)
        with self.assertRaisesRegexp(ConsistencyError, '^person does not'):
            self.db.update_person(999, institution_id=institution_id)
        with self.assertRaisesRegexp(ConsistencyError, '^no rows matched'):
            self.db.update_person(999, institution_id=institution_id,
                                  _test_skip_check=True)
        with self.assertRaises(DatabaseIntegrityError):
            self.db.update_person(person_id, institution_id=999)

    def test_password_reset_token(self):
        # Create a user record.
        user_id = self.db.add_user('user1', 'pass1')
        self.assertIsInstance(user_id, int)

        # Try making a reset token.
        token = self.db.make_password_reset_token(user_id)
        self.assertIsInstance(token, str)
        self.assertEqual(len(token), 32)

        # Using a bad token should do nothing.
        token_user_id = self.db.use_password_reset_token(b'not a valid token')
        self.assertIsNone(token_user_id)

        # Using the token should return this user id.
        token_user_id = self.db.use_password_reset_token(token)
        self.assertEqual(token_user_id, user_id)

        # Using the token again should return None because the
        # token should have been deleted.
        token_user_id = self.db.use_password_reset_token(token)
        self.assertIsNone(token_user_id)

        # Issue two more tokens: the older should be removed automatically.
        token1 = self.db.make_password_reset_token(user_id)
        token2 = self.db.make_password_reset_token(user_id)
        token_user_id = self.db.use_password_reset_token(token1)
        self.assertIsNone(token_user_id)
        token_user_id = self.db.use_password_reset_token(token2)
        self.assertEqual(token_user_id, user_id)

        # Create a token and artificially age it by putting the expiry
        # date in the past.  It should then not work.
        token = self.db.make_password_reset_token(user_id)
        with self.db._transaction() as conn:
            result = conn.execute(reset_token.update().where(
                reset_token.c.token == token
            ).values({
                reset_token.c.expiry: datetime.utcnow() - timedelta(hours=1),
            }))

            self.assertEqual(result.rowcount, 1)
        token_user_id = self.db.use_password_reset_token(token)
        self.assertIsNone(token_user_id)
