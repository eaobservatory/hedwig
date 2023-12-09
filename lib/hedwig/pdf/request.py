# Copyright (C) 2021 East Asian Observatory
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

import os

from ..config import get_config
from ..error import FormattedError


def get_proposal_filename(request):
    output_dir = get_config().get('pdf_request', 'prop_dir')

    if not output_dir:
        raise FormattedError('Proposal PDF request directory not configured.')

    if not os.path.isdir(output_dir):
        raise FormattedError('Proposal PDF request directory does not exist.')

    filename = 'prop_req_{}.pdf'.format(request.id)

    return os.path.join(output_dir, filename)
