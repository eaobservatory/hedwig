# Copyright (C) 2015-2025 East Asian Observatory
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

from ..compat import url_quote
from ..type.enum import PublicationType


def make_publication_url(type_, reference):
    """
    Make an URL for the given reference, if possible, or return None
    otherwise.
    """

    try:
        if type_ == PublicationType.DOI:
            return 'https://doi.org/' + url_quote(reference)

        elif type_ == PublicationType.ADS:
            return 'https://adsabs.harvard.edu/abs/' + url_quote(reference)

        elif type_ == PublicationType.ARXIV:
            return 'https://arxiv.org/abs/' + url_quote(reference)

        elif type_ == PublicationType.ATEL:
            return 'https://www.astronomerstelegram.org/?read=' + url_quote(reference)

    except:
        # `url_quote` could possibly raise UnicodeEncodeError.  In this case
        # return None as we can't generate an URL.
        pass

    return None
