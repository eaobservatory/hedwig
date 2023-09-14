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

from collections import namedtuple
from datetime import datetime

from ..db.meta import affiliation, \
    calculation, call, call_mid_close, call_preamble, category, \
    email, group_member, institution, institution_log, \
    member, message, message_recipient, moc, \
    oauth_code, oauth_token, person, person_log, \
    prev_proposal, prev_proposal_pub, \
    proposal, proposal_annotation, proposal_category, \
    proposal_fig, proposal_fig_link, proposal_pdf, proposal_pdf_link, \
    proposal_text, proposal_text_link, queue, \
    request_prop_copy, request_prop_pdf, \
    review, reviewer, reviewer_acceptance, \
    review_calculation, review_deadline, \
    review_fig, review_fig_link, \
    semester, site_group_member, target, user_log

Affiliation = namedtuple(
    'Affiliation',
    [x.name for x in affiliation.columns] + ['weight'])

Annotation = namedtuple(
    'Annotation',
    [x.name for x in proposal_annotation.columns])

AuthTokenInfo = namedtuple(
    'AuthTokenInfo',
    ['id', 'user_id', 'expiry', 'remote_addr', 'remote_agent',
     'user_name',
     'person_id', 'person_name'])

CalculatorInfo = namedtuple(
    'CalculatorInfo',
    ['id', 'code', 'name', 'calculator', 'modes', 'view_functions'])

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
    [x.name for x in call.columns] +
    ['state', 'facility_id', 'semester_name', 'queue_name',
     'queue_description', 'queue_description_format',
     'proposal_count'])

CallMidClose = namedtuple(
    'CallMidClose',
    [x.name for x in call_mid_close.columns])

CallPreamble = namedtuple(
    'CallPreamble',
    [x.name for x in call_preamble.columns])

Category = namedtuple(
    'Category',
    [x.name for x in category.columns])

CoMemberInfo = namedtuple(
    'CoMemberInfo',
    ['id', 'editor', 'co_member_person_id', 'co_member_institution_id'])

CurrentUser = namedtuple(
    'CurrentUser',
    ['user', 'person', 'is_admin', 'auth_token_id', 'options'])

# Pair type for conveniently passing date and time strings around.
DateAndTime = namedtuple('DateAndTime', ('date', 'time'))

Email = namedtuple(
    'Email',
    [x.name for x in email.columns])

FacilityInfo = namedtuple(
    'FacilityInfo',
    ['id', 'code', 'name', 'view'])

FacilityObsInfo = namedtuple(
    'FacilityObsInfo',
    ['geo_x', 'geo_y', 'geo_z', 'time_start', 'time_duration', 'el_min'])

GroupMember = namedtuple(
    'GroupMember',
    [x.name for x in group_member.columns] +
    ['person_name', 'person_public', 'person_registered',
     'institution_id', 'institution_name', 'institution_department',
     'institution_organization', 'institution_country',
     'queue_code', 'queue_name', 'facility_id',])

Institution = namedtuple(
    'Institution',
    [x.name for x in institution.columns])

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
    ['person_name', 'person_public', 'person_registered', 'user_id',
     'affiliation_name',
     'resolved_institution_id',
     'institution_name', 'institution_department',
     'institution_organization', 'institution_country'])

MemberInfo = namedtuple(
    'MemberInfo',
    ['id', 'pi', 'editor', 'observer', 'person_id'])

MemberInstitution = namedtuple(
    'MemberInstitution',
    ['id', 'institution_id'])

MemberPIInfo = namedtuple(
    'MemberPIInfo',
    ['person_id', 'person_name', 'person_public', 'user_id', 'affiliation_name'])

Message = namedtuple(
    'Message',
    [x.name for x in message.columns] +
    ['recipients', 'thread_identifiers'])

MessageRecipient = namedtuple(
    'MessageRecipient',
    [x.name for x in message_recipient.columns] +
    ['person_name', 'email_public'])

MOCInfo = namedtuple(
    'MOCInfo',
    [x.name for x in moc.columns])

Note = namedtuple(
    'Note',
    ['text', 'format'])


class OAuthCode(namedtuple(
        '_OAuthCode', [x.name for x in oauth_code.columns])):
    def get_redirect_uri(self):
        return self.redirect_uri

    def get_scope(self):
        return self.scope

    def get_nonce(self):
        return self.nonce

    def get_auth_time(self):
        return int(
            (self.issued - datetime.utcfromtimestamp(0)).total_seconds())


class OAuthToken(namedtuple(
        '_OAuthToken', [x.name for x in oauth_token.columns])):
    def get_client_id(self):
        return self.client_id

    def get_scope(self):
        return self.scope

    def get_expires_in(self):
        return int((self.expiry - self.issued).total_seconds())

    def get_expires_at(self):
        return int(
            (self.expiry - datetime.utcfromtimestamp(0)).total_seconds())


Person = namedtuple(
    'Person',
    [x.name for x in person.columns] +
    ['email', 'institution', 'proposals', 'reviews'])

PersonInfo = namedtuple(
    'PersonInfo',
    [x.name for x in person.columns] +
    ['institution_name', 'institution_department',
     'institution_organization', 'institution_country'])

PersonLog = namedtuple(
    'PersonLog',
    [x.name for x in person_log.columns])

PrevProposal = namedtuple(
    'PrevProposal',
    [x.name for x in prev_proposal.columns] +
    ['publications'])

PrevProposalPub = namedtuple(
    'PrevProposalPub',
    [x.name for x in prev_proposal_pub.columns] + ['proposal_id'])

