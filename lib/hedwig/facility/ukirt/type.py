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
from ...type.collection import ResultCollection, ResultTable
from ...type.enum import BaseCallType
from .meta import ukirt_request


UKIRTRequest = namedtuple(
    'UKIRTRequest',
    [x.name for x in ukirt_request.columns])


class UKIRTBrightness(EnumBasic, EnumAvailable):
    DARK = 1
    GREY = 2
    BRIGHT = 3

    BrightnessInfo = namedtuple(
        'BrightnessInfo',
        ('name', 'available'))

    _info = OrderedDict((
        (DARK,   BrightnessInfo('Dark',   True)),
        (GREY,   BrightnessInfo('Grey',   True)),
        (BRIGHT, BrightnessInfo('Bright', True)),
    ))


class UKIRTRequestTotal(namedtuple(
        'UKIRTRequestTotal',
        ('total', 'brightness', 'instrument'))):
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
        BaseCallType.TEST: {
            'code': 'TEST'},
        BaseCallType.MULTICLOSE: {
            'name': 'Rapid Turnaround', 'code': 'RT', 'url_path': 'rapid',
            'name_proposal': True},
    }

    _info = OrderedDict()
    for (role_id, role_info) in BaseCallType._info.items():
        override = _ukirt_info.get(role_id, {})
        _info[role_id] = BaseCallType.TypeInfo(
            *(role_info._replace(**override)))


class UKIRTInstrument(EnumBasic, EnumAvailable):
    WFCAM = 1
    CGS4 = 2
    MICHELLE = 3
    UFTI = 4
    UIST = 5

    InstrumentInfo = namedtuple(
        'InstrumentInfo', ('name', 'available'))

    _info = OrderedDict((
        (WFCAM,    InstrumentInfo('WFCAM', True)),
        (CGS4,     InstrumentInfo('CGS4', True)),
        (MICHELLE, InstrumentInfo('Michelle', True)),
        (UFTI,     InstrumentInfo('UFTI', True)),
        (UIST,     InstrumentInfo('UIST', True)),
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

            if not UKIRTBrightness.is_valid(record.brightness):
                raise UserError('Brightness not recognized.')

            if not isinstance(record.time, float):
                raise UserError(
                    'Please enter time as a valid number for {}.'.format(
                        UKIRTInstrument.get_name(record.instrument)))

            request_tuple = (
                record.instrument, record.brightness)

            if request_tuple in requests:
                raise UserError(
                    'There are multiple entries for {}, {}.'.format(
                        UKIRTInstrument.get_name(record.instrument),
                        UKIRTBrightness.get_name(record.brightness)))

            requests.add(request_tuple)

    def to_table(self):
        """
        Rearrange the records into a table by instrument and brightness.

        Returns: ResultTable(table, brightness values, instruments)
        """

        brightnesses = set()
        instruments = {}
        total = {}

        for request in self.values():
            brightnesses.add(request.brightness)

            instrument = instruments.get(request.instrument)
            if instrument is None:
                instrument = instruments[request.instrument] = {}

            instrument[request.brightness] = instrument.get(
                request.brightness, 0.0) + request.time

            instrument[None] = instrument.get(
                None, 0.0) + request.time

            total[request.brightness] = total.get(
                request.brightness, 0.0) + request.time

        # Include weather total if there are multiple instruments.
        if len(instruments) > 1:
            total[None] = sum(total.values())
            instruments[None] = total

        return ResultTable(
            instruments,
            OrderedDict([(k, v.name)
                         for (k, v) in UKIRTBrightness._info.items()
                         if v.available or k in brightnesses]),
            OrderedDict([(k, v.name)
                         for (k, v) in UKIRTInstrument._info.items()
                         if k in instruments]))

    def get_total(self):
        """
        Get request totals.
        """

        brightnesses = {}
        instruments = {}
        total = 0.0

        for request in self.values():
            time = request.time

            brightness = request.brightness
            brightness_info = UKIRTBrightness.get_info(brightness)
            if not brightness_info.available:
                brightness = None

            instrument = request.instrument
            if not UKIRTInstrument.get_info(instrument).available:
                instrument = None

            total += time
            brightnesses[brightness] = brightnesses.get(brightness, 0.0) + time
            instruments[instrument] = instruments.get(instrument, 0.0) + time

        return UKIRTRequestTotal(
            total=total, brightness=brightnesses, instrument=instruments)

    def to_sorted_list(self):
        """
        Get sorted list of requests with brightness/instrument as name.
        """

        instruments = UKIRTInstrument.get_options(include_unavailable=True)
        brightnesses = UKIRTBrightness.get_options(include_unavailable=True)

        # TODO iterate over brightness!

        sorted_list = []

        for (instrument, instrument_name) in instruments.items():
            for (brightness, brightness_name) in brightnesses.items():
                for request in self.values():
                    if ((request.instrument == instrument)
                            and (request.brightness == brightness)):
                        sorted_list.append(request._replace(
                            instrument=instrument_name,
                            brightness=brightness_name))

        return sorted_list
