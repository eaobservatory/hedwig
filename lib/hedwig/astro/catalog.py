# Copyright (C) 2015 East Asian Observatory
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

import csv

from ..error import UserError
from ..file.csv import decode_csv, decode_value
from ..type.collection import TargetCollection
from ..type.simple import Target
from ..type.util import null_tuple
from .coord import CoordSystem


def parse_source_list(source_list, number_from=1):
    """
    Parse a plain text source list and return a TargetCollection.
    """

    # Ensure the source_list CSV is in the format expected by the csv module.
    source_list = decode_csv(source_list)

    # Create case-insensitive system reverse lookup dictionary.
    systems = {
        system_name.upper(): system
        for (system, system_name) in CoordSystem.get_options().items()}

    ans = TargetCollection()

    # Remove trailing (and leading) whitespace from each line.
    # (Otherwise trailing tabs, for example, can end up in the "system"
    # field, causing it not to be recognised.)
    lines = [x.strip() for x in source_list.splitlines()]

    if not lines:
        raise UserError('The target list appears to be empty.')

    target_id = number_from

    try:
        # Sniff only one line as the sniffer gets confused by multiple
        # lines with different numbers of delimiters.  Also forbid ':' as
        # a delimiter (as it can be used in coordinates).
        dialect = csv.Sniffer().sniff(lines[0], delimiters=' \t,;')

        for target in csv.DictReader(
                lines,
                fieldnames=['name', 'x', 'y', 'system', 'time', 'priority'],
                dialect=dialect, restkey=None, restval=None):

            # Drop any trailing values and decode UTF-8.
            target = {
                k: decode_value(v)
                for (k, v) in target.items() if k is not None}

            # Extract target name and system.
            target_name = target['name']
            if target_name is None:
                raise UserError('Each target object should have a name.')

            system_name = target.pop('system')
            if system_name is None:
                raise UserError('No coordinate system given for "{}".',
                                target_name)

            system = systems.get(system_name.upper(), None)

            if system is None:
                raise UserError(
                    'Did not recognise coordinate system '
                    '"{}" for target "{}".',
                    system_name, target_name)

            # Add Target object to the collection.
            ans[target_id] = null_tuple(Target)._replace(
                id=target_id, system=system, **target)

            target_id += 1

    except csv.Error:
        raise UserError('Could not interpret target list file structure.')

    return TargetCollection.from_formatted_collection(ans)
