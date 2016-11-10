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

import os
from tempfile import mkstemp

from hedwig.pidfile import pidfile_write, pidfile_running, pidfile_delete

from .compat import TestCase


class VersionTestCase(TestCase):
    def test_pidfile(self):
        (fh, filename) = mkstemp()
        os.close(fh)

        pidfile_write(filename, os.getpid())

        self.assertTrue(pidfile_running(filename))

        self.assertTrue(os.path.exists(filename))

        pidfile_delete(filename)

        self.assertFalse(os.path.exists(filename))
