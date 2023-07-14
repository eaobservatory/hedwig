# Copyright (C) 2015-2023 East Asian Observatory
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

from ...error import NoSuchRecord, NoSuchValue, ParseError
from ...type.enum import BaseAffiliationType, \
    BaseCallType, BaseReviewerRole, BaseTextRole, \
    FormatType
from ...type.simple import Call, FacilityObsInfo
from ...type.util import null_tuple
from ...view.base import ViewMember
from .tool_clash import ClashTool
from .tool_avail import AvailabilityTool
from .view_admin import GenericAdmin
from .view_home import GenericHome
from .view_proposal import GenericProposal
from .view_review import GenericReview


class Generic(
        GenericAdmin, GenericHome, GenericProposal, GenericReview,
        ViewMember):
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

        return ()

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

        return (ClashTool, AvailabilityTool)

    def get_affiliation_types(self):
        """
        Get the affiliation type enum-style class to be used with this
        facility.
        """

        return BaseAffiliationType

    def get_call_types(self):
        """
        Get the call type enum-style class to be used with this facility.
        """

        return BaseCallType

    def get_text_roles(self):
        """
        Get the text roles enum-style class to be used with this
        facility.
        """

        return BaseTextRole

    def get_reviewer_roles(self):
        """
        Get the reviewer roles enum-style class to be used with this
        facility.
        """

        return BaseReviewerRole

    def get_custom_filters(self):
        """
        Return list of custom template filter functions.

        These will be registed with the web application with their names
        prefixed with the facility code and an underscore.
        """

        return []

    def get_custom_routes(self):
        """
        Return list of custom routes required for this facility.

        Note that the route information will automatically be prefixed
        as follows:

        * `template`: `<facility code>/`

        :return: a list of RouteInfo tuples
        """

        return []

    def get_new_call_default(self, type_):
        """
        Get the default parameters for a new call.

        This method is used to determine the default call parameters
        used to populate the "new call" page when it is first displayed.
        """

        return null_tuple(Call)._replace(
            semester_name='', queue_name='',
            abst_word_lim=200,
            tech_word_lim=1000, tech_fig_lim=0, tech_page_lim=1,
            sci_word_lim=2000, sci_fig_lim=4, sci_page_lim=3,
            capt_word_lim=200, expl_word_lim=200,
            tech_note='', sci_note='', prev_prop_note='',
            note_format=FormatType.PLAIN)

    def get_proposal_order(self):
        """
        Get a list of proposal sections in the order in which they should
        be shown.
        """

        return [
            'proposal_summary',
            'proposal_abstract',
            'proposal_request',
            'proposal_members',
            'proposal_previous',
            'proposal_targets',
            'proposal_calculations',
            'technical_case',
            'science_case',
        ]

    def get_proposal_order_names(self):
        """
        Get an ordered dictionary which maps proposal section codes
        to their names, in the order in which they should be shown.
        """

        names = {
            'proposal_summary': 'Summary',
            'proposal_abstract': 'Abstract',
            'proposal_request': 'Observing Request',
            'proposal_members': 'Members',
            'proposal_previous': 'Previous Proposals and Publications',
            'proposal_targets': 'Target Objects',
            'proposal_calculations': 'Calculation Results',
            'technical_case': 'Technical Justification',
            'science_case': 'Scientific Justification',
        }

        return OrderedDict(((x, names[x]) for x in self.get_proposal_order()))

    def get_observing_info(self):
        """
        Get observing information.
        """

        return null_tuple(FacilityObsInfo)

    def make_proposal_code(self, db, proposal):
        """
        Generate the proposal identifying code for a given proposal.

        This should be overridden by sub-classes to apply the naming
        scheme in use at each facility.
        """

        type_class = self.get_call_types()
        type_code = type_class.get_code(proposal.call_type)

        if type_code is None:
            suffix = ''
        else:
            suffix = '-' + type_code

        return '{}-{}-{}{}'.format(
            proposal.semester_code, proposal.queue_code, proposal.number,
            suffix)

    def parse_proposal_code(self, db, proposal_code):
        """
        Attempt to convert a proposal code into a proposal identifier.

        This is done by parsing the code and then attempting to look
        it up in the database to get the identifier number.

        :raise ParseError: if the proposal code is not understood.
        :raise NoSuchRecord: if the proposal code is understood,
            but no matching record is found in the database.
        """

        (semester_code, queue_code, call_type, proposal_number) = \
            self._parse_proposal_code(proposal_code)

        return db.search_proposal(
            facility_id=self.id_,
            semester_code=semester_code,
            queue_code=queue_code,
            call_type=call_type,
            proposal_number=proposal_number).get_single().id

    def _parse_proposal_code(self, proposal_code):
        """
        Perform the parsing step of processing a proposal code.

        This splits the code into the semester code, queue code,
        call type and proposal number.
        """

        type_class = self.get_call_types()

        try:
            components = proposal_code.split('-')
            if len(components) < 3:
                raise ParseError('Insufficient proposal code components')

            (semester_code, queue_code, proposal_number) = components[0:3]

            if len(components) == 3:
                call_type = None

            elif len(components) == 4:
                call_type = components[3]

            else:
                raise ParseError('Excess proposal code components')

            return (semester_code, queue_code, type_class.by_code(call_type),
                    int(proposal_number))

        except ValueError:
            raise ParseError('Could not parse proposal number')

        except NoSuchValue:
            raise ParseError('Did not recognise call type component')

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

    def calculate_overall_rating(self, reviews, with_std_dev=False):
        """
        Calculate the overall rating from a collection of reviewer
        records (including their reviews).
        """

        return reviews.get_overall_rating(
            self.get_review_rating_weight_function(),
            with_std_dev=with_std_dev)

    def get_review_rating_weight_function(self):
        """
        Get the numerical rating and weight of a review.

        :return: a (`rating`, `weight`) tuple.  If either value is `None` then
            the review should not be included in the overall rating.
        """

        role_class = self.get_reviewer_roles()

        def rating_weight_function(reviewer):
            role_info = role_class.get_info(reviewer.role)

            if (not role_info.rating) or (reviewer.review_rating is None):
                return (None, None)

            if role_info.weight:
                if reviewer.review_weight is None:
                    return (None, None)
                else:
                    weight = reviewer.review_weight / 100.0
            else:
                # NOTE: weighting for unrated reviews could be configurable,
                # perhaps in the facility view or perhaps in the roles class.
                # However for now assume a weighting of 100%.
                weight = 1.0

            return (reviewer.review_rating, weight)

        return rating_weight_function

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
        type is not "STANDARD") and ignoring the affiliation weight values.

        Each facility will need to override this method with a method
        implementing its own actual assignment rules.
        """

        affiliation_type_class = self.get_affiliation_types()
        affiliation_count = defaultdict(float)
        affiliation_total = 0.0

        for member in members.values():
            affiliation = member.affiliation_id
            if (affiliation is None) or (affiliation not in affiliations):
                affiliation = 0
            elif (affiliations[affiliation].type
                    != affiliation_type_class.STANDARD):
                continue

            affiliation_count[affiliation] += 1.0
            affiliation_total += 1.0

        if not affiliation_total:
            # If no valid affiliations were found, return 100% unknown.
            return {0: 1.0}

        return {k: (v / affiliation_total)
                for (k, v) in affiliation_count.items()}

    def attach_review_extra(self, db, proposals):
        """
        Get additional review information from the database.

        Placeholder method for facility-specific review information
        retrieval method.

        The reviewer records attached to each of the proposals in the
        given collection should be modified as appropriate.
        """

        pass

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
