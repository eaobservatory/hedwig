# Copyright (C) 2015-2025 East Asian Observatory
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
from contextlib import closing, contextmanager
from email.utils import parseaddr, make_msgid
from io import BytesIO
import socket
from smtplib import SMTP, SMTPException

from ..compat import python_version, unicode_to_str
from ..config import get_config
from ..error import FormattedError
from ..type.enum import MessageFormatType, MessageThreadType
from ..type.simple import MessageRecipient
from ..type.util import null_tuple
from ..util import get_logger
from .format import wrap_email_text, unwrap_email_text

use_cte_qp = True

if python_version < 3:
    from calendar import timegm
    from codecs import ascii_encode, utf_8_encode
    from email.charset import Charset, add_charset, QP, BASE64
    from email.generator import Generator as BytesGenerator
    from email.header import Header
    from email.mime.nonmultipart import MIMENonMultipart
    from email.utils import formatdate
    import re

    # Override "header_enc" method for UTF-8 to use quoted printable
    # because the default (SHORTEST) may choose BASE64 which seems to
    # ignore the maxlinelen parameter.
    add_charset(b'utf-8', QP, (QP if use_cte_qp else BASE64), b'utf-8')
    charset_utf_8 = Charset(b'utf-8')

    non_qtext = re.compile(r'[\\"]')

    def format_datetime(dt):
        result = formatdate(timegm(dt.utctimetuple()))
        if result.endswith('-0000'):
            # We are using UTC, but `formatdate` returns time zone "-0000"
            # which RFC2822 says means an unknown local time.
            result = result[:-5] + '+0000'
        return result

    def _prepare_email_message_bytes(*args, **kwargs):
        return _prepare_email_message_py2(*args, **kwargs)

    class MIMETextMaybeFlowed(MIMENonMultipart):
        """
        MIME message class for flowed text.
        """

        def __init__(self, text, charset='utf-8', **kwargs):
            """
            Based on email.mime.text.MIMEText but defaults to UTF-8.
            """

            MIMENonMultipart.__init__(
                self, 'text', 'plain', charset=charset, **kwargs)
            self.set_payload(text, charset)

        def __setitem__(self, name, val):
            """
            Overridden `__setitem__` method to ensure header names are
            native strings.  Note: we don't currently use `add_header`
            so we don't provide an overridden version of it.
            """

            MIMENonMultipart.__setitem__(self, unicode_to_str(name), val)

    class MIMETextFlowed(MIMETextMaybeFlowed):
        def __init__(self, text):
            """
            Adds format=flowed to the content type.
            """

            MIMETextMaybeFlowed.__init__(
                self, text, format='flowed')

else:
    from datetime import timezone
    from email.message import EmailMessage
    from email.generator import BytesGenerator
    from email.headerregistry import Address
    from email.policy import EmailPolicy

    policy = EmailPolicy().clone(
        cte_type='7bit',
    )

    def _prepare_email_message_bytes(*args, **kwargs):
        return _prepare_email_message_py3(*args, **kwargs)


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


def send_email_message(message, dry_run=False):
    """
    Send an email message.

    On success, returns the message identifier.
    """

    config = get_config()
    server = config.get('email', 'server')
    port = int(config.get('email', 'port'))
    from_ = config.get('email', 'from')
    maxheaderlen_str = config.get('email', 'maxheaderlen')

    maxheaderlen = None
    if maxheaderlen_str:
        maxheaderlen = int(maxheaderlen_str)

    (identifier, msg, recipients) = _prepare_email_message(
        message, from_, maxheaderlen=maxheaderlen)

    if dry_run:
        return 'DRY-RUN'

    try:
        with quitting(SMTP(server, port=port)) as smtp:
            refusal = smtp.sendmail(
                from_, recipients, msg)

            for (recipient, problem) in refusal.items():
                logger.error('Email message {} refused for {}: {}: {}',
                             message.id, recipient, problem[0], problem[1])

    except SMTPException:
        raise FormattedError('Email message {} refused for all recipients',
                             message.id)

    except socket.error:
        raise FormattedError('Email message {} not sent due to failure '
                             'to connect to email server', message.id)

    return identifier


