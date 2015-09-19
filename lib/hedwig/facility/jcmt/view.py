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

from collections import OrderedDict
import re
from urllib import urlencode

from ...error import NoSuchRecord, UserError
from ...web.util import HTTPRedirect, flash, url_for
from ...view.util import organise_collection, with_proposal
from ...type import Link, ReviewerRole, ValidationMessage
from ..generic.view import Generic
from .calculator_heterodyne import HeterodyneCalculator
from .calculator_scuba2 import SCUBA2Calculator
from .type import JCMTInstrument, JCMTOptions, \
    JCMTRequest, JCMTRequestCollection, JCMTRequestTotal, \
    JCMTWeather


class JCMT(Generic):
    cadc_advanced_search = \
        'http://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/search/'

    omp_cgi_bin = 'http://omp.eao.hawaii.edu/cgi-bin/'

    options = OrderedDict((
        ('target_of_opp', 'Target of opportunity'),
        ('daytime', 'Daytime observation'),
        ('time_specific', 'Time-specific observation'),
    ))

    @classmethod
    def get_code(cls):
        return 'jcmt'

    def get_name(self):
        return 'JCMT'

    def make_proposal_code(self, db, proposal):
        return 'M{0}{1}{2:03d}'.format(
            proposal.semester_code, proposal.queue_code, proposal.number
        ).upper()

    def _parse_proposal_code(self, proposal_code):
        """
        Perform the parsing step of processing a proposal code.

        This splits the code into the semester code, queue code
        and proposal number.
        """

        try:
            m = re.match('M(\d\d[AB])([A-Z])(\d\d\d)', proposal_code)

            if not m:
                raise NoSuchRecord(
                    'Proposal code did not match expected pattern')

            (semester_code, queue_code, proposal_number) = m.groups()

            return (semester_code, queue_code, int(proposal_number))

        except ValueError:
            raise NoSuchRecord('Could not parse proposal code')

    def get_calculator_classes(self):
        return (SCUBA2Calculator, HeterodyneCalculator)

    def make_archive_search_url(self, ra_deg, dec_deg):
        """
        Make an URL to search the JSA at CADC.
        """

        position = '{:.5f} {:.5f}'.format(ra_deg, dec_deg)

        url = (
            self.cadc_advanced_search + '?' +
            urlencode({
                'Observation.collection': 'JCMT',
                'Plane.position.bounds@Shape1Resolver.value': 'ALL',
                'Plane.position.bounds': position,
            }) +
            '#resultTableTab')

        # Advanced Search doesn't seem to like + as part of the coordinates.
        return url.replace('+', '%20')

    def make_proposal_info_urls(self, proposal_code):
        """
        Generate links to the OMP and to CADC for a given proposal code.
        """

        return [
            Link(
                'OMP', self.omp_cgi_bin + 'projecthome.pl?' +
                urlencode({
                    'urlprojid': proposal_code,
                })),
            Link(
                'CADC', self.cadc_advanced_search + '?' +
                urlencode({
                    'Observation.collection': 'JCMT',
                    'Observation.proposal.id': proposal_code,
                }) + '#resultTableTab'),
        ]

    def make_review_guidelines_url(self, role):
        """
        Make an URL for the guidelines page in the included documentation,
        if the role is external.
        """

        if role == ReviewerRole.EXTERNAL:
            return url_for('help.review_page', page_name='external_jcmt',
                           _external=True)

        else:
            return super(JCMT, self).make_review_guidelines_url(role)

    def calculate_overall_rating(self, reviews):
        """
        Calculate the overall rating from a collection of reviewer
        records (including their reviews).
        """

        return reviews.get_overall_rating(include_unweighted=False)

    def calculate_affiliation_assignment(self, db, members, affiliations):
        """
        Calculate the fractional affiliation assignment for the members
        of a proposal.

        This acts like the Generic method which it overrides but applies
        the JCMT affiliation assignment rules.
        """

        affiliation_count = {}
        affiliation_total = 0.0

        # Find the PI (if present) and their affiliation.
        try:
            pi = members.get_pi()
            pi_affiliation = pi.affiliation_id

            # Ensure the PI has a "valid" affiliation as we will use it for
            # excluded-affiliation members.
            if ((pi_affiliation is None) or
                    (pi_affiliation not in affiliations) or
                    (affiliations[pi_affiliation].exclude)):
                pi_affiliation = 0

        except KeyError:
            pi = None
            pi_affiliation = 0

        # Determine maximum affiliation weight.
        max_weight = 0.0
        for affiliation in affiliations.values():
            if affiliation.exclude or (affiliation.weight is None):
                continue
            if affiliation.weight > max_weight:
                max_weight = affiliation.weight

        # Add up weighted affiliation counts for non-PI members.
        for member in members.values():
            # Skip the PI as we will process their affiliation separately.
            if (pi is not None) and (member.id == pi.id):
                continue

            affiliation = member.affiliation_id
            if (affiliation is None) or (affiliation not in affiliations):
                affiliation = 0
            elif affiliations[affiliation].exclude:
                # Members with excluded affiliations count as the PI's
                # affiliation.
                affiliation = pi_affiliation

            if affiliation == 0:
                # Weight "unknown" as the maximum of all the other weights. In
                # practise there should never be any members in this state.
                weight = max_weight
            else:
                weight = affiliations[affiliation].weight
                if weight is None:
                    weight = 0.0

            affiliation_count[affiliation] = \
                affiliation_count.get(affiliation, 0.0) + weight
            affiliation_total += weight

        if not affiliation_total:
            # We didn't find any non-PI members (or they had zero weight),
            # simply return the PI affiliation (which already defaulted to
            # 0 i.e. "unknown" if there is no PI).
            return {pi_affiliation: 1.0}

        if pi is not None:
            # 50% of the assigment is supposed to be apportioned to the PI
            # affiliation, so add the PI with the same weight as all the other
            # members combined.
            affiliation_count[pi_affiliation] = \
                affiliation_count.get(pi_affiliation, 0.0) + affiliation_total
            affiliation_total *= 2.0

        return {k: (v / affiliation_total)
                for (k, v) in affiliation_count.items()}

    def _view_proposal_extra(self, db, proposal):
        ctx = super(JCMT, self)._view_proposal_extra(db, proposal)

        requests = db.search_jcmt_request(proposal_id=proposal.id)

        option_values = db.get_jcmt_options(proposal_id=proposal.id)
        options = []
        if option_values is not None:
            for (option, option_name) in self.options.items():
                if getattr(option_values, option):
                    options.append(option_name)

        ctx.update({
            'requests': requests.to_table(),
            'jcmt_options': options,
            'jcmt_option_values': option_values,
        })

        return ctx

    def _validate_proposal_extra(self, db, proposal, extra):
        messages = []

        if not extra['requests'].table:
            messages.append(ValidationMessage(
                True,
                'No observing time has been requested.',
                'Edit the observing request',
                url_for('.request_edit', proposal_id=proposal.id)))

        skip_missing_targets = False
        if extra['jcmt_option_values'] is not None:
            skip_missing_targets = extra['jcmt_option_values'].target_of_opp

        messages.extend(super(JCMT, self)._validate_proposal_extra(
            db, proposal, extra, skip_missing_targets=skip_missing_targets,
            check_excluded_pi=True))

        return messages

    def _get_proposal_tabulation(self, db, call):
        tabulation = super(JCMT, self)._get_proposal_tabulation(db, call)

        total = 0.0
        total_weather = {}
        total_instrument = {}
        total_affiliation = {}

        accepted = 0.0
        accepted_weather = {}
        accepted_instrument = {}
        accepted_affiliation = {}

        affiliation_ids = [x.id for x in tabulation['affiliations']]

        for proposal in tabulation['proposals']:
            request = db.search_jcmt_request(
                proposal_id=proposal['id']).get_total()

            proposal['jcmt_request'] = request

            total += request.total
            if proposal['decision_accept']:
                accepted += request.total

            for (weather, time) in request.weather.items():
                total_weather[weather] = \
                    total_weather.get(weather, 0.0) + time
                if proposal['decision_accept']:
                    accepted_weather[weather] = \
                        accepted_weather.get(weather, 0.0) + time

            for (instrument, time) in request.instrument.items():
                total_instrument[instrument] = \
                    total_instrument.get(instrument, 0.0) + time
                if proposal['decision_accept']:
                    accepted_instrument[instrument] = \
                        accepted_instrument.get(instrument, 0.0) + time

            proposal_affiliations = proposal['affiliations']
            for affiliation in affiliation_ids:
                fraction = proposal_affiliations.get(affiliation)
                if fraction is not None:
                    total_affiliation[affiliation] = \
                        total_affiliation.get(affiliation, 0.0) + \
                        request.total * fraction

                    if proposal['decision_accept']:
                        accepted_affiliation[affiliation] = \
                            accepted_affiliation.get(affiliation, 0.0) + \
                            request.total * fraction

        tabulation.update({
            'jcmt_weathers': JCMTWeather.get_available(),
            'jcmt_instruments': JCMTInstrument.get_options(),
            'jcmt_request_total': JCMTRequestTotal(
                total=total, weather=total_weather,
                instrument=total_instrument),
            'jcmt_request_accepted': JCMTRequestTotal(
                total=accepted, weather=accepted_weather,
                instrument=accepted_instrument),
            'affiliation_total': total_affiliation,
            'affiliation_accepted': accepted_affiliation,
        })

        return tabulation

    @with_proposal(permission='edit')
    def view_request_edit(self, db, proposal, can, form, is_post):
        message = None

        records = db.search_jcmt_request(proposal_id=proposal.id)
        option_values = db.get_jcmt_options(proposal_id=proposal.id)
        if option_values is None:
            option_values = JCMTOptions(
                proposal.id, *((False,) * (len(JCMTOptions._fields) - 1)))

        if is_post:
            # Temporary dictionaries for new records.
            updated_records = {}
            added_records = {}

            for param in form:
                if not param.startswith('time_'):
                    continue
                id_ = param[5:]

                if id_.startswith('new_'):
                    request_id = int(id_[4:])
                    destination = added_records
                else:
                    request_id = int(id_)
                    destination = updated_records

                request_time = form[param]
                try:
                    request_time = float(request_time)
                except ValueError:
                    # Ignore parsing error for now so that we can leave
                    # whatever the user typed in to form for them to correct.
                    pass

                destination[request_id] = JCMTRequest(
                    request_id, proposal.id,
                    int(form['instrument_' + id_]),
                    int(form['weather_' + id_]),
                    request_time)

            records = organise_collection(JCMTRequestCollection,
                                          updated_records, added_records)

            option_update = {}
            for option in self.options.keys():
                option_update[option] = 'option_{}'.format(option) in form
            option_values = option_values._replace(**option_update)

            try:
                db.sync_jcmt_proposal_request(proposal.id, records)

                db.set_jcmt_options(**option_values._asdict())

                flash('The observing request has been saved.')

                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id,
                                           _anchor='request'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Observing Request',
            'message': message,
            'proposal_id': proposal.id,
            'requests': records.values(),
            'instruments': JCMTInstrument.get_options(),
            'weathers': JCMTWeather.get_available(),
            'options': self.options,
            'option_values': option_values,
            'proposal_code': self.make_proposal_code(db, proposal),
        }
