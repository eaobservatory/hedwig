# Copyright (C) 2015-2023 East Asian Observatory
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

from ...compat import url_encode
from ...type.simple import Link
from ..generic.view import Generic


class EAOFacility(Generic):
    OMP_CGI_BIN = 'https://omp.eao.hawaii.edu/cgi-bin/'

    def make_proposal_info_urls(self, proposal_code):
        """
        Generate a link to the OMP for a given proposal code.
        """

        urls = []

        try:
            urls.append(Link(
                'OMP', self.OMP_CGI_BIN + 'projecthome.pl?' +
                url_encode({
                    'project': proposal_code,
                })))

        except UnicodeEncodeError:
            pass

        return urls
