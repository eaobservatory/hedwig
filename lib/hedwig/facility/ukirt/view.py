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

import re

from ...error import NoSuchRecord, NoSuchValue, ParseError, UserError
from ..eao.view import EAOFacility
from .calculator_imag_phot import ImagPhotCalculator
from .type import \
    UKIRTCallType


class UKIRT(EAOFacility):
    @classmethod
    def get_code(cls):
        return 'ukirt'

    def get_name(self):
        return 'UKIRT'

    def get_definite_name(self):
        return self.get_name()

    def get_call_types(self):
        return UKIRTCallType

    def get_calculator_classes(self):
        return (ImagPhotCalculator,)

    def get_target_tool_classes(self):
        return ()

    def make_proposal_code(self, db, proposal):
        type_class = self.get_call_types()
        type_code = type_class.get_code(proposal.call_type)

        components = [
            proposal.semester_code, proposal.queue_code, proposal.number]

        if type_code is None:
            return 'U/{}/{}{:03d}'.format(*components).upper()

        return 'U/{}/{}/{}{:03d}'.format(type_code, *components).upper()

    def _parse_proposal_code(self, proposal_code):
        type_class = self.get_call_types()

        try:
            m = re.match('U/(?:([A-Z]+)/)?(\d\d[ABXYZW])/([A-Z]+)(\d+)',
                         proposal_code)

            if not m:
                raise ParseError(
                    'Proposal code did not match expected pattern')

            (call_type, semester_code, queue_code,
                proposal_number) = m.groups()

            return (semester_code, queue_code, type_class.by_code(call_type),
                    int(proposal_number))

        except ValueError:
            raise ParseError('Could not parse proposal number ')

        except NoSuchValue:
            raise ParseError('Did not recognise call type code')
