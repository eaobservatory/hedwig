# Copyright (C) 2015-2019 East Asian Observatory
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


def with_can_view(obj, can_view):
    """
    Add a `can_view` field to a tuple and set it to the given value.
    """

    return namedtuple(type(obj).__name__ + 'WithCV',
                      obj._fields + ('can_view',))(*obj, can_view=can_view)


def with_can_view_edit(obj, can_view, can_edit):
    """
    Add `can_view` and `can_edit` fields to a tuple.
    """

    return namedtuple(
        type(obj).__name__ + 'WithCVE',
        obj._fields + ('can_view', 'can_edit'))(
            *obj, can_view=can_view, can_edit=can_edit)


def with_can_view_edit_rating(obj, can_view, can_edit, can_view_rating):
    """
    Add `can_view`, `can_edit` and `can_view_rating` fields to a tuple.
    """

    return namedtuple(
        type(obj).__name__ + 'WithCVER',
        obj._fields + ('can_view', 'can_edit', 'can_view_rating'))(
            *obj, can_view=can_view, can_edit=can_edit,
            can_view_rating=can_view_rating)


def with_cache(obj, cache):
    """
    Add a `cache` field to a tuple and set it to the given value.
    """

    return namedtuple(type(obj).__name__ + 'WithCache',
                      obj._fields + ('cache',))(*obj, cache=cache)


def with_deadline(obj, can_edit, deadline):
    """
    Add `can_edit` and `deadline` fields to a tuple.
    """

    return namedtuple(
        type(obj).__name__ + 'WithDeadline',
        obj._fields + ('can_edit', 'deadline',))(
            *obj, can_edit=can_edit, deadline=deadline)
