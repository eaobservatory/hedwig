# Copyright (C) 2026 East Asian Observatory
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

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from joserfc import jwt, jwk
from urllib.parse import parse_qs, urlparse

from hedwig.config import get_config
from hedwig.web.blueprint import oauth

from .base_app import WebAppTestCase


class WebAppOAuthTestCase(WebAppTestCase):
    def setUp(self):
        super(WebAppOAuthTestCase, self).setUp()

        # Set up OAuth information temporarily.
        oauth.clients = {
            'test-client': oauth.Client(
                'test-client',
                'Test Client',
                'test-client-secret-key',
                ['https://test.com/cgi-bin/login.pl']),
        }

        # Configure a signing key for the OpenID Connect ID token.
        self.private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048)

        oauth.key = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()).decode('ascii')

        # Temporarily configure issuer.
        self.config.set('oauth_oidc', 'iss', 'https://hedwig.test')

    def tearDown(self):
        super(WebAppOAuthTestCase, self).tearDown()

        # Reset oauth blueprint information for subsequent tests.
        oauth.clients = None
        oauth.key = None

    def test_oauth(self):
        # Create registered and verified account.
        user_id = self.db.add_user('user1', 'pass1')
        institution_id = self.db.add_institution(
            'institution1', '', '', '', 'US')
        person_id = self.db.add_person(
            'person1', user_id=user_id, institution_id=institution_id)
        self.db.update_person(person_id, verified=True)

        # Log in.
        rv = self.log_in('user1', 'pass1')
        self.assertInEncoded(
            '<li>You have been logged in.</li>',
            rv.data)

        # View authorize page.
        route = '/user/oauth/authorize'
        query_string = {
            'response_type': 'code',
            'client_id': 'test-client',
            'redirect_uri': 'https://test.com/cgi-bin/login.pl',
            'scope': 'openid',
            'state': 'test-state',
        }

        rv = self.client.get(route, query_string=query_string)

        self.assertEqual(rv.status_code, 200)
        self.assertInEncoded(
            'Do you wish to allow',
            rv.data)

        # Try cancel action.
        rv = self.client.post(
            route, query_string=query_string,
            data={'submit_cancel': 'Cancel'})

        self.assertEqual(rv.status_code, 302)
        redirect_params = parse_qs(urlparse(rv.location).query)
        self.assertEqual(redirect_params['error'], ['access_denied'])

        # Try confirm action.
        rv = self.client.post(
            route, query_string=query_string,
            data={'submit_confirm': 'Confirm'})

        self.assertEqual(rv.status_code, 302)
        redirect_params = parse_qs(urlparse(rv.location).query)
        self.assertIn('code', redirect_params)
        self.assertEqual(redirect_params['state'], ['test-state'])

        # Send the received code back to the server with client's secret key.
        rv = self.client.post('/user/oauth/token', data={
            'grant_type': 'authorization_code',
            'code': redirect_params['code'],
            'redirect_uri': query_string['redirect_uri'],
            'client_id': query_string['client_id'],
            'client_secret': 'test-client-secret-key',
        })

        self.assertEqual(rv.status_code, 200)
        token_data = rv.get_json()
        self.assertIn('access_token', token_data)
        self.assertEqual(token_data['token_type'], 'Bearer')
        self.assertEqual(token_data['scope'], 'openid')
        self.assertIsInstance(token_data['expires_in'], int)
        self.assertIn('id_token', token_data)

        # Examine the received id_token.
        public_key = jwk.import_key(
            self.private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo),
            key_type='RSA')

        id_token = jwt.decode(
            token_data['id_token'], public_key, algorithms=['RS512'])

        # Finally check we got the correct person_id.
        self.assertEqual(id_token.claims['sub'], person_id)
        self.assertEqual(id_token.claims['iss'], 'https://hedwig.test')
