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

from collections import namedtuple, OrderedDict

from ukirt_itc import UKIRTImagPhotITC, UKIRTITCError

from ...type.misc import SectionedList
from ...type.simple import CalculatorMode, CalculatorResult, CalculatorValue
from ...view.calculator import BaseCalculator
from ...error import CalculatorError, UserError

SkyCondition = namedtuple('SkyCondition', ('id_', 'name'))
SourceType = namedtuple('SourceType', ('name', 'options'))


class ImagPhotCalculator(BaseCalculator):
    CALC_TIME = 1
    CALC_MAG = 2
    CALC_SNR = 3

    modes = OrderedDict((
        (CALC_TIME,
            CalculatorMode('time', 'Integration time required')),
        (CALC_MAG,
            CalculatorMode('mag', 'Magnitude for given time and SNR')),
        (CALC_SNR,
            CalculatorMode('snr', 'SNR for given time and magnitude')),
    ))

    instruments = OrderedDict((
        ('WFCAM', UKIRTImagPhotITC.WFCAM),
        ('UFTI', UKIRTImagPhotITC.UFTI),
        ('UIST', UKIRTImagPhotITC.UIST),
    ))

    sky_conditions = OrderedDict((
        ('dark', SkyCondition(UKIRTImagPhotITC.SKY_DARK, 'Dark')),
        ('grey', SkyCondition(UKIRTImagPhotITC.SKY_GREY, 'Grey')),
        ('bright', SkyCondition(UKIRTImagPhotITC.SKY_BRIGHT, 'Bright')),
    ))

    source_types = OrderedDict((
        ('pnt', SourceType('Point source', {'is_extended': False})),
        ('ext', SourceType('Extended', {'is_extended': True})),
    ))

    limiting_factors = {
        UKIRTImagPhotITC.LIMIT_BACKGROUND: 'background',
        UKIRTImagPhotITC.LIMIT_READOUT: 'readout',
    }

    version = 1

    @classmethod
    def get_code(cls):
        return 'imag_phot'

    def __init__(self, *args):
        """
        Construct calculator.

        Calls the superclass constructor and then initializes a
        UKIRT imaging photometry ITC object.

        Sets up filter availablity information in `self.filters`
        based on the ITC's get_available_filters method.
        """

        super(ImagPhotCalculator, self).__init__(*args)

        self.itc = UKIRTImagPhotITC()

        self.filters = OrderedDict()
        for (filter_, instruments) in self.itc.get_available_filters().items():
            self.filters[filter_] = {
                instrument_name: instrument in instruments
                for (instrument_name, instrument) in self.instruments.items()}

    def get_name(self):
        return 'Imaging Photometry ITC'

    def get_calc_version(self):
        return self.itc.get_version()

    def get_inputs(self, mode, version=None):
        if version is None:
            version = self.version

        inputs = SectionedList()

        if version == 1:
            inputs.extend([
                CalculatorValue(
                    'inst', 'Instrument', 'Inst.', '{}', None),
                CalculatorValue(
                    'filt', 'Filter', 'Filt.', '{}', None),
            ], section='inst', section_name='Instrument and Filter')

            inputs.extend([
                CalculatorValue(
                    'type', 'Source type', 'Type', '{}', None),
                CalculatorValue(
                    'am', 'Airmass', 'AM', '{:.1f}', None),
                CalculatorValue(
                    'sky', 'Sky brightness', 'Sky', '{}', None),
                CalculatorValue(
                    'seeing', 'Seeing', 'Seeing', '{}', '"'),
            ], section='src', section_name='Source and Conditions')

            inputs.extend([
                CalculatorValue(
                    'aper', 'Aperture', 'Aper.', '{:.1f}', '"'),
            ], section='obs', section_name='Observation')

            inputs.add_section('req', 'Requirement')

            if mode != self.CALC_TIME:
                inputs.append(CalculatorValue(
                    'int_time', 'Integration time',
                    'Int. time', '{:.3f}', 'seconds'), section='req')

            if mode != self.CALC_MAG:
                inputs.append(CalculatorValue(
                    'mag', 'Magnitude', 'Mag', '{:.3f}', None), section='req')

            if mode != self.CALC_SNR:
                inputs.append(CalculatorValue(
                    'snr', 'Signal-to-noise ratio',
                    'SNR', '{:.3f}', None), section='req')

        else:
            raise CalculatorError('Unknown version.')

        return inputs

    def get_default_input(self, mode):
        inputs = {
            'inst': 'WFCAM',
            'filt': 'Z',
            'am': 1.2,
            'type': 'pnt',
            'seeing': 0.9,
            'sky': 'grey',
            'aper': 2.0,
        }

        if mode != self.CALC_TIME:
            inputs['int_time'] = 60

        if mode != self.CALC_MAG:
            inputs['mag'] = 20

        if mode != self.CALC_SNR:
            inputs['snr'] = 5

        return inputs

    def get_form_input(self, inputs, form):
        default_input = self.get_default_input(self.CALC_TIME)

        values = {}

        for input_ in inputs:
            if input_.code in ('seeing', 'aper'):
                # These values are not present in extended source mode.
                if form['type'] == 'ext':
                    values[input_.code] = default_input[input_.code]
                else:
                    values[input_.code] = form[input_.code]

            else:
                values[input_.code] = form[input_.code]

        return values

    def parse_input(self, mode, input_, defaults=None):
        parsed = {}

        for field in self.get_inputs(mode):
            try:
                if field.code in ('am', 'int_time', 'mag', 'snr'):
                    parsed[field.code] = float(input_[field.code])

                elif field.code in ('seeing', 'aper'):
                    if input_['type'] == 'ext':
                        parsed[field.code] = None
                    else:
                        parsed[field.code] = float(input_[field.code])

                else:
                    parsed[field.code] = input_[field.code]

            except ValueError:
                if (not input_[field.code]) and (defaults is not None):
                    parsed[field.code] = defaults[field.code]

                else:
                    raise UserError('Invalid value for {}.', field.name)

        return parsed

    def format_input(self, inputs, values):
        defaults = self.get_default_input(self.CALC_TIME)

        return {
            x.code:
                x.format.format(values[x.code] if values[x.code] is not None
                                else defaults.get(x.code))
                for x in inputs}

    def convert_input_mode(self, mode, new_mode, input_):
        # This calculator always just has one output which also corresponds
        # to an input.  Therefore identify these outputs.
        old_outputs = self.get_outputs(mode)
        new_outputs = self.get_outputs(new_mode)

        if (len(old_outputs) != 1) or (len(new_outputs) != 1):
            raise CalculatorError(
                'Unexpected output parameters in mode change.')

        new_output = new_outputs[0].code
        old_output = old_outputs[0].code

        # Copy inputs and calculate old output.
        new_input = input_.copy()
        output = self(mode, input_).output

        # Switch the old output to an input and delete the input corresponding
        # to the new output.
        del new_input[new_output]
        new_input[old_output] = output[old_output]

        return new_input

    def convert_input_version(self, mode, old_version, input_):
        return input_

    def get_outputs(self, mode, version=None):
        if version is None:
            version = self.version

        if version == 1:
            if mode == self.CALC_TIME:
                return [CalculatorValue(
                    'int_time', 'Integration time',
                    'Int. time', '{:.3f}', 'seconds')]

            elif mode == self.CALC_MAG:
                return [CalculatorValue(
                    'mag', 'Magnitude',
                    'Mag', '{:.3f}', None)]

            elif mode == self.CALC_SNR:
                return [CalculatorValue(
                    'snr', 'Signal-to-noise ratio',
                    'SNR', '{:.3f}', None)]

            else:
                raise CalculatorError('Unknown mode.')

        else:
            raise CalculatorError('Unknown version.')

    def get_extra_context(self):
        return {
            'instruments': list(self.instruments.keys()),
            'filters': self.filters,
            'sky_conditions': self.sky_conditions,
            'source_types': self.source_types,
        }

    def __call__(self, mode, input_):
        kwargs = {
            'filter_': input_['filt'],
            'aperture': input_['aper'],
            'seeing': input_['seeing'],
            'airmass': input_['am'],
            'with_extra_output': True,
        }

        # Look up special options.
        try:
            kwargs['instrument'] = self.instruments[input_['inst']]
        except KeyError:
            raise UserError('Instrument not recognised.')

        try:
            kwargs['sky'] = self.sky_conditions[input_['sky']].id_
        except KeyError:
            raise UserError('Sky brightness not recognised.')

        try:
            kwargs.update(self.source_types[input_['type']].options)
        except KeyError:
            raise UserError('Source type not recognised.')

        # Add mode-specific options.
        if mode != self.CALC_TIME:
            kwargs['int_time'] = input_['int_time']

        if mode != self.CALC_MAG:
            kwargs['mag'] = input_['mag']

        if mode != self.CALC_SNR:
            kwargs['snr'] = input_['snr']

        # Call ITC calculation routine.
        try:
            output = {}

            if mode == self.CALC_TIME:
                (result, extra) = self.itc.calculate_time(**kwargs)
                output['int_time'] = result

            elif mode == self.CALC_MAG:
                (result, extra) = self.itc.calculate_magnitude(**kwargs)
                output['mag'] = result

            elif mode == self.CALC_SNR:
                (result, extra) = self.itc.calculate_snr(**kwargs)
                output['snr'] = result

            else:
                raise CalculatorError('Unknown mode.')

        except UKIRTITCError as e:
            raise UserError(e.args[0])

        # Look up name of the limiting factor.
        extra['limit'] = self.limiting_factors.get(extra['limit'], None)

        return CalculatorResult(output, extra)
