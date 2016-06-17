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

from contextlib import contextmanager

from hedwig.view import auth
from hedwig.view.people import _update_session_user, _update_session_person
from hedwig.web.util import session

from .dummy_app import WebAppTestCase


class WebAppAuthTestCase(WebAppTestCase):
    def test_person(self):
        user_admin = self.db.add_user('admin', 'pass')
        person_admin = self.db.add_person('Admin', user_id=user_admin)
        self.db.update_person(person_admin, admin=True)

        user_1 = self.db.add_user('user1', 'pass1')
        person_1 = self.db.add_person('Person 1', user_id=user_1)

        user_2 = self.db.add_user('user2', 'pass2')
        person_2 = self.db.add_person('Person 2', user_id=user_2)

        with self._as_person(person_1):
            can = auth.for_person(self.db, self.db.get_person(person_1))
            self.assertEqual(can, auth.yes)

            can = auth.for_person(self.db, self.db.get_person(person_2))
            self.assertEqual(can, auth.no)

        with self._as_person(person_2, is_admin=True):
            can = auth.for_person(self.db, self.db.get_person(person_1))
            self.assertEqual(can, auth.no)

            can = auth.for_person(self.db, self.db.get_person(person_2))
            self.assertEqual(can, auth.yes)

        with self._as_person(person_admin):
            can = auth.for_person(self.db, self.db.get_person(person_1))
            self.assertEqual(can, auth.no)

            can = auth.for_person(self.db, self.db.get_person(person_2))
            self.assertEqual(can, auth.no)

        with self._as_person(person_admin, is_admin=True):
            can = auth.for_person(self.db, self.db.get_person(person_1))
            self.assertEqual(can, auth.yes)

            can = auth.for_person(self.db, self.db.get_person(person_2))
            self.assertEqual(can, auth.yes)

    @contextmanager
    def _as_person(self, person_id, is_admin=False):
        person = self.db.get_person(person_id)

        with self.app.test_request_context():
            _update_session_user(person.user_id)
            _update_session_person(person)

            if is_admin:
                session['is_admin'] = True

            yield

            session.clear()
