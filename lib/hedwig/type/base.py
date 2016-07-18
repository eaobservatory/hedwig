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

from collections import OrderedDict

from ..error import FormattedError, NoSuchValue


class CollectionByProposal(object):
    """
    Mix-in for collections of items with a `proposal_id` attribute.
    """

    def get_proposal(self, proposal_id, default=()):
        """
        Retrieve the (first found) entry for the given proposal.
        """

        for item in self.values():
            if item.proposal_id == proposal_id:
                return item

        if default == ():
            raise KeyError('no entry for proposal {}'.format(proposal_id))

        return default

    def subset_by_proposal(self, proposal_id):
        """
        Create a subset of the collection (of the same type) containing
        the entries which match the given proposal.
        """

        return type(self)((k, v) for (k, v) in self.items()
                          if v.proposal_id == proposal_id)


class CollectionOrdered(object):
    """
    Mix-in for collections with a `sort_order` attribute.
    """

    def ensure_sort_order(self):
        """
        Ensure all records have a non-`None` `sort_order` entry.

        Iterates through the entries in this collection finding the maximum
        sort_order used and all the entries without a sort order.  Then those
        entries are assigned `sort_order` values above the previous maximum
        in the order in which they appear in the collection.
        """

        i = 0
        unordered = []

        for (key, value) in self.items():
            if value.sort_order is None:
                unordered.append(key)
            elif value.sort_order > i:
                i = value.sort_order

        for key in unordered:
            i += 1
            self[key] = self[key]._replace(sort_order=i)


class EnumAvailable(object):
    """
    Mix-in for enum-style classes where the `_info` dictionary
    has names and an `available` boolean field.
    """

    @classmethod
    def get_options(cls, include_unavailable=False):
        return OrderedDict(((k, v.name) for (k, v) in cls._info.items()
                            if (v.available or include_unavailable)))

    @classmethod
    def is_available(cls, value):
        return cls._info[value].available


class EnumBasic(object):
    """
    Mix-in for enum-style classes which have an `_info` dictionary.
    """

    @classmethod
    def is_valid(cls, value):
        """
        Determine whether an enum value is valid.

        It is assumed that the value is valid if appears in the `_info`
        dictionary.
        """

        return value in cls._info

    @classmethod
    def get_info(cls, value):
        """
        Return the entry in the `_info` dictionary for a given value.
        """

        return cls._info[value]

    @classmethod
    def get_name(cls, value):
        """
        Get the name for an entry.

        This is given by the name attribute of the value's entry in the
        `_info` dictionary.
        """

        return cls._info[value].name


class EnumDisplayClass(object):
    """
    Mix-in for enum-style classes with an `_info` dictionary
    including a `display_class` attribute.
    """

    @classmethod
    def get_display_class(cls, value):
        """Get a CSS class which can be used to display a given value."""

        return cls._info[value].display_class


class EnumURLPath(object):
    """
    Mix-in for enum-style classes which have an `_info` dictionary
    containing items with an `url_path` attribute.
    """

    @classmethod
    def url_path(cls, value):
        """
        Returns the URL path for a value.

        If the URL path for the given value is `None`, an exception
        is raised.
        """

        path = cls._info[value].url_path
        if path is None:
            raise FormattedError('Value {} has no URL path', value)
        return path

    @classmethod
    def get_url_paths(cls):
        """
        Return a list of possible URL paths.

        This creates a list of all of the paths which are not `None`.
        """

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
            raise NoSuchValue('URL path "{}" not recognised', url_path)
        else:
            return default
