# Copyright (C) 2015-2023 East Asian Observatory
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

from ...email.util import is_valid_email
from ...error import ConsistencyError, Error, FormattedError, \
    NoSuchRecord, MultipleRecords
from ...type.collection import ResultCollection, MessageRecipientCollection
from ...type.enum import MessageState, MessageThreadType
from ...type.simple import Message, MessageRecipient
from ...util import is_list_like
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

        for email_address in email_addresses:
            if not is_valid_email(email_address):
                raise FormattedError(
                    'email address "{}" does not appear to be valid',
                    email_address)

        if thread_type is not None:
            if not MessageThreadType.is_valid(thread_type):
                raise FormattedError('invalid thread type {}', thread_type)

        elif thread_id is not None:
            raise Error('thread_id specified without thread_type')

        if not _test_skip_check:
            if ((not isinstance(person_ids, set)) and
                    (len(person_ids) != len(set(person_ids)))):
                raise Error('duplicate person_id for new message')

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

        return self.search_message(
            message_id=message_id, with_body=True, with_recipients=True
        ).get_single()

    def search_message(
            self, person_id=None, state=None,
            message_id=None, message_id_lt=None,
            thread_type=None, thread_id=None,
            limit=None, oldest_first=False,
            with_body=False, with_thread_identifiers=False,
            with_recipients=False, with_recipients_resolved=False,
            _conn=None):
        """
        Searches for messages.

        The selection of messages to be returned can be controlled with the
        optional keyword arguments.
        """

        default = {
            'recipients': None,
            'thread_identifiers': None,
        }

        if with_body:
            fields = [message]
        else:
            fields = [x for x in message.columns if x.name != 'body']
            default['body'] = None

        stmt = select(fields)

        if person_id is not None:
            stmt = stmt.select_from(
                message.join(message_recipient)
            ).where(
                message_recipient.c.person_id == person_id)

        if state is not None:
            stmt = stmt.where(message.c.state == state)

        if message_id is not None:
            stmt = stmt.where(message.c.id == message_id)

        if message_id_lt is not None:
            if message_id is not None:
                raise Error('message_id and message_id_lt both specified')

            stmt = stmt.where(message.c.id < message_id_lt)

        if thread_type is not None:
            stmt = stmt.where(message.c.thread_type == thread_type)

            if thread_id is not None:
                stmt = stmt.where(message.c.thread_id == thread_id)

        elif thread_id is not None:
            raise Error('thread_id specified without thread_type')

        if limit is not None:
            stmt = stmt.limit(limit)

        if oldest_first:
            stmt = stmt.order_by(message.c.id.asc())
        else:
            stmt = stmt.order_by(message.c.id.desc())

        ans = ResultCollection()
        message_ids = set()
        extra = {}

        with self._transaction(_conn=_conn) as conn:
            for row in conn.execute(stmt):
                row_key = row['id']
                message_ids.add(row_key)

                values = default.copy()
                values.update(**row)

                # For now, perform separate query for thread identifiers of
                # each message.  In principle we could do this instead for all
                # messages using a message-message join.
                if (with_thread_identifiers and
                        (values['thread_type'] is not None) and
                        (values['thread_id'] is not None)):
                    values['thread_identifiers'] = [
                        x.identifier for x in self.search_message(
                            thread_type=values['thread_type'],
                            thread_id=values['thread_id'],
                            message_id_lt=row_key,
                            state=MessageState.SENT,
                            oldest_first=True,
                            _conn=conn).values()]

                ans[row_key] = Message(**values)

            if with_recipients:
                extra['recipients'] = self.search_message_recipient(
                    message_id=message_ids,
                    with_resolved_email=with_recipients_resolved, _conn=conn)

        # Attach extra information, outside of database transaction block.
        if extra:
            for key in list(ans.keys()):
                row = ans[key]

                ans[key] = row._replace(**{k: v.subset_by_message(row.id)
                                           for (k, v) in extra.items()})

        return ans

    def search_message_recipient(
            self, message_id=None, with_resolved_email=False,
            _conn=None):
        """
        Search for message recipient records.
        """

        default = {}

        fields = [
            message_recipient.c.message_id,
            message_recipient.c.person_id,
            person.c.name.label('person_name'),
        ]

        select_from = message_recipient.join(person)

        if with_resolved_email:
            fields.extend([
                coalesce(message_recipient.c.email_address,
                         email.c.address).label('email_address'),
                coalesce(email.c.public, False).label('email_public'),
            ])

            select_from = select_from.outerjoin(
                email,
                and_(person.c.id == email.c.person_id, case([(
                    message_recipient.c.email_address.isnot(None),
                    message_recipient.c.email_address == email.c.address)],
                    else_=email.c.primary)
                ))

        else:
            fields.extend([
                message_recipient.c.email_address.label('email_address'),
            ])

            default['email_public'] = None

        stmt = select(fields).select_from(select_from)

        iter_field = None
        iter_list = None

        if message_id is not None:
            if is_list_like(message_id):
                assert iter_field is None
                iter_field = message_recipient.c.message_id
                iter_list = message_id
            else:
                stmt = stmt.where(message_recipient.c.message_id == message_id)

        ans = MessageRecipientCollection()
        # Arbitrary counter as this table doesn't have a simple primary key.
        i = 0

        with self._transaction(_conn=_conn) as conn:
            for iter_stmt in self._iter_stmt(stmt, iter_field, iter_list):
                for row in conn.execute(iter_stmt):
                    i += 1

                    values = default.copy()
                    values.update(**row)

                    ans[i] = MessageRecipient(**values)

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
