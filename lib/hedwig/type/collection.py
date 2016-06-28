# Copyright (C) 2015-2016 East Asian Observatory
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

from collections import OrderedDict, namedtuple
from math import sqrt

from ..astro.coord import CoordSystem, coord_from_dec_deg, coord_to_dec_deg, \
    format_coord, parse_coord
from ..error import NoSuchRecord, MultipleRecords, UserError
from .enum import AffiliationType, PublicationType, ReviewState
from .simple import TargetObject

ResultTable = namedtuple('ResultTable', ('table', 'columns', 'rows'))


class ResultCollection(OrderedDict):
    """
    Class used to store the results of a database search.

    This is a subclass of `OrderedDict`, ususally indexed by the
    identifier of a row in the database.
    """

    def get_single(self, default=()):
        """
        Assuming that the collection contains a single value, return
        that value.

        If the collection is empty, a `NoSuchRecord` exception is raised
        unless a value is given as the `default`, in which case it is
        returned.

        If there are multiple values in the collection, a `MultipleRecords`
        exception is raised.
        """

        n = len(self)
        if n == 0:
            if default == ():
                raise NoSuchRecord('can not get single record: no results')
            else:
                return default
        elif n > 1:
            raise MultipleRecords('can not get single record: many results')
        else:
            # WARNING: Python-2 only.
            return self.values()[0]


class OrderedResultCollection(ResultCollection):
    """
    Subclass of `ResultCollection` for results from tables with a `sort_order`
    column.
    """

    def ensure_sort_order(self):
        """
        Ensure all records have a non-`None` `sort_order` entry.

        Iterates through the entries in this collection finding the maximum
        sort_order used and all the entries without a sort order.  Then those
        entries are assigned `sort_order` values above the previous maximum
        in the order in which they appear in the collection.
        """

        i = 0
        unordered = []

        for (key, value) in self.items():
            if value.sort_order is None:
                unordered.append(key)
            elif value.sort_order > i:
                i = value.sort_order

        for key in unordered:
            i += 1
            self[key] = self[key]._replace(sort_order=i)


class AffiliationCollection(ResultCollection):
    """
    Class to hold th results of an affiliation search,
    """

    def validate(self):
        """
        Validates a set of affiliation records.

        Checks:

        * All affiliation types must be valid.

        :raises UserError: if any problems are found
        """

        for affiliation in self.values():
            if not AffiliationType.is_valid(affiliation.type):
                raise UserError(
                    'Affiliation "{}" has invalid type', affiliation.name)


class CallCollection(ResultCollection):
    """
    Class to hold the results of a search for calls for proposals.
    """

    def values_by_state(self, state):
        """
        Get a list of the calls with the given state.
        """

        return [x for x in self.values() if x.state == state]

    def values_by_queue(self, queue_id):
        """
        Get a list of the calls with the given queue ID.

        The queue ID can also be specified as a list or tuple of possible
        values.
        """

        if not(isinstance(queue_id, list) or isinstance(queue_id, tuple)):
            queue_id = (queue_id,)

        return [x for x in self.values() if x.queue_id in queue_id]


class EmailCollection(ResultCollection):
    """
    Class to hold a collection of email addresses.
    """

    def get_primary(self):
        """
        Return the primary email address.

        This is the first email address found with a true value of the
        `primary` attribute.  If no such address is found, a `KeyError`
        exception is raised.
        """

        for email in self.values():
            if email.primary:
                return email

        raise KeyError('no primary address')

    def validate(self):
        """
        Attempts to validate a collection of email records.

        Checks:

        * There is exactly one primary address.
        * No email addresses are duplicated.

        Raises a `UserError` exception for any problems found.
        """

        n_primary = 0
        seen_address = set()

        for email in self.values():
            if email.primary:
                n_primary += 1

            if email.address in seen_address:
                raise UserError('The address "{}" appears more than once.',
                                email.address)
            seen_address.add(email.address)

        if n_primary == 0:
            raise UserError('There is no primary address.')
        elif n_primary != 1:
            raise UserError('There is more than one primary address.')


