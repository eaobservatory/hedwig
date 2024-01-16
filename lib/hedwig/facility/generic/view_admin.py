# Copyright (C) 2015-2024 East Asian Observatory
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

from collections import OrderedDict, defaultdict, namedtuple
from datetime import datetime

from ...email.format import render_email_template
from ...error import NoSuchRecord, UserError
from ...type.collection import AffiliationCollection, \
    CallMidCloseCollection, ResultCollection
from ...type.enum import FormatType, GroupType, \
    PersonTitle, ProposalState, SemesterState
from ...type.simple import Affiliation, \
    CallMidClose, CallPreamble, Category, DateAndTime, \
    ProposalWithCode, Queue, Semester
from ...type.util import null_tuple
from ...view import auth
from ...web.util import ErrorPage, HTTPNotFound, HTTPRedirect, \
    flash, format_datetime, parse_datetime, url_for
from ...view.util import int_or_none, str_or_none


class GenericAdmin(object):
    def view_facility_admin(self, current_user, db):
        return {
            'title': self.get_name() + ': Administrative Menu',
        }

    def view_semester_list(self, current_user, db):
        semesters = db.search_semester(facility_id=self.id_)

        return {
            'title': 'Semester List',
            'semesters': semesters,
        }

    def view_semester_view(self, current_user, db, semester_id):
        try:
            semester = db.get_semester(self.id_, semester_id)
        except NoSuchRecord:
            raise HTTPNotFound('Semester not found')

        call_preambles = db.search_call_preamble(semester_id=semester_id)

        return {
            'title': 'Semester: {}'.format(semester.name),
            'semester': semester,
            'call_preambles': call_preambles,
        }

    def view_semester_edit(self, current_user, db, semester_id, args, form):
        """
        Edit or create a new semester.

        If the "semester_id" parameter is None, then a new semester
        will be created.  Otherwise the existing semester will be
        updated.
        """

        if semester_id is None:
            # We are creating a new semester: args should be provided
            # so that we can check for "copy" request.
            if (args is not None) and ('copy' in args):
                try:
                    semester_orig = db.get_semester(self.id_, int(args['copy']))
                except NoSuchRecord:
                    raise ErrorPage('Original semester to copy not found.')

                # Remove semester-specific identifying information.
                semester = semester_orig._replace(
                    id=None, facility_id=None, name='', code='',
                    date_start=None, date_end=None)

                flash('Details have been copied from Semester "{}".',
                      semester_orig.name)
            else:
                semester = Semester(None, None, name='', code='',
                                    date_start=None, date_end=None,
                                    description='',
                                    description_format=FormatType.PLAIN)
            title = 'Add New Semester'
            target = url_for('.semester_new')
        else:
            # Fetch the existing semester record.
            try:
                semester = db.get_semester(self.id_, semester_id)
            except NoSuchRecord:
                raise HTTPNotFound('Semester not found')

            title = 'Edit Semester: {}'.format(semester.name)
            target = url_for('.semester_edit', semester_id=semester_id)

        message = None
        semester = semester._replace(
            date_start=format_datetime(semester.date_start),
            date_end=format_datetime(semester.date_end))

        if form is not None:
            semester = semester._replace(
                name=form['semester_name'].strip(),
                code=form['semester_code'].strip(),
                date_start=DateAndTime(form['start_date'], form['start_time']),
                date_end=DateAndTime(form['end_date'], form['end_time']),
                description=form['description'],
                description_format=int(form['description_format']))

            try:
                parsed_date_start = parse_datetime(semester.date_start)
                parsed_date_end = parse_datetime(semester.date_end)

                if semester_id is None:
                    # Create the new semester.
                    new_semester_id = db.add_semester(
                        self.id_, semester.name, semester.code,
                        parsed_date_start, parsed_date_end,
                        semester.description, semester.description_format)
                    flash('New semester "{}" has been created.',
                          semester.name)
                    raise HTTPRedirect(url_for('.semester_view',
                                               semester_id=new_semester_id))

                else:
                    # Update an existing semseter.
                    db.update_semester(
                        semester_id, name=semester.name,
                        code=semester.code,
                        date_start=parsed_date_start,
                        date_end=parsed_date_end,
                        description=semester.description,
                        description_format=semester.description_format)
                    flash('Semester "{}" has been updated.', semester.name)
                    raise HTTPRedirect(url_for('.semester_view',
                                               semester_id=semester_id))

            except UserError as e:
                message = e.message

        return {
            'title': title,
            'target': target,
            'message': message,
            'semester': semester,
            'format_types': FormatType.get_options(is_system=True),
        }

    def view_call_preamble_edit(
            self, current_user, db, semester_id, call_type, form):
        type_class = self.get_call_types()

        if not type_class.is_valid(call_type):
            raise HTTPError('Call type appears to be invalid.')

        try:
            semester = db.get_semester(self.id_, semester_id)
            assert semester.id == semester_id
        except NoSuchRecord:
            raise HTTPNotFound('Semester not found.')

        message = None

        if form is not None:
            try:
                preamble = null_tuple(CallPreamble)._replace(
                    description=form['description'],
                    description_format=int(form['description_format']),
                    type=call_type)

                db.set_call_preamble(
                    type_class, semester.id, preamble.type,
                    description=preamble.description,
                    description_format=preamble.description_format)

                flash('The {} call preamble for semester {} has been saved.',
                      type_class.get_name(preamble.type).lower(),
                      semester.name)

                raise HTTPRedirect(url_for('.semester_view',
                                           semester_id=semester.id))

            except UserError as e:
                message = e.message

        else:
            try:
                preamble = db.get_call_preamble(
                    semester_id=semester.id, type_=call_type)
                assert preamble.semester_id == semester.id
                assert preamble.type == call_type
                assert preamble.id is not None
            except NoSuchRecord:
                preamble = null_tuple(CallPreamble)._replace(
                    description='', description_format=FormatType.PLAIN,
                    type=call_type)

        return {
            'title': '{}: Edit {} Call Preamble'.format(
                semester.name, type_class.get_name(preamble.type)),
            'semester': semester,
            'preamble': preamble,
            'message': message,
            'format_types': FormatType.get_options(is_system=True),
        }

    def view_queue_list(self, current_user, db):
        queues = db.search_queue(facility_id=self.id_)

        return {
            'title': 'Queue List',
            'queues': queues,
        }

    def view_queue_view(self, current_user, db, queue_id):
        try:
            queue = db.get_queue(self.id_, queue_id)
        except NoSuchRecord:
            raise HTTPNotFound('Queue not found')

        affiliations = db.search_affiliation(queue_id=queue_id, hidden=False)

        return {
            'title': 'Queue: {}'.format(queue.name),
            'queue': queue,
            'affiliations': affiliations,
            'groups': GroupType.get_options(),
        }

    def view_queue_edit(self, current_user, db, queue_id, form):
        """
        Edit or create a new queue.
        """

        if queue_id is None:
            # We are creating a new queue.
            queue = Queue(None, None, name='', code='', description='',
                          description_format=FormatType.PLAIN)
            title = 'Add New Queue'
            target = url_for('.queue_new')
        else:
            # Fetch the existing queue record.
            try:
                queue = db.get_queue(self.id_, queue_id)
            except NoSuchRecord:
                raise HTTPNotFound('Queue not found')

            title = 'Edit Queue: {}'.format(queue.name)
            target = url_for('.queue_edit', queue_id=queue_id)

        message = None

        if form is not None:
            queue = queue._replace(
                name=form['queue_name'].strip(),
                code=form['queue_code'].strip(),
                description=form['description'],
                description_format=int(form['description_format']))

            try:
                if queue_id is None:
                    # Create new queue.
                    new_queue_id = db.add_queue(self.id_, queue.name,
                                                queue.code, queue.description,
                                                queue.description_format)
                    flash('New queue "{}" has been added.', queue.name)
                    raise HTTPRedirect(url_for('.queue_view',
                                               queue_id=new_queue_id))

                else:
                    # Update existing queue.
                    db.update_queue(
                        queue_id, name=queue.name, code=queue.code,
                        description=queue.description,
                        description_format=queue.description_format)
                    flash('Queue "{}" has been updated.', queue.name)
                    raise HTTPRedirect(url_for('.queue_view',
                                               queue_id=queue_id))

            except UserError as e:
                message = e.message

        return {
            'title': title,
            'target': target,
            'message': message,
            'queue': queue,
            'format_types': FormatType.get_options(is_system=True),
        }

    def view_call_list(self, current_user, db):
        calls = db.search_call(
            facility_id=self.id_, with_proposal_count=True,
            with_proposal_count_state=ProposalState.submitted_states())

        date_current = datetime.utcnow()

        return {
            'title': 'Call List',
            'calls': calls,
        }

    def view_call_view(self, current_user, db, call_id):
        try:
            call = db.get_call(facility_id=self.id_, call_id=call_id)
        except NoSuchRecord:
            raise HTTPNotFound('Call or semester not found')

        type_class = self.get_call_types()

        mid_closes = None
        if type_class.get_info(call.type).mid_close:
            mid_closes = db.search_call_mid_close(call_id=call.id)

        ctx = {
            'title': 'Call: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
            'mid_closes': mid_closes,
            'proposal_order': self.get_proposal_order(),
        }

        ctx.update(self._view_call_extra(db, call))

        return ctx

    def _view_call_extra(self, db, call):
        return {}

    def view_call_edit(
            self, current_user, db, call_id, call_type, args, form):
        """
        Create or edit a call.
        """

        type_class = self.get_call_types()

        existing_calls = None
        message = None
        extra_info = None

        if call_id is None:
            if (args is not None) and ('copy' in args):
                try:
                    call_orig = db.get_call(self.id_, int(args['copy']))
                except NoSuchRecord:
                    raise ErrorPage('Original call to copy not found.')
                if call_orig.type != call_type:
                    raise ErrorPage('Original call is of different type.')

                # Remove call-specific identifying information.
                call = call_orig._replace(
                    id=None, semester_id=None, queue_id=None,
                    date_open=None, date_close=None,
                    state=None, facility_id=None,
                    semester_name='', queue_name='')

                extra_info = self._view_call_edit_copy(db, call_orig)

                flash('Details have been copied from {} {} {}.'.format(
                    call_orig.semester_name, call_orig.queue_name,
                    type_class.get_name(call_orig.type)))
            else:
                call = self.get_new_call_default(call_type)._replace(
                    type=call_type)

            # We are creating a new call, so need to be able to offer
            # menus of semesters and queues.
            semesters = db.search_semester(
                facility_id=self.id_,
                state=(SemesterState.FUTURE, SemesterState.CURRENT))
            if not semesters:
                raise ErrorPage('No semesters are available for this call.')
            queues = db.search_queue(facility_id=self.id_,
                                     has_affiliation=True)
            if not queues:
                raise ErrorPage(
                    'No queues (with affiliations) are available '
                    'for this call.')

            # Get list of existing calls for this type.
            existing_calls = [
                (c.semester_id, c.queue_id)
                for c in db.search_call(
                    facility_id=self.id_, type_=call_type).values()]

        else:
            # Fetch the existing call record.
            try:
                call = db.get_call(self.id_, call_id)
            except NoSuchRecord:
                raise HTTPNotFound('Call not found')

            semesters = None
            queues = None

        call = call._replace(
            date_open=format_datetime(call.date_open),
            date_close=format_datetime(call.date_close))

        if form is not None:
            call = call._replace(
                date_open=DateAndTime(form['open_date'], form['open_time']),
                date_close=DateAndTime(form['close_date'], form['close_time']),
                abst_word_lim=int(form['abst_word_lim']),
                tech_word_lim=int(form['tech_word_lim']),
                tech_fig_lim=int(form['tech_fig_lim']),
                tech_page_lim=int(form['tech_page_lim']),
                sci_word_lim=int(form['sci_word_lim']),
                sci_fig_lim=int(form['sci_fig_lim']),
                sci_page_lim=int(form['sci_page_lim']),
                capt_word_lim=int(form['capt_word_lim']),
                expl_word_lim=int(form['expl_word_lim']),
                tech_note=form['tech_note'],
                sci_note=form['sci_note'],
                prev_prop_note=form['prev_prop_note'],
                note_format=int(form['note_format']),
                multi_semester=('multi_semester' in form),
                separate=('separate' in form),
                hidden=('hidden' in form),
                allow_continuation=('allow_continuation' in form))

            if call.separate and (form['preamble'] != ''):
                call = call._replace(
                    preamble=form['preamble'],
                    preamble_format=int(form['preamble_format']))
            else:
                call = call._replace(
                    preamble=None, preamble_format=None)

            if call_id is None:
                call = call._replace(
                    semester_id=int(form['semester_id']),
                    queue_id=int(form['queue_id']))

            extra_info = self._view_call_edit_get(db, call, form)

            try:
                parsed_date_open = parse_datetime(call.date_open)
                parsed_date_close = parse_datetime(call.date_close)

                if call_id is None:
                    # Create new call.
                    if (call.semester_id, call.queue_id) in existing_calls:
                        raise UserError(
                            'A call of this type for the selected semester '
                            'and queue already exists.')

                    if ((call.semester_id not in semesters)
                            or (call.queue_id not in queues)):
                        raise UserError('Unexpected semester or queue.')

                    call_id = db.add_call(
                        type_class=type_class,
                        semester_id=call.semester_id,
                        queue_id=call.queue_id,
                        type_=call.type,
                        date_open=parsed_date_open,
                        date_close=parsed_date_close,
                        abst_word_lim=call.abst_word_lim,
                        tech_word_lim=call.tech_word_lim,
                        tech_fig_lim=call.tech_fig_lim,
                        tech_page_lim=call.tech_page_lim,
                        sci_word_lim=call.sci_word_lim,
                        sci_fig_lim=call.sci_fig_lim,
                        sci_page_lim=call.sci_page_lim,
                        capt_word_lim=call.capt_word_lim,
                        expl_word_lim=call.expl_word_lim,
                        tech_note=call.tech_note,
                        sci_note=call.sci_note,
                        prev_prop_note=call.prev_prop_note,
                        note_format=call.note_format,
                        multi_semester=call.multi_semester,
                        separate=call.separate,
                        preamble=call.preamble,
                        preamble_format=call.preamble_format,
                        hidden=call.hidden,
                        allow_continuation=call.allow_continuation)

                    # Update information in the call named tuple in case of a
                    # later error so that we have to show the edit page again.
                    call = call._replace(
                        id=call_id,
                        semester_name=semesters[call.semester_id].name,
                        queue_name=queues[call.queue_id].name)

                    flash_message = 'The new call has been added.'

                else:
                    # Update existing call.
                    db.update_call(
                        call_id, date_open=parsed_date_open,
                        date_close=parsed_date_close,
                        abst_word_lim=call.abst_word_lim,
                        tech_word_lim=call.tech_word_lim,
                        tech_fig_lim=call.tech_fig_lim,
                        tech_page_lim=call.tech_page_lim,
                        sci_word_lim=call.sci_word_lim,
                        sci_fig_lim=call.sci_fig_lim,
                        sci_page_lim=call.sci_page_lim,
                        capt_word_lim=call.capt_word_lim,
                        expl_word_lim=call.expl_word_lim,
                        tech_note=call.tech_note,
                        sci_note=call.sci_note,
                        prev_prop_note=call.prev_prop_note,
                        note_format=call.note_format,
                        multi_semester=call.multi_semester,
                        separate=call.separate,
                        preamble=call.preamble,
                        preamble_format=call.preamble_format,
                        hidden=call.hidden,
                        allow_continuation=call.allow_continuation)

                    flash_message = 'The call has been updated.'

                # Save facility-specific information.
                self._view_call_edit_save(db, call, extra_info)

                flash(flash_message)

                raise HTTPRedirect(url_for('.call_view', call_id=call.id))

            except UserError as e:
                message = e.message

        if call.id is None:
            target = url_for('.call_new', call_type=call.type)

            title = 'Add New Call'

        else:
            target = url_for('.call_edit', call_id=call.id)

            title = 'Edit Call: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type))

        ctx = {
            'title': title,
            'target': target,
            'message': message,
            'call': call,
            'call_type': call_type,
            'semesters': semesters,
            'queues': queues,
            'format_types': FormatType.get_options(is_system=True),
            'existing_calls': existing_calls,
            'proposal_order': self.get_proposal_order(),
        }

        ctx.update(self._view_call_edit_extra(db, call, extra_info))

        return ctx

    def _view_call_edit_copy(self, db, call):
        return None

    def _view_call_edit_get(self, db, call, form):
        return None

    def _view_call_edit_save(self, db, call, info):
        pass

    def _view_call_edit_extra(self, db, call, info):
        return {}

    def view_call_mid_close(self, current_user, db, call_id, form):
        """
        Edit a call's intermediate close dates.
        """

        type_class = self.get_call_types()
        message = None

        try:
            call = db.get_call(self.id_, call_id)
        except NoSuchRecord:
            raise HTTPNotFound('Call not found')

        if not type_class.get_info(call.type).mid_close:
            raise ErrorPage(
                'Calls of this type do not have intermediate close dates.')

        records = db.search_call_mid_close(call_id=call.id).map_values(
            lambda x: x._replace(date=format_datetime(x.date)))

        if form is not None:
            try:
                updated_records = {}
                added_records = {}

                for param in form:
                    if not param.startswith('date_date_'):
                        continue

                    id_ = param[10:]
                    date = DateAndTime(form[param], form['date_time_' + id_])

                    if id_.startswith('new_'):
                        id_ = int(id_[4:])
                        added_records[id_] = null_tuple(
                            CallMidClose)._replace(id=id_, date=date)

                    else:
                        id_ = int(id_)
                        updated_records[id_] = null_tuple(
                            CallMidClose)._replace(id=id_, date=date)

                records = CallMidCloseCollection.organize_collection(
                    updated_records, added_records)

                parsed_records = records.map_values(
                    lambda x: x._replace(date=parse_datetime(x.date)))

                for mid_close in parsed_records.values():
                    if mid_close.date <= call.date_open:
                        raise UserError(
                            'The date {} {} is before the call opening date.',
                            *format_datetime(mid_close.date))

                    if mid_close.date >= call.date_close:
                        raise UserError(
                            'The date {} {} is after the call closing date.',
                            *format_datetime(mid_close.date))

                db.sync_call_call_mid_close(call.id, parsed_records)

                flash('The intermediate close dates have been updated.')
                raise HTTPRedirect(url_for('.call_view', call_id=call.id))

            except UserError as e:
                message = e.message

        title = 'Intermediate close dates: {} {} {}'.format(
            call.semester_name, call.queue_name,
            type_class.get_name(call.type))

        return {
            'title': title,
            'message': message,
            'call': call,
            'mid_closes': records,
        }

    def view_call_proposals(self, current_user, db, call_id):
        try:
            call = db.get_call(self.id_, call_id)
        except NoSuchRecord:
            raise HTTPNotFound('Call not found')

        type_class = self.get_call_types()

        proposals = db.search_proposal(call_id=call_id, with_member_pi=True)

        # Count number of proposals in each state.
        n_state = defaultdict(int)
        for proposal in proposals.values():
            n_state[proposal.state] += 1

        return {
            'title': 'Proposals: {} {} {}'.format(
                call.semester_name, call.queue_name,
                type_class.get_name(call.type)),
            'call': call,
            'proposals': [
                ProposalWithCode(*x, code=self.make_proposal_code(db, x))
                for x in proposals.values()],
            'state_proposals': OrderedDict(
                (k, n_state[k]) for k in ProposalState.get_options().keys()
                if k in n_state),
        }

    def view_affiliation_edit(self, current_user, db, queue_id, form):
        affiliation_type_class = self.get_affiliation_types()

        try:
            queue = db.get_queue(self.id_, queue_id)
        except NoSuchRecord:
            raise HTTPNotFound('Queue not found')

        message = None
        records = db.search_affiliation(queue_id=queue_id)

        if form is not None:
            try:
                # Temporary (unsorted) dictionaries.
                updated_records = {}
                added_records = {}

                for param in form:
                    if not param.startswith('name_'):
                        continue

                    id_ = param[5:]
                    is_hidden = ('hidden_' + id_) in form
                    type_ = int(form['type_' + id_])

                    if id_.startswith('new_'):
                        id_ = int(id_[4:])
                        added_records[id_] = Affiliation(
                            id_, queue_id, form[param].strip(), is_hidden,
                            type_, None)

                    else:
                        id_ = int(id_)
                        updated_records[id_] = Affiliation(
                            id_, queue_id, form[param].strip(), is_hidden,
                            type_, None)

                records = AffiliationCollection.organize_collection(
                    updated_records, added_records)

                db.sync_queue_affiliation(
                    affiliation_type_class, queue_id, records)

                flash('The affiliations have been updated.')
                raise HTTPRedirect(url_for('.queue_view', queue_id=queue_id))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Affiliations',
            'message': message,
            'affiliations': records,
            'affiliation_types': affiliation_type_class.get_options(),
            'queue': queue,
        }

    def view_group_view(self, current_user, db, queue_id, group_type):
        try:
            queue = db.get_queue(self.id_, queue_id)
        except NoSuchRecord:
            raise HTTPNotFound('Queue not found')

        try:
            group_info = GroupType.get_info(group_type)
        except KeyError:
            raise HTTPNotFound('Unknown group.')

        members = db.search_group_member(
            queue_id=queue_id, group_type=group_type, with_person=True)

        return {
            'title': '{}: {}'.format(queue.name, group_info.name),
            'queue': queue,
            'group_type': group_type,
            'group_info': group_info,
            'members': members,
        }

    def view_group_member_add(
            self, current_user, db, queue_id, group_type, form):
        try:
            queue = db.get_queue(self.id_, queue_id)
        except NoSuchRecord:
            raise HTTPNotFound('Queue not found')

        try:
            group_info = GroupType.get_info(group_type)
        except KeyError:
            raise HTTPNotFound('Unknown group.')

        message_link = None
        message_invite = None

        member_info = self._read_member_form(form)

        with member_info.release() as member:
            if member['is_link'] is None:
                member_info.raise_()

            elif member['is_link']:
                try:
                    member_info.raise_()

                    try:
                        person = db.get_person(person_id=member['person_id'])
                    except NoSuchRecord:
                        raise UserError('Could not find the person profile.')

                    db.add_group_member(queue_id, group_type, person.id)

                    flash('{} has been added to the group.', person.name)

                    raise HTTPRedirect(url_for(
                        '.group_view',
                        queue_id=queue_id, group_type=group_type))

                except UserError as e:
                    message_link = e.message

            else:
                try:
                    member_info.raise_()

                    person_id = db.add_person(
                        member['name'], title=member['title'],
                        primary_email=member['email'])
                    db.add_group_member(queue_id, group_type, person_id)

                    self._message_group_invite(
                        current_user, db,
                        group_info=group_info,
                        queue=queue,
                        person_id=person_id,
                        person_name=member['name'])

                    flash('{} has been added to the group.', member['name'])

                    # Return to the group page after editing the new
                    # member's institution.
                    raise HTTPRedirect(url_for(
                        'people.person_edit_institution',
                        person_id=person_id, next_page=url_for(
                            '.group_view',
                            queue_id=queue_id, group_type=group_type)))

                except UserError as e:
                    message_invite = e.message

        # Prepare list of people to exclude from the member directory.
        existing_person_ids = [
            x.person_id for x in db.search_group_member(
                queue_id=queue_id, group_type=group_type).values()]

        return {
            'title': 'Add Group Member',
            'person_list_url': url_for('query.person_list_all'),
            'persons_exclude': existing_person_ids,
            'member': member_info.data,
            'message_link': message_link,
            'message_invite': message_invite,
            'target': url_for('.group_member_add',
                              queue_id=queue.id, group_type=group_type),
            'title_link': 'Add a Member from the Directory',
            'title_invite': 'Invite a Member to Register',
            'submit_link': 'Add to group',
            'submit_invite': 'Invite to register',
            'label_link': 'Member',
            'navigation': [
                'facility_admin',
                ('Queues', url_for('.queue_list')),
                (queue.name, url_for('.queue_view', queue_id=queue.id)),
                (group_info.name, url_for('.group_view', queue_id=queue.id,
                                          group_type=group_type))],
            'help_link': url_for('help.admin_page', page_name='review_group'),
            'titles': PersonTitle.get_options(),
        }

    def _message_group_invite(self, current_user, db, group_info, queue,
                              person_id, person_name):
        (token, expiry) = db.issue_invitation(person_id, days_valid=7)

        email_ctx = {
            'inviter_name': current_user.person.name,
            'recipient_name': person_name,
            'group': group_info,
            'queue': queue,
            'token': token,
            'expiry': expiry,
            'target_url': url_for(
                'people.invitation_token_enter',
                token=token, _external=True),
            'target_plain': url_for(
                'people.invitation_token_enter',
                _external=True),
        }

        db.add_message(
            '{} invitation'.format(group_info.name),
            render_email_template('group_invitation.txt',
                                  email_ctx, facility=self),
            [person_id])

    def view_group_member_edit(
            self, current_user, db, queue_id, group_type, form):
        try:
            queue = db.get_queue(self.id_, queue_id)
        except NoSuchRecord:
            raise HTTPNotFound('Queue not found')

        try:
            group_info = GroupType.get_info(group_type)
        except KeyError:
            raise HTTPNotFound('Unknown group.')

        message = None

        members = db.search_group_member(
            queue_id=queue_id, group_type=group_type, with_person=True)

        if form is not None:
            try:
                for member_id in list(members.keys()):
                    if 'member_{}'.format(member_id) in form:
                        # Currently nothing to update for existing members.
                        pass

                    else:
                        del members[member_id]

                db.sync_group_member(queue_id, group_type, members)
                flash('The group membership has been saved.')
                raise HTTPRedirect(url_for(
                    '.group_view', queue_id=queue_id, group_type=group_type))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Group Membership',
            'queue': queue,
            'group_type': group_type,
            'group_info': group_info,
            'members': members,
            'message': message,
        }

    def view_group_member_reinvite(
            self, current_user, db, queue_id, group_type, member_id, form):
        try:
            queue = db.get_queue(self.id_, queue_id)
        except NoSuchRecord:
            raise HTTPNotFound('Queue not found.')

        try:
            group_info = GroupType.get_info(group_type)
        except KeyError:
            raise HTTPNotFound('Unknown group.')

        try:
            member = db.search_group_member(
                queue_id=queue_id, group_type=group_type,
                group_member_id=member_id, with_person=True).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Group member record not found.')

        if member.person_registered:
            raise ErrorPage('This group member is already registered.')

        if form:
            if 'submit_confirm' in form:
                self._message_group_invite(
                    current_user, db,
                    group_info=group_info,
                    queue=queue,
                    person_id=member.person_id,
                    person_name=member.person_name)

                flash('{} has been re-invited to the group.',
                      member.person_name)

            raise HTTPRedirect(url_for('.group_view', queue_id=queue_id,
                                       group_type=group_type))

        return {
            'title': 'Re-send Group Member Invitation',
            'message':
                'Would you like to re-send an invitation to '
                '{} group "{}" to {}?'.format(
                    queue.name, group_info.name, member.person_name),
        }

    def view_category_edit(self, current_user, db, form):
        message = None
        records = db.search_category(facility_id=self.id_)

        if form is not None:
            try:
                updated_records = {}
                added_records = {}

                for param in form:
                    if not param.startswith('name_'):
                        continue

                    id_ = param[5:]
                    is_hidden = ('hidden_' + id_) in form

                    if id_.startswith('new_'):
                        id_ = int(id_[4:])
                        added_records[id_] = Category(
                            id_, self.id_, form[param].strip(), is_hidden)
                    else:
                        id_ = int(id_)
                        updated_records[id_] = Category(
                            id_, self.id_, form[param].strip(), is_hidden)

                records = ResultCollection.organize_collection(
                    updated_records, added_records)

                db.sync_facility_category(self.id_, records)

                flash('The categories have been updated.')
                raise HTTPRedirect(url_for('.facility_admin'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Categories',
            'message': message,
            'categories': records,
        }
