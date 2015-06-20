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

from collections import OrderedDict, namedtuple

from .astro.coord import CoordSystem, coord_from_dec_deg, coord_to_dec_deg, \
    format_coord, parse_coord
from .db.meta import affiliation, call, email, institution, \
    member, message, person, proposal, queue, \
    semester, target
from .error import NoSuchRecord, MultipleRecords, UserError

Affiliation = namedtuple(
    'Affiliation',
    map(lambda x: x.name, affiliation.columns))

Call = namedtuple(
    'Call',
    map(lambda x: x.name, call.columns) +
    ['facility_id', 'semester_name', 'queue_name', 'queue_description'])

Email = namedtuple(
    'Email',
    map(lambda x: x.name, email.columns))

FacilityInfo = namedtuple(
    'FacilityInfo',
    ['id', 'code', 'name', 'view'])

Institution = namedtuple(
    'Institution',
    map(lambda x: x.name, institution.columns))

InstitutionInfo = namedtuple(
    'InstitutionInfo',
    ['id', 'name', 'organization', 'country'])

Member = namedtuple(
    'Member',
    [x.name for x in member.columns if x.name not in ('institution_id',)] +
    ['person_name', 'person_public', 'person_registered',
     'affiliation_name',
     'resolved_institution_id',
     'institution_name', 'institution_organization', 'institution_country'])

MemberInfo = namedtuple(
    'MemberInfo',
    ['pi', 'editor', 'observer'])

MemberInstitution = namedtuple(
    'MemberInstitution',
    ['id', 'institution_id'])

Message = namedtuple(
    'Message',
    [x.name for x in message.columns] + ['recipients'])

MessageRecipient = namedtuple(
    'MessageRecipient',
    ['name', 'address', 'public'])

Person = namedtuple(
    'Person',
    map(lambda x: x.name, person.columns) +
    ['email', 'institution', 'proposals'])

PersonInfo = namedtuple(
    'PersonInfo',
    [x.name for x in person.columns] +
    ['institution_name', 'institution_organization', 'institution_country'])

Proposal = namedtuple(
    'Proposal',
    map(lambda x: x.name, proposal.columns) + [
        'semester_id', 'semester_name', 'semester_code',
        'queue_id', 'queue_name', 'queue_code',
        'facility_id',
        'abst_word_lim', 'tech_word_lim', 'tech_page_lim',
        'sci_word_lim', 'sci_fig_lim', 'sci_page_lim',
        'members',
    ])

ProposalFigure = namedtuple(
    'ProposalFigure',
    ['data', 'type', 'filename'])

ProposalFigureInfo = namedtuple(
    'ProposalFigInfo',
    ['id', 'proposal_id', 'role', 'type', 'state', 'caption',
     'md5sum', 'filename', 'uploaded', 'uploader', 'uploader_name',
     'has_preview'])

ProposalPDFInfo = namedtuple(
    'ProposalPDFInfo',
    ['id', 'proposal_id', 'role', 'md5sum', 'state', 'pages',
     'filename', 'uploaded', 'uploader', 'uploader_name'])

ProposalText = namedtuple(
    'ProposalText',
    ['text', 'format'])

ProposalTextInfo = namedtuple(
    'ProposalTextInfo',
    ['id', 'proposal_id', 'role', 'format', 'words',
     'edited', 'editor', 'editor_name'])

Semester = namedtuple(
    'Semester',
    map(lambda x: x.name, semester.columns))

SemesterInfo = namedtuple(
    'SemesterInfo',
    ['id', 'facility_id', 'name', 'code', 'date_start', 'date_end'])

Target = namedtuple(
    'Target',
    [x.name for x in target.columns])

Queue = namedtuple(
    'Queue',
    map(lambda x: x.name, queue.columns))

QueueInfo = namedtuple(
    'Queue',
    ['id', 'facility_id', 'name', 'code'])


class FormatType(object):
    PLAIN = 1

    _info = OrderedDict((
        (PLAIN, 'Plain'),
    ))

    @classmethod
    def is_valid(cls, format):
        return format in cls._info


class ProposalAttachmentState(object):
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
    def is_valid(cls, state):
        return state in cls._info

    @classmethod
    def get_name(cls, state):
        return cls._info[state].name

    @classmethod
    def is_ready(cls, state):
        return cls._info[state].ready

    @classmethod
    def is_error(cls, state):
        return cls._info[state].error


class ProposalFigureType(object):
    PNG = 1
    JPEG = 2
    PDF = 3

    FigureTypeInfo = namedtuple('FigureTypeInfo',
                                ('name', 'mime', 'preview'))

    _info = OrderedDict((
        (PNG,  FigureTypeInfo('PNG',  'image/png',       False)),
        (JPEG, FigureTypeInfo('JPEG', 'image/jpeg',      False)),
        (PDF,  FigureTypeInfo('PDF',  'application/pdf', True)),
    ))

    @classmethod
    def is_valid(cls, type_):
        return type_ in cls._info

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

        raise UserError('File has type "{0}" which is not recognised.',
                        mime_type)

    @classmethod
    def all_mime_types(cls):
        return [x.mime for x in cls._info.values()]


