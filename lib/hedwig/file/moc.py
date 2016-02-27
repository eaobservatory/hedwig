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

from contextlib import closing
from cStringIO import StringIO

from pymoc import MOC
from pymoc.io.fits import read_moc_fits, write_moc_fits

from ..error import Error


def read_moc(file_=None, buff=None, max_order=None):
    """
    Construct a MOC object by reading the given file or buffer.

    The MOC is then normalized to the given maximum order, if given.
    """

    moc_object = MOC()

    read_opts = {'include_meta': True}

    if file_ is not None:
        read_moc_fits(moc_object, file_, **read_opts)

    elif buff is not None:
        with closing(StringIO(buff)) as f:
            read_moc_fits(moc_object, f, **read_opts)

    else:
        raise Error('Neither MOC file nor buffer given')

    if max_order is not None:
        moc_object.normalize(max_order=max_order)

    return moc_object


def write_moc(moc_object):
    """
    Write MOC to a buffer and return it.
    """

    with closing(StringIO()) as f:
        write_moc_fits(moc_object, f)
        return f.getvalue()
