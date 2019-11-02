# Copyright (C) 2015-2019 East Asian Observatory
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
from ..type.collection import MemberCollection
from ..type.enum import ProposalState
from ..type.simple import CalculatorResult, ProposalWithCode
from ..type.util import null_tuple
from ..web.query_encode import encode_query, decode_query
from ..web.util import HTTPError, HTTPForbidden, HTTPNotFound, HTTPRedirect, \
    flash, session, url_for
from .util import int_or_none
from . import auth


CalculationInfo = namedtuple(
    'CalculationInfo', ('id', 'parent_id', 'title', 'overwrite'))


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

    def view(
            self, db, mode, args, form,
            calculation=None, review_calculation=None, can=None):
        """
        Web view handler for a generic calculator.

        Accepts additional keyword arguments for use via the proposal and
        review calculation route view functions.

        This view handler tracks two sets of identifiers:

        * `for_proposal_id` / `for_reviewer_id`

          This is a proposal / review which we are definitely interacting with.
          I.e. it:

          - Is the parent of the calculation / review calculation
            given as a keyword argument.

          - Is the proposal / review to which a calculation was saved.

          - Is passed as a query parameter `proposal_id` / `reviewer_id`
            when the user follows a link from the proposal / review to add a
            calculation.

          - Is passed as posted form argument `for_proposal_id` /
            `for_reviewer_id`.  (This is a hidden parameter allowing
            the calculator to remember the value selected in any
            of the above ways.)

          - Is used to set up the title and "back to" links on the page.

        * `calculation_info.parent_id` / `review_calculation_info.parent_id`

          This is the value posted in the form `calculation_id` /
          `review_calculation_id` select input, giving the user's choice
          from the save area of the form (or as a hidden parameter when
          there is no output thus no save area).

          This value:

          - Is initialized when a calculation / review calculation is given
            as a keyword argument.

          - Is also initialized via query parameter when the user follows
            a link to add a calculation for a proposal / review.

          - Is otherwise initialized to the first review editable by the user
            for the proposal specified by `for_proposal_id`.
        """

        role_class = self.facility.get_reviewer_roles()
        auth_cache = {} if (can is None) else can.cache

        message = None

        inputs = self.get_inputs(mode)
        output = CalculatorResult(None, None)
        query_encoded = None

        for_proposal_id = None
        for_reviewer_id = None
        calculation_info = review_calculation_info = \
            null_tuple(CalculationInfo)._replace(title='')

        if calculation is not None:
            for_proposal_id = calculation.proposal_id

            fetched_version = calculation.version
            fetched_input = calculation.input

            calculation_info = null_tuple(CalculationInfo)._replace(
                id=calculation.id,
                parent_id=for_proposal_id,
                title=calculation.title,
                overwrite=can.edit)

        elif review_calculation is not None:
            for_reviewer_id = review_calculation.reviewer_id

            fetched_version = review_calculation.version
            fetched_input = review_calculation.input

            review_calculation_info = null_tuple(CalculationInfo)._replace(
                id=review_calculation.id,
                parent_id=for_reviewer_id,
                title=review_calculation.title,
                overwrite=can.edit)

        else:
            fetched_version = None
            fetched_input = None

        # If the user is logged in, determine whether there are any proposals
        # or reviews to which they can add calculator results.
        proposals = {}
        review_proposals = {}
        if 'user_id' in session and 'person' in session:
            proposals = db.search_proposal(
                facility_id=self.facility.id_,
                person_id=session['person']['id'], person_is_editor=True,
                state=ProposalState.editable_states()).map_values(
                    (lambda proposal: ProposalWithCode(
                        *proposal,
                        code=self.facility.make_proposal_code(db, proposal))),
                    filter_value=(lambda proposal: auth.for_proposal(
                        # Emulate search_proposal(with_members=True) behavior.
                        role_class, db, proposal._replace(
                            members=MemberCollection((
                                (proposal.member.id, proposal.member),))),
                        auth_cache=auth_cache,
                        allow_unaccepted_review=False).edit))

            review_proposals = db.search_proposal(
                facility_id=self.facility.id_,
                reviewer_person_id=session['person']['id'],
                with_reviewer_role=role_class.get_calc_roles(),
                state=ProposalState.review_states()).map_values(
                    (lambda proposal: ProposalWithCode(
                        *proposal,
                        code=self.facility.make_proposal_code(db, proposal))),
                    filter_value=(lambda proposal: auth.for_review(
                        role_class, db, proposal.reviewer, proposal,
                        auth_cache=auth_cache,
                        skip_membership_test=True,
                        allow_unaccepted=False).edit))

            # If the user is viewing a proposal calculation, but is a reviewer
            # for this proposal, default to saving to that review.
            if ((for_proposal_id is not None)
                    and (review_calculation_info.parent_id is None)):
                for review_proposal in review_proposals.values():
                    if review_proposal.id == for_proposal_id:
                        review_calculation_info = review_calculation_info._replace(
                            parent_id=review_proposal.reviewer.id)
                        break

        if form is not None:
            try:
                if 'for_proposal_id' in form:
                    for_proposal_id = int(form['for_proposal_id'])

                if 'for_reviewer_id' in form:
                    for_reviewer_id = int(form['for_reviewer_id'])

                calculation_info = calculation_info._replace(
                    id=int_or_none(form.get('calculation_id', '')),
                    parent_id=int_or_none(form.get('proposal_id', '')),
                    title=form.get('calculation_title', '').strip(),
                    overwrite=('calculation_overwrite' in form))

                review_calculation_info = review_calculation_info._replace(
                    id=int_or_none(form.get('review_calculation_id', '')),
                    parent_id=int_or_none(form.get('reviewer_id', '')),
                    title=form.get('review_calculation_title', '').strip(),
                    overwrite=('review_calculation_overwrite' in form))

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

                elif any(x in form for x in (
                        'submit_save', 'submit_save_redir',
                        'review_submit_save', 'review_submit_save_redir')):
                    # Run calculation to get the outputs to save.
                    parsed_input = self.parse_input(mode, input_values)

                    output = self(mode, parsed_input)

                    # Determine which kind of request this is.
                    if any(x in form for x in (
                            'submit_save', 'submit_save_redir')):
                        is_proposal = True
                        info = calculation_info
                        parents = proposals
                    else:
                        is_proposal = False
                        info = review_calculation_info
                        parents = review_proposals

                    is_redir = any(x in form for x in (
                        'submit_save_redir', 'review_submit_save_redir'))

                    if info.parent_id is None:
                        raise HTTPError('Parent identifier not specified.')

                    # We already checked access for the listed parents, so
                    # check that this is one of them.
                    proposal = parents.get(info.parent_id)
                    if proposal is None:
                        raise HTTPForbidden('Edit permission denied.')

                    # Prepare calculation values to be saved.
                    calc_kwargs = {
                        'mode': mode,
                        'version': self.version,
                        'input_': parsed_input,
                        'output': output.output,
                        'calc_version': self.get_calc_version(),
                        'title': info.title,
                    }

                    if info.overwrite:
                        # Check that the calculation is really for the right
                        # proposal or review.
                        try:
                            if is_proposal:
                                db.search_calculation(
                                    calculation_id=info.id,
                                    proposal_id=info.parent_id).get_single()
                            else:
                                db.search_review_calculation(
                                    review_calculation_id=info.id,
                                    reviewer_id=info.parent_id).get_single()
                        except NoSuchRecord:
                            raise UserError(
                                'Can not overwrite calculation: '
                                'calculation not found.')

                        if is_proposal:
                            db.update_calculation(
                                info.id, **calc_kwargs)
                        else:
                            db.update_review_calculation(
                                info.id, **calc_kwargs)

                    else:
                        if is_proposal:
                            new_id = db.add_calculation(
                                info.parent_id, self.id_, **calc_kwargs)

                            calculation_info = \
                                calculation_info._replace(id=new_id)
                        else:
                            new_id = db.add_review_calculation(
                                info.parent_id, self.id_, **calc_kwargs)

                            review_calculation_info = \
                                review_calculation_info._replace(id=new_id)

                    if is_redir:
                        flash('The calculation has been saved.')
                        if is_proposal:
                            raise HTTPRedirect(url_for(
                                '.proposal_view', proposal_id=info.parent_id,
                                _anchor='calculations'))
                        else:
                            raise HTTPRedirect(url_for(
                                '.review_edit', reviewer_id=info.parent_id,
                                _anchor='calculations'))

                    else:
                        if is_proposal:
                            for_proposal_id = info.parent_id
                            for_reviewer_id = None
                            extra_desc = ''
                        else:
                            for_proposal_id = None
                            for_reviewer_id = info.parent_id
                            extra_desc = 'the {} for'.format(
                                role_class.get_name_with_review(
                                    proposal.reviewer.role).lower())

                        flash(
                            'The calculation has been saved to {} proposal '
                            '{}: "{}".',
                            extra_desc, proposal.code, proposal.title)

                        query_encoded = self._encode_query(
                            inputs, parsed_input)

                else:
                    raise HTTPError('Unknown action.')

            except UserError as e:
                message = e.message

        else:
            # Following a link from a proposal or review -- store the
            # identifier in the "for_<parent>_id" variable.
            if 'proposal_id' in args:
                try:
                    for_proposal_id = int(args['proposal_id'])
                except ValueError:
                    raise HTTPError('Non-integer proposal_id query argument')
                calculation_info = calculation_info._replace(
                    parent_id=for_proposal_id)

            if 'reviewer_id' in args:
                try:
                    for_reviewer_id = int(args['reviewer_id'])
                except ValueError:
                    raise HTTPError('Non-integer reviewer_id query argument')
                review_calculation_info = review_calculation_info._replace(
                    parent_id=for_reviewer_id)

            # Following a link which describes a specific calculation -- get
            # the input, run the calculation and provide an encoded query.
            if 'query' in args:
                try:
                    (fetched_version, fetched_input) = self._decode_query(
                        mode, args['query'])
                except ParseError as e:
                    raise HTTPError(e.message)

            if fetched_input is not None:
                if fetched_version != self.version:
                    fetched_input = self.convert_input_version(
                        mode, fetched_version, fetched_input)

                try:
                    output = self(mode, fetched_input)

                    query_encoded = self._encode_query(inputs, fetched_input)

                except UserError as e:
                    message = e.message

            else:
                # When we didn't receive a form submission, get the default
                # values -- need to convert these to strings to match the
                # form input strings as explained above.
                fetched_input = self.get_default_input(mode)

            input_values = self.format_input(inputs, fetched_input)

        # If we have a reviewer ID, look for information about the proposal.
        for_proposal_code = None
        for_reviewer_role = None
        if for_reviewer_id is not None:
            proposal = review_proposals.get(for_reviewer_id)
            if proposal is not None:
                for_proposal_id = proposal.id
                for_proposal_code = proposal.code
                for_reviewer_role = proposal.reviewer.role

        # Or, if we have a specific proposal ID, see if we know its code.
        elif for_proposal_id is not None:
            proposal = proposals.get(for_proposal_id)
            if proposal is not None:
                for_proposal_code = proposal.code

            else:
                for review_proposal in review_proposals.values():
                    if review_proposal.id == for_proposal_id:
                        for_proposal_code = review_proposal.code
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
            'review_proposals': review_proposals,
            'for_proposal_code':  for_proposal_code,
            'for_proposal_id': for_proposal_id,
            'for_reviewer_id': for_reviewer_id,
            'for_reviewer_role': for_reviewer_role,
            'calculation': calculation_info,
            'review_calculation': review_calculation_info,
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

        return (version, values)
