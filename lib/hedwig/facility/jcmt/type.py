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

from ...type.base import CollectionByProposal, EnumAvailable, EnumBasic
from ...type.enum import BaseCallType, BaseReviewerRole, BaseTextRole
from ...type.collection import ResultCollection, ResultTable
from ...error import UserError
from .meta import jcmt_available, jcmt_options, jcmt_request, jcmt_review

JCMTAvailable = namedtuple(
    'JCMTAvailable',
    [x.name for x in jcmt_available.columns])

JCMTOptions = namedtuple(
    'JCMTOptions',
    [x.name for x in jcmt_options.columns])

JCMTRequest = namedtuple(
    'JCMTRequest',
    [x.name for x in jcmt_request.columns])

JCMTReview = namedtuple(
    'JCMTReview',
    [x.name for x in jcmt_review.columns])


class JCMTRequestTotal(namedtuple(
        'JCMTRequestTotal',
        ('total', 'weather', 'instrument', 'total_non_free'))):
    @property
    def instrument_total(self):
        """
        Calculate totals by instrument, instead of by (instrument, ancillary)
        pair.
        """

        total = {}

        for (instrument, time) in self.instrument.items():
            if instrument is not None:
                (instrument, ancillary) = instrument
            total[instrument] = total.get(instrument, 0.0) + time

        return total

    @property
    def instrument_grouped(self):
        """
        Group instrument values by instrument.  I.e. instead of a dictionary
        by (instrument, ancillary) returns a dictionary (by instrument)
        of sub-dictionaries by ancillary.  The sub-dictionary for the unknown
        instrument (if present) just contains an entry for
        ancillary `JCMTAncillary.NONE`.
        """

        group = {}

        for (instrument, time) in self.instrument.items():
            if instrument is None:
                ancillary = JCMTAncillary.NONE
            else:
                (instrument, ancillary) = instrument

            record = group.get(instrument, None)
            if record is None:
                group[instrument] = {ancillary: time}
            else:
                record[ancillary] = record.get(ancillary, 0.0) + time

        return group


class JCMTAncillary(EnumBasic, EnumAvailable):
    NONE = 0  # Must be non-null in database for constraints to apply.
    ROVER = 1
    POL2 = 2
    FTS2 = 3

    AncillaryInfo = namedtuple('AncillaryInfo', ('name', 'available'))

    _info = OrderedDict((
        (ROVER, AncillaryInfo('Rover', False)),
        (POL2,  AncillaryInfo('POL-2', True)),
        (FTS2,  AncillaryInfo('FTS-2', False)),
    ))


class JCMTCallType(BaseCallType):
    """
    Class providing information about JCMT call types.
    """

    _jcmt_info = {
        BaseCallType.STANDARD: {
            'name': 'Regular', 'code': 'M', 'url_path': 'regular'},
        BaseCallType.IMMEDIATE: {
            'name': 'Urgent', 'code': 'S', 'url_path': 'urgent',
            'name_proposal': True},
    }

    _info = OrderedDict()
    for (role_id, role_info) in BaseCallType._info.items():
        override = _jcmt_info.get(role_id, {})
        _info[role_id] = BaseCallType.TypeInfo(
            *(role_info._replace(**override)))


