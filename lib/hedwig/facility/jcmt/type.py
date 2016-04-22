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

from collections import OrderedDict, namedtuple

from ...type.collection import ResultTable
from ...error import UserError
from .meta import jcmt_available, jcmt_options, jcmt_request

JCMTAvailable = namedtuple(
    'JCMTAvailable',
    [x.name for x in jcmt_available.columns])

JCMTOptions = namedtuple(
    'JCMTOptions',
    [x.name for x in jcmt_options.columns])

JCMTRequest = namedtuple(
    'JCMTRequest',
    [x.name for x in jcmt_request.columns])

JCMTRequestTotal = namedtuple(
    'JCMTRequestTotal',
    ('total', 'weather', 'instrument', 'total_non_free'))


class JCMTInstrument(object):
    SCUBA2 = 1
    HARP = 2
    RXA3 = 3
    RXA3M = 4

    InstrumentInfo = namedtuple('InstrumentInfo', ('name', 'available'))

    _info = OrderedDict((
        (SCUBA2, InstrumentInfo('SCUBA-2', True)),
        (HARP,   InstrumentInfo('HARP', True)),
        (RXA3,   InstrumentInfo('RxA3', False)),
        (RXA3M,  InstrumentInfo('RxA3m', True)),
    ))

    @classmethod
    def is_valid(cls, state):
        return state in cls._info

    @classmethod
    def get_name(cls, state):
        return cls._info[state].name

    @classmethod
    def get_info(cls, instrument):
        return cls._info[instrument]

    @classmethod
    def get_options(cls):
        ans = OrderedDict()

        for (k, v) in cls._info.items():
            if v.available:
                ans[k] = v.name

        return ans

    @classmethod
    def get_all_options(cls):
        return OrderedDict(((k, v.name) for (k, v) in cls._info.items()))


class JCMTAvailableCollection(OrderedDict):
    """
    Class used to represent a collection of time availability records.
    """

    def validate(self):
        """
        Attempts to validate a collection of JCMT time availabilities.

        Raises UserError is a problem is found.
        """

        weathers = set()

        for record in self.values():
            if not JCMTWeather.is_valid(record.weather):
                raise UserError('Weather band not recognised.')

            if not isinstance(record.time, float):
                raise UserError(
                    'Please enter time as a valid number for {0}'.format(
                        JCMTWeather.get_name(record.weather)))

            if record.weather in weathers:
                raise UserError(
                    'There are multiple entries for {0}'.format(
                        JCMTWeather.get_name(record.weather)))

            weathers.add(record.weather)

    def get_total(self):
        """
        Get total by weather band.

        Only weather bands currently labeled as "available" are included.
        Other time requested is returned with identifier zero.
        """

        weathers = {}
        total = 0.0

        for record in self.values():
            time = record.time

            weather = record.weather
            if not JCMTWeather.get_info(weather).available:
                weather = 0

            total += time
            weathers[weather] = weathers.get(weather, 0.0) + time

        return JCMTRequestTotal(total=total, weather=weathers, instrument={},
                                total_non_free=None)


class JCMTRequestCollection(OrderedDict):
    """
    Class used for collections of JCMT requests.  Also used for JCMT
    allocations (by the time allocation committee) since these have the
    same structure.
    """

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
                    'Please enter time as a valid number for {}, {}'.format(
                        JCMTInstrument.get_name(record.instrument),
                        JCMTWeather.get_name(record.weather)))

            request_tuple = (record.instrument, record.weather)

            if request_tuple in requests:
                raise UserError(
                    'There are multiple entries for {}, {}'.format(
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

    def get_total(self):
        """
        Get total by instrument and weather band.

        Only instruments and weather bands currently labeled as
        "available" are included.  Other time requested is
        returned with identifier zero.
        """

        weathers = {}
        instruments = {}
        total = 0.0
        total_non_free = 0.0

        for request in self.values():
            time = request.time

            weather = request.weather
            weather_info = JCMTWeather.get_info(weather)
            if not weather_info.available:
                weather = 0

            instrument = request.instrument
            if not JCMTInstrument.get_info(instrument).available:
                instrument = 0

            total += time
            weathers[weather] = weathers.get(weather, 0.0) + time
            instruments[instrument] = instruments.get(instrument, 0.0) + time

            if not weather_info.free:
                total_non_free += time

        return JCMTRequestTotal(total=total, weather=weathers,
                                instrument=instruments,
                                total_non_free=total_non_free)

    def to_sorted_list(self):
        """
        Get sorted list with weather/instrument as names.

        The collection is returned as a sorted list of JCMTRequest objects
        with the instrument and weather entries replaced by the names of the
        corresponding instrument and weather band.
        """

        # Get all the instrument and weather options, then iterate over them
        # looking for matching allocations -- this allows us to place the
        # allocations into a list which is correctly ordered by instrument
        # and then by weather band.
        instruments = JCMTInstrument.get_all_options()
        weathers = JCMTWeather.get_all_options()

        sorted_list = []

        for (instrument, instrument_name) in instruments.items():
            for (weather, weather_name) in weathers.items():
                for request in self.values():
                    if ((request.instrument != instrument) or
                            (request.weather != weather)):
                        continue

                    # Place the request in the sorted list and insert
                    # the instrument and weather band names.
                    sorted_list.append(request._replace(
                        instrument=instrument_name, weather=weather_name))

        return sorted_list


class JCMTWeather(object):
    BAND1 = 1
    BAND2 = 2
    BAND3 = 3
    BAND4 = 4
    BAND5 = 5

    WeatherInfo = namedtuple('WeatherInfo',
                             ('name', 'available', 'rep', 'min', 'max', 'free'))

    _info = OrderedDict((
        (BAND1, WeatherInfo('Band 1', True, 0.045, None, 0.05, False)),
        (BAND2, WeatherInfo('Band 2', True, 0.065, 0.05, 0.08, False)),
        (BAND3, WeatherInfo('Band 3', True, 0.1,   0.08, 0.12, False)),
        (BAND4, WeatherInfo('Band 4', True, 0.16,  0.12, 0.2,  False)),
        (BAND5, WeatherInfo('Band 5', True, 0.25,  0.2,  None, True)),
    ))

    @classmethod
    def is_valid(cls, state):
        return state in cls._info

    @classmethod
    def get_name(cls, state):
        return cls._info[state].name

    @classmethod
    def get_info(cls, type_):
        return cls._info[type_]

    @classmethod
    def get_available(cls):
        return OrderedDict(((k, v) for (k, v) in cls._info.items()
                            if v.available))

    @classmethod
    def get_all_options(cls):
        return OrderedDict(((k, v.name) for (k, v) in cls._info.items()))
