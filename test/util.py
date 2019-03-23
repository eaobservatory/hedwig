# Copyright (C) 2018-2019 East Asian Observatory
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

from contextlib import contextmanager
import logging


@contextmanager
def temporary_dict(dictionary, values):
    saved = dictionary.copy()
    dictionary.update(values)
    yield
    dictionary.clear()
    dictionary.update(saved)


@contextmanager
def null_log(logger_name):
    """
    Context manager which temporarily attaches a null handler to
    the specified logger.
    """

    logger = logging.getLogger(logger_name)
    handler = logging.NullHandler()
    logger.addHandler(handler)

    try:
        yield
    finally:
        logger.removeHandler(handler)
