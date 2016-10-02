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

from codecs import utf_8_encode, utf_8_decode
import csv

from ..compat import python_version, unicode_to_str, string_type


if python_version < 3:
    # Python 2: cvs module uses bytes strings.
    from io import BytesIO as CSVIO

    def encode_string(value):
        """
        UTF-8 encode a value if it is a string, otherwise return it as is.
        """

        if not isinstance(value, string_type):
            return value

        return utf_8_encode(value)[0]

    def encode_csv(value):
        return value

    def decode_csv(value):
        return value

    def decode_value(value):
        """
        UTF-8 decode a value extracted from a CSV file.
        """

        if value is None:
            return None

        return utf_8_decode(value, 'replace')[0]

else:
    # Python 3: cvs module works in terms of unicode strings.
    from io import StringIO as CSVIO

    def encode_string(value):
        return value

    def encode_csv(value):
        """
        UTF-8 encode whole CSV file.
        """

        return utf_8_encode(value)[0]

    def decode_csv(value):
        """
        UTF-8 decode whole CSV file.
        """

        return utf_8_decode(value, 'replace')[0]

    def decode_value(value):
        return value


class CSVDialect(csv.Dialect):
    """
    Define the CSV "dialect" in which we wish to write CSV files.
    """

    delimiter = unicode_to_str(',')
    doublequote = True
    lineterminator = unicode_to_str('\n')
    quotechar = unicode_to_str('"')
    quoting = csv.QUOTE_NONNUMERIC


class CSVWriter(object):
    """
    CSV writing utility class.

    This class sets up a CSV writer (using the standard library `csv` module)
    which writes to a `StringIO` or `BytesIO` (depending on Python version)
    buffer.
    """

    def __init__(self):
        self._buffer = CSVIO()
        self._writer = csv.writer(self._buffer, dialect=CSVDialect)

    def add_row(self, row):
        """
        Add a row to the CSV file.
        """

        self._writer.writerow([encode_string(x) for x in row])

    def get_csv(self):
        """
        Return the contents of the buffer.
        """

        return encode_csv(self._buffer.getvalue())
