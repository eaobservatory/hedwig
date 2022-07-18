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

from collections import namedtuple
import functools
import os
import re

from authlib.oauth2 import OAuth2Error
from authlib.oauth2.rfc6749 import grants
from authlib.oauth2.rfc6749.util import list_to_scope, scope_to_list
from authlib.oidc.core import UserInfo
from authlib.oidc.core import grants as oidc_grants
from authlib.integrations.flask_oauth2 import AuthorizationServer
from flask import Blueprint
from flask import request as flask_request
from flask import g as flask_g

from ...compat import str_to_unicode
from ...config import get_config, get_home
from ...error import NoSuchValue
from ...type.simple import OAuthCode, OAuthToken
from ..util import get_logger, _make_response, require_auth, session, url_for


clients = None
key = None


def create_oauth_blueprint(db, app):
    """
    Create Flask Blueprint for an OAuth 2 service.
    """

    bp = Blueprint('oauth', __name__)

    _configure_clients()
    _configure_key()

    server = AuthorizationServer()
    server.init_app(app, query_client=query_client, save_token=save_token)

    server.register_grant(
        AuthorizationCodeGrant, [OpenIDCode(require_nonce=False)])

    def db_in_g(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            flask_g.db = db
            return f(*args, **kwargs)

        return decorated

    @bp.route('/authorize', methods=['GET', 'POST'])
    @db_in_g
    @require_auth(require_person=True)
    def authorize(current_user):
        logger = get_logger()

        if flask_request.method == 'POST':
            form = flask_request.form
            try:
                if 'submit_cancel' in form:
                    return server.create_authorization_response(
                        grant_user=None)
                if 'submit_confirm' in form:
                    return server.create_authorization_response(
                        grant_user=session['person']['id'])
            except OAuth2Error as e:
                return _make_response('error.html', {
                    'title': 'Error',
                    'message': e.error,
                    'links': None,
                })

        try:
            grant = server.validate_consent_request()
        except OAuth2Error as e:
            logger.error('Error validating grant request: {}', e.message)
            return _make_response('error.html', {
                'title': 'Error',
                'message': 'Error validating request.',
                'links': None,
            })

        return _make_response('confirm.html', {
            'title': 'Authorize Access',
            'message': 'Do you wish to allow {} to access your account '
            'information?'.format(grant.client.name),
            'target': '',
        })

    @bp.route('/token', methods=['POST'])
    @db_in_g
    def issue_token():
        return server.create_token_response()

    return bp


def query_client(client_id):
    return clients.get(client_id)


def _configure_clients():
    global clients

    config = get_config()
    clients = {}

    for (client_id, client_str) in config.items('oauth_clients'):
        (client_name, client_secret, client_uris) = client_str.split(',', 2)
        clients[client_id] = Client(
            client_id, client_name, client_secret, client_uris.split(','))


def _configure_key():
    global key

    config = get_config()

    key_file = config.get('oauth_oidc', 'key')

    # Allow key_file to be skipped for the test suite.
    if key_file:
        with open(os.path.join(
                get_home(), key_file), 'r') as f:
            key = f.read()


def save_token(token_data, request):
    person_id = request.user
    if person_id is None:
        # No "client credentials" grant type support.
        raise Exception('token person_id not given')

    flask_g.db.add_oauth_token(
        token_type=str_to_unicode(token_data['token_type']),
        access_token=str_to_unicode(token_data['access_token']),
        refresh_token=str_to_unicode(token_data.get('refresh_token', None)),
        client_id=request.client.get_client_id(),
        scope=token_data['scope'],
        person_id=person_id,
        expires_in=token_data['expires_in'])


class OpenIDCode(oidc_grants.OpenIDCode):
    def exists_nonce(self, nonce, request):
        return bool(flask_g.db.search_oauth_code(
            client_id=client.id, nonce=nonce))

    def get_jwt_config(self, grant):
        if key is None:
            raise Exception('No OIDC key is present')

        return {
            'key': key,
            'alg': 'RS512',
            'iss': get_config().get('oauth_oidc', 'iss'),
            'exp': 3600,
        }

    def generate_user_info(self, user, scope):
        person = flask_g.db.get_person(person_id=user, with_email=True)

        user_info = UserInfo(
            sub=user,
            name=person.name,
            profile=url_for(
                'people.person_view', person_id=user, _external=True))

        try:
            email = person.email.get_primary()
            user_info['email'] = email.address
            user_info['email_verified'] = email.verified
        except NoSuchValue:
            pass

        return user_info


class AuthorizationCodeGrant(grants.AuthorizationCodeGrant):
    def save_authorization_code(self, code, request):
        flask_g.db.add_oauth_code(
            code=str_to_unicode(code),
            redirect_uri=request.redirect_uri,
            response_type='code',
            nonce=request.data.get('nonce'),
            client_id=request.client.get_client_id(),
            scope=request.scope,
            person_id=request.user)

    def query_authorization_code(self, code, client):
        return flask_g.db.search_oauth_code(
            client_id=client.id, code=code).get_single(default=None)

    def delete_authorization_code(self, authorization_code):
        flask_g.db.delete_oauth_code(code_id=authorization_code.id)

    def authenticate_user(self, authorization_code):
        return authorization_code.person_id


class Client(namedtuple('Client_', ['id', 'name', 'secret', 'redirect_uris'])):
    def get_client_id(self):
        return self.id

    def get_default_redirect_uri(self):
        return self.redirect_uris[0]

    def get_allowed_scope(self, scope):
        if not scope:
            return ''
        allowed = set(scope_to_list('openid'))
        return list_to_scope([s for s in scope.split() if s in allowed])

    def check_redirect_uri(self, redirect_uri):
        # Allow any port with loopback IP literal (see e.g. RFC8252 7.3).
        redirect_uri = re.sub(r'^(http://(?:127.0.0.1|\[::1\])):\d+', r'\1', redirect_uri)

        return redirect_uri in self.redirect_uris

    def has_client_secret(self):
        return True

    def check_client_secret(self, client_secret):
        return self.secret == client_secret

    def check_token_endpoint_auth_method(self, method):
        return method in ('client_secret_basic', 'client_secret_post')

    def check_response_type(self, response_type):
        return response_type == 'code'

    def check_grant_type(self, grant_type):
        return grant_type == 'authorization_code'
