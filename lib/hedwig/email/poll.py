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

from ..error import ConsistencyError
from .send import send_email_message


def send_queued_messages(db, dry_run=False):
    """
    Attempts to send any unsent email messages.

    Repeatedly queries the database for an unsent message.  If a message
    is found, it is sent and then marked as sent in the database.
    If no message is found then the loop exits.

    Returns the number of messages sent.
    """

    if dry_run:
        return 0

    message_ids = set()

    n_sent = 0

    while True:
        message = db.get_unsent_message()
        if message is None:
            break

        if message.id in message_ids:
            raise ConsistencyError('message with id={} seen more than once',
                                   message.id)
        message_ids.add(message.id)

        db.mark_message_sending(message.id)

        identifier = send_email_message(message)

        if identifier is None:
            db.mark_message_error(message.id)

        else:
            db.mark_message_sent(message.id, identifier)

            n_sent += 1

    return n_sent
