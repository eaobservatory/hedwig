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

from ...error import UserError
from ...type.base import CollectionByProposal, EnumAvailable, EnumBasic
from ...type.collection import ResultCollection
from ...type.enum import BaseCallType
from .meta import ukirt_request


UKIRTRequest = namedtuple(
    'UKIRTRequest',
    [x.name for x in ukirt_request.columns])


class UKIRTRequestTotal(namedtuple(
        'UKIRTRequestTotal',
        ('total', 'instrument'))):
    pass


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


class UKIRTInstrument(EnumBasic, EnumAvailable):
    WFCAM = 1
    UFTI = 2
    UIST = 3

    InstrumentInfo = namedtuple(
        'InstrumentInfo', ('name', 'available'))

    _info = OrderedDict((
        (WFCAM, InstrumentInfo('WFCAM', True)),
        (UFTI,  InstrumentInfo('UFTI', True)),
        (UIST,  InstrumentInfo('UIST', True)),
    ))


class UKIRTRequestCollection(ResultCollection, CollectionByProposal):
    """
    Class used for collections of UKIRT observing requests.
    """

    def validate(self):
        """
        Attempt to validate a collection of observing requests.

        :raises: UserError if a problem is found.
        """

        requests = set()

        for record in self.values():
            if not UKIRTInstrument.is_valid(record.instrument):
                raise UserError('Instrument not recognised.')

            if not isinstance(record.time, float):
                raise UserError(
                    'Please enter time as a valid number for {}.'.format(
                        UKIRTInstrument.get_name(record.instrument)))

            request_tuple = (
                record.instrument,)

            if request_tuple in requests:
                raise UserError(
                    'There are multiple entries for {}.'.format(
                        UKIRTInstrument.get_name(record.instrument)))

            requests.add(request_tuple)

    def get_total(self):
        """
        Get request totals.
        """

        instruments = {}
        total = 0.0

        for request in self.values():
            time = request.time

            instrument = request.instrument
            if not UKIRTInstrument.get_info(instrument).available:
                instrument = None

            total += time
            instruments[instrument] = instruments.get(instrument, 0.0) + time

        return UKIRTRequestTotal(total=total, instrument=instruments)

    def to_sorted_list(self):
        """
        Get sorted list of requests with instrument as name.
        """

        instruments = UKIRTInstrument.get_options(include_unavailable=True)

        sorted_list = []

        for (instrument, instrument_name) in instruments.items():
            for request in self.values():
                if (request.instrument == instrument):
                    sorted_list.append(request._replace(
                        instrument=instrument_name))

        return sorted_list
