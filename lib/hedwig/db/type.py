# Copyright (C) 2015-2023 East Asian Observatory
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

import json

from sqlalchemy.types import TypeDecorator, UnicodeText


class AutoEncoder(json.JSONEncoder):
    """
    JSON encoder class which will use object helper methods
    to convert them to a serializable form.
    """

    def default(self, obj):
        if hasattr(obj, 'as_dict'):
            return obj.as_dict()

        return super(AutoEncoder, self).default(obj)


# Based on the "Marshal JSON Strings" example in the SQLAlchemy manual,
# Custom Types / TypeDecorator Recipes section.
encoder = AutoEncoder(ensure_ascii=False)


class JSONEncoded(TypeDecorator):
    """
    Represents a data structure as JSON in a unicode text column.
    """

    impl = UnicodeText

    cache_ok = False

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        return encoder.encode(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        return json.loads(value)
