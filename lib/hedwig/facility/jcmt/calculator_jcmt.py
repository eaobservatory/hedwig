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

from collections import namedtuple, OrderedDict

from ...error import UserError
from ...web.util import ErrorPage
from ...view.calculator import BaseCalculator
from .type import JCMTWeather


class JCMTCalculator(BaseCalculator):
    PositionTypeInfo = namedtuple('PositionTypeInfo', ('name', 'no_unit'))

    position_type = OrderedDict((
        ('dec', PositionTypeInfo('declination',  False)),
        ('el',  PositionTypeInfo('elevation',    False)),
        ('zen', PositionTypeInfo('zenith angle', False)),
        ('am',  PositionTypeInfo('airmass',      True)),
    ))

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

        # Iterate through the calculation inputs by section because this is
        # more efficient than using SectionedList's indexing operations.
        for section in calculation.inputs.by_section():
            inputs = section.items

            # Record the index of each value present.
            values = {}
            for (i, input_) in enumerate(inputs):
                values[input_.code] = i

            to_remove = []

            # Go through the collection of pairs, and if we have both entries,
            # merge them.
            for (val_a, val_b) in value_tuples:
                if (val_a in values) and (val_b in values):
                    value = inputs[values[val_a]]
                    input_a = calculation.input[val_a]
                    input_b = calculation.input[val_b]
                    calculation.input[val_a] = ' '.join([
                        value.format.format(input_a),
                        ('' if (value.unit is None or
                                (val_a == 'pos' and
                                 self.position_type[input_b].no_unit)) else
                         value.unit),
                        input_b,
                    ])
                    inputs[values[val_a]] = \
                        inputs[values[val_a]]._replace(format='{}', unit=None)
                    to_remove.append(values[val_b])

            # Remove the values we no longer want (in reverse order so that we
            # don't have to worry about the indices changing as other values
            # are removed).
            for i in sorted(to_remove, reverse=True):
                del inputs[i]

    @classmethod
    def _validate_position(self, pos, pos_type):
        """
        Validate the position, with the given position type,
        raising UserError if a problem is detected.
        """

        if pos_type == 'dec':
            if not -90 <= pos <= 90:
                raise UserError(
                    'Source declination should be between -90 and 90.')
        elif pos_type == 'am':
            if not 1 <= pos <= 5:
                raise UserError(
                    'Airmass should be between 1 and 5.')
        elif not 0 <= pos <= 90:
            raise UserError(
                'Source zenith angle / elevation '
                'should be between 0 and 90.')
