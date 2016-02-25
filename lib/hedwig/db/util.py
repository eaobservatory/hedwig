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

from functools import wraps

from ..error import NoSuchRecord


def memoized(f):
    """
    Decorator to cache database metehod results.

    Expects the cache dictionary and database object to be provided as
    the first two arguments.  The database object is then passed as the
    first argument to the decorated function.  If the cache object
    is None, no memoization is performed.
    """

    @wraps(f)
    def decorated(memo_cache, db, *args):
        memo_key = (f.__name__,) + args
        if (memo_cache is not None) and (memo_key in memo_cache):
            return memo_cache[memo_key]

        value = f(db, *args)

        if memo_cache is not None:
            memo_cache[memo_key] = value
        return value

    return decorated


def require_not_none(f):
    """
    Decorator which checks that the return value of a function is not
    none.  If it is, then NoSuchRecord is raised.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        ans = f(*args, **kwargs)
        if ans is None:
            raise NoSuchRecord('function {}(*{!r}, **{!r}) returned None',
                               f.__name__, args, kwargs)
        return ans

    return decorated_function
