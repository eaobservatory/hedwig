# Copyright (C) 2023 East Asian Observatory
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

from hedwig.email.util import is_valid_email

from .compat import TestCase


class EmailUtilTestCase(TestCase):
    def test_validate_email(self):
        for address in [
                'a@x',
                'aa@xx',
                'aa+1@xx.yyy',
                'a.bb@x',
                'a.bb.ccc@x',
                'a@xx',
                'a@xx.yy',
                'a@xx.y.z',
                'a@xxx.yyy.zzz',
                'a-b@x!#$%&\'*+y',
                'a/b=c?d@x^y_z`{|}~w',
                ]:
            self.assertTrue(
                is_valid_email(address),
                'valid {}'.format(address))

        for address in [
                '@',
                'a@',
                '@x',
                'a.@x',
                'a@x.',
                '.a@x',
                'a@.x',
                'a..b@x',
                'a.b@x..y',
                'a.b.@x.y',
                'a.b@x.y.',
                '.a.b@x.y',
                'a.b@.x.y.',
                'aa(aa@xx.yy.zz',
                'aa)aa@xx.yy.zz',
                'aa<aa@xx.yy.zz',
                'aa>aa@xx.yy.zz',
                'aa[aa@xx.yy.zz',
                'aa]aa@xx.yy.zz',
                'aa:aa@xx.yy.zz',
                'aa;aa@xx.yy.zz',
                'aa@aa@xx.yy.zz',
                'aa\\aa@xx.yy.zz',
                'aa,aa@xx.yy.zz',
                'aa"aa@xx.yy.zz',
                'aa aa@xx.yy.zz',
                'aaaa@xx.y y.zz',
                ' aaa@xxx',
                'aaa@xxx ',
                ]:
            self.assertFalse(
                is_valid_email(address),
                'invalid {}'.format(address))
