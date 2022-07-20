# Copyright (C) 2018-2022 East Asian Observatory
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

from collections import defaultdict
from itertools import chain
import re

from ...error import NoSuchRecord, NoSuchValue, ParseError, UserError
from ...view.util import with_proposal
from ...web.util import HTTPRedirect, flash, url_for
from ...type.enum import PermissionType, ProposalState
from ...type.simple import ValidationMessage
from ...type.util import null_tuple
from ..eao.view import EAOFacility
from .calculator_imag_phot import ImagPhotCalculator
from .type import \
    UKIRTBrightness, UKIRTCallType, UKIRTInstrument, \
    UKIRTRequest, UKIRTRequestCollection, UKIRTRequestTotal


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
            m = re.match(r'U/(?:([A-Z]+)/)?(\d\d[ABXYZW])/([A-Z]+)(\d+)',
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

    def _copy_proposal(
            self, current_user, db, old_proposal, proposal, *args, **kwargs):
        atn = super(UKIRT, self)._copy_proposal(
            current_user, db, old_proposal, proposal, *args, **kwargs)

        # Copy observing request.
        with atn['notes'].accumulate_notes('proposal_request') as notes:
            records = db.search_ukirt_request(proposal_id=old_proposal.id)
            if records:
                records_invalid = []
                for id_, record in records.items():
                    name = '{}, {}'.format(
                        UKIRTInstrument.get_name(record.instrument),
                        UKIRTBrightness.get_name(record.brightness))
                    if not UKIRTInstrument.is_available(record.instrument):
                        records_invalid.append(id_)
                        notes.append({
                            'item': name,
                            'comment': 'instrument is no longer available.'})
                    elif not UKIRTBrightness.is_available(record.brightness):
                        records_invalid.append(id_)
                        notes.append({
                            'item': name,
                            'comment': 'brightness is no longer available.'})

                for id_ in records_invalid:
                    del records[id_]

                (n_insert, n_update, n_delete) = \
                    db.sync_ukirt_proposal_request(proposal.id, records)

                notes.append({
                    'item': '{} {}'.format(
                        n_insert, 'requests' if n_insert > 1 else 'request'),
                    'comment': 'copied to the proposal.'})

        return atn

    def _view_proposal_extra(self, db, proposal):
        ctx = super(UKIRT, self)._view_proposal_extra(db, proposal)

        requests = db.search_ukirt_request(proposal_id=proposal.id)

        ctx.update({
            'requests': requests,
        })

        return ctx

    def _validate_proposal_extra(self, db, proposal, extra):
        report = super(UKIRT, self)._validate_proposal_extra(
            db, proposal, extra, check_excluded_pi=True)

        with report.accumulate_notes('proposal_request') as messages:
            if not extra['requests']:
                messages.append(ValidationMessage(
                    True,
                    'No observing time has been requested.',
                    'Edit the observing request',
                    url_for('.request_edit', proposal_id=proposal.id)))

        return report

    def _view_proposal_feedback_extra(self, current_user, db, proposal, can):
        ctx = super(UKIRT, self)._view_proposal_feedback_extra(
            current_user, db, proposal, can)

        if proposal.state == ProposalState.ACCEPTED:
            allocations = db.search_ukirt_allocation(
                proposal_id=proposal.id)
        else:
            allocations = UKIRTRequestCollection()

        ctx.update({
            'ukirt_allocations': allocations,
        })

        return ctx

    def _get_proposal_tabulation(
            self, current_user, db, call, can, with_extra=False):
        tabulation = super(UKIRT, self)._get_proposal_tabulation(
            current_user, db, call, can, with_extra)

        exempt = UKIRTRequestTotal(
            total=0.0, instrument=defaultdict(float), brightness=defaultdict(float))
        accepted = UKIRTRequestTotal(
            total=0.0, instrument=defaultdict(float), brightness=defaultdict(float))
        total = UKIRTRequestTotal(
            total=0.0, instrument=defaultdict(float), brightness=defaultdict(float))
        original = UKIRTRequestTotal(
            total=0.0, instrument=defaultdict(float), brightness=defaultdict(float))

        accepted_affiliation = defaultdict(float)
        total_affiliation = defaultdict(float)
        original_affiliation = defaultdict(float)

        affiliation_ids = [x.id for x in tabulation['affiliations']]
        proposal_ids = [x['id'] for x in tabulation['proposals']]

        requests = db.search_ukirt_request(proposal_id=proposal_ids)
        allocations = db.search_ukirt_allocation(proposal_id=proposal_ids)

        for proposal in tabulation['proposals']:
            proposal_id = proposal['id']
            proposal_accepted = proposal['decision_accept']
            proposal_exempt = proposal['decision_exempt']
            proposal_affiliations = proposal['affiliations']

            request = requests.subset_by_proposal(proposal_id).get_total()
            proposal['ukirt_request'] = request

            allocation = None
            allocation_records = allocations.subset_by_proposal(proposal_id)
            if allocation_records:
                allocation = allocation_records.get_total()

            proposal['ukirt_allocation'] = allocation
            proposal['ukirt_allocation_different'] = \
                ((allocation is not None) and (allocation != request))

            if proposal_accepted and allocation is not None:
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

            for affiliation in affiliation_ids:
                fraction = proposal_affiliations.get(affiliation)
                if fraction is None:
                    continue

                original_affiliation[affiliation] += \
                    request.total * fraction

                if allocation is None:
                    total_affiliation[affiliation] += \
                        request.total * fraction

                else:
                    total_affiliation[affiliation] += \
                        allocation.total * fraction

                    if proposal_accepted and not proposal_exempt:
                        accepted_affiliation[affiliation] += \
                            allocation.total * fraction

        tabulation.update({
            'ukirt_instruments': UKIRTInstrument.get_options(),
            'ukirt_brightnesses': UKIRTBrightness.get_options(),
            'ukirt_exempt_total': exempt,
            'ukirt_accepted_total': accepted,
            'ukirt_request_total': total,
            'ukirt_request_original': original,
            'affiliation_accepted': accepted_affiliation,
            'affiliation_total': total_affiliation,
            'affiliation_original': original_affiliation,
        })

        return tabulation

    def _get_review_call_allocation_dynamic(self, db, call, can, proposals):
        dyn = super(UKIRT, self)._get_review_call_allocation_dynamic(
            db, call, can, proposals)

        proposal_ids = [x.id for x in proposals.values()]

        ukirt_requests = db.search_ukirt_request(proposal_id=proposal_ids)
        ukirt_allocations = db.search_ukirt_allocation(proposal_id=proposal_ids)

        for proposal in proposals.values():
            proposal_id = proposal.id

            allocation = ukirt_allocations.subset_by_proposal(proposal_id)
            if allocation:
                total = allocation.get_total()
            else:
                total = ukirt_requests.subset_by_proposal(
                    proposal_id).get_total()

            dyn[proposal_id]['time'] = total.total

        return dyn

    def _get_proposal_tabulation_titles(self, tabulation):
        return chain(
            super(UKIRT, self)._get_proposal_tabulation_titles(tabulation),
            ['Request', 'Allocation'])

    def _get_proposal_tabulation_rows(self, tabulation):
        for (row, proposal) in zip(
                super(UKIRT, self)._get_proposal_tabulation_rows(tabulation),
                tabulation['proposals']):
            request = proposal['ukirt_request']
            allocation = proposal['ukirt_allocation']
            if (allocation is None) or not proposal['decision_accept']:
                allocation = null_tuple(UKIRTRequestTotal)

            yield chain(
                row,
                [request.total, allocation.total])

    @with_proposal(permission=PermissionType.EDIT)
    def view_request_edit(self, current_user, db, proposal, can, form):
        message = None

        records = db.search_ukirt_request(proposal_id=proposal.id)

        if form is not None:
            records = self._read_request_form(proposal, form)

            try:
                db.sync_ukirt_proposal_request(proposal.id, records)

                flash('The observing request has been saved.')

                raise HTTPRedirect(url_for('.proposal_view',
                                           proposal_id=proposal.id,
                                           _anchor='request'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Observing Request',
            'proposal_id': proposal.id,
            'proposal_code': self.make_proposal_code(db, proposal),
            'message': message,
            'requests': records,
            'instruments': UKIRTInstrument.get_options(),
            'brightnesses': UKIRTBrightness.get_options(),
        }

    def _read_request_form(self, proposal, form, skip_blank_time=False):
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

            if skip_blank_time and not request_time:
                continue

            try:
                request_time = float(request_time)
            except ValueError:
                # Ignore parsing error to allow user to correc the input.
                pass

            instrument = form['instrument_' + id_]
            brightness = form['brightness_' + id_]

            destination[request_id] = UKIRTRequest(
                request_id, proposal.id,
                instrument=int(instrument),
                brightness=int(brightness),
                time=request_time)

        return UKIRTRequestCollection.organize_collection(
            updated_records, added_records)

    def _view_proposal_decision_get(self, db, proposal, form):
        """
        Read the UKIRT allocation from the form without raising parse errors.
        """

        return self._read_request_form(proposal, form, skip_blank_time=True)

    def _view_proposal_decision_save(self, db, proposal, info):
        """
        Store the UKIRT allocation.
        """

        if proposal.decision_accept and not info.get_total().total:
            raise UserError('An accepted proposal should not have '
                            'zero total time allocation.')

        db.sync_ukirt_proposal_allocation(proposal_id=proposal.id,
                                          records=info)

    def _view_proposal_decision_extra(self, db, proposal, info):
        """
        Generate extra template context for allocation on decision page.
        """

        original_request = db.search_ukirt_request(proposal_id=proposal.id)
        is_prefilled = False

        if info is None:
            allocations = db.search_ukirt_allocation(proposal_id=proposal.id)

            if not allocations:
                # Copy request to allocation, rewriting ID as None.
                allocations = UKIRTRequestCollection((
                    (n, r._replace(id=None))
                    for (n, r) in enumerate(original_request.values(), 1)))
                is_prefilled = True

        else:
            allocations = info

        return {
            'original_request': original_request,
            'is_prefilled': is_prefilled,
            'allocations': allocations,
            'instruments': UKIRTInstrument.get_options(),
            'brightnesses': UKIRTBrightness.get_options(),
        }

    def get_feedback_extra(self, db, proposal):
        """
        Get additional context for the proposal feedbacke email message.
        """

        allocations = db.search_ukirt_allocation(proposal_id=proposal.id)

        return {
            'ukirt_allocations': allocations.to_sorted_list(),
        }
