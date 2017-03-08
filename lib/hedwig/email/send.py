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

from contextlib import closing, contextmanager
from email.header import Header
from email.mime.nonmultipart import MIMENonMultipart
from email.utils import formataddr, make_msgid
from io import BytesIO
import socket
from smtplib import SMTP, SMTPException

try:
    from email.generator import BytesGenerator
except ImportError:
    from email.generator import Generator as BytesGenerator

try:
    from email.utils import format_datetime as _format_datetime
    from datetime import timezone

    def format_datetime(dt):
        # Only Python 3 has datetime.timezone, so we have to do this here
        # rather than in the main code.
        return _format_datetime(dt.replace(tzinfo=timezone.utc))

except ImportError:
    from email.utils import formatdate
    from calendar import timegm

    def format_datetime(dt):
        result = formatdate(timegm(dt.utctimetuple()))
        if result.endswith('-0000'):
            # We are using UTC, but `formatdate` returns time zone "-0000"
            # which RFC2822 says means an unknown local time.
            result = result[:-5] + '+0000'
        return result

from ..compat import unicode_to_str
from ..config import get_config
from ..util import get_logger

logger = get_logger(__name__)


@contextmanager
def quitting(smtp):
    """
    Context manager which calls the `quit` method on the given
    object at the end of the block.

    This function is analogous to the standard `contextlib.closing` function.
    """

    try:
        yield smtp
    finally:
        smtp.quit()


class MIMETextFlowed(MIMENonMultipart):
    """
    MIME message class for flowed text.
    """

    def __init__(self, text, charset='utf-8'):
        """
        Based on email.mime.text.MIMEText but adds format=flowed
        to the content type.  Also defaults to UTF-8.
        """

        MIMENonMultipart.__init__(self, 'text', 'plain',
                                  charset=charset, format='flowed')
        self.set_payload(text, charset)

    def __setitem__(self, name, val):
        """
        Overridden `__setitem__` method to ensure header names are
        native strings.  Note: we don't currently use `add_header`
        so we don't provide an overridden version of it.
        """

        MIMENonMultipart.__setitem__(self, unicode_to_str(name), val)


def send_email_message(message):
    """
    Send an email message.

    On success, returns the message identifier.  Returns None on failure.
    """

    config = get_config()
    server = config.get('email', 'server')
    from_ = config.get('email', 'from')

    (identifier, msg, recipients) = _prepare_email_message(message, from_)

    try:
        with quitting(SMTP(server)) as smtp:
            refusal = smtp.sendmail(
                from_, recipients, msg)

            for (recipient, problem) in refusal.items():
                logger.error('Email message {} refused for {}: {}: {}',
                             message.id, recipient, problem[0], problem[1])

            return identifier

    except SMTPException:
        logger.exception('Email message {} refused for all recipients',
                         message.id)
    except socket.error:
        logger.exception('Email message {} not sent due to failure '
                         'to connect to email server', message.id)

    return None


def _prepare_email_message(message, from_, identifier=None):
    """
    Prepare an email message.

    This is a separate function to allow this routine to be tested
    independently of actual message sending.
    """

    # Sort recipients into public ("to") and private ("bcc") lists,
    # unless there is only one recipient, in which case there's no
    # need to hide the address.
    recipients_plain = []
    recipients_public = []
    recipients_private = []
    single_recipient = len(message.recipients) == 1
    for recipient in message.recipients:
        recipients_plain.append(recipient.address)
        if single_recipient or recipient.public:
            recipients_public.append(formataddr((recipient.name,
                                                 recipient.address)))
        else:
            recipients_private.append(formataddr((recipient.name,
                                                  recipient.address)))

    # Generate message identifier if one has not been provided.
    if identifier is None:
        identifier = make_msgid('{}'.format(message.id))

    # Construct message.
    msg = MIMETextFlowed(message.body)

    msg['Subject'] = Header(message.subject)
    msg['Date'] = Header(format_datetime(message.date))
    msg['From'] = Header(from_)
    msg['To'] = Header(', '.join(recipients_public))
    msg['Message-ID'] = Header(identifier)
    if message.thread_identifiers:
        # Currently set this to the last message in the thread,
        # to create a nested thread structure.
        # Alternatively could set "In-Reply-To" to be the first message
        # in the thread to make a thread with a flat structure.
        msg['In-Reply-To'] = Header(message.thread_identifiers[-1])
        msg['References'] = Header(' '.join(message.thread_identifiers))

    with closing(BytesIO()) as f:
        BytesGenerator(f, mangle_from_=False).flatten(msg)
        msg = f.getvalue()

    return (identifier, msg, recipients_plain)