class JCMTInstrument(EnumBasic, EnumAvailable):
    SCUBA2 = 1
    HARP = 2
    RXA3 = 3
    RXA3M = 4

    InstrumentInfo = namedtuple(
        'InstrumentInfo', ('name', 'available', 'ancillary'))

    _info = OrderedDict((
        (SCUBA2, InstrumentInfo('SCUBA-2', True,  (JCMTAncillary.POL2,
                                                   JCMTAncillary.FTS2))),
        (HARP,   InstrumentInfo('HARP',    True,  (JCMTAncillary.ROVER,))),
        (RXA3,   InstrumentInfo('RxA3',    False, (JCMTAncillary.ROVER,))),
        (RXA3M,  InstrumentInfo('RxA3m',   True,  (JCMTAncillary.ROVER,))),
    ))

    @classmethod
    def get_ancillary(cls, instrument):
        return cls._info[instrument].ancillary

    @classmethod
    def get_name_with_ancillary(cls, instrument, ancillary):
        name = cls.get_name(instrument)
        if ancillary != JCMTAncillary.NONE:
            name = '{} + {}'.format(name, JCMTAncillary.get_name(ancillary))
        return name

    @classmethod
    def get_options_with_ancillary(cls, include_unavailable=False):
        result = OrderedDict()

        for (instrument, instrument_info) in cls._info.items():
            if not (include_unavailable or instrument_info.available):
                continue
            result[(instrument, JCMTAncillary.NONE)] = instrument_info.name

            for ancillary in instrument_info.ancillary:
                ancillary_info = JCMTAncillary.get_info(ancillary)
                if not (include_unavailable or ancillary_info.available):
                    continue

                result[(instrument, ancillary)] = '{} + {}'.format(
                    instrument_info.name, ancillary_info.name)

        return result

    @classmethod
    def has_available_ancillary(cls, instrument, ancillary):
        return ((ancillary == JCMTAncillary.NONE)
                or ((ancillary in cls._info[instrument].ancillary)
                    and JCMTAncillary.is_available(ancillary)))


class JCMTAvailableCollection(ResultCollection):
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
        total_non_free = 0.0

        for record in self.values():
            time = record.time

            weather = record.weather
            weather_info = JCMTWeather.get_info(weather)
            if not weather_info.available:
                weather = 0

            total += time
            weathers[weather] = weathers.get(weather, 0.0) + time

            if not weather_info.free:
                total_non_free += time

        return JCMTRequestTotal(total=total, weather=weathers, instrument={},
                                total_non_free=total_non_free)


class JCMTOptionsCollection(ResultCollection, CollectionByProposal):
    """
    Class to hold results of a search for JCMT options.
    """

    pass


class JCMTOptionValue(EnumAvailable):
    OptionInfo = namedtuple('OptionInfo', ('name', 'available'))

    _info = OrderedDict((
        ('target_of_opp', OptionInfo('Target of opportunity', True)),
        ('daytime',       OptionInfo('Daytime observation', True)),
        ('time_specific', OptionInfo('Time-specific observation', True)),
        ('polarimetry',   OptionInfo('Polarimetry', False)),
    ))


