# Copyright (C) 2015-2024 East Asian Observatory
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

from hedwig import auth
from hedwig.compat import string_type
from hedwig.db.compat import select
from hedwig.db.meta import auth_failure, invitation, reset_token
from hedwig.error import ConsistencyError, DatabaseIntegrityError, \
    Error, NoSuchRecord, UserError
from hedwig.type.collection import EmailCollection, ResultCollection, \
    SiteGroupMemberCollection
from hedwig.type.enum import BaseAffiliationType, BaseCallType, BaseTextRole, \
    FormatType, \
    SiteGroupType, UserLogEvent
from hedwig.type.simple import Email, \
    Institution, InstitutionInfo, MemberInstitution, \
    OAuthCode, OAuthToken, Person, SiteGroupMember, UserInfo
from .dummy_db import DBTestCase


class DBPeopleTest(DBTestCase):
    def test_user(self):
        records = self.db.search_user()
        self.assertFalse(records)

        # Check that we can create a user and get an integer user_id.
        user_id = self.db.add_user('user1', 'pass1')
        self.assertIsInstance(user_id, int)

        user_name = self.db.get_user_name(user_id)
        self.assertEqual(user_name, 'user1')

        with self.assertRaises(NoSuchRecord):
            self.db.get_user_name(1999999)

        user_id_fetched = self.db.get_user_id('user1')
        self.assertEqual(user_id_fetched, user_id)

        with self.assertRaises(NoSuchRecord):
            self.db.get_user_id('no-user')

        records = self.db.search_user()
        self.assertEqual(len(records), 1)
        self.assertIn(user_id, records)
        user_info = records[user_id]
        self.assertIsInstance(user_info, UserInfo)
        self.assertEqual(user_info.id, user_id)
        self.assertEqual(user_info.name, 'user1')
        self.assertFalse(user_info.disabled)

        records = self.db.search_user(registered=True)
        self.assertEqual(len(records), 0)
        records = self.db.search_user(registered=False)
        self.assertEqual(len(records), 1)

        # Attempting to re-create the same user is an error.
        with self.assertRaises(UserError):
            self.db.add_user('user1', 'pass1')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_user('user1', 'pass1', _test_skip_check=True)

        # Ensure that, even if we don't check for duplicate users,
        # the database traps the error.
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_user('user1', 'pass1', _test_skip_check=True)

        # Test successful authentication.
        self.assertEqual(self.db.authenticate_user('user1', 'pass1'), user_id)

        # Test unsuccessful authentication.
        auth.password_hash_delay = 0
        self.assertIsNone(self.db.authenticate_user('user1', 'wrongpass'))
        self.assertIsNone(self.db.authenticate_user('user2', 'pass1'))

        # Test creation with reference to an existing person.
        person_id = self.db.add_person('User Three')
        user_id_3 = self.db.add_user('user3', 'pass3', person_id=person_id)
        self.assertIsInstance(user_id_3, int)

        records = self.db.search_user()
        self.assertEqual(len(records), 2)
        records = self.db.search_user(registered=True)
        self.assertEqual(len(records), 1)
        self.assertIn(user_id_3, records)
        records = self.db.search_user(registered=False)
        self.assertEqual(len(records), 1)
        self.assertNotIn(user_id_3, records)

        # Attempting to reference a non-existant person is an error.
        with self.assertRaisesRegex(ConsistencyError,
                                    '^person does not exist'):
            self.db.add_user('user4', 'pass4', person_id=1999999)

        # Check that we also detects this error via.
        with self.assertRaisesRegex(ConsistencyError, '^no rows matched'):
            self.db.add_user('user4', 'pass4', person_id=1999999,
                             _test_skip_check=True)

        # Test changing a password.
        self.assertEqual(self.db.authenticate_user('user3', 'pass3'), user_id_3)
        self.db.update_user_password(user_id_3, '3ssap')
        self.assertIsNone(self.db.authenticate_user('user3', 'pass3'))
        self.assertEqual(self.db.authenticate_user('user3', '3ssap'), user_id_3)

        # Test changing a user name
        self.db.update_user_name(user_id_3, '3resu')
        self.assertEqual(self.db.get_user_name(user_id_3), '3resu')
        with self.assertRaisesRegex(ConsistencyError, '^user does not exist'):
            self.db.update_user_name(1999999, 'newname')
        with self.assertRaisesRegex(ConsistencyError, '^no rows matched'):
            self.db.update_user_name(1999999, 'newname', _test_skip_check=True)
        with self.assertRaisesRegex(UserError, r'already exists\.$'):
            self.db.update_user_name(user_id_3, 'user1')
        with self.assertRaises(DatabaseIntegrityError):
            self.db.update_user_name(user_id_3, 'user1', _test_skip_check=True)
        with self.assertRaisesRegex(UserError, 'blank'):
            self.db.update_user_name(user_id_3, '')

        # Test a disabled account.
        self.db.update_user(user_id, disabled=True)
        self.assertTrue(self.db.search_user(
            user_id=user_id).get_single().disabled)

        with self.assertRaisesRegex(UserError, 'account is disabled'):
            self.db.authenticate_user('user1', 'pass1')

        self.db.update_user(user_id, disabled=False)
        self.assertFalse(self.db.search_user(
            user_id=user_id).get_single().disabled)

    def test_user_auth_failure(self):
        allowed_failures = 5
        auth.password_hash_delay = 0

        user_id = self.db.add_user('user1', 'pass1')

        # Make the maximum number of attempts.
        for i in range(0, allowed_failures):
            self.assertIsNone(self.db.authenticate_user('user1', 'wrongpass'))

            with self.db._transaction() as conn:
                attempts = conn.execute(select([
                    auth_failure.c.attempts
                ]).where(auth_failure.c.user_name == 'user1')).scalar()

            self.assertEqual(attempts, i + 1)

        # The next failure should raise an error.
        with self.assertRaisesRegex(
                UserError, 'Too many authentication attempts'):
            self.assertIsNone(self.db.authenticate_user('user1', 'wrongpass'))

        # Delete the failure record and ensure we can try again.
        self.db._delete_auth_failure('user1')

        self.assertIsNone(self.db.authenticate_user('user1', 'wrongpass'))

    def test_user_auth_token(self):
        user_id = self.db.add_user('user1', 'pass1')

        (token, expiry) = self.db.issue_auth_token(
            user_id, remote_addr=None, remote_agent=None)

        self.assertIsInstance(token, string_type)
        self.assertRegex(token, '^[0-9a-f]{64}$')
        self.assertIsInstance(expiry, datetime)

        with self.assertRaises(NoSuchRecord):
            self.db.authenticate_token('invalid token')

        (user, auth_token_id) = self.db.authenticate_token(token)
        self.assertIsInstance(user, UserInfo)
        self.assertEqual(user.id, user_id)
        self.assertEqual(user.name, 'user1')
        self.assertIsInstance(auth_token_id, int)

        # Try disabling the account.
        self.db.update_user(user_id, disabled=True)

        with self.assertRaises(NoSuchRecord):
            self.db.authenticate_token(token)

        self.db.update_user(user_id, disabled=False)

        (user, auth_token_id) = self.db.authenticate_token(token)
        self.assertEqual(user.id, user_id)

        # Delete the token.
        self.db.delete_auth_token(token=token)

        with self.assertRaises(NoSuchRecord):
            self.db.authenticate_token(token)

    def test_user_person(self):
        # Check that we can create a person and get an integer person_id.
        person_id = self.db.add_person('User Zero')
        self.assertIsInstance(person_id, int)

        # Attempting to reference a non-existant user_id is an error.
        with self.assertRaisesRegex(ConsistencyError, '^user does not exist'):
            self.db.add_person('User One', user_id=1999999)

        # Check that the database also traps this error.
        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_person('User One', user_id=1999999,
                               _test_skip_check=True)

        # Create a person which references a valid user_id.
        user_id = self.db.add_user('user1', 'pass1')
        person_id = self.db.add_person('User One', user_id=user_id)
        self.assertIsInstance(person_id, int)

        # Check that we can't have two person records referencing the same
        # user.
        with self.assertRaisesRegex(ConsistencyError,
                                    '^person already exists with user_id'):
            person_id = self.db.add_person('User Two', user_id=user_id)

        # Check that the database also recognises this error.
        with self.assertRaises(DatabaseIntegrityError):
            person_id = self.db.add_person('User Two', user_id=user_id,
                                           _test_skip_check=True)

        # Try getting a person by user_id.
        result = self.db.get_person(person_id=None, user_id=user_id)
        self.assertIsInstance(result, Person)
        self.assertEqual(result.id, person_id)

        # And make sure get_person requires at least one non-None parameter.
        with self.assertRaisesRegex(Error, 'specified'):
            self.db.get_person(person_id=None, user_id=None)

    def test_delete_user(self):
        user_id_1 = self.db.add_user('user1', 'pass1')
        user_id_2 = self.db.add_user('user2', 'pass2')

        result = self.db.search_user()
        self.assertEqual(set(result), set((user_id_1, user_id_2)))

        # Delete a user record and check it has gone.
        self.db.delete_user(user_id_1)

        result = self.db.search_user()
        self.assertEqual(set(result), set((user_id_2,)))

        # Try deleting the record which does not exist.
        with self.assertRaisesRegex(ConsistencyError, '^user does not exist'):
            self.db.delete_user(user_id_1)

        with self.assertRaisesRegex(ConsistencyError, '^no row matched'):
            self.db.delete_user(user_id_1, _test_skip_check=True)

        # Try deleting the record for a registered user.
        self.db.add_person('User Two', user_id=user_id_2)

        with self.assertRaisesRegex(ConsistencyError, '^person exists with'):
            self.db.delete_user(user_id_2)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.delete_user(user_id_2, _test_skip_check=True)

    def test_email(self):
        # Check that we can add an email address.
        person_id = self.db.add_person('User One')
        email_id = self.db.add_email(person_id, 'one@users.net')

        self.assertIsInstance(email_id, int)

        # Test address validation.
        with self.assertRaisesRegex(UserError, 'does not appear to be valid'):
            self.db.add_email(person_id, 'A B <a.b@c.d>')

        # Test that we can't add a person with an invalid primary email.
        with self.assertRaisesRegex(UserError, 'does not appear to be valid'):
            self.db.add_person('Invalid Email', primary_email='@z')

        # Test person_id existance checking.
        with self.assertRaisesRegex(ConsistencyError,
                                    '^person does not exist'):
            email_id = self.db.add_email(1999999, 'zero@users.net')

        # Test that the database check for the same thing works.
        with self.assertRaises(DatabaseIntegrityError):
            email_id = self.db.add_email(1999999, 'zero@users.net',
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

        self.assertIsInstance(result, EmailCollection)
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
            self.assertIs(email.verified, False)
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

        # Check that the "with_email" option of "get_person" works.
        result = self.db.get_person(person_id, with_email=True)
        self.assertIsInstance(result.email, EmailCollection)
        self.assertEqual(len(result.email), 2)

    def test_verify_email(self):
        address = 'someone@somewhere.edu'
        user_id = self.db.add_user('user', 'pass')
        person_id = self.db.add_person('A Person', user_id=user_id)
        email_id = self.db.add_email(person_id, address)

        # Email record starts off not verified.
        email = self.db.search_email(person_id=person_id, address=address)
        self.assertFalse(email.get_single().verified)

        person = self.db.get_person(person_id)
        self.assertFalse(person.verified)

        # Perform verification.
        (token, expiry) = self.db.issue_email_verify_token(
            person_id, address, user_id=None)

        self.assertIsInstance(token, string_type)
        self.assertRegex(token, '^[0-9a-f]{32}$')
        self.assertIsInstance(expiry, datetime)

        with self.assertRaisesRegex(UserError, 'someone else'):
            self.db.use_email_verify_token(person_id + 1, token, user_id=None)

        verified_address = self.db.use_email_verify_token(
            person_id, token, user_id=None)

        self.assertEqual(verified_address, address)

        # Email record should now be verified.
        email = self.db.search_email(person_id=person_id, address=address)
        self.assertTrue(email.get_single().verified)

        person = self.db.get_person(person_id)
        self.assertTrue(person.verified)

    def test_sync_person_email(self):
        # Set up email addresses.
        person_1 = self.db.add_person('Person One')
        person_2 = self.db.add_person('Person Two')

        email_1a = self.db.add_email(person_1, '1a@e', True, False, False)
        email_1b = self.db.add_email(person_1, '1b@e', False, False, False)
        email_1c = self.db.add_email(person_1, '1c@e', False, False, False)
        email_2a = self.db.add_email(person_2, '2a@e', True, False, False)
        email_2b = self.db.add_email(person_2, '2b@e', False, False, False)

        values_1 = EmailCollection()
        values_1[1] = Email(email_1a, None, '1a@e', True, False, False)
        values_1[2] = Email(email_1b, None, '1b@e', False, False, False)
        values_1[3] = Email(email_1c, None, '1c@e', False, False, False)
        values_2 = EmailCollection()
        values_2[1] = Email(email_2a, None, '2a@e', True, False, False)
        values_2[2] = Email(email_2b, None, '2b@e', False, False, False)

        # Check the values match to start with.
        self._compare_email_records(
            self.db.search_email(person_id=person_1), values_1)
        self._compare_email_records(
            self.db.search_email(person_id=person_2), values_2)

        # Updating with these same values should do nothing.
        self.assertEqual(
            self.db.sync_person_email(person_1, values_1), (0, 0, 0))
        self.assertEqual(
            self.db.sync_person_email(person_2, values_2), (0, 0, 0))
        self._compare_email_records(
            self.db.search_email(person_id=person_1), values_1)
        self._compare_email_records(
            self.db.search_email(person_id=person_2), values_2)

        # Updating a value.
        values_1[2] = values_1[2]._replace(address='2b@eeeee', public=True)
        self.assertEqual(
            self.db.sync_person_email(person_1, values_1), (0, 1, 0))
        self._compare_email_records(
            self.db.search_email(person_id=person_1), values_1)

        # Insert a value.
        values_1[4] = Email(
            email_2b + 1, person_1, '1d@e', False, False, False)
        self.assertEqual(
            self.db.sync_person_email(person_1, values_1), (1, 0, 0))
        self._compare_email_records(
            self.db.search_email(person_id=person_1), values_1)

        # Delete a value.
        del values_1[3]
        self.assertEqual(
            self.db.sync_person_email(person_1, values_1), (0, 0, 1))
        self._compare_email_records(
            self.db.search_email(person_id=person_1), values_1)

        # Check Person Two's email records weren't modified in the process.
        self._compare_email_records(
            self.db.search_email(person_id=person_2), values_2)

        # Do multiple update for Person Two.
        values_2[1] = Email(email_2a, None, '2a@e', True, False, True)
        values_2[2] = Email(email_2b + 2, None, '2c@e', False, False, False)
        self.assertEqual(
            self.db.sync_person_email(person_2, values_2), (1, 1, 1))
        self._compare_email_records(
            self.db.search_email(person_id=person_2), values_2)

        # Check the validation of the record collection.
        values_2[2] = values_2[2]._replace(primary=True)
        with self.assertRaisesRegex(UserError, 'more than one primary'):
            self.db.sync_person_email(person_2, values_2)

        # Test behavior of the "verified" flag.
        person_3 = self.db.add_person('Person Three')
        email_3a = self.db.add_email(person_3, '3a@e', True, True, False)
        values_3 = EmailCollection()
        values_3[1] = Email(email_3a, person_3, '3a@e', True, True, False)
        self._compare_email_records(
            self.db.search_email(person_id=person_3), values_3)

        # Switching "verified" manually shouldn't work.
        values_3[1] = values_3[1]._replace(verified=False)
        self.db.sync_person_email(person_3, values_3)
        self.assertTrue(
            self.db.search_email(person_id=person_3)[email_3a].verified)

        # But changing the address should cause it to turn False.
        values_3[1] = values_3[1]._replace(address='a3@e')
        self.db.sync_person_email(person_3, values_3)
        self.assertFalse(
            self.db.search_email(person_id=person_3)[email_3a].verified)

    def _compare_email_records(self, got, expect):
        self.assertEqual(len(got), len(expect))
        for record in expect.values():
            self.assertIn(record.id, got)

            got_record = got[record.id]

            self.assertEqual(got_record.address, record.address)
            self.assertEqual(got_record.primary, record.primary)
            self.assertEqual(got_record.verified, record.verified)
            self.assertEqual(got_record.public, record.public)

    def test_search_person(self):
        # Set up some test records.
        user_1 = self.db.add_user('user1', 'pass1')
        user_2 = self.db.add_user('user2', 'pass2')
        user_3 = self.db.add_user('user3', 'pass3')

        person_1 = self.db.add_person('person1', user_id=user_1)
        person_2 = self.db.add_person('person2', user_id=user_2)
        person_3 = self.db.add_person('person3', user_id=user_3)

        email_1a = self.db.add_email(person_1, '1@email.a')
        email_2a = self.db.add_email(person_2, '2@email.a')
        email_2b = self.db.add_email(person_2, '2@email.b')
        email_2c = self.db.add_email(person_2, 'shared@email')
        email_3a = self.db.add_email(person_3, '3@email.a')
        email_3b = self.db.add_email(person_3, 'shared@email')

        # Check all the records were created successfully.
        for id_ in (user_1, user_2, person_1, person_2, person_3,
                    email_1a, email_2a, email_2b, email_2c,
                    email_3a, email_3b):
            self.assertIsInstance(id_, int)

        # Try searching by user ID.
        result = self.db.search_person(user_id=user_1).keys()
        self.assertEqual(set(result), set((person_1,)))

        result = self.db.search_person(user_id=user_2).keys()
        self.assertEqual(set(result), set((person_2,)))

        result = self.db.search_person(user_id=1999999).keys()
        self.assertFalse(result)

        # Try searching by email address.
        result = self.db.search_person(email_address='1@email.a').keys()
        self.assertEqual(set(result), set((person_1,)))

        result = self.db.search_person(email_address='2@email.a').keys()
        self.assertEqual(set(result), set((person_2,)))

        result = self.db.search_person(email_address='2@email.b').keys()
        self.assertEqual(set(result), set((person_2,)))

        result = self.db.search_person(email_address='shared@email').keys()
        self.assertEqual(set(result), set((person_2, person_3)))

        result = self.db.search_person(email_address='no@email').keys()
        self.assertFalse(result)

        # Try constraining both user name and user_id.
        result = self.db.search_person(
            user_id=user_2, email_address='shared@email').keys()
        self.assertEqual(set(result), set((person_2,)))
        result = self.db.search_person(
            user_id=user_3, email_address='shared@email').keys()
        self.assertEqual(set(result), set((person_3,)))
        result = self.db.search_person(
            user_id=1999999, email_address='shared@email').keys()
        self.assertFalse(result)
        result = self.db.search_person(
            user_id=user_3, email_address='no@email').keys()
        self.assertFalse(result)

    def test_institution(self):
        person_id = self.db.add_person('Institution Editor')
        self.assertIsInstance(person_id, int)

        # Try getting a non-existent institution record.
        with self.assertRaisesRegex(NoSuchRecord,
                                    '^institution does not exist'):
            institution = self.db.get_institution(1999999)

        # Check that we can add an institution.
        institution_id = self.db.add_institution('Institution One',
                                                 'Department One',
                                                 'Organization One',
                                                 'Address...', 'AX')

        self.assertIsInstance(institution_id, int)

        # Try retrieving the institution.
        institution = self.db.get_institution(institution_id)
        self.assertIsInstance(institution, Institution)
        self.assertEqual(institution.id, institution_id)
        self.assertEqual(institution.name, 'Institution One')
        self.assertEqual(institution.organization, 'Organization One')
        self.assertEqual(institution.address, 'Address...')
        self.assertEqual(institution.country, 'AX')

        # Get a list of institutions.
        institution_id2 = self.db.add_institution('Institution Two',
                                                  '', '', '', 'AX')
        result = self.db.search_institution()
        self.assertIsInstance(result, ResultCollection)
        self.assertEqual(len(result), 2)

        for ((row_id, institution), name, expected_id, org, country) in zip(
                result.items(),
                ['Institution One', 'Institution Two'],
                [institution_id, institution_id2],
                ['Organization One', ''],
                ['AX', 'AX']):
            self.assertIsInstance(institution, InstitutionInfo)
            self.assertEqual(institution.id, row_id)
            self.assertEqual(institution.id, expected_id)
            self.assertEqual(institution.name, name)
            self.assertEqual(institution.organization, org)
            self.assertEqual(institution.country, country)

        # Try updating an institution.
        with self.assertRaisesRegex(Error,
                                    '^no institution updates specified'):
            self.db.update_institution(institution_id, person_id)
        with self.assertRaisesRegex(ConsistencyError,
                                    '^institution does not exist'):
            self.db.update_institution(1999999, person_id, '...')
        with self.assertRaisesRegex(ConsistencyError, '^no rows matched'):
            self.db.update_institution(1999999, person_id, '...',
                                       _test_skip_log=True)
        with self.assertRaisesRegex(UserError, 'Country code not recognised'):
            self.db.update_institution(institution_id, person_id, country='BX')

        self.db.update_institution(institution_id, person_id,
                                   'Renamed Institution One')
        institution = self.db.get_institution(institution_id)
        self.assertIsInstance(institution, Institution)
        self.assertEqual(institution.name, 'Renamed Institution One')
        self.db.update_institution(institution_id, person_id,
                                   organization='Renamed Organization',
                                   address='New Address',
                                   country='CX')
        institution = self.db.get_institution(institution_id)
        self.assertIsInstance(institution, Institution)
        self.assertEqual(institution.organization, 'Renamed Organization')
        self.assertEqual(institution.address, 'New Address')
        self.assertEqual(institution.country, 'CX')

        # Check country validation for new institutions.
        with self.assertRaisesRegex(UserError, 'Country code not recognised'):
            self.db.add_institution('Institution Three', '', '', '', 'BX')

        # Check the institution update log.
        records = self.db.search_institution_log(institution_id=institution_id)
        self.assertEqual(len(records), 2)
        for (id_, entry) in records.items():
            self.assertIsInstance(entry.id, int)
            self.assertEqual(entry.id, id_)
            self.assertEqual(entry.institution_id, institution_id)
            self.assertFalse(entry.approved)
            self.assertIsNone(entry.institution_name)

        self.assertEqual(
            len(self.db.search_institution_log(approved=True)), 0)
        self.assertEqual(
            len(self.db.search_institution_log(approved=False)), 2)
        self.assertEqual(
            len(self.db.search_institution_log(has_unapproved=True)), 2)
        self.assertEqual(
            len(self.db.search_institution_log(has_unapproved=False)), 0)

        approved = {k: True for k in records.keys()}

        n_update = self.db.sync_institution_log_approval(approved)
        self.assertEqual(n_update, 2)

        records = self.db.search_institution_log(institution_id=institution_id)
        self.assertEqual(len(records), 2)
        for entry in records.values():
            self.assertTrue(entry.approved)

        self.assertEqual(
            len(self.db.search_institution_log(approved=True)), 2)
        self.assertEqual(
            len(self.db.search_institution_log(approved=False)), 0)
        self.assertEqual(
            len(self.db.search_institution_log(has_unapproved=True)), 0)
        self.assertEqual(
            len(self.db.search_institution_log(has_unapproved=False)), 2)

        approved = {k: False for k in approved.keys()}

        n_update = self.db.sync_institution_log_approval(approved)
        self.assertEqual(n_update, 2)

        records = self.db.search_institution_log(institution_id=institution_id)
        self.assertEqual(len(records), 2)
        for entry in records.values():
            self.assertFalse(entry.approved)

        # Check non-institution-specific update log.
        records = self.db.search_institution_log()
        self.assertEqual(len(records), 2)
        for (id_, entry) in records.items():
            self.assertEqual(entry.institution_name, 'Renamed Institution One')

        # Test deleting an institution.
        with self.assertRaisesRegex(ConsistencyError, 'does not exist'):
            self.db.delete_institution(1999999)

        with self.assertRaisesRegex(ConsistencyError, 'no row matched'):
            self.db.delete_institution(1999999, _test_skip_check=True)

        self.db.delete_institution(institution_id)

        self.assertEqual(
            list(self.db.search_institution().keys()),
            [institution_id2])

    def test_institution_merge(self):
        # Create two institution records with one person each.
        institution_1 = self.db.add_institution('Main', '', '', '', 'AX')
        institution_2 = self.db.add_institution('Duplicate', '', '', '', 'AX')

        person_1 = self.db.add_person('Person One')
        person_2 = self.db.add_person('Person Two')
        self.db.update_person(person_1, institution_id=institution_1)
        self.db.update_person(person_2, institution_id=institution_2)

        # Make an entry in the log for the duplicate.
        self.db.update_institution(institution_2, person_2, 'Duplicate!')
        self.assertEqual(len(
            self.db.search_institution_log(institution_id=institution_2)), 1)

        # Create a proposal and store the duplicate institution identifier
        # in the member record.
        (proposal_id, affiliation_id) = self._create_test_proposal(person_2)
        members = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(len(members), 1)
        member_id = members.popitem()[0]
        members = {member_id: MemberInstitution(member_id, institution_2)}
        n = self.db.sync_proposal_member_institution(proposal_id, members)
        self.assertEqual(n, (0, 1, 0))

        # Apply the merge.
        self.db.merge_institution_records(institution_1, institution_2)

        # Check the correct institution was removed.
        institution = self.db.get_institution(institution_id=institution_1)
        self.assertEqual(institution.id, institution_1)

        with self.assertRaises(NoSuchRecord):
            self.db.get_institution(institution_id=institution_2)

        # The log for the removed institution should have gone.
        self.assertEqual(len(
            self.db.search_institution_log(institution_id=institution_2)), 0)

        # The people should now both have the main institution.
        for person_id in (person_1, person_2):
            person = self.db.get_person(person_id=person_id)
            self.assertEqual(person.id, person_id)
            self.assertEqual(person.institution_id, institution_1)

        # The proposal member should have the main institution.
        members = self.db.search_member(proposal_id=proposal_id)
        self.assertEqual(len(members), 1)
        member = members.popitem()[1]
        self.assertEqual(member.resolved_institution_id, institution_1)

    def test_person(self):
        # Try getting a non-existent person record.
        with self.assertRaisesRegex(NoSuchRecord, '^person does not exist'):
            person = self.db.get_person(1999999)

        # Create a test person record.
        person_id = self.db.add_person('Person One')
        self.assertIsInstance(person_id, int)

        # Check starting state of the record.
        person = self.db.get_person(person_id)
        self.assertIsInstance(person, Person)
        self.assertIsNone(person.institution_id)
        self.assertFalse(person.public)
        self.assertFalse(person.admin)
        self.assertFalse(person.verified)

        # Create a test institution record.
        institution_id = self.db.add_institution('Institution One',
                                                 '', '', '', 'AX')
        self.assertIsInstance(institution_id, int)

        # Update the person to reference the new institution.
        self.db.update_person(person_id, institution_id=institution_id,
                              public=True)

        # Get and inspect the updated record.
        person = self.db.get_person(person_id)
        self.assertIsInstance(person, Person)
        self.assertEqual(person.institution_id, institution_id)
        self.assertTrue(person.public)

        # Check that errors are trapped.
        with self.assertRaisesRegex(Error, '^no person updates specified'):
            self.db.update_person(person_id)
        with self.assertRaisesRegex(ConsistencyError, '^person does not'):
            self.db.update_person(1999999, institution_id=institution_id)
        with self.assertRaisesRegex(ConsistencyError, '^no rows matched'):
            self.db.update_person(1999999, institution_id=institution_id,
                                  _test_skip_check=True)
        with self.assertRaises(DatabaseIntegrityError):
            self.db.update_person(person_id, institution_id=1999999)

        # We should only be able to enable administrative privileges
        # for registered users.
        with self.assertRaises(ConsistencyError):
            self.db.update_person(person_id, admin=True)
        with self.assertRaises(ConsistencyError):
            self.db.update_person(person_id, verified=True)
        person = self.db.get_person(person_id)
        self.assertFalse(person.admin)
        self.assertFalse(person.verified)

        self.db.add_user('user1', 'pass1', person_id=person_id)
        self.db.update_person(person_id, admin=True)
        person = self.db.get_person(person_id)
        self.assertTrue(person.admin)
        self.assertFalse(person.verified)

        self.db.update_person(person_id, verified=True)
        person = self.db.get_person(person_id)
        self.assertTrue(person.admin)
        self.assertTrue(person.verified)

    def test_person_merge(self):
        # Create two test person records.
        person_1 = self.db.add_person('Person One')
        self.assertIsInstance(person_1, int)

        user_1 = self.db.add_user('user1', 'pass1', person_id=person_1)
        self.assertIsInstance(user_1, int)

        person_2 = self.db.add_person('Person Two')
        self.assertIsInstance(person_2, int)

        # Check that the user log is initially as expected.
        self.assertEqual(
            [x.event for x in self.db.search_user_log(user_1).values()],
            [UserLogEvent.LINK_PROFILE, UserLogEvent.CREATE])

        # Associate some information with the second (the duplicate).
        self.db.issue_invitation(person_2)
        self.db.issue_email_verify_token(person_2, 'a@b', user_id=None)

        (proposal_id, affiliation_id) = self._create_test_proposal(person_2)
        self.db.set_proposal_text(
            BaseTextRole, proposal_id, BaseTextRole.ABSTRACT,
            'The abstract', FormatType.PLAIN, 2, person_2)

        # Check the tests that the two user identifiers exist.
        with self.assertRaisesRegex(
                ConsistencyError, 'duplicate person .* does not exist'):
            self.db.merge_person_records(person_1, 1999999)

        with self.assertRaisesRegex(
                ConsistencyError, 'main person .* does not exist'):
            self.db.merge_person_records(1999999, person_2)

        # Check constraint on whether the duplicate user is registered.
        with self.assertRaisesRegex(
                ConsistencyError, 'is not already registered'):
            self.db.merge_person_records(person_1, person_2,
                                         duplicate_person_registered=True)

        user_2 = self.db.add_user('user2', 'pass2', person_id=person_2)
        self.assertIsInstance(user_2, int)

        self.db.issue_password_reset_token(user_2, remote_addr=None)

        with self.assertRaisesRegex(
                ConsistencyError, 'is already registered'):
            self.db.merge_person_records(person_1, person_2,
                                         duplicate_person_registered=False)

        # Perform the merge.
        self.db.merge_person_records(person_1, person_2)

        # Make sure that the main record is still there and has acquired
        # associated records from the (removed) duplicate.
        record = self.db.get_user_name(user_1)
        self.assertIsNotNone(record)

        record = self.db.get_person(
            person_1, with_proposals=True, with_reviews=True)
        self.assertEqual(record.id, person_1)
        self.assertEqual(
            [x.proposal_id for x in record.proposals.values()],
            [proposal_id])
        self.assertEqual(
            [x.editor for x in self.db.search_proposal_text(
                proposal_id=proposal_id, role=BaseTextRole.ABSTRACT).values()],
            [person_1])

        # Check that the duplicate record has gone.
        with self.assertRaises(NoSuchRecord):
            self.db.get_person(person_2)

        with self.assertRaises(NoSuchRecord):
            self.db.get_user_name(user_2)

        # Check that the user log was updated.
        self.assertEqual(
            [x.event for x in self.db.search_user_log(user_1).values()],
            [UserLogEvent.MERGED,
             UserLogEvent.LINK_PROFILE, UserLogEvent.CREATE])

    def test_password_reset_token(self):
        # Create a user record.
        user_id = self.db.add_user('user1', 'pass1')
        self.assertIsInstance(user_id, int)

        # Try making a reset token.
        (token, expiry) = self.db.issue_password_reset_token(
            user_id, remote_addr=None)
        self.assertIsInstance(token, string_type)
        self.assertRegex(token, '^[0-9a-f]{32}$')

        # Using a bad token should do nothing.
        with self.assertRaises(NoSuchRecord):
            self.db.use_password_reset_token('not a valid token', 'pass2',
                                             remote_addr=None)

        self.assertEqual(self.db.authenticate_user('user1', 'pass1'), user_id)

        # Using the token should return this user name and the password
        # should have been changed.
        token_user_name = self.db.use_password_reset_token(token, 'pass3',
                                                           remote_addr=None)
        self.assertEqual(token_user_name, 'user1')

        self.assertIsNone(self.db.authenticate_user('user1', 'pass1'))

        self.assertEqual(self.db.authenticate_user('user1', 'pass3'), user_id)

        # Using the token again should return None because the
        # token should have been deleted.
        with self.assertRaises(NoSuchRecord):
            self.db.use_password_reset_token(token, 'pass4', remote_addr=None)

        # Issue two more tokens: the older should be removed automatically.
        (token1, expiry) = self.db.issue_password_reset_token(
            user_id, remote_addr=None, _test_skip_check=True)
        (token2, expiry) = self.db.issue_password_reset_token(
            user_id, remote_addr=None, _test_skip_check=True)
        with self.assertRaises(NoSuchRecord):
            self.db.use_password_reset_token(token1, 'pass5', remote_addr=None)
        token_user_name = self.db.use_password_reset_token(token2, 'pass6',
                                                           remote_addr=None)
        self.assertEqual(token_user_name, 'user1')

        # Create a token and artificially age it by putting the expiry
        # date in the past.  It should then not work.
        (token, expiry) = self.db.issue_password_reset_token(
            user_id, remote_addr=None, _test_skip_check=True)
        with self.db._transaction() as conn:
            result = conn.execute(reset_token.update().where(
                reset_token.c.token == token
            ).values({
                reset_token.c.expiry: datetime.utcnow() - timedelta(hours=1),
            }))

            self.assertEqual(result.rowcount, 1)
        with self.assertRaises(NoSuchRecord):
            self.db.use_password_reset_token(token, 'pass7', remote_addr=None)

        # Test rate limit, when _test_skip_check not specified.
        with self.assertRaisesRegex(UserError, 'Excess requests'):
            (token, expiry) = self.db.issue_password_reset_token(
                user_id, remote_addr=None)

    def test_invitation_new_user(self):
        # Create a person record.
        person_id = self.db.add_person('Person One')
        self.assertIsInstance(person_id, int)

        # Check we can generate a token of the expected format.
        (token, expiry) = self.db.issue_invitation(person_id)
        self.assertIsInstance(token, string_type)
        self.assertRegex(token, '^[0-9a-f]{32}$')
        self.assertIsInstance(expiry, datetime)

        user_id = self.db.add_user('user1', 'pass1')
        with self.assertRaisesRegex(NoSuchRecord, 'expired or non-existant'):
            self.db.use_invitation('not a valid token', user_id=user_id)

        # Try check that the user exists.
        with self.assertRaisesRegex(ConsistencyError,
                                    'user does not exist'):
            self.db.use_invitation(token, user_id=1999999)

        # Try using the token: user_id is None before but set afterwards.
        person = self.db.get_person(person_id=person_id)
        self.assertIsNone(person.user_id)
        self.assertFalse(person.verified)
        old_person_record = self.db.use_invitation(token, user_id=user_id)
        person = self.db.get_person(person_id=person_id)
        self.assertEqual(person.user_id, user_id)

        # Check the old person record was returned correctly.
        self.assertIsInstance(old_person_record, Person)
        self.assertEqual(old_person_record.id, person_id)
        self.assertIsNone(old_person_record.user_id)

        # Check the database record was marked as verified.
        self.assertTrue(person.verified)

        # The token should no longer exist.
        with self.assertRaisesRegex(NoSuchRecord, 'expired or non-existant'):
            self.db.use_invitation(token, user_id=user_id)

        # Check the user log.
        self.assertEqual(
            [x.event for x in self.db.search_user_log(user_id).values()],
            [UserLogEvent.USE_INVITE, UserLogEvent.CREATE])

        # Check error trapping.
        with self.assertRaisesRegex(ConsistencyError,
                                    'person does not exist'):
            self.db.issue_invitation(1999999)
        with self.assertRaises(DatabaseIntegrityError):
            self.db.issue_invitation(1999999, _test_skip_check=True)
        with self.assertRaisesRegex(ConsistencyError,
                                    'person is already registered'):
            self.db.issue_invitation(person_id)

        # Try artificially aging a token.
        person_id = self.db.add_person('Person Two')
        (token, expiry) = self.db.issue_invitation(person_id)
        with self.db._transaction() as conn:
            result = conn.execute(invitation.update().where(
                invitation.c.token == token
            ).values({
                invitation.c.expiry: datetime.utcnow() - timedelta(hours=1),
            }))
            self.assertEqual(result.rowcount, 1)
        with self.assertRaises(NoSuchRecord):
            self.db.use_invitation(token, user_id=user_id)

        # Try using for a person who subsequently somehow became registered.
        (token, expiry) = self.db.issue_invitation(person_id)
        user_id_2 = self.db.add_user('user2', 'pass2')
        user_id_3 = self.db.add_user('user3', 'pass3', person_id=person_id)
        with self.assertRaisesRegex(ConsistencyError,
                                    'no rows matched setting new user_id'):
            self.db.use_invitation(token, user_id=user_id_2)

    def test_invitation_user_admin(self):
        # Create an administrative person record.
        person_id = self.db.add_person('Administrator')
        self.assertIsInstance(person_id, int)
        self.db.update_person(person_id, admin=True, _test_skip_check=True)

        # Try to create an invitation to register as that person: should
        # fail unless the check is disabled.
        with self.assertRaisesRegex(UserError, 'administrative privileges'):
            self.db.issue_invitation(person_id)
        (token, expiry) = self.db.issue_invitation(person_id,
                                                   _test_skip_check=True)

        # Try to accept the invitation to register as that person.
        user_id = self.db.add_user('user1', 'pass1')
        with self.assertRaisesRegex(ConsistencyError, 'no rows matched'):
            self.db.use_invitation(token, user_id=user_id)
        person = self.db.get_person(person_id=person_id)
        self.assertIsNone(person.user_id)

    def test_invitation_replace_person(self):
        # Create test person records.
        person_id_1 = self.db.add_person('Person 1')
        self.db.add_email(person_id_1, '1@email')

        person_id_2 = self.db.add_person('Person 2')
        self.db.add_email(person_id_2, '2@email')

        user_id = self.db.add_user('user', 'pass')
        person_id_new = self.db.add_person('Person New', user_id=user_id)
        self.db.add_email(person_id_new, 'new@email')

        person = self.db.get_person(person_id_new)
        self.assertFalse(person.verified)

        # Create a proposal with 2 members.
        (proposal_id, affiliation_id) = self._create_test_proposal(person_id_1)
        self.db.add_member(proposal_id, person_id_2, affiliation_id)

        # Issue invitation token for one of the members.
        (token, expiry) = self.db.issue_invitation(person_id_2)
        self.assertIsInstance(token, string_type)
        self.assertRegex(token, '^[0-9a-f]{32}$')

        # Try check that the person exists.
        with self.assertRaisesRegex(ConsistencyError,
                                    'person does not exist'):
            self.db.use_invitation(token, new_person_id=1999999)

        # Accept the invitation with the existing new person record.
        old_user_record = self.db.use_invitation(token,
                                                 new_person_id=person_id_new)

        # Check the old person record was returned correctly.
        self.assertIsInstance(old_user_record, Person)
        self.assertEqual(old_user_record.id, person_id_2)
        self.assertEqual(
            [x.proposal_id for x in old_user_record.proposals.values()],
            [proposal_id])

        # The person should now be verified.
        person = self.db.get_person(person_id_new)
        self.assertTrue(person.verified)

        # The "temporary" person record should have gone.
        with self.assertRaises(NoSuchRecord):
            self.db.get_person(person_id=person_id_2)

        # The proposal members should by the original author and new person.
        proposal = self.db.get_proposal(None, proposal_id, with_members=True)
        self.assertEqual([x.person_id for x in proposal.members.values()],
                         [person_id_1, person_id_new])

        # The invitation should have been removed.
        person_id_new_2 = self.db.add_person('Person New 2')
        with self.assertRaisesRegex(NoSuchRecord, 'expired or non-existant'):
            self.db.use_invitation(token, new_person_id=person_id_new_2)

        # Check the user log.
        self.assertEqual(
            [x.event for x in self.db.search_user_log(user_id).values()],
            [UserLogEvent.MERGED_INVITE,
             UserLogEvent.LINK_PROFILE, UserLogEvent.CREATE])

        # Check we can't accept a token for a person who somehow became
        # a registered user in the meantime.
        person_id_3 = self.db.add_person('Person 3')
        person_id_new_3 = self.db.add_person('Person New 3')
        (token, expiry) = self.db.issue_invitation(person_id_3)
        self.db.add_user('user3', 'pass3', person_id=person_id_3)
        with self.assertRaisesRegex(ConsistencyError, 'already registered'):
            self.db.use_invitation(token, new_person_id=person_id_new_3)

    def test_site_group(self):
        person_id_1 = self.db.add_person('Person One')
        person_id_2 = self.db.add_person('Person Two')

        # Check null search result.
        result = self.db.search_site_group_member(SiteGroupType.PROFILE_VIEWER)
        self.assertIsInstance(result, SiteGroupMemberCollection)
        self.assertEqual(len(result), 0)

        # Check member add constraints.
        with self.assertRaisesRegex(Error, 'invalid site group type'):
            self.db.add_site_group_member(999, person_id_1)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_site_group_member(
                SiteGroupType.PROFILE_VIEWER, 1999999, _test_skip_check=True)

        # Add two members.
        self.db.add_site_group_member(
            SiteGroupType.PROFILE_VIEWER, person_id_1)
        self.db.add_site_group_member(
            SiteGroupType.PROFILE_VIEWER, person_id_2)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_site_group_member(
                SiteGroupType.PROFILE_VIEWER, person_id_2)

        # Check we don't find them when searching another group.
        result = self.db.search_site_group_member(999)
        self.assertEqual(len(result), 0)

        # Check the search results (without and then with person info).
        result = self.db.search_site_group_member(SiteGroupType.PROFILE_VIEWER)
        self.assertIsInstance(result, SiteGroupMemberCollection)
        self.assertEqual(len(result), 2)

        for v in result.values():
            self.assertIsInstance(v, SiteGroupMember)
            self.assertIsNone(v.person_name)

        result = self.db.search_site_group_member(
            SiteGroupType.PROFILE_VIEWER, with_person=True)
        self.assertIsInstance(result, SiteGroupMemberCollection)
        self.assertEqual(len(result), 2)

        for ((k, v), person_id, person_name) in zip(
                result.items(),
                (person_id_1, person_id_2),
                ('Person One', 'Person Two')):
            self.assertIsInstance(k, int)
            self.assertIsInstance(v, SiteGroupMember)
            self.assertEqual(k, v.id)
            self.assertEqual(v.site_group_type, SiteGroupType.PROFILE_VIEWER)
            self.assertEqual(v.person_id, person_id)
            self.assertEqual(v.person_name, person_name)

        # Check additional search criteria.
        result = self.db.search_site_group_member(person_id=person_id_1)
        self.assertEqual(len(result), 1)

        result = self.db.search_site_group_member(person_id=1999999)
        self.assertEqual(len(result), 0)

        # Remove members via sync.
        records = SiteGroupMemberCollection()
        self.db.sync_site_group_member(SiteGroupType.PROFILE_VIEWER, records)
        result = self.db.search_site_group_member(SiteGroupType.PROFILE_VIEWER)
        self.assertEqual(len(result), 0)

    def test_oauth(self):
        person_id = self.db.add_person('Test Person')

        code_id = self.db.add_oauth_code(
            'XYZ', 'xxx://yyy.zzz/', 'code', None, '123', 'openid', person_id)

        self.assertIsInstance(code_id, int)

        codes = self.db.search_oauth_code('123', 'ZYX')
        self.assertFalse(codes)

        codes = self.db.search_oauth_code('321', 'XYZ')
        self.assertFalse(codes)

        code = self.db.search_oauth_code('123', 'XYZ').get_single()
        self.assertIsInstance(code, OAuthCode)

        self.assertEqual(code.id, code_id)

        self.assertEqual(code.redirect_uri, 'xxx://yyy.zzz/')

        self.db.delete_oauth_code(code.id)

        codes = self.db.search_oauth_code('123', 'XYZ')
        self.assertFalse(codes)

        token_id = self.db.add_oauth_token(
            'Bearer', 'XYZ', None, '123', 'openid', person_id, 864000)

        self.assertIsInstance(token_id, int)

        tokens = self.db.search_oauth_token('123', access_token='ZYX')
        self.assertFalse(tokens)

        tokens = self.db.search_oauth_token('321', access_token='XYZ')
        self.assertFalse(tokens)

        tokens = self.db.search_oauth_token('123', access_token='XYZ')
        token = tokens.get_single()
        self.assertIsInstance(token, OAuthToken)

        self.assertEqual(token.id, token.id)

        self.assertEqual(token.scope, 'openid')

    def _create_test_proposal(self, person_id):
        """
        Create a proposal and return the proposal and affiliation identifiers.
        """

        facility_id = self.db.ensure_facility('test')
        semester_id = self.db.add_semester(facility_id, 'test', 'test',
                                           datetime(2000, 1, 1),
                                           datetime(2000, 6, 30))
        queue_id = self.db.add_queue(facility_id, 'test', 'test')
        call_id = self.db.add_call(
            BaseCallType, semester_id, queue_id, BaseCallType.STANDARD,
            datetime(1999, 9, 1), datetime(1999, 9, 30),
            100, 1000, 0, 1, 2000, 4, 3, 100, 100,
            '', '', '', FormatType.PLAIN, False, False, None, None, False,
            False, '', 500, 4, 1, 366)
        affiliation_id = self.db.add_affiliation(
            BaseAffiliationType, queue_id, 'Aff/n 1')
        proposal_id = self.db.add_proposal(call_id, person_id,
                                           affiliation_id, 'Proposal 1')

        return (proposal_id, affiliation_id)
