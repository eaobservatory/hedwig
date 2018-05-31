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

from collections import namedtuple

from ..error import NoSuchRecord, ParseError, UserError
from ..type.enum import ProposalState
from ..type.simple import CalculatorResult, ProposalWithCode
from ..web.query_encode import encode_query, decode_query
from ..web.util import HTTPError, HTTPForbidden, HTTPNotFound, HTTPRedirect, \
    flash, session, url_for
from . import auth


class BaseCalculator(object):
    def __init__(self, facility, id_):
        self.facility = facility
        self.id_ = id_

    @classmethod
    def get_code(cls):
        """
        Get the calculator "code".

        This is a short string used to uniquely identify the calculator
        within facilities which use it.  It will correspond to an entry
        in the "calculator" table and be used in URLs.
        """

        return NotImplementedError()

    def get_default_facility_code(self):
        """
        Get the code of the facility for which this calculator is
        designed.

        This is used by the
        :func:`~hedwig.web.blueprint.facility.make_calculator_view`
        function when constructing the names of the templates to use for
        the calculator view.
        If this method returns a value other than `None` then it
        is used as an additional facility directory in which to
        search for the calculator's HTML template.

        Calculators need only override this method if the calculator
        is intended to be used with multiple facilities.

        :return: a facility code if necessary, or `None` otherwise
        """

        return None

    def get_custom_routes(self):
        """
        Method used to find any custom routes required by this calculator.

        Note that the route information will automatically be prefixed
        as follows:

        * `template`: `<facility code>/calculator_<calculator code>_`
        * `rule`: `/calculator/<calculator code>/`
        * `endpoint`: `calc_<calculator code>_`

        :return: a list of RouteInfo tuples
        """

        return []

    def view(self, db, mode, args, form):
        """
        Web view handler for a generic calculator.
        """

        message = None

        inputs = self.get_inputs(mode)
        output = CalculatorResult(None, None)
        proposal_id = None
        for_proposal_id = None
        calculation_id = None
        calculation_title = ''
        overwrite = False
        query_encoded = None

        # If the user is logged in, determine whether there are any proposals
        # to which they can add calculator results.
        proposals = None
        if 'user_id' in session and 'person' in session:
            proposals = [
                ProposalWithCode(
                    *x, code=self.facility.make_proposal_code(db, x))
                for x in db.search_proposal(
                    facility_id=self.facility.id_,
                    person_id=session['person']['id'], person_is_editor=True,
                    state=ProposalState.editable_states()).values()]

        if form is not None:
            try:
                if 'proposal_id' in form:
                    proposal_id = int(form['proposal_id'])

                if 'for_proposal_id' in form:
                    for_proposal_id = int(form['for_proposal_id'])

                if 'calculation_title' in form:
                    calculation_title = form['calculation_title'].strip()

                if 'calculation_id' in form:
                    calculation_id = int(form['calculation_id'])

                if 'overwrite' in form:
                    overwrite = True

                # Work primarily with the un-parsed "input_values" so that,
                # in the event of a parsing error, we can still put the user
                # data back in the form for correction.
                input_values = self.get_form_input(inputs, form)

                if 'submit_mode' in form:
                    parsed_input = self.parse_input(
                        mode, input_values,
                        defaults=self.get_default_input(mode))

                    new_mode = int(form['mode'])

                    if not self.is_valid_mode(mode):
                        raise HTTPError('Invalid mode.')

                    if new_mode != mode:
                        # If the mode actually changed, convert the input
                        # and then create new formatted input values.
                        new_input = self.convert_input_mode(mode, new_mode,
                                                            parsed_input)

                        inputs = self.get_inputs(new_mode)
                        input_values = self.format_input(inputs, new_input)

                        mode = new_mode

                elif 'submit_calc' in form:
                    parsed_input = self.parse_input(mode, input_values)

                    output = self(mode, parsed_input)

                    query_encoded = self._encode_query(inputs, parsed_input)

                elif ('submit_save' in form) or ('submit_save_redir' in form):
                    parsed_input = self.parse_input(mode, input_values)

                    proposal_id = int(form['proposal_id'])

                    # Check access via the normal auth module.
                    proposal = db.get_proposal(self.facility.id_, proposal_id,
                                               with_members=True)

                    if not auth.for_proposal(
                            self.facility.get_reviewer_roles(),
                            db, proposal).edit:
                        raise HTTPForbidden(
                            'Edit permission denied for this proposal.')

                    output = self(mode, parsed_input)

                    if overwrite:
                        # Check that the calculation is really for the right
                        # proposal.
                        try:
                            calculation = db.get_calculation(calculation_id)
                        except NoSuchRecord:
                            raise UserError(
                                'Can not overwrite calculation: '
                                'calculation not found.')
                        if calculation.proposal_id != proposal_id:
                            raise UserError(
                                'Can not overwrite calculation: '
                                'it appears to be for a different proposal.')

                        db.update_calculation(
                            calculation_id,
                            mode=mode, version=self.version,
                            input_=parsed_input, output=output.output,
                            calc_version=self.get_calc_version(),
                            title=calculation_title)

                    else:
                        calculation_id = db.add_calculation(
                            proposal_id, self.id_, mode, self.version,
                            parsed_input, output.output,
                            self.get_calc_version(), calculation_title)

                    if 'submit_save_redir' in form:
                        flash('The calculation has been saved.')
                        raise HTTPRedirect(url_for('.proposal_view',
                                                   proposal_id=proposal_id,
                                                   _anchor='calculations'))

                    else:
                        for_proposal_id = proposal_id

                        flash(
                            'The calculation has been saved to proposal '
                            '{}: "{}".',
                            self.facility.make_proposal_code(db, proposal),
                            proposal.title)

                        query_encoded = self._encode_query(
                            inputs, parsed_input)

                else:
                    raise HTTPError('Unknown action.')

            except UserError as e:
                message = e.message

        else:
            if 'proposal_id' in args:
                try:
                    proposal_id = int(args['proposal_id'])
                except ValueError:
                    raise HTTPError('Non-integer proposal_id query argument')
                for_proposal_id = proposal_id

            if 'calculation_id' in args:
                try:
                    calculation = db.get_calculation(
                        int(args['calculation_id']))
                except NoSuchRecord:
                    raise HTTPNotFound('Calculation not found.')

                if calculation.calculator_id != self.id_:
                    raise HTTPError(
                        'Calculation is from a different calculator.')

                if calculation.mode != mode:
                    raise HTTPError(
                        'Calculation is from a different mode.')

                # Check authorization to see this calculation.
                proposal = db.get_proposal(
                    self.facility.id_, calculation.proposal_id,
                    with_members=True, with_reviewers=True)

                can = auth.for_proposal(self.facility.get_reviewer_roles(),
                                        db, proposal)
                if not can.view:
                    raise HTTPForbidden('Access denied for that proposal.')

                proposal_id = proposal.id
                for_proposal_id = proposal_id

                if calculation.version == self.version:
                    default_input = calculation.input
                else:
                    default_input = self.convert_input_version(
                        mode, calculation.version, calculation.input)

                calculation_id = calculation.id
                calculation_title = calculation.title
                overwrite = can.edit

                try:
                    output = self(mode, default_input)
                except UserError as e:
                    message = e.message

                query_encoded = self._encode_query(inputs, default_input)

            elif 'query' in args:
                try:
                    default_input = self._decode_query(mode, args['query'])
                except ParseError as e:
                    raise HTTPError(e.message)

                try:
                    output = self(mode, default_input)
                except UserError as e:
                    message = e.message

                query_encoded = self._encode_query(inputs, default_input)

            else:
                # When we didn't receive a form submission, get the default
                # values -- need to convert these to strings to match the
                # form input strings as explained above.
                default_input = self.get_default_input(mode)

            input_values = self.format_input(inputs, default_input)

        # If we have a specific proposal ID, see if we know its code.
        for_proposal_code = None
        if (for_proposal_id is not None) and (proposals is not None):
            for proposal in proposals:
                if proposal.id == for_proposal_id:
                    for_proposal_code = proposal.code
                    break

        ctx = {
            'title': self.get_name(),
            'message': message,
            'modes': self.modes,
            'current_mode': mode,
            'inputs': inputs,
            'outputs': self.get_outputs(mode),
            'input_values': input_values,
            'output_values': output.output,
            'output_extra': output.extra,
            'proposals': proposals,
            'proposal_id': proposal_id,
            'for_proposal_code': for_proposal_code,
            'for_proposal_id': for_proposal_id,
            'calculation_id': calculation_id,
            'calculation_title': calculation_title,
            'overwrite': overwrite,
            'query_encoded': query_encoded,
        }

        ctx.update(self.get_extra_context())

        return ctx

    def format_input(self, inputs, values):
        """
        Format the calculator inputs for display in the input form.

        This is because the input form needs to take string inputs so that
        we can give it back malformatted user input strings for correction.
        """

        return {x.code: x.format.format(values[x.code]) for x in inputs}

    def get_extra_context(self):
        """
        Method which subclasses can override to supply extra context
        information to the view template.
        """

        return {}

    def get_form_input(self, inputs, form):
        """
        Extract the input values from the submitted form.

        This example would be sufficient in the case of some input
        text boxes, but subclasses need to override to support other
        form elements such as checkboxes.
        """

        return {x.code: form[x.code] for x in inputs}

    def get_mode_info(self, mode):
        """
        Get mode information named tuple for the given mode.
        """

        return self.modes[mode]

    def is_valid_mode(self, mode):
        """
        Determine whether the given mode is valid.

        Does this by seeing if it appears in the calculator's "modes"
        attribute (normally a dictionary).
        """

        return mode in self.modes

    def condense_calculation(self, mode, version, calculation):
        """
        Method which can be called before an existing calculation
        result is to be displayed in a compact form.

        Takes a "CalculationExtra" object, which has "inputs", "input",
        "outputs" and "output" attributes and modifies it in place.
        """

        pass

    def _encode_query(self, inputs, values):
        # Convert the inputs from a dictionary to a list for compactness, by
        # placing the values in the order of the sorted keys.
        keys = sorted((x.code for x in inputs))
        query = [self.version]
        query.extend(values.get(x) for x in keys)

        try:
            return encode_query(query)
        except:
            # Suppress the error so that the calculation result is still
            # shown.  Ideally the error would be logged at this point.
            return None

    def _decode_query(self, mode, query):
        unpacked = decode_query(query)
        version = unpacked[0]

        inputs = self.get_inputs(mode, version)
        keys = sorted((x.code for x in inputs))

        if len(keys) != (len(unpacked) - 1):
            raise ParseError('Query encodes an unexpected number of values.')

        # Reassemble the values dictionary.
        values = dict(zip(keys, unpacked[1:]))

        if version != self.version:
            values = self.convert_input_version(mode, version, values)

        return values
