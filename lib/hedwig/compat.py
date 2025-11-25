# Copyright (C) 2016-2025 East Asian Observatory
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


def split_version(version):
    return tuple(int(x) for x in version.split('.'))


if python_version < 3:
    # Python 2.

    from codecs import ascii_decode, ascii_encode, utf_8_encode
    from collections import OrderedDict
    from math import floor as _math_floor
    from urllib import quote as _url_quote
    from urllib import urlencode as _urlencode

    char = unichr
    string_type = unicode
    byte_type = str

    def unicode_to_str(value):
        """Convert unicode to native string type."""
        if value is None:
            return None
        return ascii_encode(value)[0]

    def str_to_unicode(value):
        """Convert native string type to unicode."""
        if value is None:
            return None
        return ascii_decode(value)[0]

    def make_type(name, *args):
        """Create a class specified with a unicode name."""
        return type(unicode_to_str(name), *args)

    def first_value(dictionary):
        """
        Get the "first" value of a dictionary.

        :raises IndexError: if the dictionary has no first value.
        """

        try:
            return next(dictionary.itervalues())
        except StopIteration:
            raise IndexError('dictionary has no first value')

    def iter_items(dictionary):
        """
        Get an iterator for the dictionary's items.
        """

        return dictionary.iteritems()

    def floor(value):
        return int(_math_floor(value))

    def url_quote(string):
        """Unicode-safe wrapper for urllib.quote."""
        return _url_quote(utf_8_encode(string)[0])

    def url_encode(query):
        """Unicode-safe wrapper for urllib.urlencode."""
        return _urlencode(OrderedDict((
            (utf_8_encode(k)[0], utf_8_encode(v)[0])
            for (k, v) in query.items())))

    ExceptionWithMessage = Exception

else:
    # Python 3.

    from math import floor
    from urllib.parse import quote as url_quote
    from urllib.parse import urlencode as url_encode

    char = chr
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
        """
        Get the "first" value of a dictionary.

        :raises IndexError: if the dictionary has no first value.
        """

        try:
            return next(iter(dictionary.values()))
        except StopIteration:
            raise IndexError('dictionary has no first value')

    def iter_items(dictionary):
        """
        Get an iterator for the dictionary's items.
        """

        return iter(dictionary.items())

    class ExceptionWithMessage(Exception):
        """Exception class which restores the 'message' property."""
        @property
        def message(self):
            return self.args[0]
