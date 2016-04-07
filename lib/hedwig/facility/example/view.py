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

from ..generic.view import Generic
from .calculator_example import ExampleCalculator


class Example(Generic):
    @classmethod
    def get_code(cls):
        """
        Get the "code" name used to represent this facility.
        """

        return 'example'

    @classmethod
    def get_name(cls):
        """
        Get the name of the facility.
        """

        return 'Example Facility'

    def get_calculator_classes(self):
        """
        Get a tuple of calculator classes which can be used
        with this facility.
        """

        return (ExampleCalculator,)
