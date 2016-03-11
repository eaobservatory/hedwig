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

from ..error import FormattedError


class EnumBasic(object):
    """
    Mix-in for enum-style classes which have an _info dictionary.
    """

    @classmethod
    def is_valid(cls, value):
        return value in cls._info

    @classmethod
    def get_info(cls, value):
        return cls._info[value]

    @classmethod
    def get_name(cls, value):
        return cls._info[value].name


class EnumURLPath(object):
    """
    Mix-in for enum-style classes which have an _info dictionary
    containing items with an url_path attribute.
    """

    @classmethod
    def url_path(cls, value):
        path = cls._info[value].url_path
        if path is None:
            raise FormattedError('Value {} has no URL path', value)
        return path

    @classmethod
    def get_url_paths(cls):
        return [v.url_path for v in cls._info.values()
                if v.url_path is not None]

    @classmethod
    def by_url_path(cls, url_path, default=()):
        """
        Attempt to find a group by its URL path.
        """

        for (value, info) in cls._info.items():
            if url_path == info.url_path:
                return value

        if default == ():
            raise FormattedError('URL path "{}" not recognised', url_path)
        else:
            return default
