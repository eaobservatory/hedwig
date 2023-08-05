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

from collections import OrderedDict, namedtuple
import re

from ..error import NoSuchValue, UserError
from .base import EnumAllowUser, EnumAvailable, EnumBasic, EnumCode, \
    EnumDisplayClass, EnumLevel, EnumShortName, EnumURLPath


class BaseAffiliationType(EnumBasic):
    """
    Class representing types of affiliations.
    """

    STANDARD = 1
    EXCLUDED = 2
    SHARED = 3

    TypeInfo = namedtuple(
        'TypeInfo', ('name', 'tabulated'))

    _info = OrderedDict((
        (STANDARD, TypeInfo('Standard', True)),
        (SHARED,   TypeInfo('Shared',   False)),
        (EXCLUDED, TypeInfo('Excluded', False)),
    ))

    @classmethod
    def get_options(cls):
        return OrderedDict(((k, v.name) for (k, v) in cls._info.items()))

    @classmethod
    def get_tabulated_types(cls):
        return [k for (k, v) in cls._info.items() if v.tabulated]

    @classmethod
    def is_tabulated(cls, value):
        return cls._info[value].tabulated


class AnnotationType(EnumBasic):
    """
    Class representing types of annotations.
    """

    PROPOSAL_COPY = 1

    TypeInfo = namedtuple(
        'TypeInfo', ('name',))

    _info = OrderedDict((
        (PROPOSAL_COPY, TypeInfo('Proposal copy')),
    ))


