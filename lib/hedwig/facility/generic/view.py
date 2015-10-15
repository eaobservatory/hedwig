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

from collections import defaultdict, OrderedDict

from ...config import get_config
from ...error import NoSuchRecord, UserError
from ...type import GroupType
from ...web.util import ErrorPage, HTTPNotFound, session, url_for
from .calculator_example import ExampleCalculator
from .tool_clash import ClashTool
from .view_admin import GenericAdmin
from .view_proposal import GenericProposal
from .view_review import GenericReview


class Generic(GenericAdmin, GenericProposal, GenericReview):
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

        return '{}-{}-{}'.format(
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

    def make_proposal_info_urls(self, proposal_code):
        """
        Make a list of URLs ("Link" namedtuple instances
        with "text" and "url" attributes) which link to
        more information about a proposal.

        This is used, for example, for the list of previous proposals
        which have been entered by a proposal author.
        """

        return []

    def make_review_guidelines_url(self, role):
        """
        Make an URL for guidelines to be sent to reviewers.

        Returns None if there is no suitable URL defined.
        """

        return None

    def calculate_overall_rating(self, reviews):
        """
        Calculate the overall rating from a collection of reviewer
        records (including their reviews).
        """

        return reviews.get_overall_rating(include_unweighted=True)

    def calculate_affiliation_assignment(self, db, members, affiliations):
        """
        Calculate the fractional affiliation assignment for the members
        of a proposal.

        Takes a collection of affiliations and returns a dictionary of
        fractional affiliation assignment for each affiliation identifier
        in the given collection.  A special identifier of zero is used for
        any affiliations which don't appear in the given collection.

        Note: this is a simple example implementation which just counts
        the members of each affiliation (skipping those where the affiliation
        "exclude" setting is true) and ignoring the affiliation weight values.

        Each facility will need to override this method with a method
        implementing its own actual assignment rules.
        """

        affiliation_count = defaultdict(float)
        affiliation_total = 0.0

        for member in members.values():
            affiliation = member.affiliation_id
            if (affiliation is None) or (affiliation not in affiliations):
                affiliation = 0
            elif affiliations[affiliation].exclude:
                continue

            affiliation_count[affiliation] += 1.0
            affiliation_total += 1.0

        if not affiliation_total:
            return {}

        return {k: (v / affiliation_total)
                for (k, v) in affiliation_count.items()}

    def view_facility_home(self, db):
        # Determine which semesters have open calls for proposals.
        open_semesters = OrderedDict()
        for call in db.search_call(facility_id=self.id_,
                                   is_open=True).values():
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
                group_type=GroupType.CTTEE,
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
                               is_open=True, with_queue_description=True)
        if not calls:
            raise ErrorPage('No calls are currently open for this semester.')

        return {
            'title': 'Call for Semester {}'.format(semester.name),
            'semester': semester,
            'calls': list(calls.values()),
        }

    def get_feedback_extra(self, db, proposal):
        """
        Get additional context to include in the proposal feedback email
        message.

        This message informs the proposal members whether the proposal was
        accepted or rejected at the end of the review processes.  Each facility
        should override this method to supply additional information (such
        as the time allocated) to its own template for the feedback message.
        """

        return {}
