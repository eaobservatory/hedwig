# Copyright (C) 2015-2018 East Asian Observatory
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
import re

from ..error import NoSuchValue, UserError
from .base import EnumAllowUser, EnumAvailable, EnumBasic, EnumCode, \
    EnumDisplayClass, EnumURLPath


class AffiliationType(EnumBasic):
    """
    Class representing types of affiliations.
    """

    STANDARD = 1
    EXCLUDED = 2
    SHARED = 3

    TypeInfo = namedtuple(
        'TypeInfo', ('name',))

    _info = OrderedDict((
        (STANDARD, TypeInfo('Standard')),
        (EXCLUDED, TypeInfo('Excluded')),
        (SHARED,   TypeInfo('Shared')),
    ))

    @classmethod
    def get_options(cls):
        return OrderedDict(((k, v.name) for (k, v) in cls._info.items()))


class CallState(EnumBasic):
    """
    Class representing states of a call for proposals.

    Note that this state is not stored directly in the database -- it is
    determined based on the open and close dates.
    """

    UNOPENED = 1
    OPEN = 2
    CLOSED = 3

    StateInfo = namedtuple(
        'StateInfo', ('name',))

    _info = OrderedDict((
        (UNOPENED,  StateInfo('Not yet open')),
        (OPEN,      StateInfo('Open')),
        (CLOSED,    StateInfo('Closed')),
    ))


class FormatType(EnumAllowUser):
    """
    Class representing possible formatting methods for pieces of text.

    One of the enumerated values of this class should be stored with pieces
    of text in order for the system to know how to format them for display.

    A subset of the formats are marked with the `allow_user` flag: these are
    the formats which the system should allow end users to select, e.g. in
    proposals or reviews.
    """

    PLAIN = 1
    RST = 2

    FormatTypeInfo = namedtuple('FormatTypeInfo', ('name', 'allow_user'))

    _info = OrderedDict((
        (PLAIN, FormatTypeInfo('Plain', True)),
        (RST,   FormatTypeInfo('RST',   False)),
    ))


class Assessment(EnumBasic, EnumAvailable):
    """
    Class representing possible outcomes of a technical assessment.
    """

    FEASIBLE = 1
    PROBLEM = 2
    INFEASIBLE = 3

    AssessmentInfo = namedtuple('AssessmentInfo', ('name', 'available'))

    _info = OrderedDict((
        (FEASIBLE,   AssessmentInfo('Feasible', True)),
        (PROBLEM,    AssessmentInfo('Problematic', True)),
        (INFEASIBLE, AssessmentInfo('Infeasible', True)),
    ))


class AttachmentState(EnumBasic):
    """
    Class representing possible processing states for proposal attachments.

    While originally intended for proposal figures and PDF files, this is
    also used to represent the processing state of other items.
    """

    NEW = 1
    PROCESSING = 2
    READY = 3
    ERROR = 4

    AttachmentStateInfo = namedtuple('AttachmentStateInfo',
                                     ('name', 'ready', 'error'))

    _info = OrderedDict((
        (NEW,         AttachmentStateInfo('New',        False, False)),
        (PROCESSING,  AttachmentStateInfo('Processing', False, False)),
        (READY,       AttachmentStateInfo('Ready',      True,  False)),
        (ERROR,       AttachmentStateInfo('Error',      False, True)),
    ))

    @classmethod
    def is_ready(cls, state):
        """
        Determine whether a state represents succesfully completed
        processing.
        """

        return cls._info[state].ready

    @classmethod
    def is_error(cls, state):
        """
        Determine whether a state represents unsuccessful processing.
        """

        return cls._info[state].error

    @classmethod
    def unready_states(cls):
        """
        Return a list of states values which do not correspond to
        successfully completed processing.
        """

        return [k for (k, v) in cls._info.items() if not v.ready]


FileTypeInfo = namedtuple('FileTypeInfo',
                          ('name', 'mime', 'preview', 'allow_user'))


