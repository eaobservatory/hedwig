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

from collections import OrderedDict, namedtuple

from ...type import ResultTable
from ...error import UserError
from .meta import jcmt_request

JCMTRequest = namedtuple(
    'JCMTRequest',
    [x.name for x in jcmt_request.columns])


class JCMTInstrument(object):
    SCUBA2 = 1
    HARP = 2
    RXA3 = 3

    InstrumentInfo = namedtuple('InstrumentInfo', ('name', 'available'))

    _info = OrderedDict((
        (SCUBA2, InstrumentInfo('SCUBA-2', True)),
        (HARP,   InstrumentInfo('HARP', True)),
        (RXA3,   InstrumentInfo('RxA3', True)),
    ))

    @classmethod
    def is_valid(cls, state):
        return state in cls._info

    @classmethod
    def get_name(cls, state):
        return cls._info[state].name

    @classmethod
    def get_options(cls):
        ans = OrderedDict()

        for (k, v) in cls._info.items():
            if v.available:
                ans[k] = v.name

        return ans


class JCMTRequestCollection(OrderedDict):
    def validate(self):
        """
        Attempts to validate a collection of JCMT observing requests.

        Raises UserError is a problem is found.
        """

        requests = set()

        for record in self.values():
            if not JCMTInstrument.is_valid(record.instrument):
                raise UserError('Instrument not recognised.')

            if not JCMTWeather.is_valid(record.weather):
                raise UserError('Weather band not recognised.')

            if not isinstance(record.time, float):
                raise UserError(
                    'Please enter time as a valid number for {0}, {1}'.format(
                        JCMTInstrument.get_name(record.instrument),
                        JCMTWeather.get_name(record.weather)))

            request_tuple = (record.instrument, record.weather)

            if request_tuple in requests:
                raise UserError(
                    'There are multiple entries for {0}, {1}'.format(
                        JCMTInstrument.get_name(record.instrument),
                        JCMTWeather.get_name(record.weather)))

            requests.add(request_tuple)

    def to_table(self):
        """
        Rearrange the records into a table by instrument and weather
        band.

        Returns: ResultTable(table, weather bands, instruments)

        Where:
            * table is a nested dictionary of time by instrument and band,
              with additional "total" figures having identifier zero.  Totals
              by band (i.e. instrument=0) are only added if there is more than
              one instrument.
            * bands is an ordered dictionary of band names by identifier
              for bands present in the table and currently available bands.
            * instruments is an odered dictionary of instruments by identifier
              for instruments present in the table only.
        """

        weathers = set()
        instruments = {}
        total = {}

        for request in self.values():
            weathers.add(request.weather)

            instrument = instruments.get(request.instrument)
            if instrument is None:
                instrument = instruments[request.instrument] = {}

            # Add time to table cell.  (Really there should only be one
            # record per cell if the validation method was applied.)
            instrument[request.weather] = instrument.get(
                request.weather, 0.0) + request.time

            # Add time to instrument total.
            instrument[0] = instrument.get(0, 0.0) + request.time

            # Add time to weather total.
            total[request.weather] = total.get(
                request.weather, 0.0) + request.time

        # Include weather total if there are multiple instruments.
        if len(instruments) > 1:
            total[0] = sum(total.values())
            instruments[0] = total

        return ResultTable(
            instruments,
            OrderedDict([(k, v.name)
                         for (k, v) in JCMTWeather._info.items()
                         if v.available or k in weathers]),
            OrderedDict([(k, v.name)
                         for (k, v) in JCMTInstrument._info.items()
                         if k in instruments]))


class JCMTWeather(object):
    BAND1 = 1
    BAND2 = 2
    BAND3 = 3
    BAND4 = 4
    BAND5 = 5

    WeatherInfo = namedtuple('WeatherInfo', ('name', 'available'))

    _info = OrderedDict((
        (BAND1, WeatherInfo('Band 1', True)),
        (BAND2, WeatherInfo('Band 2', True)),
        (BAND3, WeatherInfo('Band 3', True)),
        (BAND4, WeatherInfo('Band 4', True)),
        (BAND5, WeatherInfo('Band 5', True)),
    ))

    @classmethod
    def is_valid(cls, state):
        return state in cls._info

    @classmethod
    def get_name(cls, state):
        return cls._info[state].name

    @classmethod
    def get_options(cls):
        ans = OrderedDict()

        for (k, v) in cls._info.items():
            if v.available:
                ans[k] = v.name

        return ans