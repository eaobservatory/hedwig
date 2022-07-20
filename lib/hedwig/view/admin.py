# Copyright (C) 2015-2022 East Asian Observatory
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

from ..compat import first_value
from ..email.format import render_email_template
from ..error import ConsistencyError, NoSuchRecord, UserError
from ..type.simple import ProposalWithCode, Link
from ..type.enum import AttachmentState, MessageState, MessageThreadType, \
    PersonTitle, RequestState, SiteGroupType
from ..web.util import ErrorPage, HTTPNotFound, HTTPRedirect, \
    flash, url_for
from . import auth
from .base import ViewMember


class AdminView(ViewMember):
    def home(self, current_user, facilities):
        return {
            'title': 'Site Administration',
            'facilities': facilities,
            'site_groups': SiteGroupType.get_options(),
        }

    def message_list(self, current_user, db, args, form):
        # Apply state updates if a form was submitted via a POST request.
        if form is not None:
            n_update = 0

            state_new = int(form['state_new'])

            if not MessageState.is_valid(state_new):
                raise ErrorPage('Requested new message state is invalid.')

            for param in form:
                if param.startswith('message_'):
                    id_ = int(param[8:])

                    state_prev = int(form['prev_state_{}'.format(id_)])

                    db.update_message(
                        message_id=id_, state=state_new, state_prev=state_prev)

                    n_update += 1

            if n_update:
                flash('The status for {} {} has been set to {}.',
                      n_update, ('message' if n_update == 1 else 'messages'),
                      MessageState.get_name(state_new).lower())

            # While preparing the display, use input values from the POST
            # form.
            current_input = form

        else:
            # While preparing the display, use input values from the query
            # parameters.
            current_input = args

        num_per_page = 100
        url_params = {}       # Params for nav links.
        set_form_params = {}  # Extras for form -- url_params will be added.
        kwargs = {'limit': num_per_page}

        person_id = current_input.get('person_id')
        if person_id is not None:
            person_id = int(person_id)
            kwargs['person_id'] = person_id
            url_params['person_id'] = person_id

        else:
            kwargs['with_recipients'] = True

        state = current_input.get('state')
        if not state:
            state = None
        if state is not None:
            state = int(state)
            kwargs['state'] = state
            url_params['state'] = state

        id_lt = current_input.get('id_lt')
        if id_lt is not None:
            id_lt = int(id_lt)
            kwargs['message_id_lt'] = id_lt
            set_form_params['id_lt'] = id_lt

        # Include all URL params in the setting form.
        set_form_params.update(url_params)

        # If responding to a POST request, redirect the user back to the
        # message page (as a GET request) so that it is safe for them to
        # refresh the page.
        if form is not None:
            raise HTTPRedirect(url_for('.message_list', **set_form_params))

        # Retreive person profile if displaying a list for a given person.
        person = None
        if person_id is not None:
            try:
                person = db.get_person(person_id)
            except:
                raise ErrorPage(
                    'Message list requested for non-existent person.')

        # Retrieve messages.
        messages = db.search_message(**kwargs)

        # Prepare pagination URLs.  Give only "first" and "next" links as
        # we can generate these with simple SQL constructs (id < x, limit).
        target_first = None
        target_next = None

        if id_lt is not None:
            target_first = url_for('.message_list', **url_params)

        # Guess that there are more messages if we have as many as the limit
        # specified.  (Might not be true if the number of messages is divisible
        # by the number per page.)
        if len(messages) >= num_per_page:
            target_next = url_for('.message_list', id_lt=min(messages.keys()),
                                  **url_params)

        return {
            'title': ('Message List' if person is None
                      else '{}: Messages'.format(person.name)),
            'person': person,
            'messages': messages,
            'target_first': target_first,
            'target_next': target_next,
            # Parameters for the filtering form at the top of the page:
            'form_params': {k: v for (k, v) in url_params.items()
                            if k != 'state'},
            # Parameters for the state setting form (submit at bottom of page).
            'set_form_params': set_form_params,
            'current_state': state,
            'states': MessageState.get_options(is_system=True),
            'states_allowed': MessageState.get_options(),
        }

    def message_view(self, current_user, db, message_id):
        try:
            message = db.get_message(message_id)
        except NoSuchRecord:
            raise HTTPNotFound('Message not found')

        return {
            'title': 'Message: {}'.format(message.subject),
            'message': message,
        }

    def message_alter_state(self, current_user, db, message_id, form):
        try:
            message = db.get_message(message_id)
        except NoSuchRecord:
            raise HTTPNotFound('Message not found')

        warning_message = None
        if form is not None:
            try:
                state_new = int(form['state'])
                state_prev = int(form['state_prev'])

                if state_new != state_prev:
                    try:
                        db.update_message(
                            message_id=message_id,
                            state=state_new, state_prev=state_prev)

                        flash(
                            'The state has been set to {}.',
                            MessageState.get_name(state_new).lower())

                    except ConsistencyError:
                        raise ErrorPage(
                            'The state could not be updated.  Perhaps it '
                            'changed since you opened the page.')

                raise HTTPRedirect(url_for(
                    '.message_view', message_id=message_id))

            except UserError as e:
                warning_message = e.message

        return {
            'title': 'Alter status: {}'.format(message.subject),
            'message': message,
            'warning_message': warning_message,
            'states': MessageState.get_options(),
        }

    def message_thread(
            self, current_user, db, facilities, thread_type, thread_id):
        messages = db.search_message(
            thread_type=thread_type, thread_id=thread_id, oldest_first=True)

        return {
            'title': 'Message thread: {}'.format(
                MessageThreadType.get_name(thread_type)),
            'messages': messages,
            'thread_links': self._make_thread_links(
                current_user, db, facilities, thread_type, thread_id)
        }

    def _make_thread_links(
            self, current_user, db, facilities, thread_type, thread_id):
        links = []

        proposal = None
        reviewer = None
        facility = None

        try:
            if thread_type in (
                    MessageThreadType.PROPOSAL_STATUS,
                    MessageThreadType.PROPOSAL_REVIEW):
                proposal = db.get_proposal(None, thread_id)

            elif thread_type == MessageThreadType.REVIEW_INVITATION:
                reviewer = db.search_reviewer(
                    reviewer_id=thread_id).get_single()
                proposal = db.get_proposal(
                    None, reviewer.proposal_id, with_members=True)

            facility = facilities.get(proposal.facility_id)

        except NoSuchRecord:
            pass

        if facility is not None:
            if proposal is not None:
                links.append(Link('View proposal', url_for(
                    '{}.proposal_view'.format(facility.code),
                    proposal_id=proposal.id)))

            if reviewer is not None:
                role_class = facility.view.get_reviewer_roles()

                can = auth.for_review(
                    role_class, current_user, db,
                    reviewer=None, proposal=proposal,
                    allow_unaccepted=True)

                links.append(Link('Review assignment', url_for(
                    '{}.review_call_reviewers'.format(facility.code),
                    call_id=proposal.call_id)))

                if can.view:
                    links.append(Link('View proposal reviews', url_for(
                        '{}.proposal_reviews'.format(facility.code),
                        proposal_id=proposal.id)))

                if can.edit:
                    links.append(Link('Edit review', url_for(
                        '{}.review_edit'.format(facility.code),
                        reviewer_id=reviewer.id)))

        return links

    def processing_status(self, current_user, db, facilities, form):
        if form is not None:
            n_reset = 0

            for param in form:
                if param.startswith('pdf_'):
                    id_ = int(param[4:])
                    state_prev = int(form['prev_{}'.format(param)])
                    if state_prev == AttachmentState.NEW:
                        continue
                    db.update_proposal_pdf(
                        pdf_id=id_, state=AttachmentState.NEW,
                        state_prev=state_prev)
                    n_reset += 1

                elif param.startswith('prop_fig_'):
                    id_ = int(param[9:])
                    state_prev = int(form['prev_{}'.format(param)])
                    if state_prev == AttachmentState.NEW:
                        continue
                    db.update_proposal_figure(
                        proposal_id=None, role=None, link_id=None, fig_id=id_,
                        state=AttachmentState.NEW, state_prev=state_prev)
                    n_reset += 1

                elif param.startswith('rev_fig_'):
                    id_ = int(param[8:])
                    state_prev = int(form['prev_{}'.format(param)])
                    if state_prev == AttachmentState.NEW:
                        continue
                    db.update_review_figure(
                        reviewer_id=None, link_id=None, fig_id=id_,
                        state=AttachmentState.NEW, state_prev=state_prev)
                    n_reset += 1

                elif param.startswith('pub_'):
                    id_ = int(param[4:])
                    state_prev = int(form['prev_{}'.format(param)])
                    if state_prev == AttachmentState.NEW:
                        continue
                    db.update_prev_proposal_pub(
                        pp_pub_id=id_, state=AttachmentState.NEW,
                        state_prev=state_prev)
                    n_reset += 1

                elif param.startswith('moc_'):
                    id_ = int(param[4:])
                    state_prev = int(form['prev_{}'.format(param)])
                    if state_prev == AttachmentState.NEW:
                        continue
                    db.update_moc(
                        moc_id=id_, state=AttachmentState.NEW,
                        state_prev=state_prev)
                    n_reset += 1

            if n_reset:
                flash('The status for {} {} has been reset.',
                      n_reset, ('entry' if n_reset == 1 else 'entries'))
            raise HTTPRedirect(url_for('.processing_status'))

        # We would like to search with the "no_link" option to only
        # receive one result per real PDF / figure.  However we need
        # the proposal / reviewer information for display purposes,
        # so fetch with links and then filter in the `_add_proposal`
        # method based on the real ID field.

        search_kwargs = {
            'state': AttachmentState.unready_states(),
            'order_by_date': True,
        }

        status_prop = {
            'pdfs': ('pdf_id', db.search_proposal_pdf(
                with_uploader_name=True, **search_kwargs)),
            'prop_figures': ('fig_id', db.search_proposal_figure(
                with_uploader_name=True, **search_kwargs)),
            'pubs': (None, db.search_prev_proposal_pub(
                with_proposal_id=True, **search_kwargs)),
        }

        status_rev = {
            'rev_figures': ('fig_id', db.search_review_figure(
                with_uploader_name=True, **search_kwargs)),
        }

        # Create empty cache dictionaries.
        proposals = {}
        reviewers = {}
        clash_tool_facilities = {}
        cache_ext = {
            'proposal_facilities': {},
            'facility_text_roles': {},
            'facility_reviewer_roles': {},
        }

        ctx = {
            'title': 'Processing Status',
            'mocs': self._add_moc_facility(
                db.search_moc(
                    facility_id=None, public=None, **search_kwargs).values(),
                facilities, clash_tool_facilities),
        }

        for (k, v) in status_prop.items():
            ctx[k] = self._add_proposal(
                db, facilities, proposals, None, *v, **cache_ext)

        for (k, v) in status_rev.items():
            ctx[k] = self._add_proposal(
                db, facilities, proposals, reviewers, *v, **cache_ext)

        return ctx

    def _add_proposal(
            self, db, facilities, proposals, reviewers, id_field, entries,
            proposal_facilities, facility_text_roles, facility_reviewer_roles):
        if not entries:
            return None

        result = []
        seen_ids = set()

        EntryWithPropRev = namedtuple(
            'EntryWithPropRev', first_value(entries)._fields + (
                'proposal', 'reviewer', 'facility_code',
                'text_roles', 'reviewer_roles'))

        for entry in entries.values():
            if id_field is not None:
                id_ = getattr(entry, id_field)
                if id_ in seen_ids:
                    continue
                seen_ids.add(id_)

            if reviewers is None:
                reviewer = None
                proposal_id = entry.proposal_id

            else:
                reviewer = reviewers.get(entry.reviewer_id)
                if reviewer is None:
                    reviewer = db.search_reviewer(
                        reviewer_id=entry.reviewer_id,
                        with_review=True).get_single()
                proposal_id = reviewer.proposal_id

            proposal = proposals.get(proposal_id)

            if proposal is None:
                proposal = db.get_proposal(facility_id=None,
                                           proposal_id=proposal_id)
                facility = facilities.get(proposal.facility_id)
                if facility is None:
                    continue
                proposal = ProposalWithCode(
                    *proposal,
                    code=facility.view.make_proposal_code(db, proposal))
                proposals[proposal_id] = proposal

                facility_code = facility.code
                proposal_facilities[proposal_id] = facility_code

                text_roles = facility.view.get_text_roles()
                facility_text_roles[facility_code] = text_roles

                reviewer_roles = facility.view.get_reviewer_roles()
                facility_reviewer_roles[facility_code] = reviewer_roles

            else:
                facility_code = proposal_facilities[proposal_id]
                text_roles = facility_text_roles[facility_code]
                reviewer_roles = facility_reviewer_roles[facility_code]

            result.append(
                EntryWithPropRev(
                    *entry, proposal=proposal, reviewer=reviewer,
                    facility_code=facility_code,
                    text_roles=text_roles, reviewer_roles=reviewer_roles))

        return result

    def _add_moc_facility(self, entries, facilities, clash_tool_facilities):
        result = []

        for entry in entries:
            facility = facilities.get(entry.facility_id)
            if facility is None:
                continue

            has_clash_tool = clash_tool_facilities.get(facility.id)
            if has_clash_tool is None:
                has_clash_tool = 'clash' in (
                    x.code for x in facility.view.target_tools.values())
                clash_tool_facilities[facility.id] = has_clash_tool
            if not has_clash_tool:
                continue

            result.append(namedtuple(
                'EntryWithCode', entry._fields + ('facility_code',))(
                *entry, facility_code=facility.code))

        return result

    def request_status(self, current_user, db, facilities, form):
        if form is not None:
            n_reset = 0

            for param in form:
                if param.startswith('prop_copy_'):
                    id_ = int(param[10:])
                    state_prev = int(form['prev_{}'.format(param)])
                    db.update_request_prop_copy(
                        request_id=id_, state=RequestState.NEW,
                        state_prev=state_prev)
                    n_reset += 1

            if n_reset:
                flash('The status for {} {} has been reset.',
                      n_reset, ('request' if n_reset == 1 else 'requests'))
            raise HTTPRedirect(url_for('.request_status'))

        search_kwargs = {
            'state': RequestState.unready_states(),
            'with_requester_name': True,
        }

        cache = {
            'proposals': {},
            'proposal_facilities': {},
        }

        ctx = {
            'title': 'Request Status',
            'req_prop_copy': self._add_req_prop(
                db, facilities,
                db.search_request_prop_copy(**search_kwargs), **cache),
        }

        return ctx

    def _add_req_prop(
            self, db, facilities, requests, proposals, proposal_facilities):
        if not requests:
            return None

        result = []

        EntryWithProp = namedtuple(
            'EntryWithProp', first_value(requests)._fields + (
                'proposal', 'facility_code'))

        for request in reversed(requests.values()):
            proposal = proposals.get(request.proposal_id)

            if proposal is None:
                proposal = db.get_proposal(
                    facility_id=None, proposal_id=request.proposal_id)
                facility = facilities.get(proposal.facility_id)
                if facility is None:
                    continue
                proposal = ProposalWithCode(
                    *proposal,
                    code=facility.view.make_proposal_code(db, proposal))

                proposals[request.proposal_id] = proposal
                proposal_facilities[request.proposal_id] = \
                    facility_code = facility.code

            else:
                facility_code = proposal_facilities[request.proposal_id]

            result.append(EntryWithProp(
                *request, proposal=proposal, facility_code=facility_code))

        return result

    def user_unregistered(self, current_user, db):
        return {
            'title': 'Unregistered Users',
            'users': db.search_user(registered=False),
        }

    def site_group_view(self, current_user, db, site_group_type):
        try:
            site_group_info = SiteGroupType.get_info(site_group_type)
        except KeyError:
            raise HTTPNotFound('Unknown site group.')

        members = db.search_site_group_member(
            site_group_type=site_group_type, with_person=True)

        return {
            'title': '{}'.format(site_group_info.name),
            'site_group_type': site_group_type,
            'site_group_info': site_group_info,
            'members': members,
        }

    def site_group_member_add(self, current_user, db, site_group_type, form):
        try:
            site_group_info = SiteGroupType.get_info(site_group_type)
        except KeyError:
            raise HTTPNotFound('Unknown site group.')

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

                    db.add_site_group_member(site_group_type, person.id)

                    flash('{} has been added to the site group.', person.name)

                    raise HTTPRedirect(url_for(
                        '.site_group_view', site_group_type=site_group_type))

                except UserError as e:
                    message_link = e.message

            else:
                try:
                    member_info.raise_()

                    person_id = db.add_person(
                        member['name'], title=member['title'],
                        primary_email=member['email'])

                    db.add_site_group_member(site_group_type, person_id)

                    self._message_site_group_invite(
                        current_user, db,
                        site_group_info=site_group_info,
                        person_id=person_id,
                        person_name=member['name'])

                    flash(
                        '{} has been added to the site group.', member['name'])

                    # Return to the site group page after editing the new
                    # member's institution.
                    raise HTTPRedirect(url_for(
                        'people.person_edit_institution',
                        person_id=person_id, next_page=url_for(
                            '.site_group_view',
                            site_group_type=site_group_type)))

                except UserError as e:
                    message_invite = e.message

        # Prepare list of people to display as the registered member directory.
        # Note that this includes people without public profiles as this page
        # is restricted to administrators.
        existing_person_ids = [
            x.person_id for x in db.search_site_group_member(
                site_group_type=site_group_type).values()]
        persons = [
            p for p in db.search_person(
                registered=True, with_institution=True).values()
            if p.id not in existing_person_ids]

        return {
            'title': 'Add Site Group Member',
            'persons': persons,
            'member': member_info.data,
            'message_link': message_link,
            'message_invite': message_invite,
            'target': url_for(
                '.site_group_member_add', site_group_type=site_group_type),
            'title_link': 'Add a Member from the Directory',
            'title_invite': 'Invite a Member to Register',
            'submit_link': 'Add to site group',
            'submit_invite': 'Invite to register',
            'label_link': 'Member',
            'navigation': [
                'site_admin',
                (site_group_info.name, url_for(
                    '.site_group_view', site_group_type=site_group_type))],
            'help_link': url_for('help.admin_page', page_name='site_group'),
            'titles': PersonTitle.get_options(),
        }

    def _message_site_group_invite(
            self, current_user, db, site_group_info, person_id, person_name):
        (token, expiry) = db.issue_invitation(person_id, days_valid=7)

        email_ctx = {
            'inviter_name': current_user.person.name,
            'recipient_name': person_name,
            'site_group': site_group_info,
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
            '{} invitation'.format(site_group_info.name),
            render_email_template('site_group_invitation.txt', email_ctx),
            [person_id])

    def site_group_member_edit(self, current_user, db, site_group_type, form):
        try:
            site_group_info = SiteGroupType.get_info(site_group_type)
        except KeyError:
            raise HTTPNotFound('Unknown site group.')

        message = None

        members = db.search_site_group_member(
            site_group_type=site_group_type, with_person=True)

        if form is not None:
            try:
                for member_id in list(members.keys()):
                    if 'member_{}'.format(member_id) in form:
                        # Currently nothing to update for existing members.
                        pass

                    else:
                        del members[member_id]

                db.sync_site_group_member(site_group_type, members)
                flash('The site group membership has been saved.')
                raise HTTPRedirect(url_for(
                    '.site_group_view', site_group_type=site_group_type))

            except UserError as e:
                message = e.message

        return {
            'title': 'Edit Site Group Membership',
            'site_group_type': site_group_type,
            'site_group_info': site_group_info,
            'members': members,
            'message': message,
        }

    def site_group_member_reinvite(
            self, current_user, db, site_group_type, member_id, form):
        try:
            site_group_info = SiteGroupType.get_info(site_group_type)
        except KeyError:
            raise HTTPNotFound('Unknown site group.')

        try:
            member = db.search_site_group_member(
                site_group_type=site_group_type,
                site_group_member_id=member_id, with_person=True).get_single()
        except NoSuchRecord:
            raise HTTPNotFound('Site group member record not found.')

        if member.person_registered:
            raise ErrorPage('This site group member is already registered.')

        if form:
            if 'submit_confirm' in form:
                self._message_site_group_invite(
                    current_user, db,
                    site_group_info=site_group_info,
                    person_id=member.person_id,
                    person_name=member.person_name)

                flash('{} has been re-invited to the site group.',
                      member.person_name)

            raise HTTPRedirect(url_for(
                '.site_group_view', site_group_type=site_group_type))

        return {
            'title': 'Re-send Site Group Member Invitation',
            'message':
                'Would you like to re-send an invitation to '
                'site group "{}" to {}?'.format(
                    site_group_info.name, member.person_name),
        }