class FigureType(EnumAllowUser):
    """
    Class representing graphics formats handled by the system.

    As for text `FormatType` values, only certain graphics formats are made
    available to users when uploading figures to their proposals.
    """

    PNG = 1
    JPEG = 2
    PDF = 3
    PS = 4
    SVG = 5

    #                       Name     MIME                     Prev.  User
    _info = OrderedDict((
        (PNG,  FileTypeInfo('PNG',  'image/png',              False, True)),
        (JPEG, FileTypeInfo('JPEG', 'image/jpeg',             False, True)),
        (PDF,  FileTypeInfo('PDF',  'application/pdf',        True,  True)),
        (PS,   FileTypeInfo('EPS',  'application/postscript', True,  False)),
        (SVG,  FileTypeInfo('SVG',  'image/svg+xml',          True,  False)),
    ))

    @classmethod
    def get_name(cls, type_):
        """Get the name of the given type."""

        return cls._info[type_].name

    @classmethod
    def get_mime_type(cls, type_):
        """Get the MIME type to be used for the given figure type."""

        return cls._info[type_].mime

    @classmethod
    def needs_preview(cls, type_):
        """
        Determine whether a figure type requires a preview image.

        This indicates that, when processing a figure, we should store
        a preview image which will be shown on the proposal in place
        of the original figure, even if it was of a suitable size to be
        shown directly.  This is used, for example, for types which the
        browser is not expected to be able to display, such as EPS.
        """

        return cls._info[type_].preview

    @classmethod
    def from_mime_type(cls, mime_type):
        """
        Determine a figure type based on the MIME type.

        Raises a `UserError` if the MIME type is not recognised.
        """

        for (type_, info) in cls._info.items():
            if info.mime == mime_type:
                return type_

        raise UserError('File has type "{}" which is not recognised.',
                        mime_type)

    @classmethod
    def can_view_inline(cls, type_):
        """
        Determine whether the type of figure is suitable for sending to the
        browser to view inline.

        This refers to the `Content-Disposition` heading, rather than whether
        we wish to show the original figure directly in a proposal -- see
        the `needs_preview` method for the latter.

        Currently implemented as any "image/\*" MIME type or PDF.
        """

        return (type_ == cls.PDF or
                cls.get_mime_type(type_).startswith('image/'))

    @classmethod
    def allowed_type_names(cls):
        """Return list of allowed type names."""

        return [x.name for x in cls._info.values() if x.allow_user]

    @classmethod
    def allowed_mime_types(cls):
        """Return list of allowed MIME types."""

        return [x.mime for x in cls._info.values() if x.allow_user]


class GroupType(EnumBasic, EnumURLPath):
    """
    Class representing groups of people related to the proposal review
    process.
    """

    CTTEE = 1
    TECH = 2
    COORD = 3

    GroupInfo = namedtuple(
        'GroupInfo',
        ('name', 'view_all_prop', 'private_moc',
         'review_coord', 'review_view', 'url_path'))

    _info = OrderedDict((
        #           Authorization: Prop   MOC    Rv Ed  Rv Vw
        (CTTEE, GroupInfo(
            'Committee',           True,  False, False, True,  'committee')),
        (TECH,  GroupInfo(
            'Technical assessors', False, True,  False, False, 'technical')),
        (COORD, GroupInfo(
            'Review coordinators', True,  False, True,  True,  'coordinator')),
    ))

    @classmethod
    def get_options(cls):
        """
        Get an OrderedDict of type names by type numbers.
        """

        return OrderedDict(((k, v.name) for (k, v) in cls._info.items()))

    @classmethod
    def view_all_groups(cls):
        """Get a list of groups with the `view_all_prop` privilege."""

        return [k for (k, v) in cls._info.items() if v.view_all_prop]

    @classmethod
    def private_moc_groups(cls):
        """Get a list of groups with the `private_moc` privilege."""

        return [k for (k, v) in cls._info.items() if v.private_moc]

    @classmethod
    def review_coord_groups(cls):
        """Get a list of groups with the `review_coord` privilege."""

        return [k for (k, v) in cls._info.items() if v.review_coord]

    @classmethod
    def review_view_groups(cls):
        """Get a list of groups with the `review_view` privilege."""

        return [k for (k, v) in cls._info.items() if v.review_view]