class CallState(EnumBasic, EnumDisplayClass):
    """
    Class representing states of a call for proposals.

    Note that this state is not stored directly in the database -- it is
    determined based on the open and close dates.
    """

    UNOPENED = 1
    OPEN = 2
    CLOSED = 3

    StateInfo = namedtuple(
        'StateInfo', ('name', 'display_class'))

    _info = OrderedDict((
        (UNOPENED,  StateInfo('Not yet open', 'future')),
        (OPEN,      StateInfo('Open',         'open')),
        (CLOSED,    StateInfo('Closed',       'closed')),
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


class AttachmentState(EnumAllowUser, EnumBasic, EnumDisplayClass):
    """
    Class representing possible processing states for proposal attachments.

    While originally intended for proposal figures and PDF files, this is
    also used to represent the processing state of other items.
    """

    NEW = 1
    PROCESSING = 2
    READY = 3
    ERROR = 4
    DISCARD = 5

    AttachmentStateInfo = namedtuple(
        'AttachmentStateInfo',
        ('name', 'ready', 'error', 'allow_user', 'display_class'))

    #       Name            Ready  Error  User   Disp.Cl.
    _info = OrderedDict((
        (NEW,         AttachmentStateInfo(
            'New',          False, False, True,  'new')),
        (PROCESSING,  AttachmentStateInfo(
            'Processing',   False, False, False, 'proc')),
        (READY,       AttachmentStateInfo(
            'Ready',        True,  False, False, 'ready')),
        (ERROR,       AttachmentStateInfo(
            'Error',        False, True,  False, 'error')),
        (DISCARD,     AttachmentStateInfo(
            'Discarded',    False, False, True,  'discard')),
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
    def unready_states(cls, include_discard=True):
        """
        Return a list of states values which do not correspond to
        successfully completed processing.
        """

        return [
            k for (k, v) in cls._info.items() if not (
                v.ready
                or (k == cls.DISCARD and not include_discard))]


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

        Currently implemented as any "image/\\*" MIME type or PDF.
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


class GroupType(EnumAllowUser, EnumBasic, EnumURLPath):
    """
    Class representing groups of people related to the proposal review
    process.
    """

    CTTEE = 1
    TECH = 2
    COORD = 3
    VIEWER = 4
    HIDDEN_CALL = 5

    PEER = -1

    GroupInfo = namedtuple(
        'GroupInfo',
        ('name', 'view_all_prop', 'private_moc',
         'review_coord', 'review_view',  'feedback_view',
         'allow_user', 'url_path'))

    _info = OrderedDict((
        #           Authorization: Prop   MOC    Rv.Ed  Rv.Vw  Fb.Vw  User
        (CTTEE, GroupInfo(
            'Committee members',   True,  False, False, True,  False, True,
            'committee')),
        (TECH,  GroupInfo(
            'Technical assessors', False, True,  False, False, False, True,
            'technical')),
        (COORD, GroupInfo(
            'Review coordinators', True,  False, True,  True,  False, True,
            'coordinator')),
        (VIEWER, GroupInfo(
            'Viewers',             True,  False, False, True,  True,  True,
            'viewer')),
        (HIDDEN_CALL, GroupInfo(
            'Hidden call',         False, False, False, False, False, True,
            'hidden')),

        (PEER, GroupInfo(
            'Peer reviewers',      False, False, False, False, False, False,
            None)),
    ))

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

    @classmethod
    def feedback_view_groups(cls):
        """Get a list of groups with the `feedback_view` privilege."""

        return [k for (k, v) in cls._info.items() if v.feedback_view]


class LogEventLevel(EnumBasic):
    """
    Class representing log event levels.

    .. note::
        These levels should be ordered with higher priority events having
        higher numerical values.  (See e.g. the `EnumLevel.events_of_level`
        method.)  As such they may change, and should therefore only be used
        in `_info` dictionaries of other classes, rather than being stored
        in the database.
    """

    MINOR = 1
    INTERMEDIATE = 2
    MAJOR = 3

    LevelInfo = namedtuple(
        'LevelInfo', ('name',))

    _info = OrderedDict((
        (MINOR,         LevelInfo('Minor')),
        (INTERMEDIATE,  LevelInfo('Intermediate')),
        (MAJOR,         LevelInfo('Major')),
    ))

    @classmethod
    def get_options(cls):
        return OrderedDict(((k, v.name) for (k, v) in cls._info.items()))


class MessageState(EnumAllowUser, EnumBasic, EnumDisplayClass):
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
        'StateInfo', ('name', 'resettable', 'allow_user', 'display_class'))

    _info = OrderedDict((
        (UNSENT,  StateInfo('Unsent',    False, True,  'new')),
        (SENDING, StateInfo('Sending',   True,  False, 'proc')),
        (SENT,    StateInfo('Sent',      False, False, 'ready')),
        (DISCARD, StateInfo('Discarded', False, True,  'discard')),
        (ERROR,   StateInfo('Error',     True,  False, 'error')),
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
    UNIVERSAL_VIEW = 4

    # Special permission types for particular types of resource.
    FEEDBACK = 10


class PersonLogEvent(EnumBasic, EnumLevel):
    """
    Class representing different types of events which are stored in the
    person event log.
    """

    PROPOSAL_CREATE = 1
    PROPOSAL_SUBMIT = 2
    PROPOSAL_WITHDRAW = 3
    PROPOSAL_REQUEST_COPY = 4
    INSTITUTION_ADD = 101
    INSTITUTION_EDIT = 102
    MEMBER_ADD = 201
    MEMBER_INVITE = 202
    MEMBER_REINVITE = 203

    EventInfo = namedtuple('EventInfo', ('description', 'level'))

    _info = {
        PROPOSAL_CREATE: EventInfo(
            'Proposal created',
            LogEventLevel.MAJOR),
        PROPOSAL_SUBMIT: EventInfo(
            'Proposal submitted',
            LogEventLevel.MINOR),
        PROPOSAL_WITHDRAW: EventInfo(
            'Proposal withdrawn',
            LogEventLevel.MINOR),
        PROPOSAL_REQUEST_COPY: EventInfo(
            'Proposal copy requested',
            LogEventLevel.MAJOR),
        INSTITUTION_ADD: EventInfo(
            'Institution added',
            LogEventLevel.MAJOR),
        INSTITUTION_EDIT: EventInfo(
            'Institution edited',
            LogEventLevel.INTERMEDIATE),
        MEMBER_ADD: EventInfo(
            'Member added from directory',
            LogEventLevel.MINOR),
        MEMBER_INVITE: EventInfo(
            'Member invited to register',
            LogEventLevel.INTERMEDIATE),
        MEMBER_REINVITE: EventInfo(
            'Member invitation resent',
            LogEventLevel.INTERMEDIATE),
    }


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


class ProposalState(EnumBasic, EnumShortName):
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

        RETRACTED is an additional state, equivalent to ABANDONED, which
        can be manually set via the administrative interface.
    """

    PREPARATION = 1
    SUBMITTED = 2
    WITHDRAWN = 3
    REVIEW = 4
    ABANDONED = 5
    ACCEPTED = 6
    REJECTED = 7
    FINAL_REVIEW = 8
    RETRACTED = 9

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
        (RETRACTED,
            StateInfo('Rtrd',  'Retracted',      False, False, False, False)),
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
    def is_open(cls, state):
        """
        Determine whether a proposal is in an open state.

        (See note for `open_states`.)
        """

        return state in cls.open_states()

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
    def closed_states(cls):
        """
        Return a list of states corresponding to proposal in closed calls.

        (See note for `open_states`.)
        """

        return [k for (k, v) in cls._info.items() if not v.edit]

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


class ProposalType(EnumBasic, EnumShortName):
    """
    Class representing various types of proposal.
    """

    STANDARD = 1
    CONTINUATION = 2

    TypeInfo = namedtuple(
        'TypeInfo',
        ('short_name', 'name'))

    #                Abbr   Name
    _info = OrderedDict((
        (STANDARD,
            TypeInfo('Std', 'Standard')),
        (CONTINUATION,
            TypeInfo('CR',  'Continuation request')),
    ))


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


class RequestState(AttachmentState):
    """
    Class representing the state of a request.
    """

    EXPIRING = 101
    EXPIRED = 102
    EXPIRE_ERROR = 103

    RequestStateInfo = namedtuple(
        'RequestStateInfo',
        ('name', 'ready', 'error', 'allow_user', 'display_class',
         'pre_ready', 'expired'))

    #       Name            Ready  Error  User   Disp.Cl.   Pre.   Exp'd
    _info = OrderedDict((
        (AttachmentState.NEW, RequestStateInfo(
            'Queued',       False, False, True,  'new',     True,  False)),
        (AttachmentState.PROCESSING, RequestStateInfo(
            'Processing',   False, False, False, 'proc',    True,  False)),
        (AttachmentState.READY, RequestStateInfo(
            'Ready',        True,  False, True,  'ready',   False, False)),
        (AttachmentState.ERROR, RequestStateInfo(
            'Error',        False, True,  False, 'error',   False, False)),
        (AttachmentState.DISCARD, RequestStateInfo(
            'Discarded',    False, False, True,  'discard', False, False)),
        (EXPIRING, RequestStateInfo(
            'Expiring',     False, False, False, 'proc',    False, True)),
        (EXPIRED, RequestStateInfo(
            'Expired',      False, False, False, 'expire',  False, True)),
        (EXPIRE_ERROR, RequestStateInfo(
            'Expiry error', False, True,  False, 'error',   False, True)),
    ))

    @classmethod
    def pre_ready_states(cls):
        """
        Return a list of values correspond to states which occur before
        processing completes.
        """

        return [k for (k, v) in cls._info.items() if v.pre_ready]

    @classmethod
    def is_pre_ready(cls, state):
        return cls._info[state].pre_ready

    @classmethod
    def is_expired(cls, state):
        return cls._info[state].expired

    @classmethod
    def is_resettable(cls, state, state_new=None):
        """
        Determine whether a state should be resettable by an administrator.

        If `state_new` is not given then this method returns `True` for any
        state which can be reset.  Otherwise it returns `True` only if it
        would be appropriate to reset the state to the given new state.
        """

        # States which can be reset to READY.
        allow_ready = (
            RequestState.EXPIRING,
            RequestState.EXPIRE_ERROR,
        )

        # States which can be reset to any other state with allow_user=True.
        allow_other = (
            RequestState.PROCESSING,
            RequestState.ERROR,
        )

        if state_new is None:
            return (state in allow_ready) or (state in allow_other)

        elif not cls.is_valid(state_new):
            # Calling `is_valid` without `is_system` returned False,
            # so this state must not have allow_user=True.
            return False

        elif state_new == RequestState.READY:
            return state in allow_ready

        else:
            return state in allow_other

    @classmethod
    def unready_states(cls, include_discard=True):
        """
        Return a list of states values which do not correspond to
        successfully completed processing.

        This extends the super-class (AttachmentState) implementation
        also to exclude EXPIRED.
        """

        return [
            k for (k, v) in cls._info.items() if not (
                v.ready
                or k == cls.EXPIRED
                or (k == cls.DISCARD and not include_discard))]

    @classmethod
    def visible_states(cls):
        """
        Return the list of states for requests which should be shown
        to requesters.
        """

        return [k for (k, v) in cls._info.items() if v.ready or v.pre_ready]

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
    PEER = 7

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
         'edit_rev', 'edit_fr', 'rating_hide', 'calc', 'figure', 'accept',
         'display_class', 'url_path', 'help_page', 'review_group'))

    # Options:  Unique Text   Ass/nt Rating Weight Cttee  "Rev"  Fbk_dr Fbk_id
    #           Note   Invite E.Rev  E.FR   Ra.Hi. Calc   Fig.   Accept
    #           Disp.cl.      URL           Help_page
    #           Review group
    _info = OrderedDict((
        (TECH,
            RoleInfo(
                'Technical',
                True,  True,  True,  False, False, False, True,  False, False,
                True,  False, True,  True,  False, True,  True,  False,
                'tech',       'technical',  'technical',
                GroupType.TECH)),
        (EXTERNAL,
            RoleInfo(
                'External',
                False, True,  False, True,  False, False, True,  False, False,
                False, True,  True,  False, False, False, False, False,
                'ext',        'external',   'external',
                None)),
        (PEER,
            RoleInfo(
                'Peer',
                False, True,  False, True,  True,  False, True,  False, False,
                False, False, True,  False, False, False, False, True,
                'ext',        'peer',       'peer',
                GroupType.PEER)),
        (CTTEE_PRIMARY,
            RoleInfo(
                'Committee Primary',
                True,  True,  False, True,  True,  True,  True,  True,  False,
                True,  False, True,  True,  True,  False, False, False,
                'cttee',      'committee',  'committee',
                GroupType.CTTEE)),
        (CTTEE_SECONDARY,
            RoleInfo(
                'Committee Secondary',
                False, True,  False, True,  True,  True,  True,  False, True,
                True,  False, True,  True,  True,  False, False, False,
                'cttee',      None,         'committee',
                None)),
        (CTTEE_OTHER,
            RoleInfo(
                'Committee Other',
                False, True,  False, True,  True,  True,  True,  False, False,
                True,  False, True,  True,  True,  False, False, False,
                'cttee',      'other',      'committee',
                None)),
        (FEEDBACK,
            RoleInfo(
                'Feedback',
                True,  True,  False, False, False, False, False, False, False,
                False, False, False, True,  False, False, False, False,
                'feedback',   'feedback',   None,
                None)),
    ))

    @classmethod
    def get_assigned_roles(cls):
        """Get an OrderedDict of reviewer group types by role numbers."""

        return OrderedDict(((k, v.review_group) for (k, v) in cls._info.items()
                            if v.review_group is not None))

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
    def get_figure_roles(cls):
        """Get list of roles who can save figures."""

        return [k for (k, v) in cls._info.items() if v.figure]

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
    def get_review_group(cls, role):
        """Get the review group for a reviewer role."""

        return cls._info[role].review_group

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

    @classmethod
    def is_accepted_review(cls, role):
        """
        Determine whether a reviews of a role must first be accepted.
        """

        return cls._info[role].accept

    @classmethod
    def is_assigned_review(cls, role):
        """
        Indicated whether a reviewer role is assigned.
        """

        return (cls._info[role].review_group is not None)


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
    REJECTED = 5

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
        (REJECTED, StateInfo(
            'Rejected',       'rejected', True,  False)),
    ))

    @classmethod
    def is_present(cls, state):
        """Determine if a state corresponds to a review in the database."""

        return cls._info[state].present


class SemesterState(EnumBasic, EnumDisplayClass):
    """
    Class representing states of a semester.

    Note that this state is not stored directly in the database -- it is
    determined based on the start and end dates.
    """

    FUTURE = 1
    CURRENT = 2
    PAST = 3

    StateInfo = namedtuple(
        'StateInfo', ('name', 'display_class'))

    _info = OrderedDict((
        (FUTURE,  StateInfo('Future',  'future')),
        (CURRENT, StateInfo('Current', 'current')),
        (PAST,    StateInfo('Past',    'past')),
    ))


class SiteGroupType(EnumAllowUser, EnumBasic, EnumURLPath):
    """
    Class representing groups of people with site-wide administrative roles.
    """

    PROFILE_VIEWER = 1

    SiteGroupInfo = namedtuple(
        'SiteGroupInfo',
        ('name', 'view_all_profile',
         'allow_user', 'url_path'))

    _info = OrderedDict((
        #           Authorization: Prof.  User
        (PROFILE_VIEWER, SiteGroupInfo(
            'Profile viewers',     True,  True,
            'prof_view')),
    ))

    @classmethod
    def view_all_profile_groups(cls):
        """Get a list of groups with the `view_all_profile` privilege."""

        return [k for (k, v) in cls._info.items() if v.view_all_profile]


class BaseTextRole(EnumBasic, EnumCode, EnumURLPath):
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

    RoleInfo = namedtuple('RoleInfo', ('name', 'code', 'url_path'))

    #                Name                        Code    Path
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


class UserLogEvent(EnumBasic, EnumLevel):
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
    MERGED = 8
    GET_EMAIL_TOKEN = 9
    USE_EMAIL_TOKEN = 10
    LOG_IN = 11
    MERGED_INVITE = 12

    EventInfo = namedtuple('EventInfo', ('description', 'level'))

    _info = {
        CREATE: EventInfo(
            'Account created',
            LogEventLevel.MAJOR),
        LINK_PROFILE: EventInfo(
            'Profile linked',
            LogEventLevel.MAJOR),
        CHANGE_NAME: EventInfo(
            'Changed user name',
            LogEventLevel.INTERMEDIATE),
        CHANGE_PASS: EventInfo(
            'Changed password',
            LogEventLevel.INTERMEDIATE),
        GET_TOKEN: EventInfo(
            'Issued password reset code',
            LogEventLevel.INTERMEDIATE),
        USE_TOKEN: EventInfo(
            'Used password reset code',
            LogEventLevel.INTERMEDIATE),
        USE_INVITE: EventInfo(
            'Profile linked via invitation',
            LogEventLevel.MAJOR),
        MERGED: EventInfo(
            'Profile merged',
            LogEventLevel.MAJOR),
        MERGED_INVITE: EventInfo(
            'Profile merged via invitation',
            LogEventLevel.MAJOR),
        GET_EMAIL_TOKEN: EventInfo(
            'Issued email verify token',
            LogEventLevel.INTERMEDIATE),
        USE_EMAIL_TOKEN: EventInfo(
            'Used email verify token',
            LogEventLevel.INTERMEDIATE),
        LOG_IN: EventInfo(
            'Logged in',
            LogEventLevel.MINOR),
    }


# NOTE: this is defined at the end since it refers to values from
# GroupType and BaseReviewerRole.
class BaseCallType(EnumBasic, EnumAvailable, EnumCode, EnumURLPath):
    """
    Class representing types of calls for proposals.

    The `name_proposal` attribute relates to how a call is named.  If
    `False` then the name relates to the call (e.g. "standard call for
    proposals") otherwise, if `True`, the name relates to the proposals
    (e.g. "call for urgent proposals").
    """

    STANDARD = 1
    IMMEDIATE = 2
    TEST = 3
    MULTICLOSE = 4
    SUPPLEMENTAL = 5

    TypeInfo = namedtuple(
        'TypeInfo',
        ('code', 'name', 'available', 'url_path', 'immediate_review',
         'name_proposal', 'mid_close', 'reviewer_roles', 'notify_group'))

    _cttee = tuple(BaseReviewerRole.get_cttee_roles())

    #       Code   Name         Avail.  URL          Im.Rv. Nm.Pr. Md.Cl.
    #       (Reviewer roles)
    #       (Notify groups)
    _info = OrderedDict((
        (STANDARD,  TypeInfo(
            None,  'Standard',  True,  'standard',   False, False, False,
            (BaseReviewerRole.TECH, BaseReviewerRole.EXTERNAL,
             BaseReviewerRole.FEEDBACK) + _cttee,
            ())),
        (IMMEDIATE, TypeInfo(
            'I',   'Immediate', True,  'immediate',  True,  False, False,
            (BaseReviewerRole.TECH, BaseReviewerRole.CTTEE_OTHER,
             BaseReviewerRole.FEEDBACK),
            (GroupType.CTTEE,))),
        (MULTICLOSE,  TypeInfo(
            'M',  'Multiple-close', True, 'multi',   False, False, True,
            (BaseReviewerRole.TECH, BaseReviewerRole.PEER,
             BaseReviewerRole.FEEDBACK),
            ())),
        (SUPPLEMENTAL, TypeInfo(
            'S', 'Supplemental', True, 'supplement', False, False, False,
            (BaseReviewerRole.TECH, BaseReviewerRole.EXTERNAL,
             BaseReviewerRole.FEEDBACK) + _cttee,
            ())),
        (TEST, TypeInfo(
            'T',   'Test',      True,  'test',       False, True,  False,
            (BaseReviewerRole.TECH, BaseReviewerRole.EXTERNAL,
             BaseReviewerRole.PEER, BaseReviewerRole.FEEDBACK) + _cttee,
            ())),
    ))

    @classmethod
    def has_immediate_review(cls, value):
        return cls._info[value].immediate_review

    @classmethod
    def has_mid_close(cls, value):
        return cls._info[value].mid_close

    @classmethod
    def has_reviewer_role(cls, value, role):
        return role in cls._info[value].reviewer_roles

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
