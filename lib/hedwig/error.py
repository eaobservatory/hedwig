# Copyright (C) 2015-2021 East Asian Observatory
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

from hedwig.compat import ExceptionWithMessage, string_type


class Error(ExceptionWithMessage):
    """Base class for exceptions in this application."""

    pass


class DatabaseError(Error):
    """Base class for exceptions raised by the database."""

    def __init__(self, orig):
        """
        Construct exception using the message from an original exception,
        which itself is stored as the "orig" attribute.
        """

        Error.__init__(self, _truncate_message(string_type(orig)))
        self.orig = orig

        # For Python 2, compatability, we can't use `raise ... from None`
        # to avoid building exception context in Python 3.  Therefore set
        # this attribute to avoid generating excessively long log entries.
        self.__suppress_context__ = True


class DatabaseIntegrityError(DatabaseError):
    """Error for database integrity failures."""
    pass


class FormattedError(Error):
    """Base class for exceptions with formatted messages."""
    def __init__(self, fmt_string, *fmt_args):
        """
        Construct exception with a message generated using string
        formatting based on the given string and taking the remaining
        arguments as the formatting parameters.
        """

        Error.__init__(self, fmt_string.format(*fmt_args))


class CalculatorError(FormattedError):
    """Error class for calculator errors."""
    pass


class ConsistencyError(FormattedError):
    """Error for when the applications detects database inconsistency."""
    pass


class ConversionError(FormattedError):
    """
    Error class for file conversion errors.
    """

    pass


class NoSuchRecord(FormattedError):
    """
    Error for when an expected database record is not present.

    This should only be used when a method is given an explicit
    record primary key such that the record non-existance is
    clearly unexpected.  In a searching operation, methods should
    instead return None or an empty collection as appropriate.
    """

    pass


class NoSuchValue(FormattedError):
    """
    Error for when the given value is not recognised.
    """

    pass


class MultipleRecords(FormattedError):
    """
    Error for when the database unexpectedly returns multiple
    records when only one was expected.
    """

    pass


class ParseError(FormattedError):
    """
    Exception class for errors encountered when attempting to parse values.
    """

    pass


class UserError(FormattedError):
    """
    Exception class for errors which are presumed to result from user
    input and with a message suitable for display to the user.
    """

    pass


def _truncate_message(
        message, max_length=500, start_length=200, end_length=200):
    """
    Function to trim an error message to avoid excessively long log messages.
    """

    if len(message) <= max_length:
        return message

    return '{}...{}'.format(message[:start_length], message[-end_length:])