class JCMTRequestCollection(ResultCollection, CollectionByProposal):
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

            if record.ancillary == JCMTAncillary.NONE:
                pass
            else:
                if not JCMTAncillary.is_valid(record.ancillary):
                    raise UserError('Ancillary instrument not recognised.')

                if (record.ancillary not in
                        JCMTInstrument.get_ancillary(record.instrument)):
                    raise UserError(
                        'Ancillary not permitted for this instrument.')

            if not JCMTWeather.is_valid(record.weather):
                raise UserError('Weather band not recognised.')

            if not isinstance(record.time, float):
                raise UserError(
                    'Please enter time as a valid number for {}, {}'.format(
                        JCMTInstrument.get_name(record.instrument),
                        JCMTWeather.get_name(record.weather)))

            request_tuple = (
                record.instrument, record.ancillary, record.weather)

            if request_tuple in requests:
                raise UserError(
                    'There are multiple entries for {}, {}'.format(
                        JCMTInstrument.get_name_with_ancillary(
                            record.instrument, record.ancillary),
                        JCMTWeather.get_name(record.weather)))

            requests.add(request_tuple)

    def to_table(self):
        """
        Rearrange the records into a table by instrument and weather
        band.

        Returns: ResultTable(table, weather bands, instruments)

        Where:
            * table is a nested dictionary of time by instrument and band,
              with additional "total" figures having identifier `None`.
              Totals by band (i.e. `instrument=None`) are only added if there
              is more than one instrument.  Instruments are identified by a
              (instrument, ancillary) pair.
            * bands is an ordered dictionary of band names by identifier
              for bands present in the table and currently available bands.
            * instruments is an ordered dictionary of instruments by identifier
              for instruments present in the table only.
        """

        weathers = set()
        instruments = {}
        total = {}

        for request in self.values():
            weathers.add(request.weather)

            # Organize by instrument including ancillary.
            instrument_key = (request.instrument, request.ancillary)

            instrument = instruments.get(instrument_key)
            if instrument is None:
                instrument = instruments[instrument_key] = {}

            # Add time to table cell.  (Really there should only be one
            # record per cell if the validation method was applied.)
            instrument[request.weather] = instrument.get(
                request.weather, 0.0) + request.time

            # Add time to instrument total.
            instrument[None] = instrument.get(None, 0.0) + request.time

            # Add time to weather total.
            total[request.weather] = total.get(
                request.weather, 0.0) + request.time

        # Include weather total if there are multiple instruments.
        if len(instruments) > 1:
            total[None] = sum(total.values())
            instruments[None] = total

        instrument_names = \
            JCMTInstrument.get_options_with_ancillary(include_unavailable=True)

        return ResultTable(
            instruments,
            OrderedDict([(k, v.name)
                         for (k, v) in JCMTWeather._info.items()
                         if v.available or k in weathers]),
            OrderedDict([(k, v)
                         for (k, v) in instrument_names.items()
                         if k in instruments]))

    def get_total(self):
        """
        Get total by instrument and weather band.

        Only instruments and weather bands currently labeled as
        "available" are included.  Other time requested is
        returned with identifier None.

        Instruments are identified by a (instrument, ancillary) pair.
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
                weather = None

            instrument = request.instrument
            ancillary = request.ancillary
            if (JCMTInstrument.get_info(instrument).available
                    and JCMTInstrument.has_available_ancillary(instrument,
                                                               ancillary)):
                instrument = (instrument, ancillary)
            else:
                instrument = None

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
        corresponding instrument (including ancillary) and weather band.
        """

        # Get all the instrument and weather options, then iterate over them
        # looking for matching allocations -- this allows us to place the
        # allocations into a list which is correctly ordered by instrument
        # and then by weather band.
        instruments = JCMTInstrument.get_options_with_ancillary(
            include_unavailable=True)
        weathers = JCMTWeather.get_options(include_unavailable=True)

        sorted_list = []

        for (instrument_ancillary, instrument_name) in instruments.items():
            (instrument, ancillary) = instrument_ancillary
            for (weather, weather_name) in weathers.items():
                for request in self.values():
                    if ((request.instrument != instrument) or
                            (request.ancillary != ancillary) or
                            (request.weather != weather)):
                        continue

                    # Place the request in the sorted list and insert
                    # the instrument and weather band names.
                    sorted_list.append(request._replace(
                        instrument=instrument_name, ancillary=None,
                        weather=weather_name))

        return sorted_list


class JCMTReviewerExpertise(EnumBasic, EnumAvailable):
    """
    Class representing reviewer expertise levels.
    """

    NON_EXPERT = 1
    INTERMEDIATE = 2
    EXPERT = 3

    ExpertiseInfo = namedtuple(
        'ExpertiseInfo', ('name', 'weight', 'available'))

    #                                Name            Wt.  Avail
    _info = OrderedDict((
        (NON_EXPERT,   ExpertiseInfo('Non-expert',   50,  True)),
        (INTERMEDIATE, ExpertiseInfo('Intermediate', 75,  True)),
        (EXPERT,       ExpertiseInfo('Expert',       100, True)),
    ))

    @classmethod
    def get_weight(cls, expertise):
        return cls._info[expertise].weight


