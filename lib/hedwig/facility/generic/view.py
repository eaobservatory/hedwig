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

from collections import OrderedDict

from ...config import get_config
from ...error import NoSuchRecord, UserError
from ...web.util import ErrorPage, HTTPNotFound, url_for
from .calculator_example import ExampleCalculator
from .tool_clash import ClashTool
from .view_admin import GenericAdmin
from .view_proposal import GenericProposal


class Generic(GenericAdmin, GenericProposal):
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
        self.calculators = OrderedDict()
        self.target_tools = OrderedDict()

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

    def get_definite_name(self):
        """
        Get the name of the facility, with a definate article
        for use in a sentence, if one would be appropriate.

        e.g. "the JCMT" or "UKIRT".

        Subclasses should override this method if they do not want
        the word "the" to appear.
        """

        return 'the {}'.format(self.get_name())

    def get_calculator_classes(self):
        """
        Get a tuple of calculator classes which can be used with this
        facility.

        Sub-classes should override this method to provide the correct
        list of calculators.
        """

        return (ExampleCalculator,)

    def get_moc_order(self):
        """
        Get the MOC order at which MOCs should be stored for this
        facility.

        The higher the order of the MOC, the more precise it becomes,
        but with an associated increase in storage space and
        search time.

        An appropriate value should be given here.  It is important
        that the value is not reduced once MOCs have already been
        stored.  That would cause there to be orders in the database
        higher than the current level and any cells in those orders
        would not be found in subsequent cell searches.
        """

        # MOC order 12 corresponds to 52" cells.
        return 12

    def get_target_tool_classes(self):
        """
        Get a tuple of the target tool classes which can be used
        with this facility.
        """

        return (ClashTool,)

    def make_proposal_code(self, db, proposal):
        """
        Generate the proposal identifying code for a given proposal.

        This should be overridden by sub-classes to apply the naming
        scheme in use at each facility.
        """

        return '{0}-{1}-{2}'.format(
            proposal.semester_code, proposal.queue_code, proposal.number)

    def parse_proposal_code(self, db, proposal_code):
        """
        Attempt to convert a proposal code into a proposal identifier.

        This is done by parsing the code and then attempting to look
        it up in the database to get the identifier number.
        """

        (semester_code, queue_code, proposal_number) = \
            self._parse_proposal_code(proposal_code)

        return db.search_proposal(
            facility_id=self.id_,
            semester_code=semester_code,
            queue_code=queue_code,
            proposal_number=proposal_number).get_single().id

    def _parse_proposal_code(self, proposal_code):
        """
        Perform the parsing step of processing a proposal code.

        This splits the code into the semester code, queue code
        and proposal number.
        """

        try:
            (semester_code, queue_code, proposal_number) = \
                proposal_code.split('-', 2)

            return (semester_code, queue_code, int(proposal_number))

        except ValueError:
            raise NoSuchRecord('Could not parse proposal code')

    def make_archive_search_url(self, ra_deg, dec_deg):
        """
        Make an URL to the facility's archive search page for
        the given coordinates.

        Returns None when not implemented.
        """

        return None

    def view_facility_home(self, db):
        # Determine which semesters have open calls for proposals.
        open_semesters = OrderedDict()
        for call in db.search_call(facility_id=self.id_,
                                   is_open=True).values():
            if call.semester_id not in open_semesters:
                open_semesters[call.semester_id] = call.semester_name

        return {
            'title': self.get_name(),
            'open_semesters': open_semesters,
            'calculators': self.calculators.values(),
            'target_tools': self.target_tools.values(),
        }

    def view_semester_calls(self, db, semester_id):
        try:
            semester = db.get_semester(self.id_, semester_id)
        except NoSuchRecord:
            raise HTTPNotFound('Semester not found')

        calls = db.search_call(facility_id=self.id_, semester_id=semester_id,
                               is_open=True, with_queue_description=True)
        if not calls:
            raise ErrorPage('No calls are currently open for this semester.')

        return {
            'title': 'Call for Semester {0}'.format(semester.name),
            'semester': semester,
            'calls': calls.values(),
        }
