# Copyright (C) 2017 East Asian Observatory
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

from collections import OrderedDict, namedtuple

from ...type.enum import BaseCallType


class UKIRTCallType(BaseCallType):
    """
    Class providing information about JCMT call types.
    """

    _ukirt_info = {
        BaseCallType.STANDARD: {
            'name': 'Regular', 'code': None, 'url_path': 'regular'},
        BaseCallType.IMMEDIATE: {
            'name': 'Urgent', 'code': 'SERV', 'url_path': 'urgent',
            'name_proposal': True},
    }

    _info = OrderedDict()
    for (role_id, role_info) in BaseCallType._info.items():
        override = _ukirt_info.get(role_id, {})
        _info[role_id] = BaseCallType.TypeInfo(
            *(role_info._replace(**override)))