class ProposalState(object):
    PREPARATION = 1
    SUBMITTED = 2
    WITHDRAWN = 3
    REVIEW = 4
    ABANDONED = 5
    ACCEPTED = 6
    REJECTED = 7

    StateInfo = namedtuple('StateInfo', ('name', 'edit', 'submitted'))

    _info = OrderedDict((
        (PREPARATION, StateInfo('In preparation', True,  False)),
        (SUBMITTED,   StateInfo('Submitted',      True,  True)),
        (WITHDRAWN,   StateInfo('Withdrawn',      True,  False)),
        (REVIEW,      StateInfo('Under review',   False, True)),
        (ABANDONED,   StateInfo('Abandoned',      False, False)),
        (ACCEPTED,    StateInfo('Accepted',       False, True)),
        (REJECTED,    StateInfo('Rejected',       False, True))
    ))

    @classmethod
    def is_submitted(cls, state):
        return cls._info[state].submitted

    @classmethod
    def is_valid(cls, state):
        return state in cls._info

    @classmethod
    def get_name(cls, state):
        return cls._info[state].name

    @classmethod
    def can_edit(cls, state):
        return cls._info[state].edit


class ProposalTextRole(object):
    ABSTRACT = 1
    TECHNICAL_CASE = 2
    SCIENCE_CASE = 3

    _info = {
        ABSTRACT: 'Abstract',
        TECHNICAL_CASE: 'Technical Justification',
        SCIENCE_CASE: 'Scientific Justification',
    }

    @classmethod
    def is_valid(cls, role):
        return role in cls._info

    @classmethod
    def get_name(cls, role):
        return cls._info[role]


class ResultCollection(OrderedDict):
    def get_single(self, default=()):
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


ResultTable = namedtuple('ResultTable', ('table', 'columns', 'rows'))


class EmailCollection(ResultCollection):
    def get_primary(self):
        for email in self.values():
            if email.primary:
                return email

        raise KeyError('no primary address')

    def validate(self):
        """
        Attempts to validate a collection of email records.

        Checks:

        * There is exactly one primary address.

        Raises UserError for any problems found.
        """

        n_primary = 0

        for email in self.values():
            if email.primary:
                n_primary += 1

        if n_primary == 0:
            raise UserError('There is no primary address.')
        elif n_primary != 1:
            raise UserError('There is more than one primary address.')


class MemberCollection(ResultCollection):
    def get_pi(self):
        for member in self.values():
            if member.pi:
                return member

        raise KeyError('no pi member')

    def get_person(self, person_id):
        for member in self.values():
            if member.person_id == person_id:
                return member

        raise KeyError('person not in member collection')

    def validate(self, editor_person_id):
        """
        Attempts to validate the members of a proposal.

        Checks:

        * There is exactly one PI.
        * The given person ID is an editor.  (To prevent people removing
          their own editor permission.)

        Raises UserError for any problems found.
        """

        n_pi = 0
        person_is_editor = None

        for member in self.values():
            if member.pi:
                n_pi += 1

            if member.person_id == editor_person_id:
                person_is_editor = member.editor

        if n_pi == 0:
            raise UserError('There is no PI specified.')
        elif n_pi != 1:
            raise UserError('There is more than one PI specified')

        if person_is_editor is None:
            raise userError('You can not remove yourself from the proposal.')
        elif not person_is_editor:
            raise userError('You can not remove yourself as an editor.')


class ProposalTextCollection(ResultCollection):
    def get_role(self, role, default=()):
        for pdf in self.values():
            if pdf.role == role:
                return pdf

        if default == ():
            raise KeyError('no text/PDF for this role')
        else:
            return default


class TargetCollection(OrderedDict):
    def to_formatted_collection(self):
        ans = OrderedDict()

        for (k, v) in self.items():
            if v.x is None or v.y is None:
                x = y = ''
            else:
                (x, y) = format_coord(v.system,
                                      coord_from_dec_deg(v.system, v.x, v.y))

            ans[k] = v._replace(x=x, y=y)

        return ans

    @classmethod
    def from_formatted_collection(cls, records):
        ans = cls()

        for (k, v) in records.items():
            system = v.system

            if not v.name:
                raise UserError('Each target object should have a name.')

            if v.x and v.y:
                (x, y) = coord_to_dec_deg(parse_coord(system,
                                                      v.x, v.y, v.name))

            elif v.x or v.y:
                raise UserError('Target "{0}" has only one coordinate.',
                                v.name)

            else:
                system = x = y = None

            ans[k] = v._replace(system=system, x=x, y=y)

        return ans


def null_tuple(type_):
    """
    Make a named tuple instance of the given type with all entries
    set to None.
    """

    return type_(*((None,) * len(type_._fields)))
