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

from sys import version_info

python_version = version_info[0]


if python_version < 3:
    # Python 2.

    from codecs import ascii_decode, ascii_encode

    string_type = unicode
    byte_type = str

    def unicode_to_str(value):
        """Convert unicode to native string type."""
        return ascii_encode(value)[0]

    def str_to_unicode(value):
        """Convert native string type to unicode."""
        return ascii_decode(value)[0]

    def make_type(name, *args):
        """Create a class specified with a unicode name."""
        return type(unicode_to_str(name), *args)

    def first_value(dictionary):
        """Get the "first" value of a dictionary."""
        return next(dictionary.itervalues())

    ExceptionWithMessage = Exception

else:
    # Python 3.

    string_type = str
    byte_type = bytes
    make_type = type

    def unicode_to_str(value):
        """Convert unicode to native string type."""
        return value

    def str_to_unicode(value):
        """Convert native string type to unicode."""
        return value

    def first_value(dictionary):
        """Get the "first" value of a dictionary."""
        return next(iter(dictionary.values()))

    class ExceptionWithMessage(Exception):
        """Exception class which restores the 'message' property."""
        @property
        def message(self):
            return self.args[0]
