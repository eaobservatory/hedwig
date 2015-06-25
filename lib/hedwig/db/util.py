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

from functools import wraps

from ..error import NoSuchRecord


def require_not_none(f):
    """
    Decorator which checks that the return value of a function is not
    none.  If it is, then NoSuchRecord is raised.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        ans = f(*args, **kwargs)
        if ans is None:
            raise NoSuchRecord('function {0}(*{1!r}, **{2!r}) returned None',
                               f.__name__, args, kwargs)
        return ans

    return decorated_function