# NOTE: this is defined after GroupType since it refers to values from that
# class.
class BaseCallType(EnumBasic, EnumAvailable, EnumCode, EnumURLPath):
    """
    Class representing types of calls for proposals.

    The `name_proposal` attribute relates to how a call is named.  If
    `False` then the name relates to the call (e.g. "standard call for
    proposals") otherwise, if `True`, the name relates to the proposals
    (e.g. "call for urguent proposals").
    """

    STANDARD = 1
    IMMEDIATE = 2

    TypeInfo = namedtuple(
        'TypeInfo',
        ('code', 'name', 'available', 'url_path', 'immediate_review',
         'name_proposal', 'notify_group'))

    #       Code  Name         Avail.  URL         Im.Rv. Nm.Pr.
    #       (Notify groups)
    _info = OrderedDict((
        (STANDARD,  TypeInfo(
            None, 'Standard',  True,  'standard',  False, False,
            ())),
        (IMMEDIATE, TypeInfo(
            'I',  'Immediate', True,  'immediate', True,  False,
            (GroupType.CTTEE,))),
    ))

    @classmethod
    def has_immediate_review(cls, value):
        return cls._info[value].immediate_review

    @classmethod
    def get_notify_group(cls, value):
        """
        Get tuple of groups which should be notified about submissions
        to calls of this type.
        """

        return cls._info[value].notify_group

    @classmethod
    def get_full_call_name(cls, value, plural=False):
        """
        Get the full name of a call for proposals.

        This returns a full name such as "standard call for proposals"
        based on the call type name and `name_proposal` attribute.
        """

        type_info = cls._info[value]

        call = 'calls' if plural else 'call'

        ans = ('{1} for {0} proposals'
               if type_info.name_proposal
               else '{0} {1} for proposals')

        return ans.format(type_info.name.lower(), call)


class MessageState(EnumAllowUser, EnumBasic):
    """
    Class representing possible status values for email messages.

    Note that this state is not stored directly in the database -- it is
    determined based on the send and sent timestamps.
    """

    UNSENT = 1
    SENDING = 2
    SENT = 3
    DISCARD = 4
    ERROR = 5

    StateInfo = namedtuple(
        'StateInfo', ('name', 'resettable', 'allow_user'))

    _info = OrderedDict((
        (UNSENT,  StateInfo('Unsent',    False, True)),
        (SENDING, StateInfo('Sending',   True,  False)),
        (SENT,    StateInfo('Sent',      False, False)),
        (DISCARD, StateInfo('Discarded', False, True)),
        (ERROR,   StateInfo('Error',     True,  False)),
    ))


class MessageThreadType(EnumBasic, EnumURLPath):
    """
    Class representing different properties which could be
    used to group messages in a thread.
    """

    PROPOSAL_STATUS = 1
    REVIEW_INVITATION = 2
    PROPOSAL_REVIEW = 3

    TypeInfo = namedtuple(
        'TypeInfo', ('name', 'url_path'))

    _info = OrderedDict((
        (PROPOSAL_STATUS,   TypeInfo('Proposal status',   'prop_stat')),
        (REVIEW_INVITATION, TypeInfo('Review invitation', 'rev_inv')),
        (PROPOSAL_REVIEW,   TypeInfo('Proposal review',   'prop_rev')),
    ))


class PermissionType(object):
    """
    Class representing different permission levels which may be required
    to interact with a particular resource.

    These are used as the `permission` argument to the "with" decorators
    in the :mod:`hedwig.view.util` module.
    """

    # General permission types, shared by multiple resources.
    # Note we give a specific value for NONE rather than simply using `None`
    # so that we can't mistake an undefined value for a valid permission type.
    NONE = 1
    VIEW = 2
    EDIT = 3

    # Special permission types for particular types of resource.
    FEEDBACK = 10


