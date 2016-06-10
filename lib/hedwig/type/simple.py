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

from collections import namedtuple

from ..db.meta import affiliation, calculation, call, category, \
    email, facility, group_member, institution, institution_log, \
    member, message, moc, person, \
    prev_proposal, prev_proposal_pub, \
    proposal, proposal_category, queue, review, reviewer, \
    semester, target, user_log

Affiliation = namedtuple(
    'Affiliation',
    [x.name for x in affiliation.columns] + ['weight'])

CalculatorInfo = namedtuple(
    'CalculatorInfo',
    ['id', 'code', 'name', 'calculator', 'modes'])

CalculatorMode = namedtuple(
    'CalculatorMode',
    ['code', 'name'])

CalculatorResult = namedtuple(
    'CalculatorResult',
    ['output', 'extra'])

CalculatorValue = namedtuple(
    'CalculatorValue',
    ['code', 'name', 'abbr', 'format', 'unit'])

Calculation = namedtuple(
    'Calculation',
    [x.name for x in calculation.columns])

Call = namedtuple(
    'Call',
    map(lambda x: x.name, call.columns) +
    ['state', 'facility_id', 'semester_name', 'queue_name',
     'queue_description', 'queue_description_format'])

Category = namedtuple(
    'Category',
    [x.name for x in category.columns])

Email = namedtuple(
    'Email',
    map(lambda x: x.name, email.columns))

Facility = namedtuple(
    'Facility',
    [x.name for x in facility.columns])

FacilityInfo = namedtuple(
    'FacilityInfo',
    ['id', 'code', 'name', 'view'])

GroupMember = namedtuple(
    'GroupMember',
    [x.name for x in group_member.columns] +
    ['person_name', 'person_public', 'person_registered',
     'institution_id', 'institution_name', 'institution_department',
     'institution_organization', 'institution_country'])

Institution = namedtuple(
    'Institution',
    map(lambda x: x.name, institution.columns))

InstitutionInfo = namedtuple(
    'InstitutionInfo',
    ['id', 'name', 'department', 'organization', 'country'])

InstitutionLog = namedtuple(
    'InstitutionLog',
    [x.name for x in institution_log.columns
     if not x.name.startswith('prev_')] +
    ['prev', 'person_name', 'institution_name'])

Link = namedtuple(
    'Link',
    ['text', 'url'])

Member = namedtuple(
    'Member',
    [x.name for x in member.columns if x.name not in ('institution_id',)] +
    ['person_name', 'person_public', 'person_registered',
     'affiliation_name',
     'resolved_institution_id',
     'institution_name', 'institution_department',
     'institution_organization', 'institution_country'])

MemberInfo = namedtuple(
    'MemberInfo',
    ['pi', 'editor', 'observer'])

MemberInstitution = namedtuple(
    'MemberInstitution',
    ['id', 'institution_id'])

MemberPIInfo = namedtuple(
    'MemberPIInfo',
    ['person_id', 'person_name', 'person_public', 'affiliation_name'])

Message = namedtuple(
    'Message',
    [x.name for x in message.columns] +
    ['recipients', 'thread_identifiers', 'state'])

MessageRecipient = namedtuple(
    'MessageRecipient',
    ['person_id', 'name', 'address', 'public'])

MOCInfo = namedtuple(
    'MOCInfo',
    [x.name for x in moc.columns])

Person = namedtuple(
    'Person',
    map(lambda x: x.name, person.columns) +
    ['email', 'institution', 'proposals', 'reviews'])

PersonInfo = namedtuple(
    'PersonInfo',
    [x.name for x in person.columns] +
    ['institution_name', 'institution_department',
     'institution_organization', 'institution_country'])

PrevProposal = namedtuple(
    'PrevProposal',
    [x.name for x in prev_proposal.columns] +
    ['publications'])

PrevProposalPub = namedtuple(
    'PrevProposalPub',
    [x.name for x in prev_proposal_pub.columns] + ['proposal_id'])

Proposal = namedtuple(
    'Proposal',
    map(lambda x: x.name, proposal.columns) + [
        'semester_id', 'semester_name', 'semester_code',
        'queue_id', 'queue_name', 'queue_code',
        'facility_id',
        'abst_word_lim',
        'tech_word_lim', 'tech_fig_lim', 'tech_page_lim',
        'sci_word_lim', 'sci_fig_lim', 'sci_page_lim',
        'capt_word_lim', 'expl_word_lim',
        'date_close',
        'has_decision',
        'decision_accept', 'decision_exempt', 'decision_ready',
        'decision_note', 'decision_note_format',
        'members', 'reviewers', 'categories',
    ])

ProposalWithCode = namedtuple('ProposalWithCode', Proposal._fields + ('code',))

ProposalCategory = namedtuple(
    'ProposalCategory',
    [x.name for x in proposal_category.columns] + ['category_name'])

ProposalFigure = namedtuple(
    'ProposalFigure',
    ['data', 'type', 'filename'])

ProposalFigureInfo = namedtuple(
    'ProposalFigInfo',
    ['id', 'proposal_id', 'role', 'type', 'state', 'caption',
     'md5sum', 'filename', 'uploaded', 'uploader', 'uploader_name',
     'has_preview'])

ProposalFigureThumbPreview = namedtuple(
    'ProposalFigureThumbPreview', ['thumbnail', 'preview'])

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

Reviewer = namedtuple(
    'Reviewer',
    [x.name for x in reviewer.columns] +
    ['person_name', 'person_public', 'person_registered',
     'institution_id', 'institution_name', 'institution_department',
     'institution_organization', 'institution_country',
     'review_present', 'invitation_token', 'invitation_expiry'] +
    ['review_{}'.format(x.name) for x in review.columns
     if x != review.c.reviewer_id])

ReviewerInfo = namedtuple(
    'ReviewerInfo',
    ['id', 'role', 'review_present'])

Semester = namedtuple(
    'Semester',
    map(lambda x: x.name, semester.columns))

SemesterInfo = namedtuple(
    'SemesterInfo',
    ['id', 'facility_id', 'name', 'code', 'date_start', 'date_end'])

Target = namedtuple(
    'Target',
    [x.name for x in target.columns])

TargetObject = namedtuple('TargetObject', ('name', 'system', 'coord'))

TargetToolInfo = namedtuple(
    'TargetToolInfo',
    ['id', 'code', 'name', 'tool'])

UserInfo = namedtuple(
    'UserInfo',
    ['id', 'name'])

UserLog = namedtuple(
    'UserLog',
    [x.name for x in user_log.columns])

Queue = namedtuple(
    'Queue',
    map(lambda x: x.name, queue.columns))

QueueInfo = namedtuple(
    'Queue',
    ['id', 'facility_id', 'name', 'code'])

ValidationMessage = namedtuple(
    'ValidationMessage',
    ['is_error', 'description', 'link_text', 'link_url'])
