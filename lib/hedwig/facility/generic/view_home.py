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
        # Determine which semesters have open calls for proposals.
        open_semesters = OrderedDict()
        for call in db.search_call(facility_id=self.id_,
                                   state=CallState.OPEN).values():
            if call.semester_id not in open_semesters:
                open_semesters[call.semester_id] = call.semester_name

        # Determine whether the person is a committee member (or administrator)
        # and if so, create a list of the review processes.
        review_calls = None
        can_view_reviews = False
        if ('user_id' in session) and session.get('is_admin', False):
            can_view_reviews = True
            queue_id = None

        elif ('user_id' in session) and ('person' in session):
            membership = db.search_group_member(
                group_type=GroupType.review_view_groups(),
                person_id=session['person']['id'])
            if membership:
                can_view_reviews = True
                queue_id = [x.queue_id for x in membership.values()]

        if can_view_reviews:
            review_calls = db.search_call(facility_id=self.id_,
                                          queue_id=queue_id).values()

        return {
            'title': self.get_name(),
            'open_semesters': open_semesters,
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
