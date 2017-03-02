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

from collections import namedtuple, OrderedDict

from ...error import NoSuchRecord
from ...type.enum import CallState, GroupType
from ...web.util import ErrorPage, HTTPNotFound, session


SpecialSemesterInfo = namedtuple('SpecialSemesterInfo', ('name', 'call_types'))


class GenericHome(object):
    def view_facility_home(self, db):
        type_class = self.get_call_types()

        # Retrieve all calls for this facility.
        facility_calls = db.search_call(facility_id=self.id_)

        # Determine which semesters have standard open calls for proposals.
        open_semesters = OrderedDict()
        open_nonstandard_semesters = False
        for call in facility_calls.values_matching(state=CallState.OPEN):
            if call.type == type_class.STANDARD:
                if call.semester_id not in open_semesters:
                    open_semesters[call.semester_id] = call.semester_name
            else:
                open_nonstandard_semesters = True

        # Determine if there are any semesters with only closed standard calls.
        closed_semesters = False
        for call in facility_calls.values_matching(state=CallState.CLOSED,
                                                   type_=type_class.STANDARD):
            if call.semester_id not in open_semesters:
                closed_semesters = True
                break

        # Determine whether the person is a committee member (or administrator)
        # and if so, create a list of the review processes.
        review_calls = None
        if ('user_id' in session) and session.get('is_admin', False):
            # Administrators can see reviews for all calls.
            review_calls = facility_calls.values()

        elif ('user_id' in session) and ('person' in session):
            membership = db.search_group_member(
                group_type=GroupType.review_view_groups(),
                person_id=session['person']['id'])
            if membership:
                review_calls = facility_calls.values_matching(
                    queue_id=[x.queue_id for x in membership.values()])

        return {
            'title': self.get_name(),
            'open_semesters': open_semesters,
            'open_nonstandard_semesters': open_nonstandard_semesters,
            'closed_semesters': closed_semesters,
            'calculators': self.calculators,
            'target_tools': self.target_tools,
            'review_calls': review_calls,
        }

    def view_semester_calls(self, db, semester_id, call_type):
        type_class = self.get_call_types()

        try:
            semester = db.get_semester(self.id_, semester_id)
            assert semester.id == semester_id
        except NoSuchRecord:
            raise HTTPNotFound('Semester not found')

        calls = db.search_call(facility_id=self.id_, semester_id=semester_id,
                               state=CallState.OPEN, type_=call_type,
                               with_queue_description=True)

        try:
            call_preamble = db.get_call_preamble(semester_id=semester.id,
                                                 type_=call_type)
        except NoSuchRecord:
            call_preamble = None

        return {
            'title': '{} Call for Semester {}'.format(
                type_class.get_name(call_type), semester.name),
            'semester': semester,
            'calls': calls,
            'call_type': call_type,
            'call_preamble': call_preamble,
        }

    def view_semester_closed(self, db):
        type_class = self.get_call_types()

        # Get list of calls, considering only those of standard type.
        calls = db.search_call(facility_id=self.id_, type_=type_class.STANDARD)

        open_semesters = set(
            x.semester_id for x in calls.values_matching(state=CallState.OPEN))

        # Determine which semesters have closed, but no open, calls for
        # proposals.
        closed_semesters = OrderedDict()
        for call in calls.values_matching(state=CallState.CLOSED):
            if ((call.semester_id not in open_semesters) and
                    (call.semester_id not in closed_semesters)):
                closed_semesters[call.semester_id] = call.semester_name

        if not closed_semesters:
            raise ErrorPage('No previous calls for proposals were found.')

        return {
            'title': 'Previous Calls for Proposals',
            'closed_semesters': closed_semesters,
        }

    def view_semester_non_standard(self, db):
        type_class = self.get_call_types()

        # Get list of open, non-standard calls.
        calls = db.search_call(
            facility_id=self.id_,
            state=CallState.OPEN,
            type_=[x for x in type_class.get_options()
                   if x != type_class.STANDARD])

        if not calls:
            raise ErrorPage('No open special calls for proposals were found.')

        # Group into semesters.
        semesters = OrderedDict()
        for call in calls.values():
            if call.semester_id in semesters:
                semester_info = semesters[call.semester_id]
                if call.type not in semester_info.call_types:
                    semester_info.call_types.append(call.type)
            else:
                semesters[call.semester_id] = SpecialSemesterInfo(
                    call.semester_name, [call.type])

        return {
            'title': 'Special Calls for Proposals',
            'semesters': semesters,
        }
