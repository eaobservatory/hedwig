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

from collections import OrderedDict, namedtuple


class SectionedList(object):
    """
    List-like class where the list can be divided into labeled sections.

    A sectioned list retains the order of its sections.  There is
    always a default section (`section = None`) which comes first
    in the ordering.

    Each section is given an idenifier (`section`) and optionally a
    name (`section_name`).  These can be set explicitly using
    :meth:`add_section` (which also establishes the section in the
    ordering) or automatically when items are added using
    :meth:`append` or :meth:`extend`.  If a section becomes empty
    it retains its position in the ordering.  However when
    removed using :meth:`delete_section` the whole section
    is forgotten, including its ordering, unless it is the default section.

    When initialized with an iterable, the items are added to the
    default section.

    .. note::
        This class includes indexing operations
        (`__delitem__`, `__getitem__` and `__setitem__`)
        but these are inefficient and provided only for
        compatibility with standard lists.
        You can gain access to the interal lists for each
        section using :meth:`by_section` and :meth:`get_section`
        which would allow more efficient operations within each section.
    """

    def __init__(self, iterable=None):
        """
        Construct new SectionedList object.

        If an iterable is provided, its entries are added to the
        default section.
        """

        default_section = []

        if iterable is not None:
            for item in iterable:
                default_section.append(item)

        self.data = OrderedDict(((None, default_section),))
        self.sections = {}

    def __delitem__(self, index):
        """
        Indexing delete operator for SectionedList objects.
        """

        (section, index) = self._find_by_index(index)

        del section[index]

    def __getitem__(self, index):
        """
        Indexing operator for SectionedList objects.
        """

        (section, index) = self._find_by_index(index)

        return section[index]

    def __iter__(self):
        """
        Iterator for SectionedList objects.

        Returns each item from each section in order.
        """

        for (section, items) in self.data.items():
            for item in items:
                yield item

    def __len__(self):
        """
        Length operator for SectionedList objects.
        """

        total = 0

        for items in self.data.values():
            total += len(items)

        return total

    def __setitem__(self, index, item):
        """
        Indexing set operator for SectionedList objects.
        """

        (section, index) = self._find_by_index(index)

        section[index] = item

    def add_section(self, section, name=None):
        """
        Add a section to the list.

        * Adds the section key to the SectionedList if it is not already
          present, so that when the list is iterated, this section comes
          next in the ordering.
        * If a name is give, adds it to the dictionary of section
          display names.

        :param section: the section identifier
        :param name: the display name for the section
        """

        if section not in self.data:
            self.data[section] = []

        if name is not None:
            self.sections[section] = name

    def append(self, item, section=None, section_name=None):
        """
        Add an item to the list.

        :param item: the item to be added
        :param section: the section in which to place the item, or
                        `None` to place it in the default section
        :param section_name: if not `None`, a display name to be added to the
                             names dictionary for the given section
        """

        section_list = self.data.get(section)

        if section_list is None:
            self.data[section] = [item]

        else:
            section_list.append(item)

        if section_name is not None:
            self.sections[section] = section_name

    def by_section(self, include_empty=False):
        """
        Iterate over the list on a section-by-section basis.

        For each section, yields a tuple `(section, section_name,
        items)` where items is the list of items for that section.

        :param include_empty: indicates whether empty sections should
                              be included

        .. warning::
            the list of items is not copied so this gives a
            direct, mutable, view of the items in the section.
        """

        for (section, items) in self.data.items():
            if items or include_empty:
                yield (section, self.sections.get(section), items)

    def delete_section(self, section):
        """
        Delete the given section from the list.

        :param section: the identifier of the section to remove

        :raise KeyError: if the given section does not exist
        """

        # Remove from the section names dictionary.
        try:
            del self.sections[section]
        except KeyError:
            pass

        # Remove the associated data.  Allow the KeyError to pass on
        # if the section didn't have a data entry.  If it's the default
        # section, don't delete it, so that it remains the first entry.
        if section is None:
            self.data[None] = []
        else:
            del self.data[section]

    def extend(self, iterable, section=None, section_name=None):
        """
        Add an iterable of items to the list.

        :param iterable: the items to be added
        :param section: the section in which to place the items, or
                        `None` to place them in the default section
        :param section_name: if not `None`, a display name to be added to the
                             names dictionary for the given section
        """

        section_list = self.data.get(section)

        if section_list is None:
            self.data[section] = list(iterable)

        else:
            for item in iterable:
                section_list.append(item)

        if section_name is not None:
            self.sections[section] = section_name

    def get_section(self, section):
        """
        Get the list of items for the given section.

        :param section: the identifier of the section to get

        :raise KeyError: if the given section does not exist

        .. warning::
            the list of items is not copied so this gives a
            direct, mutable, view of the items in the section.
        """

        if section not in self.data:
            raise KeyError('section not found: {}'.format(section))

        return self.data[section]

    def get_section_name(self, section):
        """
        Get the display name of the given section.

        :param section: the identifier of the section to get the name of

        :raise KeyError: if the given section does not exist
        """

        if section not in self.data:
            raise KeyError('section not found: {}'.format(section))

        return self.sections.get(section)

    def list_sections(self, include_empty=False):
        """
        Get a list of the sections in this list.

        :param include_empty: indicates whether empty sections should
                              be included

        :return: list of section identifiers
        """

        return [section for (section, items) in self.data.items()
                if items or include_empty]

    def _find_by_index(self, index):
        """
        Find the section and index within the section for the given
        overall list index.

        :param index: index within the entire list

        :return: `(section list, index)` tuple

        :raise IndexError: if the index is out of range
        """

        if index < 0:
            index += len(self)
            if index < 0:
                raise IndexError('SectionedList index out of range')

        for items in self.data.values():
            length = len(items)

            if index < length:
                return (items, index)

            index -= length

        raise IndexError('SectionedList index out of range')
