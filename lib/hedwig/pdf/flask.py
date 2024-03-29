# Copyright (C) 2016-2023 East Asian Observatory.
# All Rights Reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from contextlib import contextmanager

from flask import g as flask_g
from werkzeug.test import create_environ

from ..compat import first_value
from ..config import get_facilities
from ..error import FormattedError, NoSuchValue
from ..file.pdf import pdf_merge
from ..type.enum import GroupType
from ..type.simple import CurrentUser, UserInfo
from ..type.util import null_tuple
from .write import PDFWriter


class PDFWriterFlask(PDFWriter):
    """
    Base class for Hedwig PDF writers which will make requests through Flask.
    """

    def proposal(self, proposal_id):
        """
        Request PDF representation of a proposal.
        """

        proposal = self.db.get_proposal(None, proposal_id, with_members=True)

        # Determine the proposal PI.  We will access the proposal as if
        # logged in as this person.
        try:
            person_id = proposal.members.get_pi().person_id
        except NoSuchValue:
            # If there was no PI, try any proposal member.
            try:
                person_id = first_value(proposal.members).person_id
            except IndexError:
                raise FormattedError(
                    'No members found for proposal {}', proposal_id)

        # Determine URL to use to access the proposal.
        facility_code = get_facilities(db=self.db)[proposal.facility_id].code
        url = '{}/proposal/{}'.format(facility_code, proposal_id)

        # Request and return the PDF.
        return pdf_merge(self._request_pdf(url, person_id, section=True))

    def reviews(self, proposal_id):
        """
        Request PDF representation of reviews of a proposal.
        """

        # Find a reviewer who is not a member of the proposal.
        proposal = self.db.get_proposal(
            facility_id=None, proposal_id=proposal_id, with_members=True)
        for group_member in self.db.search_group_member(
                facility_id=proposal.facility_id,
                queue_id=proposal.queue_id,
                group_type=GroupType.review_view_groups()).values():
            if not proposal.members.has_person(group_member.person_id):
                person_id = group_member.person_id
                break
        else:
            raise FormattedError(
                'No non-member reviewers found for proposal {}', proposal_id)

        # Determine URL to use to access the reviews.
        facility_code = get_facilities(db=self.db)[proposal.facility_id].code
        url = '{}/proposal/{}/review/'.format(facility_code, proposal_id)

        # Request and return the PDF.
        return self._request_pdf(url, person_id)

    @contextmanager
    def _fixed_auth(self, person_id, session_options={}):
        """
        Prepare fixed log-in information by temporarily setting a
        `before_request` function to place a fixed `current_user`
        object in the flask `g` object.

        If `session_options` is provided, it should be a dictionary of extra
        information to include in the `current_user` object.
        """

        # Make sure there are no "before_request" functions, since we
        # will clear them later -- `create_web_app` should have been called
        # using: without_auth=True.
        assert (not self.app.before_request_funcs), 'no before_request func.'

        user = None
        person = None
        if person_id is not None:
            person = self.db.get_person(person_id)
            user = null_tuple(UserInfo)._replace(id=person.user_id)

        current_user = CurrentUser(
            user=user,
            person=person,
            is_admin=False,
            auth_token_id=None,
            options=session_options)

        try:
            @self.app.before_request
            def apply_fixed_auth():
                flask_g.current_user = current_user

            yield

        finally:
            # Remove our fixed log-in "before_request" function.
            self.app.before_request_funcs.clear()

    def _prepare_environ(self):
        """
        Prepare a request environment.
        """

        environ = create_environ(path='/', base_url=self.base_url)

        return environ
