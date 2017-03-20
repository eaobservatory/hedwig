# Copyright (C) 2015-2017 East Asian Observatory
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

from collections import OrderedDict
from math import cos, radians
import time

from jcmt_itc_scuba2 import SCUBA2ITC, SCUBA2ITCError

from ...compat import first_value
from ...error import CalculatorError, UserError
from ...type.misc import SectionedList
from ...type.simple import CalculatorMode, CalculatorResult, CalculatorValue
from ...view.util import parse_time
from .calculator_jcmt import JCMTCalculator
from .type import JCMTWeather


class SCUBA2Calculator(JCMTCalculator):
    CALC_TIME = 1
    CALC_RMS = 2

    modes = OrderedDict((
        (CALC_TIME, CalculatorMode('time', 'Time required for target RMS')),
        (CALC_RMS,  CalculatorMode('rms',  'RMS expected in given time')),
    ))

    version = 2

    @classmethod
    def get_code(cls):
        """
        Get the calculator "code".

        This is a short string used to uniquely identify the calculator
        within the facility which uses it.
        """

        return 'scuba2'

    def __init__(self, *args):
        """
        Construct calculator.

        Calls the superclass constructor and then initializes a SCUBA-2
        ITC object.
        """

        super(SCUBA2Calculator, self).__init__(*args)

        self.itc = SCUBA2ITC()

        self.map_modes = self.itc.get_modes()

        default_mode = first_value(self.map_modes)
        self.default_pix850 = default_mode.pix_850
        self.default_pix450 = default_mode.pix_450

    def get_name(self):
        return 'SCUBA-2 ITC'

    def get_calc_version(self):
        return self.itc.get_version()

    def get_inputs(self, mode, version=None):
        """
        Get the list of calculator inputs for a given version of the
        calculator.
        """

        if version is None:
            version = self.version

        inputs = SectionedList()

        inputs.extend([
            CalculatorValue(
                'pos',    'Source position', 'Pos.', '{:.1f}', '\u00b0'),
            CalculatorValue(
                'pos_type', 'Source position type',
                'Pos. type', '{}', None),
            CalculatorValue(
                'tau',    '225 GHz opacity',
                '\u03c4\u2082\u2082\u2085', '{}', None),
        ], section='src', section_name='Source and Conditions')

        inputs.extend([
            CalculatorValue(
                'map', 'Map type', 'Map', '{}', None),
        ], section='obs', section_name='Observation')

        if version == 2:
            inputs.extend([
                CalculatorValue(
                    'samp', 'Map sampling',
                    'Samp.', '{}', None),
            ], section='obs')

        elif version == 1:
            inputs.extend([
                CalculatorValue(
                    'mf', 'Matched filter',
                    'Match. filt.', '{}', None),
            ], section='obs')
        else:
            raise CalculatorError('Unknown version.')

        inputs.extend([
            CalculatorValue(
                'pix850', '850 \u00b5m pixel size',
                'Pixel\u2088\u2085\u2080', '{}', '"'),
            CalculatorValue(
                'pix450', '450 \u00b5m pixel size',
                'Pixel\u2084\u2085\u2080', '{}', '"'),
        ], section='obs')

        inputs.add_section('req', 'Requirement')

        if mode == self.CALC_TIME:
            if version in (1, 2):
                inputs.extend([
                    CalculatorValue(
                        'wl',  'Wavelength', '\u03bb', '{}', '\u00b5m'),
                    CalculatorValue(
                        'rms', 'Target sensitivity', '\u03c3',
                        '{:.3f}', 'mJy/beam'),
                ], section='req')
            else:
                raise CalculatorError('Unknown version.')

        elif mode == self.CALC_RMS:
            if version in (1, 2):
                inputs.extend([
                    CalculatorValue(
                        'time', 'Observing time', 'Time', '{:.3f}', 'hours'),
                ], section='req')
            else:
                raise CalculatorError('Unknown version.')

        else:
            raise CalculatorError('Unknown mode.')

        return inputs

    def get_default_input(self, mode):
        """
        Get the default input values (for the current version).
        """

        common_inputs = [
            ('map', 'daisy'),
            ('pos', 40.0),
            ('pos_type', 'dec'),
            ('tau', 0.065),
            ('samp', 'map'),
            ('pix850', self.default_pix850),
            ('pix450', self.default_pix450),
        ]

        if mode == self.CALC_TIME:
            return dict(common_inputs + [
                ('wl', 850),
                ('rms', 2.0),
            ])

        elif mode == self.CALC_RMS:
            return dict(common_inputs + [
                ('time', 30),
            ])

        else:
            raise CalculatorError('Unknown mode.')

    def format_input(self, inputs, values):
        """
        Format input values for display in the input form.
        """

        defaults = self.get_default_input(self.CALC_TIME)

        formatted_inputs = {
            x.code:
                x.format.format(values[x.code] if values[x.code] is not None
                                else defaults.get(x.code))
                if x.code not in ('map', 'samp', 'wl')
                else values[x.code]
            for x in inputs
        }

        formatted_inputs['tau_band'] = self.get_tau_band(values['tau'])

        return formatted_inputs

    def get_form_input(self, inputs, form):
        """
        Extract the input values from the submitted form.
        """

        values = {}

        for input_ in inputs:
            if input_.code == 'pix850' or input_.code == 'pix450':
                # These aren't present in the form unless samp is "custom".
                if form['samp'] != 'custom':
                    values[input_.code] = (
                        self.default_pix850 if input_.code == 'pix850' else
                        self.default_pix450)
                else:
                    values[input_.code] = form[input_.code]

            elif input_.code == 'tau':
                (tau, tau_band) = self.get_form_tau(form)
                values['tau_band'] = tau_band
                values['tau'] = tau

            elif input_.code == 'wl':
                values[input_.code] = int(form[input_.code])

            else:
                values[input_.code] = form[input_.code]

        return values

    def convert_input_mode(self, mode, new_mode, input_):
        """
        Convert the inputs for one mode to form a suitable set of inputs
        for another mode.  Only called if the mode is changed.
        """

        new_input = input_.copy()

        output = self(mode, input_).output

        if mode == self.CALC_RMS and new_mode == self.CALC_TIME:
            del new_input['time']
            new_input['wl'] = 850
            new_input['rms'] = output['rms_850']

        elif mode == self.CALC_TIME and new_mode == self.CALC_RMS:
            del new_input['rms']
            del new_input['wl']
            new_input['time'] = output['time']

        else:
            raise CalculatorError('Impossible mode change.')

        return new_input

    def convert_input_version(self, mode, old_version, input_):
        """
        Converts the inputs from an older version so that they can be
        used with the current version of the calculator.
        """

        if old_version == 1:
            input_ = input_.copy()

            if input_.pop('mf'):
                input_['samp'] = 'mf'

            else:
                input_['samp'] = 'custom'

        return input_

    def get_outputs(self, mode, version=None):
        """
        Get the list of calculator outputs for a given version of the
        calculator.
        """

        if version is None:
            version = self.version

        if mode == self.CALC_TIME:
            if version in (1, 2):
                return [
                    CalculatorValue(
                        'time', 'Observing time', 'Time', '{:.3f}', 'hours'),
                ]
            else:
                raise CalculatorError('Unknown version.')

        elif mode == self.CALC_RMS:
            if version in (1, 2):
                return [
                    CalculatorValue(
                        'rms_850', '850 \u00b5m sensitivity',
                        '\u03c3\u2088\u2085\u2080', '{:.3f}', 'mJy/beam'),
                    CalculatorValue(
                        'rms_450', '450 \u00b5m sensitivity',
                        '\u03c3\u2084\u2085\u2080', '{:.3f}', 'mJy/beam'),
                ]
            else:
                raise CalculatorError('Unknown version.')

        else:
            raise CalculatorError('Unknown mode.')

    def get_extra_context(self):
        """
        Return extra information to be given to the view template.
        """

        return {
            'weather_bands': JCMTWeather.get_available(),
            'map_modes': self.map_modes,
            'position_types': self.position_type,
        }

    def parse_input(self, mode, input_, defaults=None):
        """
        Parse inputs as obtained from the HTML form (typically unicode)
        and return values suitable for calculation (perhaps float).
        """

        parsed = {}

        for field in self.get_inputs(mode):
            try:
                if field.code in ('pos', 'pix850', 'pix450', 'rms', 'tau'):
                    parsed[field.code] = float(input_[field.code])

                elif field.code == 'time':
                    parsed[field.code] = parse_time(input_[field.code])

                else:
                    parsed[field.code] = input_[field.code]

            except ValueError:
                if (not input_[field.code]) and (defaults is not None):
                    parsed[field.code] = defaults[field.code]

                else:
                    raise UserError('Invalid value for {}.', field.name)

        self._validate_position(parsed['pos'], parsed['pos_type'])

        # Remove irrelevant pixel sizes when not using custom pixels.
        if parsed['samp'] != 'custom':
            parsed['pix850'] = None
            parsed['pix450'] = None

        return parsed

    def __call__(self, mode, input_):
        """
        Perform a calculation, taking an input dictionary and returning
        a CalculatorResult object.

        The result object contains the essential output, a dictionary with
        entries corresponding to the list given by get_outputs.  It also
        contains any extra output for display but which would not be
        stored in the database as part of the calculation result.
        """

        map_mode = input_['map']
        tau_225 = input_['tau']
        extra = {}

        # Determine sampling factors.
        if input_['samp'] == 'mf':
            factor = {850: 5, 450: 8}

        elif input_['samp'] in ('custom', 'map'):
            if input_['samp'] == 'custom':
                pix_850 = input_['pix850']
                pix_450 = input_['pix450']

            else:
                mode_info = self.map_modes.get(map_mode)
                if mode_info is None:
                    raise UserError('Unknown map type.')
                pix_850 = mode_info.pix_850
                pix_450 = mode_info.pix_450

            factor = {850: (pix_850 / 4) ** 2,
                      450: (pix_450 / 2) ** 2}

        else:
            raise UserError('Unknown map sampling option.')

        extra['f_850'] = factor[850]
        extra['f_450'] = factor[450]

        if input_['pos_type'] == 'dec':
            airmass = self.itc.estimate_airmass(input_['pos'])
        elif input_['pos_type'] == 'zen':
            airmass = 1.0 / cos(radians(input_['pos']))
        elif input_['pos_type'] == 'el':
            airmass = 1.0 / cos(radians(90.0 - input_['pos']))
        elif input_['pos_type'] == 'am':
            airmass = input_['pos']
        else:
            raise UserError('Unknown source position type.')

        if input_['pos_type'] != 'am':
            extra['airmass'] = airmass

        try:
            # Perform calculation.
            if mode == self.CALC_TIME:
                filter_ = input_['wl']
                rms = input_['rms']

                (time_tot, extra_output) = self.itc.calculate_total_time(
                    map_mode, filter_, tau_225, airmass, factor, rms,
                    with_extra_output=True)

                extra['time_src'] = extra_output.pop('time_src') / 3600.0
                extra.update(extra_output)

                output = {'time': time_tot / 3600.0}

            elif mode == self.CALC_RMS:
                # Convert time to seconds.
                time_tot = input_['time'] * 3600.0

                (rms, extra_output) = self.itc.calculate_rms_for_total_time(
                    map_mode, 850, tau_225, airmass, factor, time_tot,
                    with_extra_output=True)

                output = {
                    'rms_850': rms,
                    'rms_450': extra_output.pop('rms_alt', None),
                }

                extra['time_src'] = extra_output.pop('time_src') / 3600.0
                extra.update(extra_output)

            else:
                raise CalculatorError('Unknown mode.')

        except SCUBA2ITCError as e:
            raise UserError(e.args[0])

        # Make weather band comparison table.
        weather_band_comparison = OrderedDict()
        for (weather_band, weather_band_info) in \
                JCMTWeather.get_available().items():
            weather_band_result = {}
            for condition_name in ('rep', 'min', 'max'):
                condition_result = None
                condition_tau = getattr(weather_band_info,
                                        condition_name)

                try:
                    if condition_tau is None:
                        pass

                    elif mode == self.CALC_TIME:
                        condition_result = \
                            self.itc.calculate_total_time(
                                map_mode, filter_, condition_tau, airmass,
                                factor, rms) / 3600.0

                    elif mode == self.CALC_RMS:
                        condition_result = \
                            self.itc.calculate_rms_for_total_time(
                                map_mode, 850, condition_tau, airmass,
                                factor, time_tot)

                except SCUBA2ITCError:
                    pass

                weather_band_result[condition_name] = condition_result

            weather_band_comparison[weather_band] = weather_band_result

        primary_output = self.get_outputs(mode)[0]
        extra['wb_comparison'] = weather_band_comparison
        extra['wb_comparison_format'] = primary_output.format
        extra['wb_comparison_unit'] = primary_output.unit

        return CalculatorResult(output, extra)

    def condense_calculation(self, mode, version, calculation):
        self._condense_merge_values(calculation, (('pos', 'pos_type'),))

        if version == 2:
            # Condense map sampling input.
            inputs = calculation.inputs.get_section('obs')
            samp = calculation.input['samp']
            values = {v.code: i for (i, v) in enumerate(inputs)}
            to_remove = []

            if (samp == 'map') or (samp == 'custom'):
                del calculation.input['samp']
                to_remove.append(values['samp'])

            elif (samp == 'mf'):
                calculation.input['samp'] = True
                inputs[values['samp']] = inputs[values['samp']]._replace(
                    name='Matched filter', abbr='Match. filt.')

            for i in sorted(to_remove, reverse=True):
                del inputs[i]
