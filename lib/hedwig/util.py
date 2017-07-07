# Copyright (C) 2015-2016 East Asian Observatory
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

import logging


class FormattedLogger(object):
    """
    Logger wrapper, similar to logging.LoggerAdapter, which uses string
    formatting.
    """

    def __init__(self, logger):
        self.logger = logger

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg.format(*args), **kwargs)

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg.format(*args), **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg.format(*args), **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg.format(*args), **kwargs)

    def exception(self, msg, *args, **kwargs):
        self.logger.exception(msg.format(*args), **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.logger.critical(msg.format(*args), **kwargs)

    def log(self, level, msg, *args, **kwargs):
        self.logger.log(level, msg.format(*args), **kwargs)


def get_logger(name):
    """
    Get a "FormattedLogger" instance which uses string formatting.
    """

    return FormattedLogger(logging.getLogger(name))


def is_list_like(value):
    """
    Returns true if the value is a list-like object such as a list or a tuple.

    Currently just returns true if it is a list or tuple or set.
    """

    return (isinstance(value, list)
            or isinstance(value, tuple)
            or isinstance(value, set)
            or isinstance(value, frozenset))


def list_in_blocks(iterable, block_size):
    """
    Given an iterable object (e.g. a list) yield a sequence of lists
    each containing up to block_size items.
    """

    block = []

    for value in iterable:
        block.append(value)

        if len(block) >= block_size:
            yield block

            # Assign a new list rather than clearing in case the caller
            # keeps a reference to a previously yielded list.
            block = []

    if block:
        yield block


def matches_constraint(value, constraint):
    """
    Check whether a value matches a constraint.

    * If the constraint is None, returns True.
    * If the constraint appears like-like, return True if the value
      is in it.
    * Otherwise return True if the value is equal to the constraint.
    """

    if constraint is None:
        return True

    if is_list_like(constraint):
        return (value in constraint)

    return (value == constraint)
