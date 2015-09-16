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

from collections import namedtuple
from datetime import datetime

from ...email.format import render_email_template
from ...error import NoSuchRecord, UserError
from ...type import Affiliation, Call, Category, \
    FormatType, GroupType, MOCInfo, \
    ProposalWithCode, Queue, \
    ResultCollection, Semester, \
    null_tuple
from ...util import get_countries
from ...view import auth
from ...web.util import ErrorPage, HTTPNotFound, HTTPRedirect, \
    flash, parse_datetime, session, url_for
from ...view.util import organise_collection, with_verified_admin

CallExtra = namedtuple(
    'CallExtra',
    Call._fields + ('status',))


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

    @with_verified_admin
    def view_semester_edit(self, db, semester_id, form, is_post):
        """
        Edit or create a new semester.

        If the "semester_id" parameter is None, then a new semester
        will be created.  Otherwise the existing semester will be
        updated.
        """

        if semester_id is None:
            # We are creating a new semester.
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

            title = 'Edit Semester: {0}'.format(semester.name)
            target = url_for('.semester_edit', semester_id=semester_id)

        message = None

        if is_post:
            semester = semester._replace(
                name=form['semester_name'],
                code=form['semester_code'],
                date_start=parse_datetime('start', form),
                date_end=parse_datetime('end', form),
                description=form['description'],
                description_format=int(form['description_format']))

            try:
                if semester_id is None:
                    # Create the new semester.
                    new_semester_id = db.add_semester(
                        self.id_, semester.name, semester.code,
                        semester.date_start, semester.date_end,
                        semester.description, semester.description_format)
                    flash('New semester "{0}" has been created.',
                          semester.name)
                    raise HTTPRedirect(url_for('.semester_view',
                                               semester_id=new_semester_id))

                else:
                    # Update an existing semseter.
                    db.update_semester(
                        semester_id, name=semester.name,
                        code=semester.code,
                        date_start=semester.date_start,
                        date_end=semester.date_end,
                        description=semester.description,
                        description_format=semester.description_format)
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
            'format_types': FormatType.get_options(is_system=True),
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

        affiliations = db.search_affiliation(queue_id=queue_id, hidden=False)

        return {
            'title': 'Queue: {0}'.format(queue.name),
            'queue': queue,
            'affiliations': affiliations.values(),
            'groups': GroupType.get_options(),
        }

    @with_verified_admin
    def view_queue_edit(self, db, queue_id, form, is_post):
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

            title = 'Edit Queue: {0}'.format(queue.name)
            target = url_for('.queue_edit', queue_id=queue_id)

        message = None

        if is_post:
            queue = queue._replace(
                name=form['queue_name'],
                code=form['queue_code'],
                description=form['description'],
                description_format=int(form['description_format']))

            try:
                if queue_id is None:
                    # Create new queue.
                    new_queue_id = db.add_queue(self.id_, queue.name,
                                                queue.code, queue.description,
                                                queue.description_format)
                    flash('New queue "{0}" has been added.', queue.name)
                    raise HTTPRedirect(url_for('.queue_view',
                                               queue_id=new_queue_id))

                else:
                    # Update existing queue.
                    db.update_queue(
                        queue_id, name=queue.name, code=queue.code,
                        description=queue.description,
                        description_format=queue.description_format)
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
            'format_types': FormatType.get_options(is_system=True),
        }

    def view_call_list(self, db):
        calls = db.search_call(facility_id=self.id_)

        date_current = datetime.utcnow()

        return {
            'title': 'Call List',
            'calls': [CallExtra(*x, status=(
                      'Closed' if date_current > x.date_close
                      else ('Open' if date_current >= x.date_open
                            else 'Not yet open')))
                      for x in calls.values()],
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

    @with_verified_admin
    def view_call_edit(self, db, call_id, form, is_post):
        """
        Create or edit a call.
        """

        if call_id is None:
            # We are creating a new call, so need to be able to offer
            # menus of semesters and queues.
            call = Call(None, semester_id=None, queue_id=None,
                        date_open=None, date_close=None,
                        facility_id=None, semester_name='',
                        queue_name='', queue_description=None,
                        queue_description_format=None,
                        abst_word_lim=200,
                        tech_word_lim=1000, tech_fig_lim=0, tech_page_lim=1,
                        sci_word_lim=2000, sci_fig_lim=4, sci_page_lim=3,
                        capt_word_lim=200, expl_word_lim=200,
                        tech_note='', sci_note='', prev_prop_note='',
                        note_format=FormatType.PLAIN)
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
                    note_format=int(form['note_format']))

                if call_id is None:
                    # Create new call.
                    call = call._replace(
                        semester_id=int(form['semester_id']),
                        queue_id=int(form['queue_id']))

                    new_call_id = db.add_call(
                        semester_id=call.semester_id,
                        queue_id=call.queue_id,
                        date_open=call.date_open,
                        date_close=call.date_close,
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
                        note_format=call.note_format)
                    flash('The new call has been added.')
                    raise HTTPRedirect(url_for('.call_view',
                                               call_id=new_call_id))

                else:
                    # Update existing call.
                    db.update_call(
                        call_id, date_open=call.date_open,
                        date_close=call.date_close,
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
                        note_format=call.note_format)
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
            'format_types': FormatType.get_options(is_system=True),
        }

    @with_verified_admin
    def view_call_proposals(self, db, call_id):
        try:
            call = db.get_call(self.id_, call_id)
        except NoSuchRecord:
            raise HTTPNotFound('Call not found')

        proposals = db.search_proposal(call_id=call_id, person_pi=True)

        return {
            'title': 'Proposals: {0} {1}'.format(call.semester_name,
                                                 call.queue_name),
            'call': call,
            'proposals': [
                ProposalWithCode(*x, code=self.make_proposal_code(db, x),
                                 facility_code=None)
                for x in proposals.values()],
        }

    @with_verified_admin
    def view_affiliation_edit(self, db, queue_id, form, is_post):
        try:
            queue = db.get_queue(self.id_, queue_id)
        except NoSuchRecord:
            raise HTTPNotFound('Queue not found')

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
                    is_exclude = ('exclude_' + id_) in form

                    if id_.startswith('new_'):
                        id_ = int(id_[4:])
                        added_records[id_] = Affiliation(
                            id_, queue_id, form[param], is_hidden,
                            is_exclude, None)

                    else:
                        id_ = int(id_)
                        updated_records[id_] = Affiliation(
                            id_, queue_id, form[param], is_hidden,
                            is_exclude, None)

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
            'queue': queue,
        }

    @with_verified_admin
    def view_group_view(self, db, queue_id, group_type):
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

        countries = get_countries()

        return {
            'title': '{}: {}'.format(queue.name, group_info.name),
            'queue': queue,
            'group_type': group_type,
            'group_info': group_info,
            'members': [
                x._replace(institution_country=countries.get(
                    x.institution_country, 'Unknown country'))
                for x in members.values()],
        }

    @with_verified_admin
    def view_group_member_add(self, db, queue_id, group_type, form):
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

        member = dict(person_id=None, name='', email='')

        if form is not None:
            if 'person_id' in form:
                member['person_id'] = int(form['person_id'])
            member['name'] = form.get('name', '')
            member['email'] = form.get('email', '')

            if 'submit_link' in form:
                try:
                    if member['person_id'] is None:
                        raise UserError(
                            'No-one was selected from the directory.')
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

            elif 'submit_invite' in form:
                try:
                    if not member['name']:
                        raise UserError('Please enter the person\'s name.')
                    if not member['email']:
                        raise UserError('Please enter an email address.')

                    person_id = db.add_person(member['name'])
                    db.add_email(person_id, member['email'], primary=True)
                    db.add_group_member(queue_id, group_type, person_id)
                    (token, expiry) = db.add_invitation(person_id)

                    email_ctx = {
                        'inviter_name': session['person']['name'],
                        'recipient_name': member['name'],
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

                    flash('{} has been added to the group.', member['name'])

                    # Return to the group page after editing the new
                    # member's institution.
                    session['next_page'] = url_for(
                        '.group_view',
                        queue_id=queue_id, group_type=group_type)

                    raise HTTPRedirect(url_for(
                        'people.person_edit_institution', person_id=person_id))

                except UserError as e:
                    message_invite = e.message

            else:
                raise ErrorPage('Unknown action.')

        # Prepare list of people to display as the registered member directory.
        cs = get_countries()
        existing_person_ids = [
            x.person_id for x in db.search_group_member(
                queue_id=queue_id, group_type=group_type).values()]
        persons = [
            p._replace(institution_country=cs.get(p.institution_country))
            for p in db.search_person(registered=True, public=True,
                                      with_institution=True).values()
            if p.id not in existing_person_ids]

        return {
            'title': 'Add Group Member',
            'persons': persons,
            'member': member,
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
        }

    @with_verified_admin
    def view_group_member_edit(self, db, queue_id, group_type, form):
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
            'members': members.values(),
            'message': message,
        }

    @with_verified_admin
    def view_category_edit(self, db, form):
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
                        added_records[id_] = Category(id_, self.id_,
                                                      form[param], is_hidden)
                    else:
                        id_ = int(id_)
                        updated_records[id_] = Category(id_, self.id_,
                                                        form[param], is_hidden)

                records = organise_collection(
                    ResultCollection, updated_records, added_records)

                db.sync_facility_category(self.id_, records)

                flash('The categories have been updated.')
                raise HTTPRedirect(url_for('.facility_admin'))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Categories',
            'message': message,
            'categories': records.values(),
        }

    def view_moc_list(self, db):
        mocs = db.search_moc(facility_id=self.id_, public=None)

        return {
            'title': 'Coverage List',
            'mocs': mocs.values(),
        }

    @with_verified_admin
    def view_moc_edit(self, db, moc_id, form, file_):
        if moc_id is None:
            # We are uploading a new MOC -- create a blank record.
            moc = null_tuple(MOCInfo)._replace(
                name='', description='', description_format=FormatType.PLAIN,
                public=True)
            title = 'New Coverage Map'
            target = url_for('.moc_new')

        else:
            # We are editing an existing MOC -- fetch its info from
            # the database.
            try:
                moc = db.search_moc(
                    facility_id=self.id_, moc_id=moc_id,
                    public=None, with_description=True).get_single()
            except NoSuchRecord:
                raise HTTPNotFound('Coverage map not found')

            title = 'Edit {}'.format(moc.name)
            target = url_for('.moc_edit', moc_id=moc_id)

        message = None

        if form is not None:
            try:
                moc = moc._replace(
                    name=form['name'],
                    description=form['description'],
                    description_format=int(form['description_format']),
                    public=('public' in form))

                moc_file = None
                if file_:
                    try:
                        moc_file = file_.read(10 * 1024 * 1024)

                        # Did we get all of the file within the size limit?
                        if len(file_.read(1)):
                            raise UserError('The uploaded file was too large.')

                    finally:
                        file_.close()

                elif moc_id is None:
                    raise UserError('No new MOC file was received.')

                moc_order = (None if moc_file is None
                             else self.get_moc_order())

                if moc_id is None:
                    moc_id = db.add_moc(self.id_, moc.name, moc.description,
                                        moc.description_format,
                                        moc.public, moc_order, moc_file)
                    flash('The new coverage map has been stored.')
                else:
                    db.update_moc(
                        moc_id, name=moc.name, description=moc.description,
                        description_format=moc.description_format,
                        public=moc.public,
                        moc_order=moc_order, moc_file=moc_file)

                    if moc_file is None:
                        flash('The coverage map details have been updated.')
                    else:
                        flash('The updated coverage map has been stored.')

                raise HTTPRedirect(url_for('.moc_list'))

            except UserError as e:
                message = e.message

        return {
            'title': title,
            'target': target,
            'moc': moc,
            'message': message,
            'format_types': FormatType.get_options(is_system=True),
        }

    @with_verified_admin
    def view_moc_delete(self, db, moc_id, form):
        try:
            moc = db.search_moc(facility_id=self.id_, moc_id=moc_id,
                                public=None).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Coverage map not found')

        if form:
            if 'submit_cancel' in form:
                raise HTTPRedirect(url_for('.moc_list'))

            elif 'submit_confirm' in form:
                db.delete_moc(self.id_, moc_id)
                flash('The coverage map has been deleted.')
                raise HTTPRedirect(url_for('.moc_list'))

        return {
            'title': 'Delete Coverage: {}'.format(moc.name),
            'message': 'Are you sure you wish to delete this coverage map?',
        }