class GroupMemberCollection(ResultCollection):
    """
    Class to hold a collection of review group members.
    """

    def values_by_group_type(self, group_type):
        """
        Get a list of the group members with the given role.
        """

        return [x for x in self.values() if x.group_type == group_type]


class MemberCollection(OrderedResultCollection):
    """
    Class to hold a collection of proposal members.
    """

    def get_pi(self, default=()):
        """
        Retrive the record corresponding to the principal investigator (PI).

        :return: the first member found with a true value for the `pi`
            attribute, or if no such member is found, the given default
            value.

        :raises KeyError: if no PI member is found and no default is given.
        """

        for member in self.values():
            if member.pi:
                return member

        if default == ():
            raise KeyError('no pi member')
        else:
            return default

    def get_person(self, person_id):
        """
        Retrieve the record corresponding to the given person.

        If no member with this `person_id` is found, a `KeyError`
        exception is raised.
        """

        for member in self.values():
            if member.person_id == person_id:
                return member

        raise KeyError('person not in member collection')

    def get_students(self):
        """
        Get a list of student members.

        This constructs a list of the members with the `student` attribute
        set to a true value.
        """

        ans = []

        for member in self.values():
            if member.student:
                ans.append(member)

        return ans

    def has_person(self, person_id):
        """
        Check for an entry for a given person.
        """

        for member in self.values():
            if member.person_id == person_id:
                return True

        return False

    def validate(self, editor_person_id):
        """
        Attempts to validate the members of a proposal.

        Checks:

        * There is exactly one PI.
        * There is at least one editor.
        * The given person ID is an editor.  (To prevent people removing
          their own editor permission.)

        Raises a `UserError` exception for any problems found.

        `editor_person_id` can be set to `None` to disable the person checks.
        """

        n_pi = 0
        n_editor = 0
        person_is_editor = None

        for member in self.values():
            if member.pi:
                n_pi += 1

            if member.editor:
                n_editor += 1

            if ((editor_person_id is not None) and
                    (member.person_id == editor_person_id)):
                person_is_editor = member.editor

        if n_pi == 0:
            raise UserError('There is no PI specified.')
        elif n_pi != 1:
            raise UserError('There is more than one PI specified.')

        if n_editor == 0:
            raise UserError('There are no specified editors.')

        if editor_person_id is not None:
            if person_is_editor is None:
                raise UserError(
                    'You can not remove yourself from the proposal.')
            elif not person_is_editor:
                raise UserError(
                    'You can not remove yourself as an editor.')


class PrevProposalCollection(ResultCollection):
    """
    Class to represent a collection of previous proposals.
    """

    def validate(self):
        """
        Attempt to validate the previous proposal collection.

        Checks:

        * Each entry has a proposal code.
        * No entry has more than 6 publications.
        * No code or identifier is repeated.

        Raises a `UserError` exception for any problems found.
        """

        seen_codes = set()
        seen_ids = {}

        for pp in self.values():
            if not pp.proposal_code:
                raise UserError(
                    'A proposal code must be specified for each entry.')

            if pp.proposal_code in seen_codes:
                raise UserError(
                    'Proposal code {} is listed more than once.',
                    pp.proposal_code)

            if pp.proposal_id is not None:
                if pp.proposal_id in seen_ids:
                    raise UserError(
                        'Proposal codes {} and {} appear to refer to '
                        'the same proposal.',
                        seen_ids[pp.proposal_id], pp.proposal_code)

            if len(pp.publications) > 6:
                raise UserError(
                    'More than 6 publications are specified for proposal {}.',
                    pp.proposal_code)

            for publication in pp.publications:
                if not publication.description:
                    raise UserError(
                        'Description missing for a publication for '
                        'proposal {}', pp.proposal_code)

                if not PublicationType.is_valid(publication.type):
                    raise UserError(
                        'Unknown publication type for publication "{}" '
                        '(for proposal {}).',
                        publication.description, pp.proposal_code)

                type_info = PublicationType.get_info(publication.type)
                if type_info.regex is not None:
                    for regex in type_info.regex:
                        if regex.search(publication.description):
                            break
                    else:
                        raise UserError(
                            '{} "{}" (for proposal {}) does not appear '
                            'to be valid.  An entry of the form "{}" was '
                            'expected.  If you are having trouble entering '
                            'this reference, please change the type to '
                            '"{}" to avoid this system trying to process it.',
                            type_info.name, publication.description,
                            pp.proposal_code, type_info.placeholder,
                            PublicationType.get_info(
                                PublicationType.PLAIN).name)

            # Record the code and identifier to check for duplicates.
            seen_codes.add(pp.proposal_code)

            if pp.proposal_id is not None:
                seen_ids[pp.proposal_id] = pp.proposal_code


