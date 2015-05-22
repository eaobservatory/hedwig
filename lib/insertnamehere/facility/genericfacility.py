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

from ..error import NoSuchRecord, UserError
from ..view.auth import can_be_admin
from ..web.util import ErrorPage, HTTPNotFound, HTTPRedirect, url_for


class GenericFacility(object):
    """
    Base class for Facility objects.
    """

    def __init__(self, id_):
        """
        Construct facility object.

        Takes the facility "id" as recorded in the database.  Instances of
        this class should be constructed by looking up the facility's "code"
        (from the get_code class method) in the database, then calling
        this constructor with the associated identifier.
        """

        self.id_ = id_

    @classmethod
    def get_code(cls):
        """
        Get the facility "code".

        This is a short string to uniquely identify the facility.  It will
        correspond to an entry in the "facility" table.
        """

        return 'generic'

    def get_name(self):
        """
        Get the name of the facility.
        """

        return 'Generic Facility'

    def view_facility_home(self, db):
        return {
            'title': self.get_name(),
        }

    def view_facility_admin(self, db):
        return {
            'title': self.get_name() + ': Administrative Menu',
        }

    def view_semester_list(self, db):
        semesters = db.search_semester(facility_id=self.id_)

        return {
            'title': 'Semester List',
            'semesters': semesters,
        }

    def view_semester_new(self, db, form, is_post):
        if not can_be_admin(db):
            raise HTTPForbidden('Could not verify administrative access.')

        message = None
        semester_name = form.get('semester_name', '')

        if is_post:
            try:
                db.add_semester(self.id_, semester_name)
                raise HTTPRedirect(url_for('.semester_list'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Add New Semester',
            'target': url_for('.semester_new'),
            'message': message,
            'semester_name': semester_name,
        }

    def view_semester_view(self, db, semester_id):
        try:
            semester = db.get_semester(semester_id)
        except NoSuchRecord:
            raise HTTPNotFound('Semester not found')

        if semester.facility_id != self.id_:
            raise ErrorPage('Semester is not for this facility')

        return {
            'title': 'Semester: {0}'.format(semester.name),
            'semester_id': semester_id,
        }

    def view_semester_edit(self, db, semester_id, form, is_post):
        if not can_be_admin(db):
            raise HTTPForbidden('Could not verify administrative access.')

        try:
            semester = db.get_semester(semester_id)
        except NoSuchRecord:
            raise HTTPNotFound('Semester not found')

        if semester.facility_id != self.id_:
            raise ErrorPage('Semester is not for this facility')

        message = None
        semester_name = form.get('semester_name', semester.name)

        if is_post:
            semester_name = form['semester_name']
            try:
                db.update_semester(semester_id, name=semester_name)
                raise HTTPRedirect(url_for('.semester_list'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Semester: {0}'.format(semester.name),
            'target': url_for('.semester_edit', semester_id=semester_id),
            'message': message,
            'semester_name': semester_name,
        }
