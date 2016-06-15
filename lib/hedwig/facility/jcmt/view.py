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

from collections import defaultdict, namedtuple, OrderedDict
from itertools import count, izip
import re
from urllib import urlencode

from ...error import NoSuchRecord, UserError
from ...web.util import HTTPRedirect, flash, url_for
from ...view.util import organise_collection, with_call_review, with_proposal
from ...type.collection import ResultTable
from ...type.enum import AffiliationType, ProposalState
from ...type.simple import Link, ValidationMessage
from ...type.util import null_tuple
from ..generic.view import Generic
from .calculator_heterodyne import HeterodyneCalculator
from .calculator_scuba2 import SCUBA2Calculator
from .type import \
    JCMTAvailable, JCMTAvailableCollection, \
    JCMTInstrument, JCMTOptions, \
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
        ('polarimetry', 'Polarimetry'),
    ))

    @classmethod
    def get_code(cls):
        return 'jcmt'

    def get_name(self):
        return 'JCMT'

    def make_proposal_code(self, db, proposal):
        return 'M{}{}{:03d}'.format(
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

        role_class = self.get_reviewer_roles()

        if role == role_class.EXTERNAL:
            return url_for('help.review_page', page_name='external_jcmt',
                           _external=True)

        else:
            return super(JCMT, self).make_review_guidelines_url(role)

    def calculate_overall_rating(self, reviews, with_std_dev=False):
        """
        Calculate the overall rating from a collection of reviewer
        records (including their reviews).
        """

        return reviews.get_overall_rating(include_unweighted=False,
                                          with_std_dev=with_std_dev)

    def calculate_affiliation_assignment(self, db, members, affiliations):
        """
        Calculate the fractional affiliation assignment for the members
        of a proposal.

        This acts like the Generic method which it overrides but applies
        the JCMT affiliation assignment rules.
        """

        affiliation_count = defaultdict(float)
        affiliation_total = 0.0

        # Determine total and maximum affiliation weight.
        total_weight = 0.0
        max_weight = 0.0
        affiliation_weight = {}
        for affiliation in affiliations.values():
            if ((affiliation.type == AffiliationType.EXCLUDED) or
                    (affiliation.type == AffiliationType.SHARED) or
                    (affiliation.weight is None)):
                continue

            total_weight += affiliation.weight

            if affiliation.weight > max_weight:
                max_weight = affiliation.weight

            affiliation_weight[affiliation.id] = affiliation.weight

        # Determine affiliation fractions, in case there are any proposal
        # members with shared affiliation.
        affiliation_fraction = {k: v / total_weight
                                for (k, v) in affiliation_weight.items()}

        # Find the PI (if present) and their affiliation.
        try:
            pi = members.get_pi()
            pi_affiliation = pi.affiliation_id

            # Ensure the PI has a "valid" affiliation as we will use it for
            # excluded-affiliation members.
            if ((pi_affiliation is None) or
                    (pi_affiliation not in affiliations) or
                    (affiliations[pi_affiliation].type ==
                        AffiliationType.EXCLUDED)):
                pi_affiliation = 0

            elif affiliations[pi_affiliation].type == AffiliationType.SHARED:
                # Use special value "None" for shared affiliation (not to be
                # confused with "0" meaning unknown).
                pi_affiliation = None

        except KeyError:
            # KeyError is raised if MemberCollection.get_pi fails to find a
            # PI: record that there is no PI and their affiliation is therefore
            # unknown (represented by "0").
            pi = None
            pi_affiliation = 0

        # Add up weighted affiliation counts for non-PI members.
        for member in members.values():
            # Skip the PI as we will process their affiliation separately.
            if (pi is not None) and (member.id == pi.id):
                continue

            affiliation = member.affiliation_id
            if (affiliation is None) or (affiliation not in affiliations):
                affiliation = 0
            elif affiliations[affiliation].type == AffiliationType.EXCLUDED:
                # Members with excluded affiliations count as the PI's
                # affiliation.
                affiliation = pi_affiliation
            elif affiliations[affiliation].type == AffiliationType.SHARED:
                affiliation = None

            if affiliation is None:
                # Affiliation is shared -- assign by squared affiliation
                # fractions because the CoI's affiliation is shared
                # based on the affiliation weights and each of those
                # affiliations also gets weighted by the same weight.
                for (aff_id, aff_frac) in affiliation_fraction.items():
                    affiliation_count[aff_id] += aff_frac * max_weight

                affiliation_total += max_weight

            else:
                # Non-shared affiliation -- determine weighting factor to use.
                if affiliation == 0:
                    # Weight "unknown" as the maximum of all the other
                    # weights. In practise there should never be any members
                    # in this state.
                    weight = max_weight
                else:
                    weight = affiliations[affiliation].weight
                    if weight is None:
                        weight = 0.0

                affiliation_count[affiliation] += weight
                affiliation_total += weight

        if not affiliation_total:
            # We didn't find any non-PI members (or they had zero weight),
            # so set the PI weight to 1.0.  Otherwise prepare to add the PI
            # affiliation at the same total weight.  But if there is also
            # no PI, return 100% unknown.
            if pi is None:
                return {0: 1.0}

            pi_weight = 1.0

        else:
            pi_weight = affiliation_total

        if pi is not None:
            # 50% of the assigment is supposed to be apportioned to the PI
            # affiliation, so add the PI with the same weight as all the other
            # members combined.
            if pi_affiliation is None:
                # Affiliation is shared -- assign by affiliation fractions
                # multiplied by the PI's weighting factor.
                for (aff_id, aff_frac) in affiliation_fraction.items():
                    affiliation_count[aff_id] += pi_weight * aff_frac
            else:
                affiliation_count[pi_affiliation] += pi_weight

            affiliation_total += pi_weight

        return {k: (v / affiliation_total)
                for (k, v) in affiliation_count.items()}

    def _view_proposal_extra(self, db, proposal):
        ctx = super(JCMT, self)._view_proposal_extra(db, proposal)

        requests = db.search_jcmt_request(proposal_id=proposal.id)

        option_values = db.get_jcmt_options(proposal_id=proposal.id)

        ctx.update({
            'requests': requests.to_table(),
            'jcmt_options': self._get_option_names(option_values),
            'jcmt_option_values': option_values,
        })

        return ctx

    def _get_option_names(self, option_values):
        options = []

        if option_values is not None:
            for (option, option_name) in self.options.items():
                if getattr(option_values, option):
                    options.append(option_name)

        return options

    def _view_proposal_feedback_extra(self, db, proposal):
        ctx = super(JCMT, self)._view_proposal_feedback_extra(db, proposal)

        if proposal.state == ProposalState.ACCEPTED:
            allocations = db.search_jcmt_allocation(
                proposal_id=proposal.id).to_table()
        else:
            allocations = null_tuple(ResultTable)

        ctx.update({
            'jcmt_allocations': allocations,
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

    def _get_proposal_tabulation(self, db, call, can, auth_cache,
                                 with_extra=False):
        tabulation = super(JCMT, self)._get_proposal_tabulation(
            db, call, can, auth_cache, with_extra)

        exempt = JCMTRequestTotal(total=0.0, weather=defaultdict(float),
                                  instrument=defaultdict(float),
                                  total_non_free=None)
        accepted = JCMTRequestTotal(total=0.0, weather=defaultdict(float),
                                    instrument=defaultdict(float),
                                    total_non_free=None)
        total = JCMTRequestTotal(total=0.0, weather=defaultdict(float),
                                 instrument=defaultdict(float),
                                 total_non_free=None)
        original = JCMTRequestTotal(total=0.0, weather=defaultdict(float),
                                    instrument=defaultdict(float),
                                    total_non_free=None)

        accepted_affiliation = defaultdict(float)
        total_affiliation = defaultdict(float)
        original_affiliation = defaultdict(float)

        affiliation_ids = [x.id for x in tabulation['affiliations']]

        for proposal in tabulation['proposals']:
            request = db.search_jcmt_request(
                proposal_id=proposal['id']).get_total()

            proposal['jcmt_request'] = request

            if with_extra:
                proposal['jcmt_options'] = self._get_option_names(
                    db.get_jcmt_options(proposal_id=proposal['id']))

            # Read the committee's time allocation, but only if there is one.
            # Since decisions can now be returned to "undecided", we need
            # to search for allocations regardless of decision presence.
            allocation = None
            proposal_accepted = proposal['decision_accept']
            proposal_exempt = proposal['decision_exempt']
            allocation_records = db.search_jcmt_allocation(
                proposal_id=proposal['id'])
            if allocation_records:
                allocation = allocation_records.get_total()

            proposal['jcmt_allocation'] = allocation
            proposal['jcmt_allocation_different'] = \
                ((allocation is not None) and (allocation != request))

            if proposal_accepted:
                if proposal_exempt:
                    exempt = exempt._replace(
                        total=(exempt.total + allocation.total))

                accepted = accepted._replace(
                    total=(accepted.total + allocation.total))

            if allocation is not None:
                total = total._replace(total=(total.total + allocation.total))
            else:
                total = total._replace(total=(total.total + request.total))

            original = original._replace(
                total=(original.total + request.total))

            for (weather, time) in request.weather.items():
                original.weather[weather] += time
                if allocation is None:
                    total.weather[weather] += time

            if allocation is not None:
                for (weather, time) in allocation.weather.items():
                    if proposal_accepted:
                        if proposal_exempt:
                            exempt.weather[weather] += time
                        accepted.weather[weather] += time
                    total.weather[weather] += time

            for (instrument, time) in request.instrument.items():
                original.instrument[instrument] += time
                if allocation is None:
                    total.instrument[instrument] += time

            if allocation is not None:
                for (instrument, time) in allocation.instrument.items():
                    if proposal_accepted:
                        if proposal_exempt:
                            exempt.instrument[instrument] += time
                        accepted.instrument[instrument] += time
                    total.instrument[instrument] += time

            proposal_affiliations = proposal['affiliations']
            for affiliation in affiliation_ids:
                fraction = proposal_affiliations.get(affiliation)
                if fraction is None:
                    continue

                original_affiliation[affiliation] += \
                    request.total_non_free * fraction

                if allocation is None:
                    total_affiliation[affiliation] += \
                        request.total_non_free * fraction

                else:
                    total_affiliation[affiliation] += \
                        allocation.total_non_free * fraction

                    if proposal_accepted and not proposal_exempt:
                        accepted_affiliation[affiliation] += \
                            allocation.total_non_free * fraction

        # Fetch the amount of time available and distribute it among the
        # affiliations under the assumption that the affiliation weights
        # are percentages.
        available = db.search_jcmt_available(call_id=call.id).get_total()

        total_weight = 0.0
        available_affiliation = {}

        for affiliation in tabulation['affiliations']:
            if (affiliation.id == 0) or (affiliation.weight is None):
                continue

            total_weight += affiliation.weight
            available_affiliation[affiliation.id] = \
                available.total_non_free * affiliation.weight / 100.0

        # Assign the remaining time to the "Unknown" affiliation.
        available_affiliation[0] = \
            (1.0 - (total_weight / 100.0)) * available.total_non_free

        tabulation.update({
            'jcmt_weathers': JCMTWeather.get_available(),
            'jcmt_instruments': JCMTInstrument.get_options(),
            'jcmt_exempt_total': exempt,
            'jcmt_accepted_total': accepted,
            'jcmt_request_total': total,
            'jcmt_request_original': original,
            'jcmt_available': available,
            'affiliation_accepted': accepted_affiliation,
            'affiliation_available': available_affiliation,
            'affiliation_total': total_affiliation,
            'affiliation_original': original_affiliation,
        })

        return tabulation

    def _get_proposal_tabulation_titles(self, tabulation):
        return (
            super(JCMT, self)._get_proposal_tabulation_titles(tabulation) +
            ['Options', 'Request'] +
            [x.name for x in tabulation['jcmt_weathers'].values()] +
            ['Unknown weather'] +
            [x for x in tabulation['jcmt_instruments'].values()] +
            ['Unknown instrument'] +
            ['Allocation'] +
            [x.name for x in tabulation['jcmt_weathers'].values()] +
            ['Unknown weather'] +
            [x for x in tabulation['jcmt_instruments'].values()] +
            ['Unknown instrument']
        )

    def _get_proposal_tabulation_rows(self, tabulation):
        weathers = list(tabulation['jcmt_weathers'].keys()) + [0]
        instruments = list(tabulation['jcmt_instruments'].keys()) + [0]

        for (row, proposal) in izip(
                super(JCMT, self)._get_proposal_tabulation_rows(tabulation),
                tabulation['proposals']):
            request = proposal['jcmt_request']
            allocation = proposal['jcmt_allocation']
            if (allocation is None) or (not proposal['decision_accept']):
                allocation = JCMTRequestTotal(None, {}, {}, {})

            yield (
                row +
                [
                    ', '.join(proposal['jcmt_options']),
                    request.total,
                ] +
                [request.weather.get(x) for x in weathers] +
                [request.instrument.get(x) for x in instruments] +
                [allocation.total] +
                [allocation.weather.get(x) for x in weathers] +
                [allocation.instrument.get(x) for x in instruments]
            )

    @with_proposal(permission='edit')
    def view_request_edit(self, db, proposal, can, form):
        message = None

        records = db.search_jcmt_request(proposal_id=proposal.id)
        option_values = db.get_jcmt_options(proposal_id=proposal.id)
        if option_values is None:
            option_values = JCMTOptions(
                proposal.id, *((False,) * (len(JCMTOptions._fields) - 1)))

        if form is not None:
            records = self._read_request_form(proposal, form)

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

    def _read_request_form(self, proposal, form, skip_blank_time=False):
        """
        Read a set of JCMT observing requests (or time allocations) from
        the form and return as a JCMTRequestCollection object.

        Can optionally skip entries with blank times, rather than leaving
        them as non-floats to cause an error to be raised later.
        """

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

            if skip_blank_time and (not request_time):
                continue

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

        return organise_collection(JCMTRequestCollection,
                                   updated_records, added_records)

    def _view_proposal_decision_get(self, db, proposal, form):
        """
        Read the JCMT observing allocation from the form without raising
        parsing errors yet.
        """

        return self._read_request_form(proposal, form, skip_blank_time=True)

    def _view_proposal_decision_save(self, db, proposal, info):
        """
        Store the JCMT observing allocation.
        """

        if proposal.decision_accept and (not info.get_total().total):
            raise UserError('An accepted proposal should not have '
                            'zero total time allocation.')

        db.sync_jcmt_proposal_allocation(proposal_id=proposal.id,
                                         records=info)

    def _view_proposal_decision_extra(self, db, proposal, info):
        """
        Generate template context for the JCMT allocation on the
        decision page.
        """

        original_request = db.search_jcmt_request(proposal_id=proposal.id)
        is_prefilled = False

        if info is None:
            allocations = db.search_jcmt_allocation(proposal_id=proposal.id)

            # If there is no allocation saved, load the original request.
            if not allocations:
                # Re-write IDs as None.
                allocations = JCMTRequestCollection((
                    (n, r._replace(id=None))
                    for (n, r) in izip(count(1), original_request.values())))
                is_prefilled = True

        else:
            allocations = info

        return {
            'original_request': original_request.to_table(),
            'is_prefilled': is_prefilled,
            'allocations': allocations.values(),
            'instruments': JCMTInstrument.get_options(),
            'weathers': JCMTWeather.get_available(),
        }

    @with_call_review(permission='edit')
    def view_review_call_available(self, db, call, can, auth_cache, form):
        message = None

        weathers = JCMTWeather.get_available()
        available = db.search_jcmt_available(call_id=call.id)

        if form is not None:
            updated_records = {}
            added_records = {}
            try:
                for weather_id in weathers.keys():
                    time = form.get('available_{}'.format(weather_id), '')
                    if time == '':
                        continue
                    try:
                        time = float(time)
                    except ValueError:
                        # Ignore parsing error for now so that we can return
                        # the string to the user for correction.
                        pass

                    for record in available.values():
                        if record.weather == weather_id:
                            updated_records[record.id] = record._replace(
                                time=time)
                            break
                    else:
                        added_records[weather_id] = JCMTAvailable(
                            id=None, call_id=None,
                            weather=weather_id, time=time)

                available = organise_collection(JCMTAvailableCollection,
                                                updated_records, added_records)

                updates = db.sync_jcmt_call_available(call.id, available)

                if any(updates):
                    flash('The time available has been saved.')

                raise HTTPRedirect(url_for('.review_call', call_id=call.id))

            except UserError as e:
                message = e.message

        # Straightforwardly organize available time by weather band (assuming
        # no duplicated) rather than using get_total so that we can allow for
        # unparsed strings still being present.
        available_weather = {}
        for record in available.values():
            weather = record.weather
            if not JCMTWeather.get_info(weather).available:
                weather = 0
            available_weather[weather] = record.time

        return {
            'title': 'Time Available: {} {}'.format(call.semester_name,
                                                    call.queue_name),
            'call': call,
            'message': message,
            'weathers': weathers,
            'available': available_weather,
        }

    def get_feedback_extra(self, db, proposal):
        """
        Get additional context to include in the proposal feedback email
        message.

        Retrieves the proposal's time allocation for display in the message.
        The allocation is returned as a sorted list of JCMTRequest objects
        with the instrument and weather entries replaced by the names of the
        corresponding instrument and weather band.
        """

        allocations = db.search_jcmt_allocation(proposal_id=proposal.id)

        return {
            'jcmt_allocation': allocations.to_sorted_list(),
        }
