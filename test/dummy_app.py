# Copyright (C) 2016 East Asian Observatory
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

from codecs import utf_8_decode

from hedwig import auth
from hedwig.config import get_config
from hedwig.web.app import create_web_app

from .dummy_config import DummyConfigTestCase
from .dummy_db import get_dummy_database


class WebAppTestCase(DummyConfigTestCase):
    facility_spec = 'Generic'

    def setUp(self):
        DummyConfigTestCase.setUp(self)

        self.config = get_config()
        self.db = get_dummy_database(facility_spec=self.facility_spec,
                                     randomize_ids=False)
        auth._rounds = 10
        auth.password_hash_delay = 0

        app_info = create_web_app(db=self.db, facility_spec=self.facility_spec,
                                  _test_return_extra=True)

        self.app = app_info['app']
        self.app.config['TESTING'] = True

        self.facilities = app_info['facilities']

        self.client = self.app.test_client()

    def tearDown(self):
        DummyConfigTestCase.tearDown(self)

        del self.db

    def log_in(self, user_name, password):
        return self.client.post(
            '/user/log_in',
            data={'user_name': user_name, 'password': password},
            follow_redirects=True)

    def log_out(self):
        return self.client.get('/user/log_out', follow_redirects=True)

    def assertInEncoded(self, member, container, *args, **kwargs):
        """
        Decode given "container" (string) before asserting that the "member"
        (substring) is in it.
        """

        return self.assertIn(member, utf_8_decode(container)[0],
                             *args, **kwargs)

    def _get_facility_view(self, code):
        for facility in self.facilities.values():
            if facility.code == code:
                return facility.view

        raise Exception('facility {} not found'.format(code))
