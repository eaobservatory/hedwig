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

from collections import namedtuple

from ..error import NoSuchRecord, UserError
from ..type import CalculatorResult, Proposal, ProposalState
from ..web.util import HTTPError, HTTPForbidden, HTTPNotFound, HTTPRedirect, \
    flash, session, url_for
from . import auth

ProposalWithCode = namedtuple('ProposalWithCode', Proposal._fields + ('code',))


class BaseCalculator(object):
    def __init__(self, facility, id_):
        self.facility = facility
        self.id_ = id_

    def view(self, db, mode, args, form):
        """
        Web view handler for a generic calculator.
        """

        message = None

        inputs = self.get_inputs(mode)
        output = CalculatorResult(None, None)
        proposal_id = None
        calculation_id = None
        calculation_proposal = None
        calculation_title = ''
        overwrite = False

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

                if 'calculation_title' in form:
                    calculation_title = form['calculation_title']

                if 'calculation_id' in form:
                    calculation_id = int(form['calculation_id'])

                if 'calculation_proposal' in form:
                    calculation_proposal = int(form['calculation_proposal'])

                if 'overwrite' in form:
                    overwrite = True

                # Work primarily with the un-parsed "input_values" so that,
                # in the event of a parsing error, we can still put the user
                # data back in the form for correction.
                input_values = self.get_form_input(inputs, form)
                parsed_input = self.parse_input(mode, input_values)

                if 'submit_mode' in form:
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
                    output = self(mode, parsed_input)

                elif ('submit_save' in form) or ('submit_save_redir' in form):
                    proposal_id = int(form['proposal_id'])

                    # Check access via the normal auth module.
                    proposal = db.get_proposal(self.facility.id_, proposal_id,
                                               with_members=True)

                    if not auth.for_proposal(db, proposal).edit:
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
                            title=calculation_title)

                    else:
                        db.add_calculation(
                            proposal_id, self.id_, mode, self.version,
                            parsed_input, output.output, calculation_title)

                    if 'submit_save_redir' in form:
                        flash('The calculation has been saved.')
                        raise HTTPRedirect(url_for('.proposal_view',
                                                   proposal_id=proposal_id))

                    else:
                        flash(
                            'The calculation has been saved to proposal '
                            '{}: "{}".',
                            self.facility.make_proposal_code(db, proposal),
                            proposal.title)

                else:
                    raise HTTPError('Unknown action.')

            except UserError as e:
                message = e.message

        else:
            if 'proposal_id' in args:
                proposal_id = args['proposal_id']

            if 'calculation_id' in args:
                try:
                    calculation = db.get_calculation(
                        int(args['calculation_id']))
                except NoSuchRecord:
                    raise HTTPNotFound('Calculation not found.')

                # Check authorization to see this calculation.
                proposal = db.get_proposal(
                    self.facility.id_, calculation.proposal_id,
                    with_members=True)

                can = auth.for_proposal(db, proposal)
                if not can.view:
                    raise HTTPForbidden('Access denied for that proposal.')

                proposal_id = proposal.id

                if calculation.version == self.version:
                    default_input = calculation.input
                else:
                    default_input = self.convert_input_version(
                        calculation.version, calculation.input)

                output = self(mode, default_input)
                calculation_id = calculation.id
                calculation_proposal = proposal_id
                calculation_title = calculation.title
                overwrite = can.edit

            else:
                # When we didn't receive a form submission, get the default
                # values -- need to convert these to strings to match the
                # form input strings as explained above.
                default_input = self.get_default_input(mode)

            input_values = self.format_input(inputs, default_input)

        ctx = {
            'title': self.get_name(),
            'target': url_for('.calc_{}_{}'.format(self.get_code(),
                                                   self.modes[mode].code)),
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
            'calculation_id': calculation_id,
            'calculation_proposal': calculation_proposal,
            'calculation_title': calculation_title,
            'overwrite': overwrite,
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