class JCMTReviewerRole(BaseReviewerRole):
    """
    Class providing information about reviewer roles for JCMT.
    """

    RoleInfo = namedtuple(
        'RoleInfo', BaseReviewerRole.RoleInfo._fields + (
            'jcmt_expertise', 'jcmt_external'))

    _jcmt_default_info = (False, False)

    # Define JCMT-specific role information.
    #        Exp.   Ext.Q.
    _jcmt_info = {
        BaseReviewerRole.EXTERNAL: (
            (False, True),
            {}),
        BaseReviewerRole.CTTEE_PRIMARY: (
            (True, False),
            {'name': 'TAC Primary', 'weight': False}),
        BaseReviewerRole.CTTEE_SECONDARY: (
            (True, False),
            {'name': 'TAC Secondary', 'unique': True, 'weight': False}),
        BaseReviewerRole.CTTEE_OTHER: (
            (True, False),
            {'name': 'Rating', 'name_review': False, 'url_path': 'rating',
             'weight': False}),
    }

    # Merge with base role information.
    _info = OrderedDict()
    for role_id, role_info in BaseReviewerRole._info.items():
        (extra, override) = _jcmt_info.get(role_id, (_jcmt_default_info, {}))
        _info[role_id] = RoleInfo(*(role_info._replace(**override) + extra))


class JCMTReviewRatingJustification(EnumBasic, EnumAvailable):
    RatingInfo = namedtuple('RatingInfo', ('name', 'available'))

    _info = OrderedDict((
        (1, RatingInfo('Extremely thorough and compelling', True)),
        (2, RatingInfo('Convincing and well described', True)),
        (3, RatingInfo('Adequate, with minor problems', True)),
        (4, RatingInfo('Inadequate (too brief, confusing, incomplete '
                       'or incorrect)', True)),
    ))


class JCMTReviewRatingTechnical(EnumBasic, EnumAvailable):
    RatingInfo = namedtuple('RatingInfo', ('name', 'available'))

    _info = OrderedDict((
        (1, RatingInfo('Thorough and clearly understood', True)),
        (2, RatingInfo('Correct and well described', True)),
        (3, RatingInfo('Adequate, with minor problems', True)),
        (4, RatingInfo('Inadequately described or poorly understood', True)),
    ))


class JCMTReviewRatingUrgency(EnumBasic, EnumAvailable):
    RatingInfo = namedtuple('RatingInfo', ('name', 'available'))

    _info = OrderedDict((
        (1, RatingInfo('Timely and competitive: must be done now', True)),
        (2, RatingInfo('Should be done now', True)),
        (3, RatingInfo('Urgency is not a major consideration', True)),
    ))


class JCMTTextRole(BaseTextRole):
    """
    Class providing information about proposal text roles for JCMT.
    """

    PR_SUMMARY = 101

    RoleInfo = BaseTextRole.RoleInfo

    #                Name                        Short   Path
    _info = BaseTextRole._info.copy()
    _info.update({
        PR_SUMMARY:
            RoleInfo('Public Summary',           'pr',   None),
    })


class JCMTWeather(EnumBasic, EnumAvailable):
    BAND1 = 1
    BAND2 = 2
    BAND3 = 3
    BAND4 = 4
    BAND5 = 5

    WeatherInfo = namedtuple(
        'WeatherInfo',
        ('name', 'available', 'rep', 'min', 'max', 'free'))

    _info = OrderedDict((
        (BAND1, WeatherInfo('Band 1', True, 0.045, None, 0.05, False)),
        (BAND2, WeatherInfo('Band 2', True, 0.065, 0.05, 0.08, False)),
        (BAND3, WeatherInfo('Band 3', True, 0.1,   0.08, 0.12, False)),
        (BAND4, WeatherInfo('Band 4', True, 0.16,  0.12, 0.2,  False)),
        (BAND5, WeatherInfo('Band 5', True, 0.25,  0.2,  None, True)),
    ))

    @classmethod
    def get_available(cls):
        return OrderedDict(((k, v) for (k, v) in cls._info.items()
                            if v.available))