# Note that the Proposal tuple has fields "members", for when all members of a
# proposal are represented, and "member" for when information about a single
# member is retrieved.  This is to avoid confusion where the "members" field
# was previously used to hold only a single member information object.
# The same scheme is used for the "reviewers" and "reviewer" fields.
Proposal = namedtuple(
    'Proposal',
    [x.name for x in proposal.columns] + [
        'semester_id', 'semester_name', 'semester_code',
        'semester_start', 'semester_end',
        'queue_id', 'queue_name', 'queue_code',
        'call_type', 'call_separate', 'call_hidden',
        'facility_id',
        'abst_word_lim',
        'tech_word_lim', 'tech_fig_lim', 'tech_page_lim',
        'sci_word_lim', 'sci_fig_lim', 'sci_page_lim',
        'capt_word_lim', 'expl_word_lim',
        'date_close', 'multi_semester',
        'has_decision',
        'decision_accept', 'decision_exempt', 'decision_ready',
        'decision_note', 'decision_note_format',
        'member', 'members', 'reviewer', 'reviewers', 'categories',
    ])

ProposalWithCode = namedtuple('ProposalWithCode', Proposal._fields + ('code',))

ProposalCategory = namedtuple(
    'ProposalCategory',
    [x.name for x in proposal_category.columns] + ['category_name'])

ProposalFigure = namedtuple(
    'ProposalFigure',
    ['data', 'type', 'filename'])

ProposalFigureInfo = namedtuple(
    'ProposalFigureInfo',
    [x.name for x in proposal_fig_link.columns] +
    [x.name for x in proposal_fig.columns
     if x.name not in ('figure', 'id')] +
    ['uploader_name', 'has_preview'])

ProposalFigureThumbPreview = namedtuple(
    'ProposalFigureThumbPreview', ['thumbnail', 'preview'])

ProposalPDFInfo = namedtuple(
    'ProposalPDFInfo',
    [x.name for x in proposal_pdf_link.columns] +
    [x.name for x in proposal_pdf.columns
     if x.name not in ('pdf', 'id')] +
    ['uploader_name'])

ProposalText = namedtuple(
    'ProposalText',
    [x.name for x in proposal_text_link.columns] +
    [x.name for x in proposal_text.columns
     if x.name not in ('id',)] +
    ['editor_name'])

RequestPropCopy = namedtuple(
    'RequestPropCopy',
    [x.name for x in request_prop_copy.columns] +
    ['requester_name'])

RequestPropPDF = namedtuple(
    'RequestPropPDF',
    [x.name for x in request_prop_pdf.columns] +
    ['requester_name'])

Reviewer = namedtuple(
    'Reviewer',
    [x.name for x in reviewer.columns] +
    ['person_name', 'person_public', 'person_registered', 'user_id',
     'institution_id', 'institution_name', 'institution_department',
     'institution_organization', 'institution_country',
     'invitation_token', 'invitation_expiry', 'review_extra',
     'acceptance_accepted', 'acceptance_text', 'acceptance_format',
     'acceptance_date',
     'note', 'note_format'] +
    ['review_{}'.format(x.name) for x in review.columns
     if x != review.c.reviewer_id])

ReviewerAcceptance = namedtuple(
    'ReviewerAcceptance',
    [x.name for x in reviewer_acceptance.columns])

ReviewerInfo = namedtuple(
    'ReviewerInfo',
    ['id', 'role', 'review_state', 'person_id', 'proposal_id', 'accepted'])

ReviewCalculation = namedtuple(
    'ReviewCalculation',
    [x.name for x in review_calculation.columns])

ReviewDeadline = namedtuple(
    'ReviewDeadline',
    [x.name for x in review_deadline.columns])

ReviewFigureInfo = namedtuple(
    'ReviewFigureInfo',
    [x.name for x in review_fig_link.columns] +
    [x.name for x in review_fig.columns
     if x.name not in ('figure', 'id')] +
    ['uploader_name', 'has_preview'])

RouteInfo = namedtuple(
    'RouteInfo',
    ['template', 'rule', 'endpoint', 'func', 'options'])

Semester = namedtuple(
    'Semester',
    [x.name for x in semester.columns])

SemesterInfo = namedtuple(
    'SemesterInfo',
    ['id', 'facility_id', 'name', 'code', 'date_start', 'date_end', 'state'])

SiteGroupMember = namedtuple(
    'SiteGroupMember',
    [x.name for x in site_group_member.columns] +
    ['person_name', 'person_public', 'person_registered',
     'institution_id', 'institution_name', 'institution_department',
     'institution_organization', 'institution_country'])

Target = namedtuple(
    'Target',
    [x.name for x in target.columns])

TargetFracTime = namedtuple('TargetFracTime', ('coord', 'frac_time'))

TargetObject = namedtuple('TargetObject', ('name', 'system', 'coord', 'time'))

TargetToolInfo = namedtuple(
    'TargetToolInfo',
    ['id', 'code', 'name', 'tool'])

TextCopyInfo = namedtuple(
    'TextCopyInfo',
    ['role', 'section', 'word_lim', 'fig_lim', 'capt_word_lim', 'page_lim'])

UserInfo = namedtuple(
    'UserInfo',
    ['id', 'name', 'disabled'])

UserLog = namedtuple(
    'UserLog',
    [x.name for x in user_log.columns])

Queue = namedtuple(
    'Queue',
    [x.name for x in queue.columns])

QueueInfo = namedtuple(
    'Queue',
    ['id', 'facility_id', 'name', 'code'])

ValidationMessage = namedtuple(
    'ValidationMessage',
    ['is_error', 'description', 'link_text', 'link_url'])
