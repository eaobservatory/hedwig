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

from .base_app import WebAppTestCase


class JCMTWebAppTestCase(WebAppTestCase):
    facility_spec = 'JCMT'

    def test_review_guidelines(self):
        view = self._get_facility_view('jcmt')

        # Test make_review_guidelines_url
        role_class = view.get_reviewer_roles()

        with self.app.test_request_context():
            url = view.make_review_guidelines_url(role_class.EXTERNAL)
            self.assertTrue(url.endswith('help/review/external_jcmt'))

            url = view.make_review_guidelines_url(role_class.TECH)
            self.assertIsNone(url)
