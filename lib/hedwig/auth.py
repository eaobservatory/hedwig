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

from binascii import hexlify, unhexlify
from codecs import ascii_decode, utf_8_encode
try:
    from hashlib import pbkdf2_hmac
except ImportError:
    from backports.pbkdf2 import pbkdf2_hmac
from os import urandom

_rounds = 1000000

# Time to sleep as a delay which simulates hashing the password.
password_hash_delay = 10


def create_password_hash(password_raw):
    """
    Create hash and salt for the given raw password.

    The password is encoded as UTF-8 and a salt read from "os.random".
    Returns ASCII hex representation of the hash and salt.
    """

    password_salt = urandom(32)
    password_hash = pbkdf2_hmac(
        'sha256', utf_8_encode(password_raw)[0], password_salt, _rounds)

    return (ascii_decode(hexlify(password_hash))[0],
            ascii_decode(hexlify(password_salt))[0])


def check_password_hash(password_raw, password_hash, password_salt):
    """
    Checks the given raw password against the hash and salt.

    Assumes that the hash and salt are given in ASCII hex representation
    and checks whether the password re-generates the hash when hashed
    using the salt.
    """

    return password_hash == ascii_decode(hexlify(pbkdf2_hmac(
        'sha256', utf_8_encode(password_raw)[0], unhexlify(password_salt),
        _rounds)))[0]


def generate_token():
    """
    Generate random token strings, to be used for things such as password
    reset codes and invitations.
    """

    return ascii_decode(hexlify(urandom(16)))[0]
