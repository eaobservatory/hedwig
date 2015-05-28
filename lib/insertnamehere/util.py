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

from collections import OrderedDict

import pycountry

countries = None


def get_countries():
    """
    Get ordered dictionary of 2-letter country codes mapping to
    country names.  This is sorted by country name.
    """

    global countries

    if countries is None:
        items = []

        for c in pycountry.countries:
            # Try to get the "common_name" if it exists, otherwise use the
            # normal "name" field.
            items.append((c.alpha2, getattr(c, 'common_name', c.name)))

        items.sort(key=lambda x: x[1])

        countries = OrderedDict(items)

    return countries
