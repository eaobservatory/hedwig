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

from codecs import utf_8_encode
from cStringIO import StringIO
import csv


def encode_string(value):
    """
    UTF-8 encode a value if it is a string, otherwise return it as is.
    """

    if not isinstance(value, unicode):
        return value

    return utf_8_encode(value)[0]


class CSVDialect(csv.Dialect):
    """
    Define the CSV "dialect" in which we wish to write CSV files.
    """

    delimiter = b','
    doublequote = True
    lineterminator = b'\n'
    quotechar = b'"'
    quoting = csv.QUOTE_NONNUMERIC


class CSVWriter(object):
    def __init__(self):
        self._buffer = StringIO()
        self._writer = csv.writer(self._buffer, dialect=CSVDialect)

    def add_row(self, row):
        self._writer.writerow([encode_string(x) for x in row])

    def get_csv(self):
        return self._buffer.getvalue()
