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

from __future__ import \
    absolute_import, division, print_function, \
    unicode_literals

from collections import namedtuple

from ...type.base import CollectionByProposal
from ...type.collection import ResultCollection
from .meta import example_request


ExampleRequest = namedtuple(
    'ExampleRequest',
    [x.name for x in example_request.columns])


class ExampleRequestCollection(
        ResultCollection, CollectionByProposal):
    """
    Class to hold a collection of requests to use
    the Example Facility.
    """

    pass
