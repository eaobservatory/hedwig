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


def label_quartiles(mapping):
    """
    Given a dictionary of some values (e.g. ratings) by some keys
    (e.g. proposal identifiers), return a new dictionary which maps
    the keys to quartile labels,

    The labels should be:
        4: upper quartile (value > Q3)
        3: upper middle quartile (value > Q2)
        2: lower middle quartile (value > Q1)
        1: lower quartile (otherwise)

    Note that we do not need to calculate precise quartile values
    since we never report these values.  We need only choose points
    at which to break the input values into four approximately equally
    sized collections.
    """

    n = len(mapping)

    if n == 0:
        return {}

    sorted_values = sorted(mapping.values())

    assert len(sorted_values) == n

    q1 = sorted_values[max(0, int(0.25 * n - 1))]
    q2 = sorted_values[max(0, int(0.50 * n - 1))]
    q3 = sorted_values[max(0, int(0.75 * n - 1))]

    labeled_mapping = {}

    for (key, value) in mapping.items():
        if value > q3:
            labeled_mapping[key] = 4
        elif value > q2:
            labeled_mapping[key] = 3
        elif value > q1:
            labeled_mapping[key] = 2
        else:
            labeled_mapping[key] = 1

    assert len(labeled_mapping) == n

    return labeled_mapping
