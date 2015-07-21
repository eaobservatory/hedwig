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

from jcmt_itc_heterodyne import HeterodyneITC, HeterodyneITCError
from jcmt_itc_heterodyne.receiver import HeterodyneReceiver, ReceiverInfo

from ...error import CalculatorError, UserError
from ...type import CalculatorMode, CalculatorResult, CalculatorValue
from ...view.util import parse_time
from .calculator_jcmt import JCMTCalculator

ReceiverInfoID = namedtuple('ReceiverInfoID', ReceiverInfo._fields + ('id', ))

MappingMode = namedtuple('MappingMode', ('id', 'name', 'sw_modes'))
SwitchingMode = namedtuple('SwitchingMode', ('id', 'name'))


class HeterodyneCalculator(JCMTCalculator):
    CALC_TIME = 1
    CALC_RMS_FROM_ELAPSED_TIME = 2
    CALC_RMS_FROM_INT_TIME = 3

    modes = OrderedDict((
        (CALC_TIME,
            CalculatorMode('time', 'Time required for target RMS')),
        (CALC_RMS_FROM_ELAPSED_TIME,
            CalculatorMode('rms_el', 'RMS expected in elapsed time')),
        (CALC_RMS_FROM_INT_TIME,
            CalculatorMode('rms_int', 'RMS for integration time per point')),
    ))

    _map_modes = OrderedDict((
        ('grid',   MappingMode(HeterodyneITC.GRID, 'Grid', None)),
        ('jiggle', MappingMode(HeterodyneITC.JIGGLE, 'Jiggle', None)),
        ('raster', MappingMode(HeterodyneITC.RASTER, 'Raster', None)),
    ))

    switch_modes = OrderedDict((
        ('bmsw', SwitchingMode(HeterodyneITC.BMSW, 'Beam')),
        ('pssw', SwitchingMode(HeterodyneITC.PSSW, 'Position')),
        ('frsw', SwitchingMode(HeterodyneITC.FRSW, 'Frequency')),
    ))

    version = 1

    @classmethod
    def get_code(cls):
        """
        Get the calculator "code".

        This is a short string used to uniquely identify the calculator
        within the facility which uses it.
        """

        return 'heterodyne'

    def __init__(self, *args):
        """
        Construct calculator.

        Calls the superclass constructor and then initializes a
        Heterodyne ITC object.
        """

        super(HeterodyneCalculator, self).__init__(*args)

        self.itc = HeterodyneITC()

        # Determine which combinations of mapping and switching modes
        # are allowed.
        valid_modes = self.itc.get_valid_modes()
        self.map_modes = OrderedDict((
            (map_code, map_mode._replace(sw_modes=[
                sw_code for (sw_code, sw_mode) in self.switch_modes.items()
                if (map_mode.id, sw_mode.id) in valid_modes
            ]))
            for (map_code, map_mode) in self._map_modes.items()
        ))

    def get_name(self):
        return 'Heterodyne ITC'

    def get_calc_version(self):
        return self.itc.get_version()

    def get_inputs(self, mode, version=None):
        """
        Get the list of calculator inputs for a given version of the
        calculator.
        """

        if version is None:
            version = self.version

        if version == 1:
            common_inputs = [
                CalculatorValue('rx', 'Receiver', 'Receiver', '{}', None),
                CalculatorValue('mm', 'Mapping mode', 'Mode', '{}', None),
                CalculatorValue('sw', 'Switching mode', 'Switch', '{}', None),
                CalculatorValue('freq', 'Frequency', 'Frequency', '{}', 'GHz'),
                CalculatorValue('res', 'Frequency resolution', 'Resolution', '{}', None),
                CalculatorValue('res_unit', 'Resolution unit', 'Res. Unit', '{}', None),
                CalculatorValue('tau', '225 GHz opacity', 'tau225', '{}', None),
                CalculatorValue('pos', 'Source position', 'Pos.', '{}', '\u00b0'),
                CalculatorValue('pos_type', 'Source position type', 'Pos. type', '{}', None),
                CalculatorValue('sb', 'Sideband mode', 'SB', '{}', None),
                CalculatorValue('dual_pol', 'Dual polarization', 'DP', '{}', None),
                CalculatorValue('n_pt', 'Number of points', 'Points', '{}', None),
                CalculatorValue('dim_x', 'Raster width', 'x', '{}', '"'),
                CalculatorValue('dim_y', 'Raster height', 'y', '{}', '"'),
                CalculatorValue('dx', 'Pixel width', 'dx', '{}', '"'),
                CalculatorValue('dy', 'Pixel/scan height', 'dy', '{}', '"'),
                CalculatorValue('basket', 'Basket weave', 'BW', '{}', None),
                CalculatorValue('sep_off', 'Separate offs', 'SO', '{}', None),
                CalculatorValue('cont', 'Continuum mode', 'CM', '{}', None),
            ]

        else:
            raise CalculatorError('Unknown version.')

        if mode == self.CALC_TIME:
            if version == 1:
                return common_inputs + [
                    CalculatorValue('rms', 'Target sensitivity', '\u03c3', '{}', 'K TA*'),
                ]
            else:
                raise CalculatorError('Unknown version.')

        elif mode == self.CALC_RMS_FROM_ELAPSED_TIME:
            if version == 1:
                return common_inputs + [
                    CalculatorValue('elapsed', 'Elapsed time', 'Elapsed', '{}', 'hours'),
                ]
            else:
                raise CalculatorError('Unknown version.')

        elif mode == self.CALC_RMS_FROM_INT_TIME:
            if version == 1:
                return common_inputs + [
                    CalculatorValue('int_time', 'Integration time', 'Int. time', '{}', 'seconds'),
                ]
            else:
                raise CalculatorError('Unknown version.')

        else:
            raise CalculatorError('Unknown mode.')

    def get_default_input(self, mode):
        """
        Get the default input values (for the current version).
        """

        common_inputs = [
            ('rx', 'HARP'),
            ('mm', 'raster'),
            ('sw', 'pssw'),
            ('freq', 345.796),
            ('res', 0.488),
            ('res_unit', 'MHz'),
            ('tau', 0.1),
            ('pos', 40.0),
            ('pos_type', 'dec'),
            ('sb', 'ssb'),
            ('dual_pol', False),
            ('n_pt', 1),
            ('dim_x', 180),
            ('dim_y', 180),
            ('dx', 8),
            ('dy', 8),
            ('basket', False),
            ('sep_off', False),
            ('cont', False),
        ]

        if mode == self.CALC_TIME:
            return dict(common_inputs + [
                ('rms', 1.0),
            ])

        elif mode == self.CALC_RMS_FROM_ELAPSED_TIME:
            return dict(common_inputs + [
                ('elapsed', 0.75),
            ])

        elif mode == self.CALC_RMS_FROM_INT_TIME:
            return dict(common_inputs + [
                ('int_time', 30.0),
            ])

        else:
            raise CalculatorError('Unknown mode.')

    def format_input(self, inputs, values):
        """
        Format input values for display in the input form.
        """

        formatted_inputs = {
            x.code:
                x.format.format(values[x.code])
                if x.code not in ('rx', 'mm', 'sw', 'sb', 'dual_pol', 'n_pt',
                                  'basket', 'sep_off', 'cont', 'res_unit')
                else values[x.code]
            for x in inputs
        }

        formatted_inputs.update({
            'tau_band': self.get_tau_band(values['tau']),
            'dy_spacing': '{:.3f}'.format(values['dy']),
        })

        return formatted_inputs

    def get_form_input(self, inputs, form):
        """
        Extract the input values from the submitted form.
        """

        defaults = self.get_default_input(self.CALC_TIME)

        receiver = self.get_receiver_by_name(form['rx'], as_object=True)
        map_mode = self.map_modes[form['mm']].id

        values = {}

        for input_ in inputs:
            if input_.code in ('dual_pol', 'basket', 'sep_off', 'cont'):
                # Checkboxes: true if they appear in the form parameters.
                values[input_.code] = input_.code in form

            elif input_.code == 'tau':
                (tau, tau_band) = self.get_form_tau(form)
                values['tau'] = tau
                values['tau_band'] = tau_band

            elif input_.code == 'n_pt':
                if map_mode == HeterodyneITC.GRID:
                    try:
                        values[input_.code] = int(form['n_pt'])
                    except ValueError:
                        # Prefer to convert to integer so that the value could
                        # match a possible jiggle pattern point count, but if
                        # that fails, leave as a string so that we can warn
                        # as normal for a malformed value.
                        values[input_.code] = form['n_pt']
                elif map_mode == HeterodyneITC.JIGGLE:
                    if receiver.array is None:
                        values[input_.code] = int(form['n_pt_jiggle'])
                    else:
                        values[input_.code] = int(
                            form['n_pt_jiggle_' + receiver.name])
                else:
                    values[input_.code] = defaults.get(input_.code, None)

            else:
                # Need to allow parameters not to exist when they can
                # be disabled (e.g. raster parameters in other modes).
                # For now, allow all input values to be filled from the
                # general defaults.  TODO: be more specific here?
                value = form.get(input_.code, None)
                if value is None:
                    value = defaults.get(input_.code, None)
                values[input_.code] = value

        values['dy_spacing'] = form.get('dy_spacing_' + receiver.name, None)
        if values['dy_spacing'] is None:
            values['dy_spacing'] = '{:.3f}'.format(defaults['dy'])

        return values

    def convert_input_mode(self, mode, new_mode, input_):
        """
        Convert the inputs for one mode to form a suitable set of
        inputs for another mode.  Only called if the mode is changed.
        """

        new_input = input_.copy()

        result = self(mode, input_)

        if new_mode == self.CALC_TIME:
            if mode == self.CALC_RMS_FROM_ELAPSED_TIME:
                new_input['rms'] = result.output['rms']
                del new_input['elapsed']
            elif mode == self.CALC_RMS_FROM_INT_TIME:
                new_input['rms'] = result.output['rms']
                del new_input['int_time']
            else:
                raise CalculatorError('Impossible mode change.')

        elif new_mode == self.CALC_RMS_FROM_ELAPSED_TIME:
            if mode == self.CALC_TIME:
                new_input['elapsed'] = result.output['elapsed']
                del new_input['rms']
            elif mode == self.CALC_RMS_FROM_INT_TIME:
                new_input['elapsed'] = result.output['elapsed']
                del new_input['int_time']
            else:
                raise CalculatorError('Impossible mode change.')

        elif new_mode == self.CALC_RMS_FROM_INT_TIME:
            if mode == self.CALC_TIME:
                new_input['int_time'] = result.extra['int_time']
                del new_input['rms']
            elif mode == self.CALC_RMS_FROM_ELAPSED_TIME:
                new_input['int_time'] = result.extra['int_time']
                del new_input['elapsed']
            else:
                raise CalculatorError('Impossible mode change.')

        else:
            raise CalculatorError('Unknown mode.')

        return new_input

    def convert_input_version(self, old_version, input_):
        """
        Converts the inputs from an older version so that they can be
        used with the current version of the calculator.
        """

        return input_

    def get_outputs(self, mode, version=None):
        """
        Get the list of calculator outputs for a given version of the
        calculator.
        """

        if version is None:
            version = self.version

        if mode == self.CALC_TIME:
            if version == 1:
                return [
                    CalculatorValue(
                        'elapsed', 'Elapsed time', 'Elapsed',
                        '{:.3f}', 'hours'),
                ]
            else:
                raise CalculatorError('Unknown version.')

        elif mode == self.CALC_RMS_FROM_ELAPSED_TIME:
            if version == 1:
                return [
                    CalculatorValue(
                        'rms', 'Sensitivity', '\u03bb', '{:.3f}', 'K TA*'),
                ]
            else:
                raise CalculatorError('Unknown version.')

        elif mode == self.CALC_RMS_FROM_INT_TIME:
            if version == 1:
                return [
                    CalculatorValue(
                        'rms', 'Sensitivity', '\u03bb', '{:.3f}', 'K TA*'),
                    CalculatorValue(
                        'elapsed', 'Elapsed time', 'Elapsed',
                        '{:.3f}', 'hours'),
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
            'weather_bands': self.bands,
            'receivers': HeterodyneReceiver.get_all_receivers().values(),
            'map_modes': self.map_modes,
            'switch_modes': self.switch_modes,
            'jiggle_patterns': self.itc.get_jiggle_patterns(),
        }

    def parse_input(self, mode, input_):
        """
        Parse inputs as obtained from the HTML form (typically unicode)
        and return values suitable for calculation (perhaps float).
        """

        receiver = self.get_receiver_by_name(input_['rx'], as_object=True)

        parsed = {}

        for field in self.get_inputs(mode):
            try:
                if field.code in ('freq', 'res', 'pos', 'rms', 'tau'):
                    parsed[field.code] = float(input_[field.code])

                elif field.code == 'dx':
                    if receiver.array is None:
                        if input_[field.code] is None:
                            parsed[field.code] = None
                        else:
                            parsed[field.code] = float(input_[field.code])
                    else:
                        # The "dx" input is disabled for array receivers:
                        # always use the pixel size.
                        parsed[field.code] = receiver.pixel_size

                elif field.code == 'dy':
                    if receiver.array is None:
                        if input_[field.code] is None:
                            parsed[field.code] = None
                        else:
                            parsed[field.code] = float(input_[field.code])
                    else:
                        parsed[field.code] = float(input_['dy_spacing'])

                elif field.code in ('dim_x', 'dim_y', 'int_time'):
                    if input_[field.code] is None:
                        parsed[field.code] = None
                    else:
                        parsed[field.code] = float(input_[field.code])

                elif field.code in ('n_pt'):
                    if input_[field.code] is None:
                        parsed[field.code] = None
                    else:
                        parsed[field.code] = int(input_[field.code])

                elif field.code == 'elapsed':
                    parsed[field.code] = parse_time(input_[field.code])

                else:
                    parsed[field.code] = input_[field.code]

            except ValueError:
                raise UserError('Invalid value for {}.', field.name)

        if parsed['pos_type'] == 'dec':
            if not -90 <= parsed['pos'] <= 90:
                raise UserError(
                    'Source declination should be between -90 and 90.')
        elif not 0 <= parsed['pos'] <= 90:
            raise UserError(
                'Source zenith angle / elevation '
                'should be between 0 and 90.')

        return parsed

    def get_receiver_by_name(self, receiver_name, as_object=False):
        """
        Get a receiver by name.
        """
        for (rx_id, rx_info) in HeterodyneReceiver.get_all_receivers().items():
            if rx_info.name == receiver_name:
                if as_object:
                    return rx_info
                return rx_id

        raise UserError('Receiver not recognised.')

    def __call__(self, mode, input_):
        """
        Perform a calculation, taking an input dictionary and returning
        a CalculatorResult object.

        The result object contains the essential output, a dictionary with
        entries corresponding to the list given by get_outputs.  It also
        contains any extra output for display but which would not be
        stored in the database as part of the calculation result.
        """

        extra_output = {}

        if input_['pos_type'] == 'dec':
            zenith_angle_deg = self.itc.estimate_zenith_angle_deg(
                input_['pos'])
            extra_output['zenith_angle'] = zenith_angle_deg
        elif input_['pos_type'] == 'zen':
            zenith_angle_deg = input_['pos']
        elif input_['pos_type'] == 'el':
            zenith_angle_deg = 90.0 - input_['pos']
            extra_output['zenith_angle'] = zenith_angle_deg
        else:
            raise UserError('Unknown source position type.')

        receiver = self.get_receiver_by_name(input_['rx'])

        freq = input_['freq']
        freq_res = input_['res']
        freq_res_unit = input_['res_unit']
        if freq_res_unit == 'MHz':
            extra_output['res_velocity'] = \
                self.itc.freq_res_to_velocity(freq, freq_res)
        elif freq_res_unit == 'km/s':
            freq_res = self.itc.velocity_to_freq_res(freq, freq_res)
            extra_output['res_freq'] = freq_res
        else:
            raise CalculatorError('Frequency units not recognised.')

        kwargs = {
            'receiver': receiver,
            'map_mode': self.map_modes[input_['mm']].id,
            'sw_mode': self.switch_modes[input_['sw']].id,
            'freq': freq,
            'freq_res': freq_res,
            'tau_225': input_['tau'],
            'zenith_angle_deg': zenith_angle_deg,
            'is_dsb': (input_['sb'] == 'dsb'),
            'dual_polarization': input_['dual_pol'],
            'n_points': input_['n_pt'],
            'dim_x': input_['dim_x'],
            'dim_y': input_['dim_y'],
            'dx': input_['dx'],
            'dy': input_['dy'],
            'basket_weave': input_['basket'],
            'separate_offs': input_['sep_off'],
            'continuum_mode': input_['cont'],
            'with_extra_output': True,
        }

        try:
            if mode == self.CALC_TIME:
                (result, extra) = self.itc.calculate_time(
                    input_['rms'], **kwargs)

                output = {
                    'elapsed': result / 3600.0,
                }

            elif mode == self.CALC_RMS_FROM_ELAPSED_TIME:
                (result, extra) = self.itc.calculate_rms_for_elapsed_time(
                    input_['elapsed'] * 3600.0, **kwargs)

                output = {
                    'rms': result,
                }

            elif mode == self.CALC_RMS_FROM_INT_TIME:
                (result, extra) = self.itc.calculate_rms_for_int_time(
                    input_['int_time'], **kwargs)

                output = {
                    'rms': result,
                    'elapsed': extra.pop('elapsed_time') / 3600.0,
                }

            else:
                raise CalculatorError('Unknown mode.')

        except HeterodyneITCError as e:
            raise UserError(e.message)

        extra_output.update(extra)

        return CalculatorResult(output, extra_output)