class PersonTitle(EnumBasic, EnumAvailable):
    """
    Class containing a list of personal titles.
    """

    TitleInfo = namedtuple('TitleInfo', ('name', 'available'))

    _info = OrderedDict((
        (1, TitleInfo('Dr.', True)),
        (2, TitleInfo('Miss', True)),
        (3, TitleInfo('Mr.', True)),
        (4, TitleInfo('Mrs.', True)),
        (5, TitleInfo('Ms.', True)),
        (6, TitleInfo('Prof.', True)),
    ))


class ProposalState(EnumBasic):
    """
    Class representing various states a proposal can be in.

    The proposal state is used to control which operations are permitted
    for any given proposal.  Note that the call closing process
    (:func:`hedwig.admin.proposal.close_call_proposals`),
    review closing processess
    (:func:`hedwig.admin.proposal.finalize_call_review`)
    and decision feedback sending process
    (:func:`hedwig.admin.proposal.send_call_proposal_feedback`)
    update the proposal state automatically.

    Proposals transition between states as follows::

        PREPARATION ----------------------------
            |                                   |
        submission                              |
            |                                   |
            V      -- withdrawl ->              |
        SUBMITTED                     WITHDRAWN |
            |      <- submission --       |     |
        . . | . . . . . . . . . . . . . . | . . | . . . . call closing
            |                             |     |
            V                             V     V
        REVIEW                           ABANDONED
            |
        . . | . . . . . . . . . . . . . . . . . . . . . . review closing
            |
            V
        FINAL_REVIEW -----------
            |                   |
        . . | . . . . . . . . . | . . . . . . . . . . . . decision ready
            |                   |
            V                   V
        ACCEPTED            REJECTED

    .. note::
        For calls with the "immediate_review" attribute set, submission
        of the proposal changes the state directly from PREPARATION
        to REVIEW.
    """

    PREPARATION = 1
    SUBMITTED = 2
    WITHDRAWN = 3
    REVIEW = 4
    ABANDONED = 5
    ACCEPTED = 6
    REJECTED = 7
    FINAL_REVIEW = 8

    StateInfo = namedtuple(
        'StateInfo',
        ('short_name', 'name', 'edit', 'submitted', 'review', 'reviewed'))
    # Note: currently edit=True implies a proposal for which the call
    # has not been closed.  An extra entry must be added to the tuple (and
    # the "open_states" method adjusted) if this changes.

    #                 Abbr     Name              Edit   Sub/d  Rev    Rev/d
    _info = OrderedDict((
        (PREPARATION,
            StateInfo('Prep',  'In preparation', True,  False, False, False)),
        (WITHDRAWN,
            StateInfo('Wdwn',  'Withdrawn',      True,  False, False, False)),
        (SUBMITTED,
            StateInfo('Sub',   'Submitted',      True,  True,  False, False)),
        (REVIEW,
            StateInfo('Rev',   'Under review',   False, True,  True,  False)),
        (FINAL_REVIEW,
            StateInfo('FR',    'Final review',   False, True,  True,  False)),
        (ACCEPTED,
            StateInfo('Acc',   'Accepted',       False, True,  False, True)),
        (REJECTED,
            StateInfo('Rej',   'Rejected',       False, True,  False, True)),
        (ABANDONED,
            StateInfo('Abnd',  'Abandoned',      False, False, False, False)),
    ))

    @classmethod
    def is_submitted(cls, state):
        """Determine whether a proposal has been submitted."""

        return cls._info[state].submitted

    @classmethod
    def is_reviewed(cls, state):
        """Determine whether a proposal has been reviewed."""

        return cls._info[state].reviewed

    @classmethod
    def get_short_name(cls, state):
        """Get the abbreviated name for a proposal state."""

        return cls._info[state].short_name

    @classmethod
    def can_edit(cls, state):
        """Determine whether a proposal can be edited."""

        return cls._info[state].edit

    @classmethod
    def editable_states(cls):
        """Return a list of states in which proposals can be edited."""

        return [k for (k, v) in cls._info.items() if v.edit]

    @classmethod
    def submitted_states(cls):
        """Return a list of states corresponding to submitted proposals."""

        return [k for (k, v) in cls._info.items() if v.submitted]

    @classmethod
    def review_states(cls):
        """Return a list of states corresponding to the review process.'"""

        return [k for (k, v) in cls._info.items() if v.review]

    @classmethod
    def reviewed_states(cls):
        """Return a list of states corresponding to reviewed proposals."""

        return [k for (k, v) in cls._info.items() if v.reviewed]

    @classmethod
    def open_states(cls):
        """
        Return a list of states corresponding to proposals in open calls
        for proposals.

        Note: we currently assume the state is "open" if it is editable,
        but this extra accessor method is provided in case this fact changes.
        """

        return [k for (k, v) in cls._info.items() if v.edit]

    @classmethod
    def by_name(cls, name):
        """
        Attempt to find a state value by name.

        Returns None if no match is found.
        """

        lowername = name.lower()
        for (state, info) in cls._info.items():
            if lowername == info.name.lower():
                return state

        raise NoSuchValue('State name "{}" not recognised', name)

    @classmethod
    def get_options(cls):
        """
        Get states and names.

        :return OrderedDict: state names by state number
        """

        return OrderedDict((k, v.name) for (k, v) in cls._info.items())


