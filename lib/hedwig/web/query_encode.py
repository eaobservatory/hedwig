# Copyright (C) 2018 East Asian Observatory
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

from base64 import urlsafe_b64decode, urlsafe_b64encode
from codecs import ascii_decode, ascii_encode

import msgpack

from ..error import Error, ParseError


def decode_query(encoded):
    """
    Attempt to convert encoded query data back to the original form.

    The first character of the encoded data is inspected to determine
    the encoding form. The remaining data are converted to binary
    and passed to the appropriate decoding function.

    Currently only Base 64-encoded msgpack is supported, with
    designator 'M'.
    """

    query_format = encoded[0]
    try:
        query = ascii_encode(encoded[1:])[0]
    except UnicodeEncodeError:
        raise ParseError('Unexpected character in encoded query.')

    if query_format == 'M':
        return _decode_query_msgpack(query)

    raise ParseError('Unknown query encoding format "{}".', query_format)


def encode_query(query):
    """
    Convert query data (such as a list of parameters) into a form suitable
    for including in an URL to make a 'permalink'.

    Returns a character identifying the encoding scheme followed by
    the encoded data.
    """

    encoded = _encode_query_msgpack(query)

    try:
        encoded = ascii_decode(encoded)[0]
    except UnicodeEncodeError:
        raise Error('Unexpected character in encoded query.')

    return 'M' + encoded


def _decode_query_msgpack(query):
    # Add missing padding to Base 64 string.
    trailing = len(query) % 4
    if trailing == 2:
        query = query + b'=='
    elif trailing == 3:
        query = query + b'='

    try:
        return msgpack.unpackb(urlsafe_b64decode(query), raw=False)
    except:
        raise ParseError('Could not decode query specification.')


def _encode_query_msgpack(query):
    try:
        encoded = urlsafe_b64encode(msgpack.packb(query, use_bin_type=True))
    except:
        raise Error('Could not encode query specification.')

    # Remove Base 64 padding.
    return encoded.rstrip(b'=')
