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

from ...error import NoSuchRecord, UserError
from ...type import Affiliation, Call, Queue, ResultCollection, Semester
from ...view import auth
from ...web.util import HTTPForbidden, HTTPNotFound, HTTPRedirect, \
    flash, url_for
from ...view.util import organise_collection


class GenericAdmin(object):
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

    def view_semester_view(self, db, semester_id):
        try:
            semester = db.get_semester(self.id_, semester_id)
        except NoSuchRecord:
            raise HTTPNotFound('Semester not found')

        return {
            'title': 'Semester: {0}'.format(semester.name),
            'semester_id': semester_id,
        }

    def view_semester_edit(self, db, semester_id, form, is_post):
        """
        Edit or create a new semester.

        If the "semester_id" parameter is None, then a new semester
        will be created.  Otherwise the existing semester will be
        updated.
        """

        if not auth.can_be_admin(db):
            raise HTTPForbidden('Could not verify administrative access.')

        if semester_id is None:
            # We are creating a new semester.
            semester = Semester(None, None, name='')
            title = 'Add New Semester'
            target = url_for('.semester_new')
        else:
            # Fetch the existing semester record.
            try:
                semester = db.get_semester(self.id_, semester_id)
            except NoSuchRecord:
                raise HTTPNotFound('Semester not found')

            title = 'Edit Semester: {0}'.format(semester.name)
            target = url_for('.semester_edit', semester_id=semester_id)

        message = None

        if is_post:
            semester = semester._replace(name=form['semester_name'])

            try:
                if semester_id is None:
                    # Create the new semester.
                    db.add_semester(self.id_, semester.name)
                    flash('New semester "{0}" has been created.',
                          semester.name)
                    raise HTTPRedirect(url_for('.semester_list'))

                else:
                    # Update an existing semseter.
                    db.update_semester(semester_id, name=semester.name)
                    flash('Semester "{0}" has been updated.', semester.name)
                    raise HTTPRedirect(url_for('.semester_list'))

            except UserError as e:
                message = e.message

        return {
            'title': title,
            'target': target,
            'message': message,
            'semester': semester,
        }

    def view_queue_list(self, db):
        queues = db.search_queue(facility_id=self.id_)

        return {
            'title': 'Queue List',
            'queues': queues,
        }

    def view_queue_view(self, db, queue_id):
        try:
            queue = db.get_queue(self.id_, queue_id)
        except NoSuchRecord:
            raise HTTPNotFound('Queue not found')

        return {
            'title': 'Queue: {0}'.format(queue.name),
            'queue_id': queue_id,
        }

    def view_queue_edit(self, db, queue_id, form, is_post):
        """
        Edit or create a new queue.
        """

        if not auth.can_be_admin(db):
            raise HTTPForbidden('Could not verify administrative access.')

        if queue_id is None:
            # We are creating a new queue.
            queue = Queue(None, None, name='')
            title = 'Add New Queue'
            target = url_for('.queue_new')
        else:
            # Fetch the existing queue record.
            try:
                queue = db.get_queue(self.id_, queue_id)
            except NoSuchRecord:
                raise HTTPNotFound('Queue not found')

            title = 'Edit Queue: {0}'.format(queue.name)
            target = url_for('.queue_edit', queue_id=queue_id)

        message = None

        if is_post:
            queue = queue._replace(name=form['queue_name'])

            try:
                if queue_id is None:
                    # Create new queue.
                    db.add_queue(self.id_, queue.name)
                    flash('New queue "{0}" has been added.', queue.name)
                    raise HTTPRedirect(url_for('.queue_list'))

                else:
                    # Update existing queue.
                    db.update_queue(queue_id, name=queue.name)
                    flash('Queue "{0}" has been updated.', queue.name)
                    raise HTTPRedirect(url_for('.queue_list'))

            except UserError as e:
                message = e.message

        return {
            'title': title,
            'target': target,
            'message': message,
            'queue': queue,
        }

    def view_call_list(self, db):
        calls = db.search_call(facility_id=self.id_)

        return {
            'title': 'Call List',
            'calls': calls,
        }

    def view_call_view(self, db, call_id):
        try:
            call = db.get_call(facility_id=self.id_, call_id=call_id)
        except NoSuchRecord:
            raise HTTPNotFound('Call or semester not found')

        return {
            'title': 'Call: {0} {1}'.format(call.semester_name,
                                            call.queue_name),
            'call': call,
        }

    def view_call_edit(self, db, call_id, form, is_post):
        """
        Create or edit a call.
        """

        if not auth.can_be_admin(db):
            raise HTTPForbidden('Could not verify administrative access.')

        if call_id is None:
            # We are creating a new call, so need to be able to offer
            # menus of semesters and queues.
            call = Call(None, semester_id=None, queue_id=None,
                        facility_id=None, semester_name='', queue_name='')
            semesters = db.search_semester(facility_id=self.id_)
            queues = db.search_queue(facility_id=self.id_)
            title = 'Add New Call'
            target = url_for('.call_new')
        else:
            # Fetch the existing call record.
            try:
                call = db.get_call(self.id_, call_id)
            except NoSuchRecord:
                raise HTTPNotFound('Call not found')

            semesters = None
            queues = None
            title = 'Edit Call: {0} {1}'.format(call.semester_name,
                                                call.queue_name)
            target = url_for('.call_edit', call_id=call_id)

        message = None

        if is_post:
            try:
                if call_id is None:
                    # Create new call.
                    call = call._replace(semester_id=int(form['semester_id']))
                    call = call._replace(queue_id=int(form['queue_id']))

                    db.add_call(semester_id=call.semester_id,
                                queue_id=call.queue_id)
                    flash('The new call has been added.')
                    raise HTTPRedirect(url_for('.call_list'))

                else:
                    # Update existing call.
                    # The call table doesn't yet have anything we can
                    # actually edit.
                    # db.update_call(call_id, ...)
                    flash('The call has been updated.')
                    raise HTTPRedirect(url_for('.call_list'))

            except UserError as e:
                message = e.message

        return {
            'title': title,
            'target': target,
            'message': message,
            'call': call,
            'semesters': (None if semesters is None else semesters.values()),
            'queues': (None if queues is None else queues.values()),
        }

    def view_affiliation_edit(self, db, form, is_post):
        if not auth.can_be_admin(db):
            raise HTTPForbidden('Could not verify administrative access.')

        message = None
        records = db.search_affiliation(facility_id=self.id_)

        if is_post:
            try:
                # Temporary (unsorted) dictionaries.
                updated_records = {}
                added_records = {}

                for param in form:
                    if not param.startswith('name_'):
                        continue

                    id_ = param[5:]
                    is_hidden = ('hidden_' + id_) in form

                    if id_.startswith('new_'):
                        id_ = int(id_[4:])
                        added_records[id_] = Affiliation(
                            id_, self.id_, form[param], is_hidden)

                    else:
                        id_ = int(id_)
                        updated_records[id_] = Affiliation(
                            id_, self.id_, form[param], is_hidden)

                records = organise_collection(
                    ResultCollection, updated_records, added_records)

                db.sync_facility_affiliation(self.id_, records)

                flash('The affiliations have been updated.')
                raise HTTPRedirect(url_for('.facility_admin'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Affiliations',
            'message': message,
            'affiliations': records.values(),
        }