class PublicationType(EnumBasic, EnumAvailable):
    """
    Class representing different ways in which a publication can be
    identified.

    Contains the following extra entries for each type:

    placeholder
        Text to show to the user as a pattern, in error messages and
        as a placeholder in form text boxes.

    regex
        A list of regular expressions -- identifiers should match one
        of them.

    prefix
        A list of prefixes, in lower case, which might be used with
        the identifier.  These, if present, should be stripped off
        automatically.
    """

    PLAIN = 1
    DOI = 2
    ADS = 3
    ARXIV = 4

    PubTypeInfo = namedtuple(
        'PubTypeInfo', ('name', 'available', 'placeholder', 'regex', 'prefix'))

    _info = OrderedDict((
        (PLAIN, PubTypeInfo(
            'Text description',
            True,
            '',
            None,
            None)),
        (DOI, PubTypeInfo(
            'DOI',
            True,
            '00.0000/XXXXXX',
            [re.compile(r'^\d+(?:\.\d+)+\/\S*$')],
            ['doi:'])),
        (ADS, PubTypeInfo(
            'ADS bibcode',
            True,
            '0000..............X',
            [re.compile(r'^\d{4}\S{14}[A-Za-z]$')],
            None)),
        (ARXIV, PubTypeInfo(
            'arXiv article ID',
            True,
            '0000.00000',
            [re.compile(r'^\d+\.\d+(?:v\d+)?$'),
             re.compile(r'^\S+\/\d+(?:v\d+)?$')],
            ['arxiv:'])),
    ))


