# Copyright (C) 2015-2016 East Asian Observatory
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


def null_tuple(type_):
    """
    Make a named tuple instance of the given type with all entries
    set to None.
    """

    return type_(*((None,) * len(type_._fields)))


def with_can_edit(obj, can_edit):
    """
    Add a `can_edit` field to a tuple and set it to the given value.
    """

    return namedtuple(type(obj).__name__ + 'WithCE',
                      obj._fields + ('can_edit',))(*obj, can_edit=can_edit)
