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

from collections import OrderedDict

from ...error import NoSuchRecord
from ...type import CallState, GroupType
from ...web.util import ErrorPage, HTTPNotFound, session


class GenericHome(object):
    def view_facility_home(self, db):
        # Retrieve all calls for this facility.
        facility_calls = db.search_call(facility_id=self.id_)

        # Determine which semesters have open calls for proposals.
        open_semesters = OrderedDict()
        for call in facility_calls.values_by_state(CallState.OPEN):
            if call.semester_id not in open_semesters:
                open_semesters[call.semester_id] = call.semester_name

        # Determine if there are any semesters with only closed calls.
        closed_semesters = False
        for call in facility_calls.values_by_state(CallState.CLOSED):
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
                review_calls = facility_calls.values_by_queue(
                    [x.queue_id for x in membership.values()])

        return {
            'title': self.get_name(),
            'open_semesters': open_semesters,
            'closed_semesters': closed_semesters,
            'calculators': self.calculators.values(),
            'target_tools': self.target_tools.values(),
            'review_calls': review_calls,
        }

    def view_semester_calls(self, db, semester_id):
        try:
            semester = db.get_semester(self.id_, semester_id)
        except NoSuchRecord:
            raise HTTPNotFound('Semester not found')

        calls = db.search_call(facility_id=self.id_, semester_id=semester_id,
                               state=CallState.OPEN,
                               with_queue_description=True)
        if not calls:
            raise ErrorPage('No calls are currently open for this semester.')

        return {
            'title': 'Call for Semester {}'.format(semester.name),
            'semester': semester,
            'calls': list(calls.values()),
        }

    def view_semester_closed(self, db):
        calls = db.search_call(facility_id=self.id_)

        open_semesters = set(
            x.semester_id for x in calls.values_by_state(CallState.OPEN))

        # Determine which semesters have closed, but no open, calls for
        # proposals.
        closed_semesters = OrderedDict()
        for call in calls.values_by_state(CallState.CLOSED):
            if ((call.semester_id not in open_semesters) and
                    (call.semester_id not in closed_semesters)):
                closed_semesters[call.semester_id] = call.semester_name

        if not closed_semesters:
            raise ErrorPage('No previous calls for proposals were found.')

        return {
            'title': 'Previous Calls for Proposals',
            'closed_semesters': closed_semesters,
        }