class BaseReviewerRole(EnumBasic, EnumDisplayClass, EnumURLPath):
    """
    Base for classes representing roles in which a person may provide a review
    for a proposal.

    Each facility should provide a version of this class customized as
    required for that facility.  Meanwhile this base class defines some
    basic roles which are used by general parts of the Hedwig system.
    An example is FEEDBACK, which is used when sending feedback
    to proposal members at the end of the review process.
    """

    TECH = 1
    EXTERNAL = 2
    CTTEE_PRIMARY = 3
    CTTEE_SECONDARY = 4
    CTTEE_OTHER = 5
    FEEDBACK = 6

    # Type which describes how the reviewer roles are defined, where:
    # * name_review indicates whether the name can be suffixed with "review".
    # * edit_rev and edit_fr indicate which states the review can be edited in.
    # * rating_hide indicates whether the rating should be hidden until
    #   the proposal is in the final review state.
    # * feedback_direct and feedback_indirect correspond to authorization to
    #   "directly" and "indirectly" add/edit feedback.
    RoleInfo = namedtuple(
        'RoleInfo',
        ('name', 'unique', 'text', 'assessment', 'rating', 'weight',
         'cttee', 'name_review', 'feedback_direct', 'feedback_indirect',
         'note', 'invite',
         'edit_rev', 'edit_fr', 'rating_hide', 'calc',
         'display_class', 'url_path'))

    # Options:  Unique Text   Ass/nt Rating Weight Cttee  "Rev"  Fbk_dr Fbk_id
    #           Note   Invite E.Rev  E.FR   Ra.Hi. Calc   Disp.cl. URL
    _info = OrderedDict((
        (TECH,
            RoleInfo(
                'Technical',
                True,  True,  True,  False, False, False, True,  False, False,
                True,  False, True,  True,  False, True,  'tech', 'technical')),
        (EXTERNAL,
            RoleInfo(
                'External',
                False, True,  False, True,  False, False, True,  False, False,
                False, True,  True,  False, False, False, 'ext', 'external')),
        (CTTEE_PRIMARY,
            RoleInfo(
                'Committee Primary',
                True,  True,  False, True,  True,  True,  True,  True,  False,
                True,  False, True,  True,  True,  False, 'cttee', 'committee')),
        (CTTEE_SECONDARY,
            RoleInfo(
                'Committee Secondary',
                False, True,  False, True,  True,  True,  True,  False, True,
                True,  False, True,  True,  True,  False, 'cttee', None)),
        (CTTEE_OTHER,
            RoleInfo(
                'Committee Other',
                False, True,  False, True,  True,  True,  True,  False, False,
                True,  False, True,  True,  True,  False, 'cttee', 'other')),
        (FEEDBACK,
            RoleInfo(
                'Feedback',
                True,  True,  False, False, False, False, False, False, False,
                False, False, False, True,  False, False, 'feedback', 'feedback')),
    ))

    @classmethod
    def get_calc_roles(cls):
        """Get list of roles who can save calculations."""

        return [k for (k, v) in cls._info.items() if v.calc]

    @classmethod
    def get_cttee_roles(cls):
        """Get a list of roles corresponding to committee reviews."""

        return [k for (k, v) in cls._info.items() if v.cttee]

    @classmethod
    def get_editable_roles(cls, state):
        """Get a list of roles which are editable in a specific state."""

        roles = []

        for (role_id, role_info) in cls._info.items():
            if ((role_info.edit_rev and (state == ProposalState.REVIEW))
                    or (role_info.edit_fr
                        and (state == ProposalState.FINAL_REVIEW))):
                roles.append(role_id)

        return roles

    @classmethod
    def get_editable_states(cls, role):
        """Get a list of the states in which a review is editable."""

        role_info = cls._info[role]

        states = []

        if role_info.edit_rev:
            states.append(ProposalState.REVIEW)

        if role_info.edit_fr:
            states.append(ProposalState.FINAL_REVIEW)

        return states

    @classmethod
    def get_name_with_review(cls, role):
        """Get the name of the role, possibly with the word "Review" added."""

        role_info = cls._info[role]

        if role_info.name_review:
            return '{} Review'.format(role_info.name)

        return role_info.name

    @classmethod
    def get_rating_viewable_states(cls, role):
        """Get a list of states in which the rating is viewable."""

        states = [ProposalState.FINAL_REVIEW] + ProposalState.reviewed_states()

        if not cls._info[role].rating_hide:
            states.append(ProposalState.REVIEW)

        return states

    @classmethod
    def get_feedback_roles(cls, include_indirect=True):
        """Get list of roles who can write the feedback review."""

        return [k for (k, v) in cls._info.items()
                if (v.feedback_direct or (include_indirect
                                          and v.feedback_indirect))]

    @classmethod
    def get_invited_roles(cls):
        """Get list of roles for invited reviewers."""

        return [k for (k, v) in cls._info.items() if v.invite]

    @classmethod
    def get_options(cls):
        """
        Get an OrderedDict of role names by role numbers.
        """

        return OrderedDict(((k, v.name) for (k, v) in cls._info.items()))

    @classmethod
    def is_invited_review(cls, role):
        """Indicate whether the given role is for invited reviews."""

        return cls._info[role].invite

    @classmethod
    def is_name_review(cls, role):
        """
        Determine whether a role name should be followed by the word "Review".
        """

        return cls._info[role].name_review


