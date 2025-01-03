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

from datetime import datetime

from hedwig.compat import first_value
from hedwig.error import ConsistencyError, DatabaseIntegrityError, Error
from hedwig.type.enum import MessageFormatType, MessageState, MessageThreadType
from hedwig.type.collection import ResultCollection
from hedwig.type.simple import Message, MessageRecipient
from .dummy_db import DBTestCase


class DBMessageTest(DBTestCase):
    def test_basic_message(self):
        # Check null results.
        messages = self.db.search_message()
        self.assertFalse(messages)

        # Create test message.
        person_1 = self.db.add_person('Person One')
        self.db.add_email(person_1, '1@a', primary=True, public=True)

        with self.assertRaisesRegex(Error, '^duplicate person_id'):
            self.db.add_message(
                'test', 'test message', [person_1, person_1])

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_message(
                'test', 'test message', [person_1, person_1],
                _test_skip_check=True)

        with self.assertRaises(DatabaseIntegrityError):
            self.db.add_message(
                'test', 'test message', [1999999])

        with self.assertRaisesRegex(Error, 'invalid message format type'):
            self.db.add_message(
                'test', 'message', [person_1], format_type=999)

        message_id = self.db.add_message('test', 'test message', [person_1])
        self.assertIsInstance(message_id, int)

        # Test "search_message" method.
        messages = self.db.search_message()
        self.assertIsInstance(messages, ResultCollection)
        self.assertEqual(set(messages.keys()), set((message_id,)))
        message = messages[message_id]
        self.assertIsInstance(message, Message)

        self.assertEqual(message.id, message_id)
        self.assertEqual(message.subject, 'test')
        self.assertIsNone(message.body)
        self.assertIsNone(message.timestamp_send)
        self.assertIsNone(message.timestamp_sent)
        self.assertIsNone(message.identifier)
        self.assertIsNone(message.recipients)
        self.assertIsNone(message.thread_type)
        self.assertIsNone(message.thread_id)
        self.assertEqual(message.state, MessageState.UNSENT)
        self.assertEqual(message.format, MessageFormatType.PLAIN)

        # Test a search as if preparing to send messages.
        messages = self.db.search_message(
            state=MessageState.UNSENT,
            oldest_first=True, with_thread_identifiers=True,
            with_recipients=True, with_recipients_resolved=True,
            with_body=True)
        self.assertIsInstance(messages, ResultCollection)
        self.assertEqual(set(messages.keys()), set((message_id,)))
        message = messages[message_id]
        self.assertIsInstance(message, Message)
        self.assertEqual(message.id, message_id)
        self.assertEqual(message.subject, 'test')
        self.assertEqual(message.body, 'test message')
        self.assertIsNone(message.timestamp_send)
        self.assertIsNone(message.timestamp_sent)
        self.assertIsNone(message.identifier)
        self.assertIsNotNone(message.recipients)
        self.assertEqual(len(message.recipients), 1)
        recipient = list(message.recipients.values())[0]
        self.assertIsInstance(recipient, MessageRecipient)
        self.assertEqual(recipient.person_name, 'Person One')
        self.assertEqual(recipient.email_address, '1@a')
        self.assertTrue(recipient.email_public)

        self.db.update_message(
            message.id,
            state_prev=MessageState.UNSENT, state=MessageState.SENDING,
            state_is_system=True, timestamp_send=datetime.utcnow())

        messages = self.db.search_message()
        self.assertEqual(set(messages.keys()), set((message_id,)))
        message = messages[message_id]
        self.assertIsInstance(message.timestamp_send, datetime)
        self.assertEqual(message.state, MessageState.SENDING)

        self.assertFalse(self.db.search_message(state=MessageState.UNSENT))

        self.db.update_message(
            message_id,
            state_prev=MessageState.SENDING,
            state=MessageState.SENT,
            state_is_system=True,
            timestamp_sent=datetime.utcnow(),
            identifier='<1@localhost>')

        self.assertFalse(self.db.search_message(state=MessageState.UNSENT))

        messages = self.db.search_message()
        self.assertEqual(set(messages.keys()), set((message_id,)))
        message = messages[message_id]
        self.assertEqual(message.id, message_id)
        self.assertEqual(message.subject, 'test')
        self.assertIsNone(message.body)
        self.assertIsInstance(message.timestamp_send, datetime)
        self.assertIsInstance(message.timestamp_sent, datetime)
        self.assertEqual(message.identifier, '<1@localhost>')
        self.assertIsNone(message.recipients)
        self.assertEqual(message.state, MessageState.SENT)

        with self.assertRaisesRegex(ConsistencyError, '^message does not ex'):
            self.db.update_message(
                1999999, identifier='<2@localhost>')

        with self.assertRaisesRegex(ConsistencyError, '^no rows matched'):
            self.db.update_message(
                1999999, identifier='<2@localhost>', _test_skip_check=True)

        # Test "update_message" method.
        self.db.update_message(message_id=message_id,
                               state=MessageState.UNSENT)

        message = self.db.get_message(message_id)
        self.assertEqual(message.state, MessageState.UNSENT)

        self.db.update_message(message_id=message_id,
                               state=MessageState.DISCARD)

        messages = self.db.search_message()
        self.assertEqual(set(messages.keys()), set((message_id,)))
        message = messages[message_id]
        self.assertEqual(message.state, MessageState.DISCARD)

        self.assertFalse(self.db.search_message(state=MessageState.UNSENT))

        self.db.update_message(message_id=message_id,
                               state=MessageState.UNSENT)

        messages = self.db.search_message(state=MessageState.UNSENT)
        self.assertEqual(len(messages), 1)
        self.assertEqual(first_value(messages).id, message_id)

        with self.assertRaisesRegex(ConsistencyError, '^message does not'):
            self.db.update_message(
                message_id=1999999, state=MessageState.DISCARD)

        with self.assertRaisesRegex(ConsistencyError, '^no rows matched'):
            self.db.update_message(
                message_id=1999999, state=MessageState.DISCARD,
                _test_skip_check=True)

        with self.assertRaisesRegex(Error, '^invalid state'):
            self.db.update_message(message_id=message_id, state=999)

        with self.assertRaisesRegex(Error, '^no message updates specified'):
            self.db.update_message(message_id=message_id)

    def test_multiple_message(self):
        # Create some person records with multiple email addresses.
        person_1 = self.db.add_person('Person One')
        self.db.add_email(person_1, '1@a', primary=False, public=True)
        self.db.add_email(person_1, '1@b', primary=True, public=True)
        self.db.add_email(person_1, '1@c', primary=False, public=True)

        person_2 = self.db.add_person('Person Two')
        self.db.add_email(person_2, '2@a', primary=True, public=False)
        self.db.add_email(person_2, '2@b', primary=False, public=True)
        self.db.add_email(person_2, '2@c', primary=False, public=True)

        person_3 = self.db.add_person('Person Three')
        self.db.add_email(person_3, '3@a', primary=False, public=False)
        self.db.add_email(person_3, '3@b', primary=False, public=True)
        self.db.add_email(person_3, '3@c', primary=True, public=True)

        person_4 = self.db.add_person('Person Four')
        self.db.add_email(person_4, '4@a', primary=False, public=False)
        self.db.add_email(person_4, '4@b', primary=True, public=False)
        self.db.add_email(person_4, '4@c', primary=False, public=True)

        # Create two test messages.
        message_12 = self.db.add_message(
            'test', 'test message', [person_1, person_2],
            format_type=MessageFormatType.PLAIN)
        message_34 = self.db.add_message(
            'test', 'test message', [person_3, person_4],
            format_type=MessageFormatType.PLAIN_FLOWED)

        self.assertIsInstance(message_12, int)
        self.assertIsInstance(message_34, int)
        self.assertNotEqual(message_12, message_34)

        # Check that each message has the correct set of recipients.
        messages = self.db.search_message(
            state=MessageState.UNSENT,
            oldest_first=True, with_thread_identifiers=True,
            with_recipients=True, with_recipients_resolved=True,
            with_body=True)
        self.assertEqual(list(messages.keys()), [message_12, message_34])

        message = messages[message_12]
        self.assertEqual(message.id, message_12)
        self.assertEqual(message.format, MessageFormatType.PLAIN)
        self.assertEqual(set(message.recipients.values()), set((
            MessageRecipient(message_12, person_1, '1@b', 'Person One', True),
            MessageRecipient(message_12, person_2, '2@a', 'Person Two', False),
        )))

        message = messages[message_34]
        self.assertEqual(message.id, message_34)
        self.assertEqual(message.format, MessageFormatType.PLAIN_FLOWED)
        self.assertEqual(set(message.recipients.values()), set((
            MessageRecipient(message_34, person_3, '3@c', 'Person Three', True),
            MessageRecipient(message_34, person_4, '4@b', 'Person Four', False),
        )))

    def test_explicit_email(self):
        # Create some person records with multiple email addresses.
        person_1 = self.db.add_person('Person One')
        self.db.add_email(person_1, '1@a', primary=False, public=True)
        self.db.add_email(person_1, '1@b', primary=True, public=True)
        self.db.add_email(person_1, '1@c', primary=False, public=True)

        person_2 = self.db.add_person('Person Two')
        self.db.add_email(person_2, '2@a', primary=True, public=False)
        self.db.add_email(person_2, '2@b', primary=False, public=True)
        self.db.add_email(person_2, '2@c', primary=False, public=True)

        person_3 = self.db.add_person('Person Three')
        self.db.add_email(person_3, '3@a', primary=True, public=False)
        self.db.add_email(person_3, '3@b', primary=False, public=True)
        self.db.add_email(person_3, '3@c', primary=False, public=False)

        # Try setting an invalid specific email address.
        with self.assertRaisesRegex(Error, 'does not appear to be valid'):
            self.db.add_message(
                'test invalid address', 'test message',
                [person_1], ['@xyz'])

        # Create test message, giving specific email addresses.
        message_id = self.db.add_message('test', 'test message',
                                         [person_1, person_2, person_3],
                                         ['1@c', '2@b', '3@c'])

        self.assertIsInstance(message_id, int)

        # Check that the message has the correct set of addresses.
        messages = self.db.search_message(
            state=MessageState.UNSENT,
            oldest_first=True, with_thread_identifiers=True,
            with_recipients=True, with_recipients_resolved=True,
            with_body=True)

        self.assertEqual(len(messages), 1)
        message = first_value(messages)

        self.assertEqual(message.id, message_id)
        self.assertEqual(set(message.recipients.values()), set((
            MessageRecipient(message_id, person_1, '1@c', 'Person One', True),
            MessageRecipient(message_id, person_2, '2@b', 'Person Two', True),
            MessageRecipient(message_id, person_3, '3@c', 'Person Three', False),
        )))

        self.db.update_message(
            message.id,
            state_prev=MessageState.UNSENT, state=MessageState.SENDING,
            state_is_system=True, timestamp_send=datetime.utcnow())

        # Check handling of an email address which isn't in the email table.
        # (This can happen if an address is changed after an email is already
        # inserted into the database with an explicit address.)
        message_id = self.db.add_message('test', 'test message',
                                         [person_1], ['1@d'])

        message = self._get_unsent_message()

        self.assertEqual(message.id, message_id)
        self.assertEqual(set(message.recipients.values()), set((
            MessageRecipient(message_id, person_1, '1@d', 'Person One', False),
        )))

    def test_message_thread(self):
        person = self.db.add_person('Test Person')
        self.db.add_email(person, 'test@email', primary=True, public=True)

        message_args = ['test', 'test message', [person]]

        with self.assertRaisesRegex(Error, '^invalid thread type'):
            message = self.db.add_message(
                *message_args, thread_type=999, thread_id=123)

        with self.assertRaisesRegex(
                Error, '^thread_id specified without thread_type'):
            message = self.db.add_message(
                *message_args, thread_type=None, thread_id=123)

        # Store a message not in our thread.
        message_0 = self.db.add_message(
            *message_args, thread_type=MessageThreadType.PROPOSAL_STATUS,
            thread_id=321)

        # Store multiple messages in a thread.
        message_kwargs = {
            'thread_type': MessageThreadType.PROPOSAL_STATUS,
            'thread_id': 123,
        }

        message_1 = self.db.add_message(*message_args, **message_kwargs)
        message_2 = self.db.add_message(*message_args, **message_kwargs)
        message_3 = self.db.add_message(*message_args, **message_kwargs)
        message_4 = self.db.add_message(*message_args, **message_kwargs)

        # Retrieve the messages and check the thread identifiers.
        message = self._get_unsent_message()
        self.assertIsNotNone(message)
        self.assertEqual(message.id, message_0)
        self.assertEqual(message.thread_identifiers, [])

        self.db.update_message(
            message_0, identifier='<0@id>',
            state=MessageState.SENT, state_is_system=True)

        message = self._get_unsent_message()
        self.assertIsNotNone(message)
        self.assertEqual(message.id, message_1)
        self.assertEqual(message.thread_identifiers, [])

        self.db.update_message(
            message_1, identifier='<1@id>',
            state=MessageState.SENT, state_is_system=True)

        # Send message 4 out of order -- we shouldn't see its identifer
        # in query results as it comes after the other messages.
        self.db.update_message(
            message_4, identifier='<4@id>',
            state=MessageState.SENT, state_is_system=True)

        message = self._get_unsent_message()
        self.assertIsNotNone(message)
        self.assertEqual(message.id, message_2)
        self.assertEqual(message.thread_identifiers, ['<1@id>'])

        self.db.update_message(
            message_2, identifier='<2@id>',
            state=MessageState.SENT, state_is_system=True)

        message = self._get_unsent_message()
        self.assertIsNotNone(message)
        self.assertEqual(message.id, message_3)
        self.assertEqual(message.thread_identifiers, ['<1@id>', '<2@id>'])

    def _get_unsent_message(self):
        return first_value(self.db.search_message(
            state=MessageState.UNSENT,
            oldest_first=True, with_thread_identifiers=True,
            with_recipients=True, with_recipients_resolved=True,
            with_body=True))