def _prepare_email_message(message, from_, identifier=None, maxheaderlen=None):
    """
    Prepare an email message.

    This is a separate function to allow this routine to be tested
    independently of actual message sending.
    """

    (from_name, from_address) = parseaddr(from_)

    # Collect recipients in the ("to") list based on their public setting
    # unless there is only one recipient, in which case there's no
    # need to hide the address.  Place all recipients' addresses in the
    # "plain" list used to actually send the message ("to" + "bcc").
    recipients_plain = []
    recipients_public = []
    single_recipient = len(message.recipients) == 1
    for recipient in message.recipients.values():
        recipients_plain.append(recipient.email_address)
        if single_recipient or recipient.email_public:
            recipients_public.append(
                (recipient.person_name, recipient.email_address))

    # Generate message identifier if one has not been provided.
    if identifier is None:
        identifier = make_msgid('{}'.format(message.id))

    # Prepare extra header values.
    extra_headers = OrderedDict()

    extra_headers['Message-ID'] = identifier
    if message.thread_identifiers:
        # Currently set this to the last message in the thread,
        # to create a nested thread structure.
        # Alternatively could set "In-Reply-To" to be the first message
        # in the thread to make a thread with a flat structure.
        extra_headers['In-Reply-To'] = message.thread_identifiers[-1]
        extra_headers['References'] = ' '.join(message.thread_identifiers)

    extra_headers['X-Hedwig-ID'] = '{}'.format(message.id)
    if (message.thread_id is not None) and (message.thread_type is not None):
        extra_headers['X-Hedwig-Thread'] = '{} {}'.format(
            MessageThreadType.url_path(message.thread_type), message.thread_id)

    msg = _prepare_email_message_bytes(
        message=message,
        from_=null_tuple(MessageRecipient)._replace(
            person_name=from_name, email_address=from_address),
        recipients=recipients_public,
        extra_headers=extra_headers,
        maxheaderlen=maxheaderlen)

    return (identifier, msg, recipients_plain)


def _prepare_email_message_py3(
        message, from_, recipients, extra_headers, maxheaderlen):
    """
    Generate email message using the "new" EmailMessage API.
    """

    generator_kwargs = {}
    if maxheaderlen is not None:
        generator_kwargs['maxheaderlen'] = maxheaderlen

    msg = EmailMessage(policy=policy)

    message_body = _prepare_email_message_body(message)

    if use_cte_qp:
        msg.set_content(
            message_body,
            charset='utf-8',
            cte='quoted-printable')

    else:
        msg.set_content(
            message_body,
            charset='utf-8',
            cte='base64',
            params={'format': 'flowed'})

    msg['Subject'] = message.subject
    msg['Date'] = message.date.replace(tzinfo=timezone.utc)
    msg['From'] = Address(
        display_name=from_.person_name, addr_spec=from_.email_address)
    msg['To'] = [
        Address(display_name=person_name, addr_spec=email_address)
        for (person_name, email_address) in recipients]

    for (extra_header, header_value) in extra_headers.items():
        msg[extra_header] = header_value

    with closing(BytesIO()) as f:
        BytesGenerator(f, mangle_from_=False, **generator_kwargs).flatten(msg)
        msg = f.getvalue()

    return msg


def _prepare_email_message_py2(
        message, from_, recipients, extra_headers, maxheaderlen):
    """
    Generate email message using the email.mime package found in Python 2.
    """

    header_kwargs = {}
    generator_kwargs = {}
    if maxheaderlen is not None:
        header_kwargs['maxlinelen'] = maxheaderlen
        header_kwargs['charset'] = 'utf-8'
        generator_kwargs['maxheaderlen'] = maxheaderlen

    message_body = _prepare_email_message_body(message)

    if use_cte_qp:
        msg = MIMETextMaybeFlowed(message_body)

    else:
        msg = MIMETextFlowed(message_body)

    msg['Subject'] = Header(message.subject, **header_kwargs)
    msg['Date'] = Header(format_datetime(message.date), **header_kwargs)
    msg['From'] = _prepare_address_header(
        ((from_.person_name, from_.email_address),))
    msg['To'] = _prepare_address_header(recipients)

    for (extra_header, header_value) in extra_headers.items():
        msg[extra_header] = Header(header_value, **header_kwargs)

    with closing(BytesIO()) as f:
        BytesGenerator(f, mangle_from_=False, **generator_kwargs).flatten(msg)
        msg = f.getvalue()

    return msg


def _prepare_email_message_body(message):
    if message.format == MessageFormatType.PLAIN_FLOWED:
        if use_cte_qp:
            return unwrap_email_text(message.body)

    elif message.format == MessageFormatType.PLAIN:
        if not use_cte_qp:
            return wrap_email_text(message.body)

    else:
        raise FormattedError(
            'Email message format type {} not recognized',
            message.format)

    return message.body


def _prepare_address_header(names_addresses):
    """
    Encode an email address header ('From' or 'To') with the given names and
    addresses.  The addresses must be ASCII and will be enclosed in angle
    brackets.  The names will be enclosed in double quotes if ASCII or
    encoded as quoted printable otherwise.
    """

    encoded = []

    for (name, address) in names_addresses:
        try:
            name_ascii = ascii_encode(name)[0]
            name_encoded = b'"{}"'.format(
                non_qtext.sub(r'\\\g<0>', name_ascii))
        except UnicodeEncodeError:
            name_encoded = charset_utf_8.header_encode(utf_8_encode(name)[0])

        try:
            address_encoded = ascii_encode(address)[0]
        except UnicodeEncodeError:
            raise FormattedError(
                'Could not prepare email message because address "{}" could '
                'not be encoded as ASCII.', address)

        encoded.append(b'{} <{}>'.format(name_encoded, address_encoded))

    return b', '.join(encoded)
