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

from datetime import datetime

try:
    from itertools import zip_longest
except ImportError:
    from itertools import izip_longest as zip_longest

from sqlalchemy.sql import select
from sqlalchemy.sql.expression import and_, case, column, not_
from sqlalchemy.sql.functions import coalesce

from ...error import ConsistencyError, FormattedError, \
    NoSuchRecord, MultipleRecords
from ...type.collection import ResultCollection
from ...type.enum import MessageState, MessageThreadType
from ...type.simple import Message, MessageRecipient
from ..meta import email, message, message_recipient, person


class MessagePart(object):
    def add_message(self, subject, body, person_ids, email_addresses=[],
                    thread_type=None, thread_id=None,
                    _test_skip_check=False):
        """
        Add a message to the database.

        "email_addresses" can normally be left empty, but if it is necessary to
        send to a particular address (rather than the person's primary address)
        then it can be a list with email addresses in the same order as the
        person_ids list.
        """

        if thread_type is not None:
            if not MessageThreadType.is_valid(thread_type):
                raise FormattedError('invalid thread type {}', thread_type)

        elif thread_id is not None:
            raise ConsistencyError('thread_id specified without thread_type')

        if not _test_skip_check:
            if ((not isinstance(person_ids, set)) and
                    (len(person_ids) != len(set(person_ids)))):
                raise ConsistencyError('duplicate person_id for new message')

        with self._transaction() as conn:
            result = conn.execute(message.insert().values({
                message.c.date: datetime.utcnow(),
                message.c.subject: subject,
                message.c.body: body,
                message.c.thread_type: thread_type,
                message.c.thread_id: thread_id,
                message.c.state: MessageState.UNSENT,
            }))

            message_id = result.inserted_primary_key[0]

            for (person_id, email_address) in zip_longest(person_ids,
                                                          email_addresses):
                conn.execute(message_recipient.insert().values({
                    message_recipient.c.message_id: message_id,
                    message_recipient.c.person_id: person_id,
                    message_recipient.c.email_address: email_address,
                }))

        return message_id

    def get_message(self, message_id):
        """
        Retrieve a message from the database.
        """

        with self._transaction() as conn:
            recipients = []

            for row in conn.execute(select([
                    message_recipient.c.person_id,
                    person.c.name,
                    message_recipient.c.email_address.label('address'),
                    ]).select_from(message_recipient.join(person)).where(
                        message_recipient.c.message_id == message_id)):
                recipients.append(MessageRecipient(public=None, **row))

            row = conn.execute(message.select().where(
                message.c.id == message_id).limit(1)).first()

            if row is None:
                raise NoSuchRecord('message not found with id {}', message_id)

            ans = Message(recipients=recipients, thread_identifiers=None,
                          **row)

        return ans

    def get_unsent_message(self):
        """
        Return the first unsent message, if there is one, or None otherwise.
        """

        with self._transaction() as conn:
            result = conn.execute(message.select().where(
                message.c.state == MessageState.UNSENT,
            ).order_by(
                message.c.id.asc()
            ).limit(1)).first()

            if result is None:
                return None

            message_id = result['id']

            # Find the identifiers for previous messages in the same thread,
            # oldest first.
            thread_type = result['thread_type']
            thread_id = result['thread_id']
            thread_identifiers = []

            if (thread_type is not None) and (thread_id is not None):
                for row in conn.execute(select([
                        message.c.identifier,
                        ]).select_from(message).where(and_(
                            message.c.thread_type == thread_type,
                            message.c.thread_id == thread_id,
                            message.c.id < message_id,
                            message.c.state == MessageState.SENT,
                            message.c.identifier.isnot(None),
                        )).order_by(message.c.id.asc())):
                    thread_identifiers.append(row['identifier'])

            # Find the recipients of the message: perform an outer join
            # with the email table in case the address is not there -- in that
            # case assume the address is not public.
            recipients = []

            for row in conn.execute(select([
                    message_recipient.c.person_id,
                    person.c.name,
                    coalesce(message_recipient.c.email_address,
                             email.c.address).label('address'),
                    coalesce(email.c.public, False).label('public'),
                    ]).select_from(
                        message_recipient.join(person).outerjoin(
                            email,
                            and_(person.c.id == email.c.person_id, case([(
                                message_recipient.c.email_address.isnot(None),
                                message_recipient.c.email_address ==
                                email.c.address)],
                                else_=email.c.primary)
                            ))
                    ).where(
                        message_recipient.c.message_id == message_id)):
                recipients.append(MessageRecipient(**row))

        return Message(
            recipients=recipients, thread_identifiers=thread_identifiers,
            **result)

    def mark_message_sending(self, message_id,
                             _conn=None, _test_skip_check=False):
        """
        Marks the given message as being sent.
        """

        self.update_message(
            message_id,
            state=MessageState.SENDING,
            state_prev=MessageState.UNSENT,
            state_is_system=True,
            timestamp_send=datetime.utcnow(),
            _conn=_conn)

    def mark_message_error(self, message_id,
                           _conn=None, _test_skip_check=False):
        """
        Marks the given message as having been unsuccesfully attempted
        to be sent.

        This is simply a convenience method which in turn calls
        `update_message`.
        """

        self.update_message(
            message_id,
            state=MessageState.ERROR,
            state_prev=MessageState.SENDING,
            state_is_system=True,
            _conn=_conn, _test_skip_check=_test_skip_check)

    def mark_message_sent(self, message_id, identifier,
                          _conn=None, _test_skip_check=False):
        """
        Marks the given message as sent.

        The "identifier" should be the email's "Message-ID" header.
        """

        self.update_message(
            message_id,
            state=MessageState.SENT,
            state_prev=MessageState.SENDING,
            state_is_system=True,
            timestamp_sent=datetime.utcnow(),
            identifier=identifier,
            _conn=_conn, _test_skip_check=_test_skip_check)

    def search_message(self, person_id=None, state=None, message_id_lt=None,
                       thread_type=None, thread_id=None,
                       limit=None, oldest_first=False,
                       _conn=None):
        """
        Searches for messages.

        The selection of messages to be returned can be controlled with the
        optional keyword arguments.
        """

        stmt = select([
            message.c.id,
            message.c.date,
            message.c.subject,
            message.c.timestamp_send,
            message.c.timestamp_sent,
            message.c.identifier,
            message.c.thread_type,
            message.c.thread_id,
            message.c.state,
        ])

        if person_id is not None:
            stmt = stmt.select_from(message.join(message_recipient)).where(
                message_recipient.c.person_id == person_id)

        if state is not None:
            stmt = stmt.where(message.c.state == state)

        if message_id_lt is not None:
            stmt = stmt.where(message.c.id < message_id_lt)

        if thread_type is not None:
            stmt = stmt.where(message.c.thread_type == thread_type)

            if thread_id is not None:
                stmt = stmt.where(message.c.thread_id == thread_id)

        elif thread_id is not None:
            raise ConsistencyError('thread_id specified without thread_type')

        if limit is not None:
            stmt = stmt.limit(limit)

        ans = ResultCollection()

        if oldest_first:
            stmt = stmt.order_by(message.c.id.asc())
        else:
            stmt = stmt.order_by(message.c.id.desc())

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt):
                ans[row['id']] = Message(body=None, recipients=None,
                                         thread_identifiers=None, **row)

        return ans

    def update_message(self, message_id,
                       state=None, state_prev=None,
                       state_is_system=False,
                       timestamp_send=(), timestamp_sent=(),
                       identifier=None,
                       _conn=None, _test_skip_check=False):
        """
        Update a message record.
        """

        values = {}

        stmt = message.update().where(message.c.id == message_id)

        if state is not None:
            if not MessageState.is_valid(
                    state, is_system=state_is_system):
                raise FormattedError('invalid state {} for message update',
                                     state)

            values[message.c.state] = state

        if state_prev is not None:
            stmt = stmt.where(message.c.state == state_prev)

        if timestamp_send != ():
            values[message.c.timestamp_send] = timestamp_send

        if timestamp_sent != ():
            values[message.c.timestamp_sent] = timestamp_sent

        if identifier is not None:
            values[message.c.identifier] = identifier

        if not values:
            raise FormattedError('no message updates specified')

        with self._transaction(_conn=_conn) as conn:
            if not _test_skip_check and not self._exists_id(
                    conn, message, message_id):
                raise ConsistencyError(
                    'message does not exist with id={}', message_id)

            result = conn.execute(stmt.values(values))

            if result.rowcount != 1:
                raise ConsistencyError(
                    'no rows matched updating message with id={}', message_id)
