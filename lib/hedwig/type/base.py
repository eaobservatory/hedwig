# Copyright (C) 2016-2019 East Asian Observatory
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

from collections import OrderedDict, defaultdict
from operator import attrgetter

from ..error import FormattedError, NoSuchValue


class CollectionByCall(object):
    """
    Mix-in for collections of items with a `call_id` attribute.
    """

    def subset_by_call(self, call_id):
        """
        Create a subset containing entries for the given call.
        """

        return type(self)((k, v) for (k, v) in self.items()
                          if v.call_id == call_id)


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
            raise NoSuchValue('no entry for proposal {}'.format(proposal_id))

        return default

    def subset_by_proposal(self, proposal_id):
        """
        Create a subset of the collection (of the same type) containing
        the entries which match the given proposal.
        """

        return type(self)((k, v) for (k, v) in self.items()
                          if v.proposal_id == proposal_id)


class CollectionByReviewerRole(object):
    """
    Mix-in for collections of items with a reviewer `role` attribute.
    """

    def has_role(self, role):
        """
        Check if the collection has an entry in the given role.
        """

        for entry in self.values():
            if entry.role == role:
                return True

        return False

    def values_by_role(self, role):
        """
        Get a list of the reviewers with the given role.
        """

        return [x for x in self.values() if x.role == role]

    def values_in_role_order(self, role_class, cttee_role=None):
        """
        Iterate over the values of the collection in the order of
        the reviewer roles.

        Optionally return only committee roles (`cttee_role` = `True`) or
        non-committee roles (`cttee_role` = `False`).

        Note: operates by looping over known roles.  Any reviewers with
        invalid (or no longer recognized) roles will not be yielded.
        """

        cttee_roles = None
        if cttee_role is not None:
            cttee_roles = role_class.get_cttee_roles()

        for role in role_class.get_options().keys():
            if cttee_role is not None:
                if ((cttee_role and (role not in cttee_roles)) or
                        ((not cttee_role) and (role in cttee_roles))):
                    continue

            for entry in self.values():
                if entry.role == role:
                    yield entry


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

    def values_in_sorted_order(self):
        """
        Return values ordered by the `sort_order` attribute.

        Normally we would already have sorted the collection in this order
        when constructing it.  So this method is intended to be used
        while editing a collection which may have some incomplete information
        in it.

        Entries with a `sort_order` attribute of `None` should be
        returned last.
        """

        ans = list(self.values())

        ans.sort(key=lambda x: (x.sort_order is None, x.sort_order))

        return ans


class CollectionSortable(object):
    """
    Mix-in for collections with a `sort_attr` class attribute.

    The `sort_attr` should be a sequence of `(reverse, tuple)`
    pairs where `reverse` indicates whether the sort should be
    reversed and `tuple` is a tuple containing attribute names.
    Sorting parameters are specified in top-down order, both
    in the attributes tuples and in the sequence as a whole.
    """

    def values_in_sorted_order(self):
        """
        Return values in a suitably sorted order.

        This operates by placing the values in a list and applying each sort
        operation specified by `sort_attr` in reverse order.
        """

        ans = list(self.values())

        for (reverse, attrs) in reversed(self.sort_attr):
            ans.sort(key=attrgetter(*attrs), reverse=reverse)

        return ans


class EnumAllowUser(object):
    """
    Mix-in for enum-style classes where the `_info` dictionary
    has names and an `allow_user` boolean field.

    .. note::
        If combined with `EnumBasic`, this mix-in should be listed first
        in the order of base classes so that its `is_valid` method
        overrides that from `EnumBasic`.
    """

    @classmethod
    def is_valid(cls, value, is_system=False):
        """
        Determines whether the given value is allowed.

        By default only allows values for which `allow_user` is enabled.
        However with the `is_system` flag, allows any value.
        """

        value_info = cls._info.get(value, None)

        if value_info is None:
            return False

        return is_system or value_info.allow_user

    @classmethod
    def get_options(cls, is_system=False):
        """
        Get an OrderedDict of names by value.

        By default only returns values for which `allow_user` is enabled.
        However with the `is_system` flag, all values are returned.
        """

        return OrderedDict(((k, v.name) for (k, v) in cls._info.items()
                            if is_system or v.allow_user))


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


class EnumCode(object):
    """
    Mix-in for enum-style classes with an `_info` dictionary including a
    `code` attribute.
    """

    @classmethod
    def get_code(cls, value):
        """
        Get the code for an entry.
        """

        return cls._info[value].code

    @classmethod
    def by_code(cls, code):
        """
        Attempt to find a value by its code.
        """

        for (value, info) in cls._info.items():
            if info.code == code:
                return value

        if code is None:
            raise NoSuchValue('Null code not recognised')

        raise NoSuchValue('Code "{}" not recognised', code)


class EnumDisplayClass(object):
    """
    Mix-in for enum-style classes with an `_info` dictionary
    including a `display_class` attribute.
    """

    @classmethod
    def get_display_class(cls, value):
        """Get a CSS class which can be used to display a given value."""

        return cls._info[value].display_class


class EnumShortName(object):
    """
    Mix-in for enum-style classes with an `_info` dictionary
    including a `short_name` attribute.
    """

    @classmethod
    def get_short_name(cls, value):
        """Get the abbreviated name for a value."""

        return cls._info[value].short_name


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
