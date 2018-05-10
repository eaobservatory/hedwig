# Copyright (C) 2015-2018 East Asian Observatory
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
import json
from math import acos, degrees

from jcmt_itc_heterodyne import HeterodyneITC, HeterodyneITCError
from jcmt_itc_heterodyne.receiver import HeterodyneReceiver, ReceiverInfo
from jcmt_itc_heterodyne.line_catalog import get_line_catalog

from ...error import CalculatorError, UserError
from ...type.misc import SectionedList
from ...type.simple import \
    CalculatorMode, CalculatorResult, CalculatorValue, \
    RouteInfo
from ...view.util import parse_time
from .calculator_jcmt import JCMTCalculator
from .type import JCMTWeather

ReceiverInfoID = namedtuple('ReceiverInfoID', ReceiverInfo._fields + ('id', ))

MappingMode = namedtuple('MappingMode', ('id', 'name', 'sw_modes'))
SwitchingMode = namedtuple('SwitchingMode', ('id', 'name'))
ACSISMode = namedtuple('ACSISMode', ('name', 'freq_res', 'array_only'))
RVSystem = namedtuple('RVSystem', ('id', 'name', 'no_unit'))


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

    # Note: the JavaScript assumes that each array-only mode is preceeded
    # by the equivalent non-array-only mode.  In other words, if an array-only
    # mode is selected when a non-array receiver is chosen, it should change
    # to the preceeding mode.
    acsis_modes = OrderedDict((
        (1, ACSISMode('250 MHz',  0.0305, False)),
        (2, ACSISMode('400 MHz',  0.061,  True)),
        (3, ACSISMode('1000 MHz', 0.488,  False)),
        (4, ACSISMode('1600 MHz', 0.977,  True)),
    ))

    rv_systems = OrderedDict((
        ('z',   RVSystem(None,                     'redshift', True)),
        ('rad', RVSystem(HeterodyneITC.RV_DEF_RAD, 'radio',    False)),
        ('opt', RVSystem(HeterodyneITC.RV_DEF_OPT, 'optical',  False)),
    ))

    version = 2

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

        # Prepare JSON version of the line catalog: convert to lists so
        # that the ordering is preserved in the JSON.
        self.line_catalog = get_line_catalog()
        self.line_catalog_json = json.dumps([
            [s, [t for t in ts.items()]]
            for (s, ts) in self.line_catalog.items()
        ])

    def get_name(self):
        return 'Heterodyne ITC'

    def get_calc_version(self):
        return self.itc.get_version()

    def get_custom_routes(self):
        """
        Get list of custom routes used by this calculator.
        """

        return [
            RouteInfo(
                None,
                'line_catalog',
                'line_cat',
                self.view_line_catalog,
                {'send_file_opts': {
                    'allow_cache': True,
                    'fixed_type': 'application/json'}}),
        ]

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
                'rx', 'Receiver', 'Receiver', '{}', None),
            CalculatorValue(
                'res', 'Spectral resolution',
                '\u0394\u03bd', '{:.4f}', None),
            CalculatorValue(
                'res_unit', 'Resolution unit',
                '\u0394\u03bd unit', '{}', None),
            CalculatorValue(
                'sb', 'Sideband mode', 'SB', '{}', None),
            CalculatorValue(
                'dual_pol', 'Dual polarization', 'DP', '{}', None),
            CalculatorValue(
                'cont', 'Continuum mode', 'CM', '{}', None),
        ], section='rx', section_name='Receiver')

        inputs.extend([
            CalculatorValue(
                'species', 'Species', 'Spec.', '{}', None),
            CalculatorValue(
                'trans', 'Transition', 'Trans.', '{}', None),
            CalculatorValue(
                'freq', 'Rest frequency', '\u03bd\u2080', '{:.3f}', 'GHz'),
            CalculatorValue(
                'rv', 'Radial velocity', 'Rad. vel.', '{}', 'km/s'),
            CalculatorValue(
                'rv_sys', 'Radial velocity system',
                'Rad. vel. sys.', '{}', None),
            CalculatorValue(
                'pos', 'Source position', 'Pos.', '{:.1f}', '\u00b0'),
            CalculatorValue(
                'pos_type', 'Source position type', 'Pos. type', '{}', None),
            CalculatorValue(
                'tau', '225 GHz opacity',
                '\u03c4\u2082\u2082\u2085', '{:.3f}', None),
        ], section='src', section_name='Source and Conditions')

        inputs.extend([
            CalculatorValue(
                'mm', 'Mapping mode', 'Mode', '{}', None),
            CalculatorValue(
                'sw', 'Switching mode', 'Switch', '{}', None),
            CalculatorValue(
                'n_pt', 'Number of points', 'Points', '{:d}', None),
            CalculatorValue(
                'sep_off', 'Separate offs', 'SO', '{}', None),

            CalculatorValue(
                'dim_x', 'Raster width', 'x', '{}', '"'),
            CalculatorValue(
                'dim_y', 'Raster height', 'y', '{}', '"'),
            CalculatorValue(
                'dx', 'Pixel width', 'dx', '{}', '"'),
            CalculatorValue(
                'dy', 'Pixel/scan height', 'dy', '{}', '"'),
            CalculatorValue(
                'basket', 'Basket weave', 'BW', '{}', None),
        ], section='obs', section_name='Observation')

        if version == 2:
            pass

        elif version == 1:
            inputs.delete_item_where(lambda x: x.code in (
                'rv', 'rv_sys', 'species', 'trans'))

        else:
            raise CalculatorError('Unknown version.')

        inputs.add_section('req', 'Requirement')

        if mode == self.CALC_TIME:
            if version in (1, 2):
                inputs.extend([
                    CalculatorValue(
                        'rms', 'Target sensitivity',
                        '\u03c3', '{:.3f}', 'K TA*'),
                ], section='req')
            else:
                raise CalculatorError('Unknown version.')

        elif mode == self.CALC_RMS_FROM_ELAPSED_TIME:
            if version in (1, 2):
                inputs.extend([
                    CalculatorValue(
                        'elapsed', 'Elapsed time',
                        'Elapsed', '{:.3f}', 'hours'),
                ], section='req')
            else:
                raise CalculatorError('Unknown version.')

        elif mode == self.CALC_RMS_FROM_INT_TIME:
            if version in (1, 2):
                inputs.extend([
                    CalculatorValue(
                        'int_time', 'Integration time',
                        'Int. time', '{:.3f}', 'seconds'),
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
            ('rx', 'HARP'),
            ('mm', 'raster'),
            ('sw', 'pssw'),
            ('species', 'CO'),
            ('trans', '3 - 2'),
            ('freq', None),
            ('rv', 0.0),
            ('rv_sys', 'z'),
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

        defaults = self.get_default_input(self.CALC_TIME)

        is_array_receiver = self.get_receiver_by_name(
            values['rx'], as_object=True).array is not None

        formatted_inputs = {}

        for x in inputs:
            code = x.code
            value = values[code]

            formatted = None

            if code in ('species', 'trans'):
                # Only fill in the defaults if we do not have an
                # explicitly defined frequency.
                if (value is None) and (values['freq'] is None):
                    value = defaults.get(code)

                formatted = '' if (value is None) else value

            if value is None:
                value = defaults.get(code)

            if formatted is not None:
                pass

            elif code == 'freq':
                formatted = '' if (value is None) else x.format.format(value)

            elif code in (
                    'rx', 'mm', 'sw', 'sb', 'dual_pol', 'n_pt',
                    'basket', 'sep_off', 'cont', 'res_unit', 'rv_sys',
                    ):
                formatted = value

            else:
                formatted = x.format.format(value)

            formatted_inputs[code] = formatted

        acsis_mode = None
        if values['res_unit'] == 'MHz':
            for (acsis_mode_num, acsis_mode_info) in self.acsis_modes.items():
                if acsis_mode_info.array_only and not is_array_receiver:
                    continue

                if abs(values['res'] - acsis_mode_info.freq_res) < 0.0001:
                    acsis_mode = acsis_mode_num
                    break

        formatted_inputs.update({
            'tau_band': self.get_tau_band(values['tau']),
            'acsis_mode': acsis_mode,
            'dy_spacing': '{:.3f}'.format(
                values['dy'] if values['dy'] is not None else defaults['dy']),
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

            elif input_.code in ('freq', 'species', 'trans'):
                values[input_.code] = form.get(input_.code, '')

            elif input_.code == 'tau':
                (tau, tau_band) = self.get_form_tau(form)
                values['tau'] = tau
                values['tau_band'] = tau_band

            elif input_.code == 'res':
                if form['acsis_mode'] == 'other':
                    values[input_.code] = form[input_.code]
                    values['acsis_mode'] = None
                else:
                    acsis_mode = int(form['acsis_mode'])
                    values[input_.code] = self.acsis_modes[acsis_mode].freq_res
                    values['acsis_mode'] = acsis_mode

            elif input_.code == 'res_unit':
                if form['acsis_mode'] == 'other':
                    values[input_.code] = form[input_.code]
                else:
                    values[input_.code] = 'MHz'

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

    def convert_input_version(self, mode, old_version, input_):
        """
        Converts the inputs from an older version so that they can be
        used with the current version of the calculator.
        """

        if old_version == 1:
            input_ = input_.copy()

            input_['species'] = None
            input_['trans'] = None
            input_['rv'] = 0.0
            input_['rv_sys'] = 'z'

        return input_

    def get_outputs(self, mode, version=None):
        """
        Get the list of calculator outputs for a given version of the
        calculator.
        """

        if version is None:
            version = self.version

        outputs = []

        if mode == self.CALC_TIME:
            if version in (1, 2):
                outputs.extend([
                    CalculatorValue(
                        'elapsed', 'Elapsed time', 'Elapsed',
                        '{:.3f}', 'hours'),
                ])
            else:
                raise CalculatorError('Unknown version.')

        elif mode == self.CALC_RMS_FROM_ELAPSED_TIME:
            if version in (1, 2):
                outputs.extend([
                    CalculatorValue(
                        'rms', 'Sensitivity', '\u03c3', '{:.3f}', 'K TA*'),
                ])
            else:
                raise CalculatorError('Unknown version.')

        elif mode == self.CALC_RMS_FROM_INT_TIME:
            if version in (1, 2):
                outputs.extend([
                    CalculatorValue(
                        'rms', 'Sensitivity', '\u03c3', '{:.3f}', 'K TA*'),
                    CalculatorValue(
                        'elapsed', 'Elapsed time', 'Elapsed',
                        '{:.3f}', 'hours'),
                ])
            else:
                raise CalculatorError('Unknown version.')

        else:
            raise CalculatorError('Unknown mode.')

        return outputs

    def get_extra_context(self):
        """
        Return extra information to be given to the view template.
        """

        return {
            'weather_bands': JCMTWeather.get_available(),
            'receivers': HeterodyneReceiver.get_all_receivers().values(),
            'map_modes': self.map_modes,
            'switch_modes': self.switch_modes,
            'jiggle_patterns': self.itc.get_jiggle_patterns(),
            'acsis_modes': self.acsis_modes,
            'int_time_minimum': self.itc.int_time_minimum,
            'position_types': self.position_type,
            'rv_systems': self.rv_systems,
        }

    def parse_input(self, mode, input_, defaults=None):
        """
        Parse inputs as obtained from the HTML form (typically unicode)
        and return values suitable for calculation (perhaps float).
        """

        receiver = self.get_receiver_by_name(input_['rx'], as_object=True)

        parsed = {}

        for field in self.get_inputs(mode):
            try:
                if field.code == 'freq':
                    parsed[field.code] = (
                        None if (input_[field.code] == '')
                        else float(input_[field.code]))

                elif field.code in ('res', 'pos', 'rms', 'tau', 'rv'):
                    parsed[field.code] = float(input_[field.code])

                elif field.code == 'dx':
                    if receiver.array is None:
                        parsed[field.code] = float(input_[field.code])
                    else:
                        # The "dx" input is disabled for array receivers:
                        # always use the pixel size.
                        parsed[field.code] = receiver.pixel_size

                elif field.code == 'dy':
                    if receiver.array is None:
                        parsed[field.code] = float(input_[field.code])
                    else:
                        parsed[field.code] = float(input_['dy_spacing'])

                elif field.code in ('dim_x', 'dim_y', 'int_time'):
                    parsed[field.code] = float(input_[field.code])

                elif field.code in ('n_pt'):
                    parsed[field.code] = int(input_[field.code])

                elif field.code == 'elapsed':
                    parsed[field.code] = parse_time(input_[field.code])

                else:
                    parsed[field.code] = input_[field.code]

            except ValueError:
                if (not input_[field.code]) and (defaults is not None):
                    parsed[field.code] = defaults[field.code]

                else:
                    raise UserError(
                        'Invalid value for {}.', field.name.lower())

        self._validate_position(parsed['pos'], parsed['pos_type'])

        map_mode = self.map_modes[parsed['mm']].id

        # Remove irrelevant input values for the given mode.
        if map_mode == HeterodyneITC.RASTER:
            parsed['n_pt'] = None
        else:
            parsed['dim_x'] = None
            parsed['dim_y'] = None
            parsed['dx'] = None
            parsed['dy'] = None

        if parsed['freq'] is not None:
            parsed['species'] = None
            parsed['trans'] = None
        elif '' in (parsed['species'], parsed['trans']):
            # If all lines are out of range, all entries in the transition
            # select control will be disabled, so there will be no input.
            raise UserError('Transition line not selected (or out of range).')

        return parsed

    def get_receiver_by_name(self, receiver_name, as_object=False):
        """
        Get a receiver by name.
        """
        for (rx_id, rx_info) in HeterodyneReceiver.get_all_receivers().items():
            if rx_info.name == receiver_name:
                if as_object:
                    return ReceiverInfoID(*rx_info, id=rx_id)
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
        elif input_['pos_type'] == 'zen':
            zenith_angle_deg = input_['pos']
        elif input_['pos_type'] == 'el':
            zenith_angle_deg = 90.0 - input_['pos']
        elif input_['pos_type'] == 'am':
            zenith_angle_deg = degrees(acos(1.0 / input_['pos']))
        else:
            raise UserError('Unknown source position type.')

        if input_['pos_type'] != 'zen':
            extra_output['zenith_angle'] = zenith_angle_deg

        # Determine redshift.
        try:
            rv_def = self.rv_systems[input_['rv_sys']].id
        except KeyError:
            raise UserError('Unknown radial velocity type.')

        if rv_def is None:
            redshift = input_['rv']

        else:
            try:
                redshift = self.itc.velocity_to_redshift(input_['rv'], rv_def)
            except HeterodyneITCError as e:
                raise UserError(e.args[0])

            if redshift != 0.0:
                extra_output['redshift'] = redshift

        # Determine sky frequency and resolution.
        rest_freq = input_['freq']
        if rest_freq is None:
            try:
                transitions = self.line_catalog[input_['species']]
                rest_freq = transitions[input_['trans']]
            except KeyError:
                raise UserError('Transition line not recognized.')

            extra_output['rest_freq'] = rest_freq

        if redshift == 0.0:
            sky_freq = rest_freq
        else:
            sky_freq = rest_freq / (1.0 + redshift)
            extra_output['sky_freq'] = sky_freq

        freq_resolution = input_['res']
        freq_res_unit = input_['res_unit']
        if freq_res_unit == 'MHz':
            sky_freq_res = freq_resolution

            if redshift == 0.0:
                rest_freq_res = sky_freq_res
            else:
                rest_freq_res = sky_freq_res * (1.0 + redshift)
                extra_output['rest_freq_res'] = rest_freq_res

            extra_output['velocity_res'] = \
                self.itc.freq_res_to_velocity(rest_freq, rest_freq_res)

        elif freq_res_unit == 'km/s':
            rest_freq_res = self.itc.velocity_to_freq_res(
                rest_freq, freq_resolution)
            extra_output['rest_freq_res'] = rest_freq_res

            if redshift == 0.0:
                sky_freq_res = rest_freq_res
            else:
                sky_freq_res = rest_freq_res / (1.0 + redshift)
                extra_output['sky_freq_res'] = sky_freq_res

        else:
            raise CalculatorError('Frequency units not recognised.')

        receiver = self.get_receiver_by_name(input_['rx'], as_object=True)

        if sky_freq < receiver.f_min:
            raise UserError(
                'The sky frequency ({:.3f} GHz) is below the minimum '
                'frequency ({} GHz) of this receiver.',
                sky_freq, receiver.f_min)

        elif sky_freq > receiver.f_max:
            raise UserError(
                'The sky frequency ({:.3f} GHz) is above the maximum '
                'frequency ({} GHz) of this receiver.',
                sky_freq, receiver.f_max)

        kwargs = {
            'receiver': receiver.id,
            'map_mode': self.map_modes[input_['mm']].id,
            'sw_mode': self.switch_modes[input_['sw']].id,
            'freq': sky_freq,
            'freq_res': sky_freq_res,
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
                    input_['rms'], tau_225=input_['tau'], **kwargs)

                output = {
                    'elapsed': result / 3600.0,
                }

            elif mode == self.CALC_RMS_FROM_ELAPSED_TIME:
                (result, extra) = self.itc.calculate_rms_for_elapsed_time(
                    input_['elapsed'] * 3600.0, tau_225=input_['tau'],
                    **kwargs)

                output = {
                    'rms': result,
                }

            elif mode == self.CALC_RMS_FROM_INT_TIME:
                (result, extra) = self.itc.calculate_rms_for_int_time(
                    input_['int_time'], tau_225=input_['tau'], **kwargs)

                output = {
                    'rms': result,
                    'elapsed': extra.pop('elapsed_time') / 3600.0,
                }

            else:
                raise CalculatorError('Unknown mode.')

        except HeterodyneITCError as e:
            raise UserError(e.args[0])

        weather_band_comparison = OrderedDict()
        kwargs['with_extra_output'] = False
        for (weather_band, weather_band_info) in \
                JCMTWeather.get_available().items():
            weather_band_result = {}
            for condition_name in ('rep', 'min', 'max'):
                condition_tau = getattr(weather_band_info, condition_name)
                if condition_tau is None:
                    weather_band_result[condition_name] = None
                    continue

                condition_result = None

                try:
                    if mode == self.CALC_TIME:
                        condition_result = \
                            self.itc.calculate_time(
                                input_['rms'], tau_225=condition_tau,
                                **kwargs) / 3600.0

                    elif mode == self.CALC_RMS_FROM_ELAPSED_TIME:
                        condition_result = \
                            self.itc.calculate_rms_for_elapsed_time(
                                input_['elapsed'] * 3600.0,
                                tau_225=condition_tau, **kwargs)

                    elif mode == self.CALC_RMS_FROM_INT_TIME:
                        condition_result = \
                            self.itc.calculate_rms_for_int_time(
                                input_['int_time'], tau_225=condition_tau,
                                **kwargs)

                except HeterodyneITCError as e:
                    pass

                weather_band_result[condition_name] = condition_result

            weather_band_comparison[weather_band] = weather_band_result

        primary_output = self.get_outputs(mode)[0]
        extra['wb_comparison'] = weather_band_comparison
        extra['wb_comparison_format'] = primary_output.format
        extra['wb_comparison_unit'] = primary_output.unit

        extra_output.update(extra)

        return CalculatorResult(output, extra_output)

    def condense_calculation(self, mode, version, calculation):
        self._condense_merge_values(calculation, (('pos', 'pos_type'),
                                                  ('res', 'res_unit')))

        self._condense_tau_band(calculation, 'tau')

        self._condense_rv_sys(calculation, 'rv', 'rv_sys')

    def _condense_rv_sys(self, calculation, code, code_sys):
        try:
            input_sys = calculation.input[code_sys]

        except KeyError:
            return

        if input_sys == 'z':
            calculation.inputs.replace_item_where(
                (lambda x: x.code == code),
                (lambda x: x._replace(
                    name='Redshift', abbr=None, unit=None)))

        else:
            system_name = self.rv_systems[input_sys].name

            calculation.inputs.replace_item_where(
                (lambda x: x.code == code),
                (lambda x: x._replace(
                    unit='{} {}'.format(x.unit, system_name))))

        calculation.inputs.delete_item_where(
            lambda x: x.code == code_sys)

    def view_line_catalog(self, db):
        """
        View handler for line catalog query function.

        This returns the line catalog (from the Heterodyne ITC module)
        in JSON format to make it available to the JavaScript managing
        the web interface.
        """

        return self.line_catalog_json
