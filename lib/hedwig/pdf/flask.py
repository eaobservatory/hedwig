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

from werkzeug.test import create_environ

from ..compat import first_value
from ..config import get_facilities
from ..error import FormattedError, NoSuchValue
from ..file.pdf import pdf_merge
from ..view.people import _update_session_user
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

    def _prepare_environ(self, person_id=None, session_extra=None):
        """
        Prepare a request environment.

        If session_extra is provided, it should be a dictionary of extra
        entries to be added to the session.
        """

        person = None
        if person_id is not None:
            person = self.db.get_person(person_id)

        environ = create_environ(path='/', base_url=self.base_url)

        if (person is not None) or (session_extra is not None):
            # Emulate logging in as the given person and set the given
            # session values, then add the session cookie to the environment.
            with self.app.test_client() as client:
                with client.session_transaction() as sess:
                    if person is not None:
                        _update_session_user(person.user_id, sess=sess)

                    if session_extra is not None:
                        sess.update(session_extra)

                environ['HTTP_COOKIE'] = '; '.join(map(
                    lambda x: '{}={}'.format(x.name, x.value),
                    client.cookie_jar))

        return environ
