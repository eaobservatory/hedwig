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
import re

from ..error import UserError
from .base import EnumBasic, EnumURLPath


class CallState(EnumBasic):
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


class FormatType(object):
    PLAIN = 1
    RST = 2

    FormatTypeInfo = namedtuple('FormatTypeInfo', ('name', 'allow_user'))

    _info = OrderedDict((
        (PLAIN, FormatTypeInfo('Plain', True)),
        (RST,   FormatTypeInfo('RST',   False)),
    ))

    @classmethod
    def is_valid(cls, format_, is_system=False):
        """
        Determines whether the given format is allowed.

        By default only allows formats for which "allow_user" is enabled.
        However with the "is_system" flag, allows any format.
        """

        format_info = cls._info.get(format_, None)

        if format_info is None:
            return False

        return is_system or format_info.allow_user

    @classmethod
    def get_options(cls, is_system=False):
        """
        Get an OrderedDict of type names by type numbers.
        """

        return OrderedDict([(k, v.name) for (k, v) in cls._info.items()
                            if is_system or v.allow_user])


class Assessment(EnumBasic):
    FEASIBLE = 1
    PROBLEM = 2
    INFEASIBLE = 3

    AssessmentInfo = namedtuple('AssessmentInfo', ('name',))

    _info = OrderedDict((
        (FEASIBLE,   AssessmentInfo('Feasible')),
        (PROBLEM,    AssessmentInfo('Problematic')),
        (INFEASIBLE, AssessmentInfo('Infeasible')),
    ))

    @classmethod
    def get_options(cls):
        return OrderedDict(((k, v.name) for (k, v) in cls._info.items()))


class AttachmentState(EnumBasic):
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
        return cls._info[state].ready

    @classmethod
    def is_error(cls, state):
        return cls._info[state].error

    @classmethod
    def unready_states(cls):
        return [k for (k, v) in cls._info.items() if not v.ready]


FileTypeInfo = namedtuple('FileTypeInfo',
                          ('name', 'mime', 'preview', 'allow_user'))


