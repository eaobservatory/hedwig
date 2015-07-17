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

from collections import namedtuple, OrderedDict

from ...view.calculator import BaseCalculator

WeatherBand = namedtuple('WeatherBand', ('rep', 'min', 'max'))


class JCMTCalculator(BaseCalculator):
    bands = OrderedDict((
        (1, WeatherBand(0.045, None, 0.05)),
        (2, WeatherBand(0.065, 0.05, 0.08)),
        (3, WeatherBand(0.1,   0.08, 0.12)),
        (4, WeatherBand(0.16,  0.12, 0.2)),
        (5, WeatherBand(0.23,  0.2,  None)),
    ))

    def get_tau_band(self, tau):
        """
        Finds the band number matching the given tau.

        Returns None if a match within 0.0001 was not found.
        """

        for (band_num, band_info) in self.bands.items():
            if abs(tau - band_info.rep) < 0.0001:
                return band_num

        return None

    def get_form_tau(self, form):
        """
        Extracts the tau value from the given form.

        Uses the "tau_band" select element unless "other" is selected,
        in which case it uses the "tau" input box.


        Returns a (tau, band) tuple.
        """

        if form['tau_band'] == 'other':
            return (form['tau_value'], None)
        else:
            tau_band = int(form['tau_band'])
            return (self.bands[tau_band].rep, tau_band)