class ReviewState(EnumBasic, EnumAvailable, EnumDisplayClass):
    """
    Class representing states of a review.

    The "available" flag indicates which states are offered as search
    criteria in the web interface.  This excludes ADDABLE as review
    searches will not find reviews in this state.
    """

    NOT_DONE = 1
    DONE = 2
    ADDABLE = 3
    PREPARATION = 4

    StateInfo = namedtuple(
        'StateInfo', ('name', 'display_class', 'available', 'present'))

    #       name              class       avail. pres.
    _info = OrderedDict((
        (NOT_DONE, StateInfo(
            'Not done',       'not_done', True,  False)),
        (PREPARATION, StateInfo(
            'In preparation', 'not_done', True,  True)),
        (DONE,     StateInfo(
            'Done',           'done',     True,  True)),
        (ADDABLE,  StateInfo(
            'Addable',        'addable',  False, False)),
    ))

    @classmethod
    def is_present(cls, state):
        """Determine if a state corresponds to a review in the database."""

        return cls._info[state].present


class SemesterState(EnumBasic):
    """
    Class representing states of a semester.

    Note that this state is not stored directly in the database -- it is
    determined based on the start and end dates.
    """

    FUTURE = 1
    CURRENT = 2
    PAST = 3

    StateInfo = namedtuple(
        'StateInfo', ('name',))

    _info = OrderedDict((
        (FUTURE,  StateInfo('Future')),
        (CURRENT, StateInfo('Current')),
        (PAST,    StateInfo('Past')),
    ))


class BaseTextRole(EnumBasic, EnumURLPath):
    """
    Base for classes representing roles which a piece of text may have
    on a proposal.

    It is recommended that facility-specific subclasses allocate higher
    identifier numbers for facility-specific roles, e.g. numbers above 100.
    """

    ABSTRACT = 1
    TECHNICAL_CASE = 2
    SCIENCE_CASE = 3
    TOOL_NOTE = 4

    RoleInfo = namedtuple('RoleInfo', ('name', 'shortname', 'url_path'))

    #                Name                        Short   Path
    _info = {
        ABSTRACT:
            RoleInfo('Abstract',                 'abst', None),
        TECHNICAL_CASE:
            RoleInfo('Technical Justification',  'tech', 'technical'),
        SCIENCE_CASE:
            RoleInfo('Scientific Justification', 'sci',  'scientific'),
        TOOL_NOTE:
            RoleInfo('Note on Tool Results',     'tool', None),
    }

    @classmethod
    def short_name(cls, role):
        """Get the short name of a role."""

        return cls._info[role].shortname


class UserLogEvent(EnumBasic):
    """
    Class representing different types of events which are stored in the
    user account log.
    """

    CREATE = 1
    LINK_PROFILE = 2
    CHANGE_NAME = 3
    CHANGE_PASS = 4
    GET_TOKEN = 5
    USE_TOKEN = 6
    USE_INVITE = 7

    EventInfo = namedtuple('EventInfo', ('description',))

    _info = {
        CREATE:       EventInfo('Account created'),
        LINK_PROFILE: EventInfo('Profile linked'),
        CHANGE_NAME:  EventInfo('Changed user name'),
        CHANGE_PASS:  EventInfo('Changed password'),
        GET_TOKEN:    EventInfo('Issued password reset code'),
        USE_TOKEN:    EventInfo('Used password reset code'),
        USE_INVITE:   EventInfo('Profile linked via invitation'),
    }
