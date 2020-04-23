# Copyright (C) 2020 East Asian Observatory
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

from hedwig.type.simple import OAuthCode, OAuthToken

from .compat import TestCase


class SimpleTypeTestCase(TestCase):
    def test_oauth_code(self):
        code = OAuthCode(
            id=123,
            code='XYZ',
            redirect_uri='http://localhost:49000/',
            response_type='code',
            nonce='ABC',
            client_id=456,
            scope='openid',
            person_id=789,
            issued=datetime.utcfromtimestamp(3600),
            expiry=datetime.utcfromtimestamp(3700))

        self.assertEqual(code.get_redirect_uri(), 'http://localhost:49000/')

        self.assertEqual(code.get_scope(), 'openid')

        self.assertEqual(code.get_nonce(), 'ABC')

        self.assertEqual(code.get_auth_time(), 3600)

    def test_oauth_token(self):
        token = OAuthToken(
            id=123,
            token_type='Bearer',
            access_token='XYZ',
            refresh_token=None,
            revoked=False,
            client_id=456,
            scope='openid',
            person_id=789,
            issued=datetime.utcfromtimestamp(3600),
            expiry=datetime.utcfromtimestamp(3700))

        self.assertEqual(token.get_client_id(), 456)

        self.assertEqual(token.get_scope(), 'openid')

        self.assertEqual(token.get_expires_in(), 100)

        self.assertEqual(token.get_expires_at(), 3700)
