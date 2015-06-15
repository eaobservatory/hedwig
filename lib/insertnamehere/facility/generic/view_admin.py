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
    flash, parse_datetime, url_for
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
            'semester': semester,
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
            semester = Semester(None, None, name='', code='',
                                date_start=None, date_end=None,
                                description='')
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
            semester = semester._replace(
                name=form['semester_name'],
                code=form['semester_code'],
                date_start=parse_datetime('start', form),
                date_end=parse_datetime('end', form),
                description=form['description'])

            try:
                if semester_id is None:
                    # Create the new semester.
                    new_semester_id = db.add_semester(
                        self.id_, semester.name, semester.code,
                        semester.date_start, semester.date_end,
                        semester.description)
                    flash('New semester "{0}" has been created.',
                          semester.name)
                    raise HTTPRedirect(url_for('.semester_view',
                                               semester_id=new_semester_id))

                else:
                    # Update an existing semseter.
                    db.update_semester(semester_id, name=semester.name,
                                       code=semester.code,
                                       date_start=semester.date_start,
                                       date_end=semester.date_end,
                                       description=semester.description)
                    flash('Semester "{0}" has been updated.', semester.name)
                    raise HTTPRedirect(url_for('.semester_view',
                                               semester_id=semester_id))

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
            'queue': queue,
        }

    def view_queue_edit(self, db, queue_id, form, is_post):
        """
        Edit or create a new queue.
        """

        if not auth.can_be_admin(db):
            raise HTTPForbidden('Could not verify administrative access.')

        if queue_id is None:
            # We are creating a new queue.
            queue = Queue(None, None, name='', code='', description='')
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
            queue = queue._replace(name=form['queue_name'],
                                   code=form['queue_code'],
                                   description=form['description'])

            try:
                if queue_id is None:
                    # Create new queue.
                    new_queue_id = db.add_queue(self.id_, queue.name,
                                                queue.code, queue.description)
                    flash('New queue "{0}" has been added.', queue.name)
                    raise HTTPRedirect(url_for('.queue_view',
                                               queue_id=new_queue_id))

                else:
                    # Update existing queue.
                    db.update_queue(queue_id, name=queue.name, code=queue.code,
                                    description=queue.description)
                    flash('Queue "{0}" has been updated.', queue.name)
                    raise HTTPRedirect(url_for('.queue_view',
                                               queue_id=queue_id))

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
                        date_open=None, date_close=None,
                        facility_id=None, semester_name='',
                        queue_name='', queue_description=None,
                        abst_word_lim=200, tech_word_lim=1000, tech_page_lim=1,
                        sci_word_lim=2000, sci_fig_lim=4, sci_page_lim=3)
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
                call = call._replace(
                    date_open=parse_datetime('open', form),
                    date_close=parse_datetime('close', form),
                    abst_word_lim=int(form['abst_word_lim']),
                    tech_word_lim=int(form['tech_word_lim']),
                    tech_page_lim=int(form['tech_page_lim']),
                    sci_word_lim=int(form['sci_word_lim']),
                    sci_fig_lim=int(form['sci_fig_lim']),
                    sci_page_lim=int(form['sci_page_lim']))

                if call_id is None:
                    # Create new call.
                    call = call._replace(
                        semester_id=int(form['semester_id']),
                        queue_id=int(form['queue_id']))

                    new_call_id = db.add_call(semester_id=call.semester_id,
                                              queue_id=call.queue_id,
                                              date_open=call.date_open,
                                              date_close=call.date_close,
                                              abst_word_lim=call.abst_word_lim,
                                              tech_word_lim=call.tech_word_lim,
                                              tech_page_lim=call.tech_page_lim,
                                              sci_word_lim=call.sci_word_lim,
                                              sci_fig_lim=call.sci_fig_lim,
                                              sci_page_lim=call.sci_page_lim)
                    flash('The new call has been added.')
                    raise HTTPRedirect(url_for('.call_view',
                                               call_id=new_call_id))

                else:
                    # Update existing call.
                    db.update_call(call_id, date_open=call.date_open,
                                   date_close=call.date_close,
                                   abst_word_lim=call.abst_word_lim,
                                   tech_word_lim=call.tech_word_lim,
                                   tech_page_lim=call.tech_page_lim,
                                   sci_word_lim=call.sci_word_lim,
                                   sci_fig_lim=call.sci_fig_lim,
                                   sci_page_lim=call.sci_page_lim)
                    flash('The call has been updated.')
                    raise HTTPRedirect(url_for('.call_view', call_id=call_id))

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

    def view_affiliation_edit(self, db, queue_id, form, is_post):
        if not auth.can_be_admin(db):
            raise HTTPForbidden('Could not verify administrative access.')

        message = None
        records = db.search_affiliation(queue_id=queue_id)

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
                            id_, queue_id, form[param], is_hidden)

                    else:
                        id_ = int(id_)
                        updated_records[id_] = Affiliation(
                            id_, queue_id, form[param], is_hidden)

                records = organise_collection(
                    ResultCollection, updated_records, added_records)

                db.sync_queue_affiliation(queue_id, records)

                flash('The affiliations have been updated.')
                raise HTTPRedirect(url_for('.queue_view', queue_id=queue_id))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Affiliations',
            'message': message,
            'affiliations': records.values(),
            'queue_id': queue_id,
        }