class ProposalTextCollection(ResultCollection):
    """
    Class to represent a collection of pieces of text for a proposal.

    This is also used for PDF files attached to the proposals in
    place of text.
    """

    def get_role(self, role, default=()):
        """
        Retrieve the entry corresponding to the given role.

        If no entry with a `role` attribute matching the given value
        is found, a `KeyError` exception is raised unless a `default`
        value is given, in which case that value is returned.
        """

        for pdf in self.values():
            if pdf.role == role:
                return pdf

        if default == ():
            raise KeyError('no text/PDF for this role')
        else:
            return default


class ProposalFigureCollection(ResultCollection):
    """
    Class representing a collection of figures attached to a proposal.
    """

    def values_by_role(self, role):
        """
        Return a list of values for the given role.
        """

        return [x for x in self.values() if x.role == role]


class ReviewerCollection(ResultCollection):
    """
    Collection class for reviewers of a proposal, possibly also
    including their reviews.
    """

    def __init__(self, role_class, *args, **kwargs):
        super(ReviewerCollection, self).__init__(*args, **kwargs)

        self.role_class = role_class

    def get_overall_rating(self, rating_weight_function, with_std_dev):
        """
        Create weighted average of the ratings of completed reviews.

        :param rating_weight_function: a function to be called for each
            review in the collection.  It should return a pair of
            (rating, weight) where the review will be ignored if the
            rating or weight is None.  The weight should be a fractional
            value from 0.0 to 1.0.

        :param with_std_dev: requests calculation of the standard deviation.

        :return: the overall rating (floating point number), unless the
            standard deviation is requested, when a pair retuned as
            (overall_rating, standard_deviation).
        """

        total_rating = 0.0
        total_weight = 0.0
        rating_and_weight = []

        for review in self.values():
            # Skip incomplete reviews.
            if review.review_state != ReviewState.DONE:
                continue

            # Get rating and weight for this review.
            (rating, weight) = rating_weight_function(review)

            if (rating is None) or (weight) is None:
                continue

            # Add to running totals.
            total_rating += rating * weight
            total_weight += weight

            # Record the validated ratings with their weights in case
            # we want also to calculate the standard deviation.
            rating_and_weight.append((review.review_rating, weight))

        if not total_weight:
            return (None, None) if with_std_dev else None

        overall_rating = total_rating / total_weight

        if not with_std_dev:
            return overall_rating

        # If we require the standard deviation, iterate over the values
        # again to calculate the deviation from the weighted mean.
        total_dev = 0.0

        for (rating, weight) in rating_and_weight:
            total_dev += weight * ((rating - overall_rating) ** 2)

        std_dev = sqrt(total_dev / total_weight)

        return (overall_rating, std_dev)

    def has_person(self, person_id, roles=None):
        """
        Check for an entry for a given person.

        Returns True if entry is found matching the given `person_id`.
        Optionally also checks that the reviewer `role` attribute is
        in the given set of `roles`.

        Returns False if no matching record is found.
        """

        for member in self.values():
            if ((member.person_id == person_id) and
                    ((roles is None) or (member.role in roles))):
                return True

        return False

    def has_role(self, role):
        """
        Check if the collection has an entry in the given role.
        """

        for member in self.values():
            if member.role == role:
                return True

        return False

    def person_id_by_role(self, role):
        """
        Get a list of the person identifiers for members of this
        reveiwer collection with the given role.
        """

        return [x.person_id for x in self.values() if x.role == role]

    def role_by_person_id(self, person_id):
        """
        Get a list of the reviewer roles for the given person.
        """

        return [x.role for x in self.values() if x.person_id == person_id]

    def values_by_role(self, role):
        """
        Get a list of the reviewers with the given role.
        """

        return [x for x in self.values() if x.role == role]

    def values_in_role_order(self, role_class, cttee_role=None):
        """
        Iterate over the values of the collection in the order of
        the reviewer roles.

        Optionally return only committee roles (`cttee_role` = `True`) or
        non-committee roles (`cttee_role` = `False`).

        Note: operates by looping over known roles.  Any reviewers with
        invalid (or no longer recognized) roles will not be yielded.
        """

        cttee_roles = None
        if cttee_role is not None:
            cttee_roles = role_class.get_cttee_roles()

        for role in role_class.get_options().keys():
            if cttee_role is not None:
                if ((cttee_role and (role not in cttee_roles)) or
                        ((not cttee_role) and (role in cttee_roles))):
                    continue

            for member in self.values():
                if member.role == role:
                    yield member


