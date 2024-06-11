# Copyright (C) 2017-2022 East Asian Observatory
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
import warnings

from astropy import units
from astropy.coordinates import AltAz, ICRS, SkyCoord
from astropy.time import Time
from astropy.utils.exceptions import AstropyWarning
from numpy import arange, newaxis, nonzero

from ...astro.coord import concatenate_coord_objects, get_earth_location
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
            self.location = get_earth_location(obs_info)
            self.time_start = obs_info.time_start
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

    def _view_proposal(
            self, current_user, db, proposal, target_objects,
            extra_info, args, auth_cache):
        # Overwrite the "extra_info" with the semester start and end dates.
        # If the proposal is for a multi-semester call, use one year from the
        # semester start instead.
        return self._view_any_mode(
            current_user, db, target_objects,
            [proposal.semester_start,
             ((proposal.semester_start + timedelta(days=365))
              if proposal.multi_semester else proposal.semester_end)],
            args, None, auth_cache)

    def _view_any_mode(
            self, current_user, db, target_objects,
            extra_info, args, form, auth_cache):
        if self.location is None:
            raise ErrorPage(
                'Observing information is not available for this facility.')

        message = None
        date_start = None
        date_end = None

        (date_start_str, date_end_str) = extra_info

        if (date_start_str is None) or (date_end_str) is None:
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
            if isinstance(date_start_str, datetime):
                date_start = date_start_str
                date_start_str = date_start.strftime('%Y-%m-%d')

            if isinstance(date_end_str, datetime):
                date_end = date_end_str
                date_end_str = date_end.strftime('%Y-%m-%d')

        ctx = {
            'date_start': date_start_str,
            'date_end': date_end_str,
            'avail_date': None,
        }

        try:
            if date_start is None:
                try:
                    date_start = datetime.strptime(date_start_str, '%Y-%m-%d')
                except ValueError:
                    raise UserError(
                        'Did not understand start date "{}".', date_start_str)

            if date_end is None:
                try:
                    date_end = datetime.strptime(date_end_str, '%Y-%m-%d')
                except ValueError:
                    raise UserError(
                        'Did not understand end date "{}".', date_end_str)

            if target_objects is not None:
                ctx.update(self._do_availability_search(
                    target_objects, date_start, date_end))

        except UserError as e:
            message = e.message

        ctx['message'] = message

        return ctx

    def _do_availability_search(self, target_objects, date_start, date_end):
        avail_date = None
        avail_time = None
        avail_target = None
        target_hits = None
        n_max = 0
        target_max = 0

        date_range = (Time(date_end) - Time(date_start)).sec / 86400

        # Choose a suitable date step.
        if date_range < 0:
            raise UserError(
                'End date is before start date.')
        elif date_range > 370:
            raise UserError(
                'Excessive date range.  Please select a range of '
                'one year or less.')
        elif date_range > 190:
            date_step = 28
        elif date_range > 92:
            date_step = 14
        elif date_range > 7:
            date_step = 7
        else:
            date_step = 1

        # Choose a suitable time step.
        time_duration = self.time_duration
        if time_duration > 86400:
            time_duration = 86400
            time_step = 7200
        elif time_duration > 43200:
            time_step = 7200
        else:
            time_step = 3600

        n = 0
        avail_date = OrderedDict()
        avail_time = []
        if len(target_objects) > 1:
            target_hits = defaultdict(int)

        targets = concatenate_coord_objects(target_objects)

        dates = (
            Time(datetime.combine(date_start, self.time_start))
            + arange(0, date_range + 1,
                     date_step)[:, newaxis] * units.day
            + arange(0, self.time_duration + 1,
                     time_step)[newaxis, :] * units.second)

        frame = AltAz(location=self.location, obstime=dates[:, :, newaxis])

        with warnings.catch_warnings():
            # Ignore warning about not having the latest IERS data.
            warnings.simplefilter('ignore', AstropyWarning)

            targets = targets[newaxis, newaxis, :].transform_to(frame)

        all_available = (targets.alt > self.el_min)

        (n_date, n_time, n_target_shape) = all_available.shape

        for i_date in range(0, n_date):
            date_str = dates[i_date, 0].datetime.strftime('%Y-%m-%d')
            result = avail_date[date_str] = []

            for i_time in range(0, n_time):
                n_target = 0

                (available,) = nonzero(all_available[i_date, i_time, :])

                for i in available:
                    n_target += 1

                    if target_hits is not None:
                        target_hits[i] += 1

                if i_date == 0:
                    avail_time.append(
                        dates[i_date, i_time].datetime.strftime('%H:%M'))

                result.append(n_target)

                if n_target > n_max:
                    n_max = n_target

                n += 1

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
            'avail_el_min': self.el_min.value,
        }

    def _view_extra_info(self, args, form):
        """
        Read the start and end date from the form.
        """

        date_start = None
        date_end = None

        if form is not None:
            date_start = form['date_start']
            date_end = form['date_end']

        return [date_start, date_end]