class FigureType(object):
    PNG = 1
    JPEG = 2
    PDF = 3
    PS = 4
    SVG = 5

    _info = OrderedDict((
        (PNG,  FileTypeInfo('PNG',  'image/png',              False, True)),
        (JPEG, FileTypeInfo('JPEG', 'image/jpeg',             False, True)),
        (PDF,  FileTypeInfo('PDF',  'application/pdf',        True,  True)),
        (PS,   FileTypeInfo('EPS',  'application/postscript', True,  False)),
        (SVG,  FileTypeInfo('SVG',  'image/svg+xml',          True,  False)),
    ))

    @classmethod
    def is_valid(cls, type_, is_system=False):
        """
        Determine if the given figure type is valid.

        By default only allows types where "allow_user" is enabled.
        """

        type_info = cls._info.get(type_, None)

        if type_info is None:
            return False

        return is_system or type_info.allow_user

    @classmethod
    def get_name(cls, type_):
        return cls._info[type_].name

    @classmethod
    def get_mime_type(cls, type_):
        return cls._info[type_].mime

    @classmethod
    def needs_preview(cls, type_):
        return cls._info[type_].preview

    @classmethod
    def from_mime_type(cls, mime_type):
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

        Currently implemented as any image/* MIME type or PDF, which
        means it returns True for all types at the time of writing.
        """

        return (type_ == cls.PDF or
                cls.get_mime_type(type_).startswith('image/'))

    @classmethod
    def allowed_type_names(cls):
        return [x.name for x in cls._info.values() if x.allow_user]

    @classmethod
    def allowed_mime_types(cls):
        return [x.mime for x in cls._info.values() if x.allow_user]


class GroupType(EnumBasic, EnumURLPath):
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
    def get_options(cls, by_url_path=False):
        """
        Get an OrderedDict of type names by type numbers.
        """

        if by_url_path:
            return OrderedDict(((v.url_path, v.name)
                                for v in cls._info.values()))

        return OrderedDict(((k, v.name) for (k, v) in cls._info.items()))

    @classmethod
    def view_all_groups(cls):
        return [k for (k, v) in cls._info.items() if v.view_all_prop]

    @classmethod
    def private_moc_groups(cls):
        return [k for (k, v) in cls._info.items() if v.private_moc]

    @classmethod
    def review_coord_groups(cls):
        return [k for (k, v) in cls._info.items() if v.review_coord]

    @classmethod
    def review_view_groups(cls):
        return [k for (k, v) in cls._info.items() if v.review_view]


class MessageState(object):
    UNSENT = 1
    SENDING = 2
    SENT = 3

    StateInfo = namedtuple(
        'StateInfo', ('name',))

    _info = OrderedDict((
        (UNSENT,  StateInfo('Unsent')),
        (SENDING, StateInfo('Sending')),
        (SENT,    StateInfo('Sent')),
    ))

    @classmethod
    def get_options(cls):
        return OrderedDict(((k, v.name) for (k, v) in cls._info.items()))


class ProposalState(EnumBasic):
    PREPARATION = 1
    SUBMITTED = 2
    WITHDRAWN = 3
    REVIEW = 4
    ABANDONED = 5
    ACCEPTED = 6
    REJECTED = 7

    StateInfo = namedtuple(
        'StateInfo', ('short_name', 'name', 'edit', 'submitted', 'reviewed'))
    # Note: currently edit=True implies a proposal for which the the call
    # has not been closed.  An extra entry must be added to the tuple (and
    # the "open_states" method adjusted) if this changes.

    #                 Abbr     Name              Edit   Sub/d  Rev/d
    _info = OrderedDict((
        (PREPARATION,
            StateInfo('Prep',  'In preparation', True,  False, False)),
        (SUBMITTED,
            StateInfo('Sub',   'Submitted',      True,  True,  False)),
        (WITHDRAWN,
            StateInfo('Wdwn',  'Withdrawn',      True,  False, False)),
        (REVIEW,
            StateInfo('Rev',   'Under review',   False, True,  False)),
        (ABANDONED,
            StateInfo('Abnd',  'Abandoned',      False, False, False)),
        (ACCEPTED,
            StateInfo('Acc',   'Accepted',       False, True,  True)),
        (REJECTED,
            StateInfo('Rej',   'Rejected',       False, True,  True)),
    ))

    @classmethod
    def is_submitted(cls, state):
        return cls._info[state].submitted

    @classmethod
    def is_reviewed(cls, state):
        return cls._info[state].reviewed

    @classmethod
    def get_short_name(cls, state):
        return cls._info[state].short_name

    @classmethod
    def can_edit(cls, state):
        return cls._info[state].edit

    @classmethod
    def editable_states(cls):
        return [k for (k, v) in cls._info.items() if v.edit]

    @classmethod
    def submitted_states(cls):
        return [k for (k, v) in cls._info.items() if v.submitted]

    @classmethod
    def reviewed_states(cls):
        return [k for (k, v) in cls._info.items() if v.reviewed]

    @classmethod
    def open_states(cls):
        # Note: we currently assume the state is "open" if it is editable,
        # but this extra accessor method is provided in case this fact changes.
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

        return None


class PublicationType(EnumBasic):
    PLAIN = 1
    DOI = 2
    ADS = 3
    ARXIV = 4

    PubTypeInfo = namedtuple('PubTypeInfo', ('name', 'placeholder', 'regex'))

    _info = OrderedDict((
        (PLAIN, PubTypeInfo('Text description',
                            '',
                            None)),
        (DOI,   PubTypeInfo('DOI',
                            '00.0000/XXXXXX',
                            [re.compile('^\d+\.\d+\/.*$')])),
        (ADS,   PubTypeInfo('ADS bibcode',
                            '0000..............X',
                            [re.compile('^\d\d\d\d..............[A-Za-z]$')])),
        (ARXIV, PubTypeInfo('arXiv article ID',
                            '0000.00000',
                            [re.compile('^\d+\.\d+$'),
                             re.compile('^.+\/\d+$')])),
    ))

    @classmethod
    def get_options(cls):
        return cls._info.copy()


class ReviewerRole(EnumBasic):
    TECH = 1
    EXTERNAL = 2
    CTTEE_PRIMARY = 3
    CTTEE_SECONDARY = 4
    CTTEE_OTHER = 5
    FEEDBACK = 6

    # Type which describes how the reviewer roles are defined, where:
    # * name_review indicates whether the name can be suffixed with "review".
    RoleInfo = namedtuple(
        'RoleInfo',
        ('name', 'unique', 'text', 'assessment', 'rating', 'weight',
         'cttee', 'name_review', 'feedback', 'note', 'display_class'))

    # Options:  Unique Text   Ass/nt Rating Weight Cttee  "Rev"  Feedbk Note
    _info = OrderedDict((
        (TECH,
            RoleInfo(
                'Technical',
                True,  True,  True,  False, False, False, True,  False, True,
                'tech')),
        (EXTERNAL,
            RoleInfo(
                'External',
                False, True,  False, True,  False, False, True,  False, False,
                'ext')),
        (CTTEE_PRIMARY,
            RoleInfo(
                'TAC Primary',
                True,  True,  False, True,  True,  True,  True,  True,  True,
                'cttee')),
        (CTTEE_SECONDARY,
            RoleInfo(
                'TAC Secondary',
                False, True,  False, True,  True,  True,  True,  True,  True,
                'cttee')),
        (CTTEE_OTHER,
            RoleInfo(
                'Rating',
                False, False, False, True,  True,  True,  False, False, False,
                'cttee')),
        (FEEDBACK,
            RoleInfo(
                'Feedback',
                True,  True,  False, False, False, False, False, False, False,
                'feedback')),
    ))

    @classmethod
    def get_cttee_roles(cls):
        return [k for (k, v) in cls._info.items() if v.cttee]

    @classmethod
    def get_feedback_roles(cls):
        """Get list of roles who can write the feedback review."""

        return [k for (k, v) in cls._info.items() if v.feedback]

    @classmethod
    def get_options(cls):
        """
        Get an OrderedDict of role names by role numbers.
        """

        return OrderedDict(((k, v.name) for (k, v) in cls._info.items()))


class TextRole(EnumBasic, EnumURLPath):
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
        return cls._info[role].shortname


class UserLogEvent(EnumBasic):
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
