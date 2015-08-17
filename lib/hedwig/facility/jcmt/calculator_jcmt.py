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

from ...web.util import ErrorPage
from ...view.calculator import BaseCalculator
from .type import JCMTWeather


class JCMTCalculator(BaseCalculator):
    def get_tau_band(self, tau):
        """
        Finds the band number matching the given tau.

        Returns None if a match within 0.0001 was not found.
        """

        for (band_num, band_info) in JCMTWeather.get_available().items():
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
            try:
                return (JCMTWeather.get_info(tau_band).rep, tau_band)
            except KeyError:
                raise ErrorPage('Invalid weather band "{}".', tau_band)

    def _condense_merge_values(self, calculation, value_tuples):
        """
        Helper routine for the "condense_calculation" method.

        Takes a collection of value tuples (currently assumed to be
        pairs).  Then updates the calculation to merge the two
        values in each of those pairs.
        """

        # Create dictionary with an entry for each value we are interested in.
        values = {}
        for value_tuple in value_tuples:
            for value in value_tuple:
                values[value] = None

        # Record the index of each value, if it's present.
        for i in range(0, len(calculation.inputs)):
            input_ = calculation.inputs[i]
            for value in list(values.keys()):
                if input_.code == value:
                    values[value] = i

        to_remove = []

        # Go through the collection of pairs, and if we have both entries,
        # merge them.
        for (val_a, val_b) in value_tuples:
            if (values[val_a] is not None) and (values[val_b] is not None):
                value = calculation.inputs[values[val_a]]
                calculation.input[val_a] = ' '.join([
                    value.format.format(calculation.input[val_a]),
                    ('' if value.unit is None else value.unit),
                    calculation.input[val_b],
                ])
                calculation.inputs[values[val_a]] = \
                    calculation.inputs[values[val_a]]._replace(
                        format='{}', unit=None)
                to_remove.append(values[val_b])

        # Remove the values we no longer want (in reverse order so that we
        # don't have to worry about the indices changing as other values
        # are removed).
        for i in sorted(to_remove, reverse=True):
            del calculation.inputs[i]
