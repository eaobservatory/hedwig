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

from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta

try:
    from datetime import timezone as _timezone

    utc = _timezone.utc

except ImportError:
    # From example in Python 2 datetime documentation:
    from datetime import tzinfo

    _zero_offset = timedelta(seconds=0)

    class _UTC(tzinfo):
        def utcoffset(self, dt):
            return _zero_offset

        def tzname(self, dt):
            return 'UTC'

        def dst(self, dt):
            return _zero_offset

    utc = _UTC()

from astropy import units
from astropy.coordinates import AltAz, EarthLocation, concatenate
from numpy import nonzero

from ...compat import first_value
from ...error import UserError
from ...view.tool import BaseTargetTool
from ...web.util import ErrorPage


class AvailabilityTool(BaseTargetTool):
    def __init__(self, *args, **kwargs):
        super(AvailabilityTool, self).__init__(*args, **kwargs)

        # Check whether observing info required attributes are present.
        obs_info = self.facility.get_observing_info()
        if any(getattr(obs_info, x) is None for x in (
                'geo_x', 'geo_y', 'geo_z',
                'time_start', 'time_duration', 'el_min')):
            self.location = None

        else:
            self.location = EarthLocation.from_geocentric(
                obs_info.geo_x, obs_info.geo_y, obs_info.geo_z, units.m)
            self.time_start = obs_info.time_start.replace(tzinfo=utc)
            self.time_duration = obs_info.time_duration.total_seconds()
            self.el_min = obs_info.el_min * units.deg

    @classmethod
    def get_code(cls):
        """
        Get the target tool code.
        """

        return 'avail'

    def get_name(self):
        """
        Get the target tool name.
        """

        return 'Target Availability'

    def get_default_facility_code(self):
        """
        Get the code of the facility for which this target tool is
        designed.
        """

        return 'generic'

    def _view_single(self, db, target_object, args, form):
        return self._view_form_mode(
            db, (None if target_object is None else [target_object]), form)

    def _view_upload(self, db, target_objects, args, form):
        return self._view_form_mode(db, target_objects, form)

    def _view_proposal(self, db, proposal, target_objects, args, auth_cache):
        return self._view_any_mode(
            db, target_objects, proposal.semester_start, proposal.semester_end)

    def _view_form_mode(self, db, target_objects, form):
        message = None
        date_start = None
        date_end = None

        if form is None:
            try:
                # Get defaults for the date range from the facility's defined
                # semesters.  The first value should be the furthest forward.
                semester = first_value(
                    db.search_semester(facility_id=self.facility.id_))
                date_start = semester.date_start
                date_end = semester.date_end
            except IndexError:
                # If no semesters are defined, consider one year from the
                # current date.
                date_start = datetime.utcnow()
                date_end = date_start + timedelta(days=365)

            date_start_str = date_start.strftime('%Y-%m-%d')
            date_end_str = date_end.strftime('%Y-%m-%d')

        else:
            date_start_str = form['date_start']
            date_end_str = form['date_end']

            try:
                try:
                    date_start = datetime.strptime(date_start_str, '%Y-%m-%d')
                except ValueError:
                    raise UserError(
                        'Did not understand start date "{}".', date_start_str)

                try:
                    date_end = datetime.strptime(date_end_str, '%Y-%m-%d')
                except ValueError:
                    raise UserError(
                        'Did not understand end date "{}".', date_end_str)

            except UserError as e:
                message = e.message

        ctx = {
            'date_start': date_start_str,
            'date_end': date_end_str,
        }

        # Only over-write superclass message if defined.
        if message is not None:
            ctx['message'] = message

        ctx.update(self._view_any_mode(
            db, target_objects, date_start, date_end))

        return ctx

    def _view_any_mode(self, db, target_objects, date_start, date_end):
        if self.location is None:
            raise ErrorPage(
                'Observing information is not available for this facility.')

        avail_date = None
        avail_time = None
        avail_target = None
        target_hits = None
        n_max = 0
        target_max = 0

        if target_objects is not None:
            try:
                date = date_start.replace(tzinfo=utc)
                date_end = date_end.replace(tzinfo=utc)
                date_range = ((date_end - date).total_seconds()) / 86400

                # Choose a suitable date step.
                if date_range > 370:
                    raise UserError(
                        'Excessive date range.  Please select a range of '
                        'one year or less.')
                elif date_range > 190:
                    date_step = timedelta(days=28)
                elif date_range > 92:
                    date_step = timedelta(days=14)
                elif date_range > 7:
                    date_step = timedelta(days=7)
                else:
                    date_step = timedelta(days=1)

                # Choose a suitable time step.
                time_duration = self.time_duration
                if time_duration > 86400:
                    time_duration = 86400
                    time_step = 7200
                elif time_duration > 43200:
                    time_step = 7200
                else:
                    time_step = 3600

            except UserError as e:
                return {
                    'avail_date': None,
                    'message': e.message,
                }

            n = 0
            avail_date = OrderedDict()
            if len(target_objects) > 1:
                target_hits = defaultdict(int)

            targets = concatenate([x.coord.cirs for x in target_objects])

            while date <= date_end:
                dt_start = datetime.combine(date, self.time_start)
                time_obs = 0

                times = []
                result = avail_date[dt_start.strftime('%Y-%m-%d')] = []

                while time_obs <= time_duration:
                    n_target = 0
                    dt = dt_start + timedelta(seconds=time_obs)
                    frame = AltAz(location=self.location, obstime=dt)

                    (available,) = nonzero(
                        targets.transform_to(frame).alt > self.el_min)

                    for i in available:
                        n_target += 1

                        if target_hits is not None:
                            target_hits[i] += 1

                    times.append(dt.strftime('%H:%M'))
                    result.append(n_target)

                    if n_target > n_max:
                        n_max = n_target

                    n += 1
                    time_obs += time_step

                if avail_time is None:
                    avail_time = times
                else:
                    assert times == avail_time

                date = date + date_step

            if (target_hits is not None) and (n > 0):
                avail_target = OrderedDict(
                    (x.name, (100.0 * target_hits[i]) / n)
                    for (i, x) in enumerate(target_objects))

                target_max = max(avail_target.values())

        return {
            'avail_date': avail_date,
            'avail_date_max': (n_max if n_max > 0 else 1),
            'avail_time': avail_time,
            'avail_target': avail_target,
            'avail_target_max': (target_max if target_max > 0 else 1),
        }
