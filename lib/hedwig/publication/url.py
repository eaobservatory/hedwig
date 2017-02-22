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

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

from ..type.enum import PublicationType


def make_publication_url(type_, reference):
    """
    Make an URL for the given reference, if possible, or return None
    otherwise.
    """

    if type_ == PublicationType.DOI:
        return 'http://doi.org/' + quote(reference)

    elif type_ == PublicationType.ADS:
        return 'http://adsabs.harvard.edu/abs/' + quote(reference)

    elif type_ == PublicationType.ARXIV:
        return 'http://arxiv.org/abs/' + quote(reference)

    else:
        return None
