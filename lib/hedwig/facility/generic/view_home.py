# Copyright (C) 2015-2025 East Asian Observatory
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

from ...error import NoSuchRecord, MultipleRecords
from ...type.enum import CallState, GroupType, ProposalState
from ...type.simple import CallPreamble
from ...type.util import null_tuple
from ...util import matches_constraint
from ...view import auth
from ...web.util import ErrorPage, HTTPNotFound


class GenericHome(object):
    def view_facility_home(self, current_user, db):
        type_class = self.get_call_types()
        auth_cache = {}

        # Retrieve all calls for this facility.
        facility_calls = db.search_call(
            facility_id=self.id_,
            with_proposal_count=True,
            with_proposal_count_state=ProposalState.review_states())

        # Determine which semesters have standard open calls for proposals.
        open_calls_std = facility_calls.map_values(filter_value=(
            lambda x: x.state == CallState.OPEN
            and (not x.separate)
            and x.type == type_class.STANDARD
            and auth.for_call(
                current_user, db, x, auth_cache=auth_cache).view))

        open_calls_nonstd = facility_calls.map_values(filter_value=(
            lambda x: x.state == CallState.OPEN
            and (x.separate or (x.type != type_class.STANDARD))
            and auth.for_call(
                current_user, db, x, auth_cache=auth_cache).view))

        open_semesters = set((x.semester_id for x in open_calls_std.values()))

        closed_calls_std = False
        for call in facility_calls.values_matching(
                state=CallState.CLOSED, type_=type_class.STANDARD):
            if ((call.semester_id not in open_semesters)
                    and auth.for_call(
                        current_user, db, call, auth_cache=auth_cache).view):
                closed_calls_std = True
                break

        # Create a list of the review processes which the user can view.
        review_calls = facility_calls.map_values(filter_value=(
            lambda x: auth.for_call_review(
                current_user, db, x, auth_cache=auth_cache).view))

        return {
            'title': self.get_name(),
            'open_calls_std': open_calls_std,
            'open_calls_std_count': len(set((
                (x.semester_id, (x.queue_id if x.separate else None))
                for x in open_calls_std.values()))),
            'open_calls_nonstd': open_calls_nonstd,
            'closed_calls_std': closed_calls_std,
            'calculators': self.calculators,
            'target_tools': self.target_tools,
            'review_calls': review_calls,
            'show_admin_links': current_user.is_admin,
        }

    def view_semester_calls(
            self, current_user, db, semester_id, call_type, queue_id):
        type_class = self.get_call_types()
        auth_cache = {}

        try:
            semester = db.get_semester(self.id_, semester_id)
            assert semester.id == semester_id
        except NoSuchRecord:
            raise HTTPNotFound('Semester not found.')

        title = '{} Call for Semester {}'.format(
            type_class.get_name(call_type), semester.name)

        separate = (queue_id is not None)

        # Search for open calls, unless this is a "separate" queue-based call
        # page, in which case we need all calls so that we can get the correct
        # preamble (and will filter by state = OPEN later).
        calls = db.search_call(
            facility_id=self.id_, semester_id=semester_id,
            state=(None if separate else CallState.OPEN),
            type_=call_type,
            queue_id=queue_id, separate=separate,
            with_queue_description=True,
            with_preamble=separate
        ).map_values(
            filter_value=(lambda x: auth.for_call(
                current_user, db, x, auth_cache=auth_cache).view))

        call_preamble = None

        if separate:
            try:
                separate_call = calls.get_single()
                title = '{} ({} Queue)'.format(
                    title, separate_call.queue_name)

                if ((separate_call.preamble is not None)
                        and (separate_call.preamble_format is not None)):
                    call_preamble = null_tuple(CallPreamble)._replace(
                        description=separate_call.preamble,
                        description_format=separate_call.preamble_format)

            except NoSuchRecord:
                queue = db.get_queue(facility_id=self.id_, queue_id=queue_id)
                title = '{} ({} Queue)'.format(
                    title, queue.name)
            except MultipleRecords:
                raise ErrorPage('Multiple calls found.')

            calls = calls.map_values(
                filter_value=(lambda x: x.state == CallState.OPEN))

        if call_preamble is None:
            try:
                call_preamble = db.get_call_preamble(
                    semester_id=semester.id, type_=call_type)

            except NoSuchRecord:
                pass

        call_mid_closes = None
        if type_class.get_info(call_type).mid_close:
            call_mid_closes = db.search_call_mid_close(
                call_id=list(calls.keys()), closed=False)

        return {
            'title': title,
            'separate': separate,
            'semester': semester,
            'calls': calls,
            'call_type': call_type,
            'call_preamble': call_preamble,
            'call_mid_closes': call_mid_closes,
            'show_admin_links': (calls and current_user.is_admin),
        }

    def view_semester_closed(self, current_user, db):
        type_class = self.get_call_types()
        auth_cache = {}

        # Get list of calls, considering only those of standard type.
        calls = db.search_call(
            facility_id=self.id_, type_=type_class.STANDARD, separate=False,
        ).map_values(
            filter_value=(lambda x: auth.for_call(
                current_user, db, x, auth_cache=auth_cache).view))

        open_semesters = set(
            x.semester_id for x in calls.values_matching(state=CallState.OPEN))
        closed_semesters = set(
            x.semester_id for x in calls.values_matching(state=CallState.CLOSED))

        closed_calls = calls.map_values(filter_value=(
            lambda x: (x.semester_id in closed_semesters)
            and (x.semester_id not in open_semesters)))

        if not closed_calls:
            raise ErrorPage('No previous calls for proposals were found.')

        return {
            'title': 'Previous Calls for Proposals',
            'closed_calls_std': closed_calls,
            'closed_calls_std_count': len(set((
                (x.semester_id, (x.queue_id if x.separate else None))
                for x in closed_calls.values()))),
        }

    def view_semester_non_standard(self, current_user, db):
        type_class = self.get_call_types()
        auth_cache = {}

        # Get list of open, non-standard calls.
        calls = db.search_call(
            facility_id=self.id_,
            state=CallState.OPEN,
        ).map_values(filter_value=(
            lambda x:
                (x.separate or (x.type != type_class.STANDARD))
                and auth.for_call(
                    current_user, db, x, auth_cache=auth_cache).view))

        if not calls:
            raise ErrorPage('No open special calls for proposals were found.')

        return {
            'title': 'Special Calls for Proposals',
            'open_calls': calls,
            'open_calls_count': len(set((
                (x.semester_id, x.type, (x.queue_id if x.separate else None))
                for x in calls.values()))),
        }