class TargetCollection(OrderedResultCollection):
    """
    Collection for target objects listed on a proposal.
    """

    def to_formatted_collection(self):
        """
        Construct an `OrderedDict` in which the target values
        (`x`, `y`, `time`, `priority`) are replaced with formatted strings.
        """

        ans = OrderedDict()

        for (k, v) in self.items():
            if v.x is None or v.y is None:
                x = y = ''
            else:
                (x, y) = format_coord(v.system,
                                      coord_from_dec_deg(v.system, v.x, v.y))

            if v.time is None:
                time = ''
            else:
                time = '{}'.format(v.time)

            if v.priority is None:
                priority = ''
            else:
                priority = '{}'.format(v.priority)

            ans[k] = v._replace(x=x, y=y, time=time, priority=priority)

        return ans

    @classmethod
    def from_formatted_collection(cls, records):
        """
        Construct an instance of this class where, for every entry in the
        input collection, the `x`, `y`, `time` and `priority` values are
        parsed.  (As decimal degrees (`float`), `float` and `int`
        respectively.)
        """

        ans = cls()

        for (k, v) in records.items():
            system = v.system

            if not v.name:
                raise UserError('Each target object should have a name.')

            if v.x and v.y:
                (x, y) = coord_to_dec_deg(parse_coord(system,
                                                      v.x, v.y, v.name))

            elif v.x or v.y:
                raise UserError('Target "{}" has only one coordinate.',
                                v.name)

            else:
                system = x = y = None

            try:
                if v.time:
                    time = float(v.time)
                else:
                    time = None
            except ValueError:
                raise UserError('Could not parse time for "{}".', v.name)

            try:
                if v.priority:
                    priority = int(v.priority)
                else:
                    priority = None
            except ValueError:
                raise UserError('Could not parse priority for "{}".', v.name)

            ans[k] = v._replace(system=system, x=x, y=y,
                                time=time, priority=priority)

        return ans

    def to_object_list(self):
        """
        Returns a list of `TargetObject` instances representing members of the
        collection for which coordinates have been defined.
        """

        ans = []

        for v in self.values():
            if not (v.x is None or v.y is None):
                ans.append(TargetObject(
                    v.name, v.system, coord_from_dec_deg(v.system, v.x, v.y)))

        return ans

    def total_time(self):
        """
        Returns the sum of the "time" value for each target in the collection
        for which this value isn't undefined.

        A total of 0.0 will be returned if no targets had defined times.  (Or
        if the times add up to zero.)
        """

        total = 0.0

        for v in self.values():
            if v.time is not None:
                total += v.time

        return total
