# Copyright (C) 2015-2025 East Asian Observatory
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

from sqlalchemy.schema import Column, ForeignKey, Index, MetaData, \
    PrimaryKeyConstraint, Table, UniqueConstraint

from sqlalchemy.types import Boolean, DateTime, Float, Integer, \
    LargeBinary, Unicode, UnicodeText

from .type import JSONEncoded

metadata = MetaData()

table_opts = {
    'mysql_engine': 'InnoDB',
    'mysql_charset': 'utf8',
    'sqlite_autoincrement': True,
}

affiliation = Table(
    'affiliation',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('queue_id', None,
           ForeignKey('queue.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('name', Unicode(255), nullable=False),
    Column('hidden', Boolean, default=False, nullable=False),
    Column('type', Integer, nullable=False,
           doc='Type of affiliation (facility-specific meaning).'),
    UniqueConstraint('queue_id', 'name'),
    **table_opts)

affiliation_weight = Table(
    'affiliation_weight',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('affiliation_id', None,
           ForeignKey('affiliation.id',
                      onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('call_id', None,
           ForeignKey('call.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('weight', Float(precision=53, asdecimal=False), nullable=True,
           doc='Weighting factor for assignment calculations, if necessary. '
           'The actual calculation will be facility-specific.'),
    Column('hidden', Boolean, default=None, nullable=True),
    Column('type', Integer, default=None, nullable=True),
    UniqueConstraint('affiliation_id', 'call_id'),
    **table_opts)


def _note_cols():
    return [
        Column('note', UnicodeText, nullable=False),
        Column('note_format', Integer, nullable=False),
    ]


affiliation_weight_note = Table(
    'affiliation_weight_note',
    metadata,
    Column('call_id', None,
           ForeignKey('call.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           primary_key=True, nullable=False),
    *_note_cols(),
    **table_opts)

auth_failure = Table(
    'auth_failure',
    metadata,
    Column('user_name', Unicode(255), primary_key=True, nullable=False),
    Column('attempts', Integer, nullable=False),
    Column('expiry', DateTime(), nullable=False, index=True),
    **table_opts)

auth_token = Table(
    'auth_token',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('token', Unicode(255), unique=True, nullable=False),
    Column('user_id', None,
           ForeignKey('user.id', onupdate='RESTRICT', ondelete='CASCADE'),
           nullable=False),
    Column('expiry', DateTime(), nullable=False, index=True),
    Column('remote_addr', Unicode(255), nullable=True),
    Column('remote_agent', Unicode(255), nullable=True),
    **table_opts)

available_note = Table(
    'available_note',
    metadata,
    Column('call_id', None,
           ForeignKey('call.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           primary_key=True, nullable=False),
    *_note_cols(),
    **table_opts)

calculator = Table(
    'calculator',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('facility_id', None,
           ForeignKey('facility.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('code', Unicode(31), nullable=False),
    UniqueConstraint('code', 'facility_id'),
    **table_opts)


def _calculation_cols():
    return [
        Column('sort_order', Integer, nullable=False),
        Column('calculator_id', None,
               ForeignKey('calculator.id', onupdate='RESTRICT',
                          ondelete='RESTRICT'),
               nullable=False),
        Column('mode', Integer, nullable=False),
        Column('version', Integer, nullable=False),
        Column('input', JSONEncoded, nullable=False),
        Column('output', JSONEncoded, nullable=False),
        Column('date_run', DateTime(), nullable=False),
        Column('calc_version', Unicode(31), nullable=False),
        Column('title', Unicode(255), nullable=False),
    ]


calculation = Table(
    'calculation',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    *_calculation_cols(),
    **table_opts)

call = Table(
    'call',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('semester_id', None,
           ForeignKey('semester.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('queue_id', None,
           ForeignKey('queue.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('type', Integer, nullable=False),
    Column('date_open', DateTime(), nullable=False),
    Column('date_close', DateTime(), nullable=False),
    Column('abst_word_lim', Integer, nullable=False),
    Column('tech_word_lim', Integer, nullable=False),
    Column('tech_fig_lim', Integer, nullable=False),
    Column('tech_page_lim', Integer, nullable=False),
    Column('sci_word_lim', Integer, nullable=False),
    Column('sci_fig_lim', Integer, nullable=False),
    Column('sci_page_lim', Integer, nullable=False),
    Column('capt_word_lim', Integer, nullable=False),
    Column('expl_word_lim', Integer, nullable=False),
    Column('tech_note', UnicodeText, nullable=False),
    Column('sci_note', UnicodeText, nullable=False),
    Column('prev_prop_note', UnicodeText, nullable=False),
    Column('note_format', Integer, nullable=False),
    Column('multi_semester', Boolean, default=False, nullable=False),
    Column('separate', Boolean, default=False, nullable=False),
    Column('preamble', UnicodeText, nullable=True),
    Column('preamble_format', Integer, nullable=True),
    Column('hidden', Boolean, default=False, nullable=False),
    Column('allow_continuation', Boolean, default=False, nullable=False),
    Column('cnrq_note', UnicodeText, nullable=False),
    Column('cnrq_word_lim', Integer, nullable=False),
    Column('cnrq_fig_lim', Integer, nullable=False),
    Column('cnrq_page_lim', Integer, nullable=False),
    Column('cnrq_max_age', Integer, nullable=True),
    UniqueConstraint('semester_id', 'queue_id', 'type'),
    **table_opts)

call_mid_close = Table(
    'call_mid_close',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('call_id', None,
           ForeignKey('call.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('date', DateTime(), nullable=False),
    Column('closed', Boolean, default=False, nullable=False),
    UniqueConstraint('call_id', 'date'),
    **table_opts)

call_preamble = Table(
    'call_preamble',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('semester_id', None,
           ForeignKey('semester.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('type', Integer, nullable=False),
    Column('description', UnicodeText, nullable=False),
    Column('description_format', Integer, nullable=False),
    UniqueConstraint('semester_id', 'type'),
    **table_opts)

category = Table(
    'category',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('facility_id', None,
           ForeignKey('facility.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('name', Unicode(255), nullable=False),
    Column('hidden', Boolean, default=False, nullable=False),
    UniqueConstraint('facility_id', 'name'),
    **table_opts)

decision = Table(
    'decision',
    metadata,
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           primary_key=True, nullable=False),
    Column('accept', Boolean, nullable=True,
           doc='Indicates whether the time allocation committee decided '
               'to accept the proposal'),
    Column('exempt', Boolean, default=False, nullable=False,
           doc='True if the proposal time allocation is exempt from '
               'affiliation totals, e.g. for overall "best science" '
               'proposals.'),
    Column('ready', Boolean, default=False, nullable=False,
           doc='True if the committee is ready for an email message to be '
               'sent to the proposal members to inform them of the decision.'),
    Column('note', UnicodeText, nullable=False),
    Column('note_format', Integer, nullable=False),
    **table_opts)

email = Table(
    'email',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='CASCADE'),
           nullable=False),
    Column('address', Unicode(255), nullable=False),
    Column('primary', Boolean, default=False, nullable=False),
    Column('verified', Boolean, default=False, nullable=False),
    Column('public', Boolean, default=False, nullable=False),
    UniqueConstraint('person_id', 'address'),
    **table_opts)

facility = Table(
    'facility',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('code', Unicode(31), nullable=False, unique=True),
    **table_opts)

group_member = Table(
    'group_member',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('queue_id', None,
           ForeignKey('queue.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('group_type', Integer, nullable=False),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    UniqueConstraint('queue_id', 'group_type', 'person_id'),
    **table_opts)

institution = Table(
    'institution',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('name', Unicode(255), nullable=False),
    Column('department', Unicode(255), nullable=False),
    Column('organization', Unicode(255), nullable=False),
    Column('address', UnicodeText, nullable=False),
    Column('country', Unicode(2), nullable=False),
    Column('name_abbr', Unicode(31), nullable=True),
    Column('department_abbr', Unicode(31), nullable=True),
    Column('organization_abbr', Unicode(31), nullable=True),
    **table_opts)

institution_log = Table(
    'institution_log',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('institution_id', None,
           ForeignKey('institution.id', onupdate='RESTRICT',
                      ondelete='RESTRICT'),
           nullable=False),
    Column('date', DateTime(), nullable=False),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('prev_name', Unicode(255), nullable=False),
    Column('prev_department', Unicode(255), nullable=False),
    Column('prev_organization', Unicode(255), nullable=False),
    Column('prev_address', UnicodeText, nullable=False),
    Column('prev_country', Unicode(2), nullable=False),
    Column('prev_name_abbr', Unicode(31), nullable=True),
    Column('prev_department_abbr', Unicode(31), nullable=True),
    Column('prev_organization_abbr', Unicode(31), nullable=True),
    Column('approved', Boolean, default=False, nullable=False),
    **table_opts)

invitation = Table(
    'invitation',
    metadata,
    Column('token', Unicode(255), primary_key=True),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           unique=True, nullable=False),
    Column('expiry', DateTime(), nullable=False, index=True),
    **table_opts)

member = Table(
    'member',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('sort_order', Integer, nullable=False),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('pi', Boolean, nullable=False),
    Column('editor', Boolean, nullable=False),
    Column('observer', Boolean, nullable=False),
    Column('reviewer', Boolean, nullable=False),
    Column('student', Boolean, nullable=False, default=False),
    Column('affiliation_id', None,
           ForeignKey('affiliation.id', onupdate='RESTRICT',
                      ondelete='RESTRICT'),
           nullable=False),
    Column('institution_id', None,
           ForeignKey('institution.id', onupdate='RESTRICT',
                      ondelete='RESTRICT'),
           nullable=True),
    UniqueConstraint('proposal_id', 'person_id'),
    **table_opts)

message = Table(
    'message',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('date', DateTime(), nullable=False),
    Column('subject', Unicode(255), nullable=False),
    Column('body', UnicodeText, nullable=False),
    Column('timestamp_send', DateTime(), default=None, index=True),
    Column('timestamp_sent', DateTime(), default=None),
    Column('identifier', Unicode(255), default=None),
    Column('thread_type', Integer, default=None),
    Column('thread_id', Integer, default=None),
    Column('state', Integer, nullable=False, index=True),
    Column('format', Integer, nullable=False),
    **table_opts)

message_recipient = Table(
    'message_recipient',
    metadata,
    Column('message_id', None,
           ForeignKey('message.id', onupdate='RESTRICT', ondelete='CASCADE'),
           nullable=False),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='CASCADE'),
           nullable=False),
    Column('email_address', Unicode(255), nullable=True),
    PrimaryKeyConstraint('message_id', 'person_id',
                         name='message_recipient_pk'),
    **table_opts)

moc = Table(
    'moc',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('facility_id', None,
           ForeignKey('facility.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('name', Unicode(255), nullable=False),
    Column('description', UnicodeText, nullable=False),
    Column('description_format', Integer, nullable=False),
    Column('public', Boolean, nullable=False),
    Column('uploaded', DateTime(), nullable=False),
    Column('num_cells', Integer, nullable=False),
    Column('area', Float(precision=53, asdecimal=False), nullable=True),
    Column('state', Integer, nullable=False, index=True),
    UniqueConstraint('facility_id', 'name'),
    **table_opts)

moc_cell = Table(
    'moc_cell',
    metadata,
    Column('moc_id', None,
           ForeignKey('moc.id', onupdate='RESTRICT', ondelete='CASCADE'),
           nullable=False),
    Column('order', Integer, nullable=False),
    Column('cell', Integer, nullable=False),
    Index('idx_moc_cell', 'moc_id', 'order', 'cell', unique=True),
    **table_opts)

moc_fits = Table(
    'moc_fits',
    metadata,
    Column('moc_id', None,
           ForeignKey('moc.id', onupdate='RESTRICT', ondelete='CASCADE'),
           primary_key=True, nullable=False),
    Column('fits', LargeBinary(2**32 - 1), nullable=False),
    **table_opts)


def _oauth_cols():
    return [
        Column('client_id', Unicode(63), nullable=False),
        Column('scope', Unicode(255), default='', nullable=False),
        Column(
            'person_id', None,
            ForeignKey('person.id', onupdate='RESTRICT', ondelete='CASCADE'),
            nullable=False),
        Column('issued', DateTime(), nullable=False),
        Column('expiry', DateTime(), nullable=False, index=True),
    ]


oauth_code = Table(
    'oauth_code',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('code', Unicode(255), unique=True, nullable=False),
    Column('redirect_uri', Unicode(255), nullable=False),
    Column('response_type', Unicode(255), nullable=False),
    Column('nonce', Unicode(255), nullable=True),
    *_oauth_cols(),
    **table_opts)

oauth_token = Table(
    'oauth_token',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('token_type', Unicode(63), nullable=False),
    Column('access_token', Unicode(255), unique=True, nullable=False),
    Column('refresh_token', Unicode(255), index=True, nullable=True),
    Column('revoked', Boolean, default=False, nullable=False),
    *_oauth_cols(),
    **table_opts)

person = Table(
    'person',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('name', Unicode(255), nullable=False),
    Column('title', Integer, nullable=True),
    Column('public', Boolean, default=False, nullable=False),
    Column('user_id', None,
           ForeignKey('user.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           unique=True),
    Column('institution_id', None,
           ForeignKey('institution.id', onupdate='RESTRICT',
                      ondelete='RESTRICT')),
    Column('admin', Boolean, default=False, nullable=False),
    Column('verified', Boolean, default=False, nullable=False),
    **table_opts)

person_log = Table(
    'person_log',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('date', DateTime(), nullable=False),
    Column('event', Integer, nullable=False),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=True),
    Column('institution_id', None,
           ForeignKey('institution.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=True),
    Column('other_person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=True),
    **table_opts)

prev_proposal = Table(
    'prev_proposal',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('this_proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=True),
    Column('proposal_code', Unicode(255), nullable=False),
    Column('continuation', Boolean, nullable=False),
    Column('sort_order', Integer, nullable=False),
    **table_opts)

prev_proposal_pub = Table(
    'prev_proposal_pub',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('prev_proposal_id', None,
           ForeignKey('prev_proposal.id',
                      onupdate='RESTRICT', ondelete='CASCADE'),
           nullable=False),
    Column('description', Unicode(255), nullable=False),
    Column('type', Integer, nullable=False),
    Column('state', Integer, nullable=False, index=True),
    Column('title', Unicode(255), nullable=True),
    Column('author', Unicode(255), nullable=True),
    Column('year', Unicode(31), nullable=True),
    Column('edited', DateTime(), nullable=False),
    **table_opts)

proposal = Table(
    'proposal',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('call_id', None,
           ForeignKey('call.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('number', Integer, nullable=False),
    Column('state', Integer, nullable=False),
    Column('title', Unicode(255), nullable=False),
    Column('type', Integer, nullable=False),
    UniqueConstraint('call_id', 'number'),
    **table_opts)

proposal_annotation = Table(
    'proposal_annotation',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('type', Integer, nullable=False),
    Column('date', DateTime(), nullable=False),
    Column('annotation', JSONEncoded, nullable=False),
    **table_opts)

proposal_category = Table(
    'proposal_category',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('category_id', None,
           ForeignKey('category.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    **table_opts)

proposal_text = Table(
    'proposal_text',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('text', UnicodeText, nullable=False),
    Column('format', Integer, nullable=False),
    Column('words', Integer, nullable=False),
    Column('edited', DateTime(), nullable=False),
    Column('editor', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    **table_opts)

proposal_text_link = Table(
    'proposal_text_link',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('role', Integer, nullable=False),
    Column('text_id', None,
           ForeignKey('proposal_text.id',
                      onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Index('idx_text_prop_role', 'proposal_id', 'role', unique=True),
    **table_opts)


def _fig_cols():
    return [
        Column('type', Integer, nullable=False),
        Column('state', Integer, nullable=False, index=True),
        Column('figure', LargeBinary(2**24 - 1), nullable=False),
        Column('md5sum', Unicode(40), nullable=False),
        Column('filename', Unicode(255), nullable=False),
        Column('uploaded', DateTime(), nullable=False),
        Column('uploader', None,
               ForeignKey('person.id',
                          onupdate='RESTRICT', ondelete='RESTRICT'),
               nullable=False),
    ]


proposal_fig = Table(
    'proposal_fig',
    metadata,
    Column('id', Integer, primary_key=True),
    *_fig_cols(),
    **table_opts)

proposal_fig_link = Table(
    'proposal_fig_link',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('role', Integer, nullable=False),
    Column('fig_id', None,
           ForeignKey('proposal_fig.id',
                      onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('sort_order', Integer, nullable=False),
    Column('caption', UnicodeText, nullable=False),
    **table_opts)


def _fig_preview_cols():
    return [
        Column('preview', LargeBinary(2**24 - 1), nullable=False),
    ]


proposal_fig_preview = Table(
    'proposal_fig_preview',
    metadata,
    Column('fig_id', None,
           ForeignKey('proposal_fig.id',
                      onupdate='RESTRICT', ondelete='CASCADE'),
           primary_key=True, nullable=False),
    *_fig_preview_cols(),
    **table_opts)


def _fig_thumbnail_cols():
    return [
        Column('thumbnail', LargeBinary(2**24 - 1), nullable=False),
    ]


proposal_fig_thumbnail = Table(
    'proposal_fig_thumbnail',
    metadata,
    Column('fig_id', None,
           ForeignKey('proposal_fig.id',
                      onupdate='RESTRICT', ondelete='CASCADE'),
           primary_key=True, nullable=False),
    *_fig_thumbnail_cols(),
    **table_opts)

proposal_pdf = Table(
    'proposal_pdf',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('pdf', LargeBinary(2**32 - 1), nullable=False),
    Column('md5sum', Unicode(40), nullable=False),
    Column('state', Integer, nullable=False, index=True),
    Column('pages', Integer, nullable=False),
    Column('filename', Unicode(255), nullable=False),
    Column('uploaded', DateTime(), nullable=False),
    Column('uploader', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    **table_opts)

proposal_pdf_link = Table(
    'proposal_pdf_link',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('role', Integer, nullable=False),
    Column('pdf_id', None,
           ForeignKey('proposal_pdf.id',
                      onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Index('idx_pdf_prop_role', 'proposal_id', 'role', unique=True),
    **table_opts)

proposal_pdf_preview = Table(
    'proposal_pdf_preview',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('pdf_id', None,
           ForeignKey('proposal_pdf.id',
                      onupdate='RESTRICT', ondelete='CASCADE'),
           nullable=False),
    Column('page', Integer, nullable=False),
    Column('preview', LargeBinary(2**24 - 1), nullable=False),
    Index('idx_pdf_id_page', 'pdf_id', 'page', unique=True),
    **table_opts)

queue = Table(
    'queue',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('facility_id', None,
           ForeignKey('facility.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('name', Unicode(255), nullable=False),
    Column('code', Unicode(31), nullable=False),
    Column('description', UnicodeText, nullable=False),
    Column('description_format', Integer, nullable=False),
    UniqueConstraint('facility_id', 'name'),
    UniqueConstraint('facility_id', 'code'),
    **table_opts)


def _request_cols():
    return [
        Column('state', Integer, nullable=False, index=True),
        Column('requested', DateTime(), nullable=False),
        Column('requester', None,
               ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
               nullable=False),
        Column('processed', DateTime(), nullable=True),
    ]


request_prop_copy = Table(
    'request_prop_copy',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('call_id', None,
           ForeignKey('call.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('affiliation_id', None,
           ForeignKey('affiliation.id', onupdate='RESTRICT',
                      ondelete='RESTRICT'),
           nullable=False),
    Column('copy_members', Boolean, nullable=False),
    Column('copy_proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=True),
    Column('continuation', Boolean, nullable=False),
    *_request_cols(),
    **table_opts)

request_prop_pdf = Table(
    'request_prop_pdf',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    *_request_cols(),
    **table_opts)

reset_token = Table(
    'reset_token',
    metadata,
    Column('token', Unicode(255), primary_key=True),
    Column('user_id', None,
           ForeignKey('user.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           unique=True, nullable=False),
    Column('expiry', DateTime(), nullable=False, index=True),
    **table_opts)

review = Table(
    'review',
    metadata,
    Column('reviewer_id', None,
           ForeignKey('reviewer.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           primary_key=True, nullable=False),
    Column('text', UnicodeText, nullable=True),
    Column('format', Integer, nullable=True),
    Column('assessment', Integer, nullable=True),
    Column('rating', Integer, nullable=True),
    Column('weight', Integer, nullable=True),
    Column('edited', DateTime(), nullable=False),
    Column('note', UnicodeText, nullable=True),
    Column('note_format', Integer, nullable=True),
    Column('note_public', Boolean, nullable=False),
    Column('state', Integer, nullable=False, index=True),
    **table_opts)

reviewer = Table(
    'reviewer',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('role', Integer, nullable=False),
    Column('notified', Boolean, default=False, nullable=False),
    Column('accepted', Boolean, nullable=True),
    Column('thanked', Boolean, nullable=True),
    UniqueConstraint('proposal_id', 'person_id', 'role'),
    **table_opts)

reviewer_acceptance = Table(
    'reviewer_acceptance',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('role', Integer, nullable=False),
    Column('accepted', Boolean, nullable=False),
    Column('text', UnicodeText, nullable=True),
    Column('format', Integer, nullable=True),
    Column('date', DateTime(), nullable=False),
    UniqueConstraint('proposal_id', 'person_id', 'role'),
    **table_opts)

reviewer_note = Table(
    'reviewer_note',
    metadata,
    Column('reviewer_id', None,
           ForeignKey('reviewer.id',
                      onupdate='RESTRICT', ondelete='CASCADE'),
           primary_key=True, nullable=False),
    *_note_cols(),
    **table_opts)

review_calculation = Table(
    'review_calculation',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('reviewer_id', None,
           ForeignKey('reviewer.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    *_calculation_cols(),
    **table_opts)

review_deadline = Table(
    'review_deadline',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('call_id', None,
           ForeignKey('call.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('role', Integer, nullable=False),
    Column('date', DateTime(), nullable=False),
    UniqueConstraint('call_id', 'role'),
    **table_opts)

review_fig = Table(
    'review_fig',
    metadata,
    Column('id', Integer, primary_key=True),
    *_fig_cols(),
    **table_opts)

review_fig_link = Table(
    'review_fig_link',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('reviewer_id', None,
           ForeignKey('reviewer.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('fig_id', None,
           ForeignKey('review_fig.id',
                      onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('sort_order', Integer, nullable=False),
    Column('caption', UnicodeText, nullable=False),
    **table_opts)

review_fig_preview = Table(
    'review_fig_preview',
    metadata,
    Column('fig_id', None,
           ForeignKey('review_fig.id',
                      onupdate='RESTRICT', ondelete='CASCADE'),
           primary_key=True, nullable=False),
    *_fig_preview_cols(),
    **table_opts)

review_fig_thumbnail = Table(
    'review_fig_thumbnail',
    metadata,
    Column('fig_id', None,
           ForeignKey('review_fig.id',
                      onupdate='RESTRICT', ondelete='CASCADE'),
           primary_key=True, nullable=False),
    *_fig_thumbnail_cols(),
    **table_opts)

semester = Table(
    'semester',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('facility_id', None,
           ForeignKey('facility.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('name', Unicode(255), nullable=False),
    Column('code', Unicode(31), nullable=False),
    Column('date_start', DateTime(), nullable=False),
    Column('date_end', DateTime(), nullable=False),
    Column('description', UnicodeText, nullable=False),
    Column('description_format', Integer, nullable=False),
    UniqueConstraint('facility_id', 'name'),
    UniqueConstraint('facility_id', 'code'),
    **table_opts)

site_group_member = Table(
    'site_group_member',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('site_group_type', Integer, nullable=False),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    UniqueConstraint('site_group_type', 'person_id'),
    **table_opts)

target = Table(
    'target',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('sort_order', Integer, nullable=False),
    Column('name', Unicode(255), nullable=False),
    Column('system', Integer, nullable=True),
    Column('x', Float(precision=53, asdecimal=False), nullable=True),
    Column('y', Float(precision=53, asdecimal=False), nullable=True),
    Column('time', Float(precision=53, asdecimal=False), nullable=True),
    Column('priority', Integer, nullable=True),
    Column('note', Unicode(255), nullable=True),
    **table_opts)

user = Table(
    'user',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('name', Unicode(255), unique=True, nullable=False),
    Column('password', Unicode(255)),
    Column('salt', Unicode(255)),
    Column('disabled', Boolean, default=False, nullable=False),
    **table_opts)

user_log = Table(
    'user_log',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', None,
           ForeignKey('user.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('date', DateTime(), nullable=False),
    Column('event', Integer, nullable=False),
    Column('remote_addr', Unicode(50), nullable=True),
    **table_opts)

verify_token = Table(
    'verify_token',
    metadata,
    Column('token', Unicode(255), primary_key=True),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('email_address', Unicode(255), nullable=False),
    Column('expiry', DateTime(), nullable=False, index=True),
    UniqueConstraint('person_id', 'email_address'),
    **table_opts)
