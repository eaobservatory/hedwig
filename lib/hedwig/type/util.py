# Copyright (C) 2015-2026 East Asian Observatory
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

from ..compat import move_to_end
from ..error import FormattedError, MultipleValues, NoSuchValue
from .enum import SyncOperation


def compare_collections(
        original, other, match_attrs, sort_attrs,
        update_attrs=(), hide_deleted=False):
    """
    Create a comparison between two database record collections.

    This function prepares a new collection of the same type as
    the `original` collection.  The entries are annotated
    (using the `with_sync_operation` function) to include the
    type of change (unchanged, insert, update or delete)
    as a value of the `SyncOperation` enum class and a tuple of
    the updated attributes.

    Entries are intended to be usable with syncing database
    methods (i.e. those based on `_sync_records), once deleted
    entries are removed (unless `hide_deleted` is in use).
    I.e. new entries will have `None` in their `id` attribute
    and will be assigned keys following the original key values.

    :param original: original collection.
    :param other: collection for comparison.
    :param match_attrs: tuple of attributes used to match values.
        This must uniquely identify records in each collection.
    :param sort_attrs: tuple of attributes used to sort the final comparison.
    :param update_attrs: tuple of attributes to be updated.  This must include
        `hidden` if `hide_deleted` is specified.
    :param hide_deleted: if specified, mark deleted records as updated
        with the `hidden` attribute set, instead of deleting them.
    """

    # If we are using 'hide_deleted' then we need to update 'hidden' so that
    # un-hiding works.
    if hide_deleted and ('hidden' not in update_attrs):
        raise FormattedError(
            'Hide deleted specified when comparing collections but '
            'hidden not among the update attributes: {!r}.',
            update_attrs)

    # Prepare a list of (key, value) pairs from which to construct
    # a collection.
    comparison = []
    seen_values = set()

    # Check for modified or deleted entries.
    for (k, v) in original.items():
        match_key = tuple((getattr(v, attr) for attr in match_attrs))
        try:
            nv = other.get_value(
                (lambda x: all(
                    getattr(x, attr) == val
                    for (attr, val) in zip(match_attrs, match_key))))

            seen_values.add(match_key)

            # Check for modified attributes.
            modified = {}
            for attr in update_attrs:
                if getattr(v, attr) != getattr(nv, attr):
                    modified[attr] = getattr(nv, attr)

            if not modified:
                comparison.append((k, with_sync_operation(
                    v, SyncOperation.UNCHANGED)))

            else:
                comparison.append((k, with_sync_operation(
                    v._replace(**modified),
                    SyncOperation.UPDATE, tuple(modified.keys()))))

        except NoSuchValue:
            # The entry was deleted: hide it if requested (unless it is
            # already hidden).
            if hide_deleted:
                if v.hidden:
                    comparison.append((k, with_sync_operation(
                        v, SyncOperation.UNCHANGED)))

                else:
                    comparison.append((k, with_sync_operation(
                        v._replace(hidden=True),
                        SyncOperation.UPDATE, ('hidden',))))

            else:
                comparison.append((k, with_sync_operation(
                    v, SyncOperation.DELETE)))

        except MultipleValues:
            raise FormattedError(
                'Multiple matches found for key {!r} comparing collections',
                match_key)

    # Add any inserted entries.
    max_key = max(x[0] for x in comparison) if comparison else 0
    for (k, v) in other.items():
        match_key = tuple((getattr(v, attr) for attr in match_attrs))

        if match_key not in seen_values:
            max_key = max_key + 1
            comparison.append((max_key, with_sync_operation(
                v._replace(id=None), SyncOperation.INSERT)))

    # Sort to combine the inserted entries with the original ones.
    comparison.sort(key=(
        lambda entry: tuple(getattr(entry[1], attr) for attr in sort_attrs)))

    # Return as a collection of the original type.
    return type(original)(comparison)


def insert_after(dictionary, key_after, key_new, value):
    """
    Insert the given new (key, value) pair into an ordered dictionary
    after the given key.

    :param dictionary: the dictionary to modify
    :param key_after: the original key after which to insert
    :param key_new: the new key to insert
    :param value: the new value to insert

    :raises KeyError: if the dictionary already contains `key_new`
    """

    if key_new in dictionary:
        raise KeyError('key {} already present'.format(key_new))

    keys = list(dictionary.keys())

    dictionary[key_new] = value

    found = False
    for key in keys:
        if found:
            move_to_end(dictionary, key)

        elif key == key_after:
            found = True


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


def with_proposals(obj, proposal=None):
    """
    Add a `proposals` attribute to a tuple,``

    The new attribute is a list.  If a `proposal` is given then
    it is included (as the only member) in this list.
    """

    proposals = []
    if proposal is not None:
        proposals.append(proposal)

    return namedtuple(
        type(obj).__name__ + 'WithProposals',
        obj._fields + ('proposals',))(*obj, proposals=proposals)


def with_sync_operation(obj, sync_operation, sync_update=()):
    """
    Add `sync_operation` and `sync_update` fields to a tuple, setting them
    to the given values.
    """

    return namedtuple(
        type(obj).__name__ + 'WithSO',
        obj._fields + ('sync_operation', 'sync_update'))(
            *obj, sync_operation=sync_operation, sync_update=sync_update)
