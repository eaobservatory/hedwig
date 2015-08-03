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

from sqlalchemy.schema import Column, ForeignKey, Index, MetaData, \
    PrimaryKeyConstraint, Table, UniqueConstraint

from sqlalchemy.types import Boolean, DateTime, Float, Integer, \
    LargeBinary, String, Unicode, UnicodeText

from .type import JSONEncoded

metadata = MetaData()

_table_opts = {
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
    UniqueConstraint('queue_id', 'name'),
    **_table_opts)

auth_failure = Table(
    'auth_failure',
    metadata,
    Column('user_name', Unicode(255), primary_key=True, nullable=False),
    Column('attempts', Integer, nullable=False),
    Column('expiry', DateTime(), nullable=False, index=True),
    **_table_opts)

calculator = Table(
    'calculator',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('facility_id', None,
           ForeignKey('facility.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('code', Unicode(31), nullable=False),
    UniqueConstraint('code', 'facility_id'),
    **_table_opts)

calculation = Table(
    'calculation',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
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
    **_table_opts)

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
    Column('note_format', Integer, nullable=False),
    UniqueConstraint('semester_id', 'queue_id'),
    **_table_opts)

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
    **_table_opts)

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
    **_table_opts)

facility = Table(
    'facility',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('code', Unicode(31), nullable=False, unique=True),
    **_table_opts)

institution = Table(
    'institution',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('name', Unicode(255), nullable=False),
    Column('organization', Unicode(255), nullable=False),
    Column('address', UnicodeText, nullable=False),
    Column('country', Unicode(2), nullable=False),
    **_table_opts)

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
    Column('prev_organization', Unicode(255), nullable=False),
    Column('prev_address', UnicodeText, nullable=False),
    Column('prev_country', Unicode(2), nullable=False),
    **_table_opts)

invitation = Table(
    'invitation',
    metadata,
    Column('token', String(255), primary_key=True),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           unique=True, nullable=False),
    Column('expiry', DateTime(), nullable=False, index=True),
    **_table_opts)

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
    **_table_opts)

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
    **_table_opts)

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
    **_table_opts)

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
    UniqueConstraint('facility_id', 'name'),
    **_table_opts)

moc_cell = Table(
    'moc_cell',
    metadata,
    Column('moc_id', None,
           ForeignKey('moc.id', onupdate='RESTRICT', ondelete='CASCADE'),
           nullable=False),
    Column('order', Integer, nullable=False),
    Column('cell', Integer, nullable=False),
    Index('idx_moc_cell', 'moc_id', 'order', 'cell', unique=True),
    **_table_opts)

person = Table(
    'person',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('name', Unicode(255), nullable=False),
    Column('public', Boolean, default=False, nullable=False),
    Column('user_id', None,
           ForeignKey('user.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           unique=True),
    Column('institution_id', None,
           ForeignKey('institution.id', onupdate='RESTRICT',
                      ondelete='RESTRICT')),
    Column('admin', Boolean, default=False, nullable=False),
    **_table_opts)

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
    **_table_opts)

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
    **_table_opts)

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
    UniqueConstraint('call_id', 'number'),
    **_table_opts)

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
    **_table_opts)

proposal_text = Table(
    'proposal_text',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('role', Integer, nullable=False),
    Column('text', UnicodeText, nullable=False),
    Column('format', Integer, nullable=False),
    Column('words', Integer, nullable=False),
    Column('edited', DateTime(), nullable=False),
    Column('editor', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Index('idx_text_prop_role', 'proposal_id', 'role', unique=True),
    **_table_opts)

proposal_fig = Table(
    'proposal_fig',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('sort_order', Integer, nullable=False),
    Column('role', Integer, nullable=False),
    Column('type', Integer, nullable=False),
    Column('state', Integer, nullable=False, index=True),
    Column('figure', LargeBinary(2**24 - 1), nullable=False),
    Column('md5sum', String(40), nullable=False),
    Column('filename', Unicode(255), nullable=False),
    Column('uploaded', DateTime(), nullable=False),
    Column('uploader', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('caption', UnicodeText, nullable=False),
    **_table_opts)

proposal_fig_preview = Table(
    'proposal_fig_preview',
    metadata,
    Column('fig_id', None,
           ForeignKey('proposal_fig.id',
                      onupdate='RESTRICT', ondelete='CASCADE'),
           primary_key=True, nullable=False),
    Column('preview', LargeBinary(2**24 - 1), nullable=False),
    **_table_opts)

proposal_fig_thumbnail = Table(
    'proposal_fig_thumbnail',
    metadata,
    Column('fig_id', None,
           ForeignKey('proposal_fig.id',
                      onupdate='RESTRICT', ondelete='CASCADE'),
           primary_key=True, nullable=False),
    Column('thumbnail', LargeBinary(2**24 - 1), nullable=False),
    **_table_opts)

proposal_pdf = Table(
    'proposal_pdf',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('role', Integer, nullable=False),
    Column('pdf', LargeBinary(2**32 - 1), nullable=False),
    Column('md5sum', String(40), nullable=False),
    Column('state', Integer, nullable=False, index=True),
    Column('pages', Integer, nullable=False),
    Column('filename', Unicode(255), nullable=False),
    Column('uploaded', DateTime(), nullable=False),
    Column('uploader', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Index('idx_pdf_prop_role', 'proposal_id', 'role', unique=True),
    **_table_opts)

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
    **_table_opts)

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
    **_table_opts)

reset_token = Table(
    'reset_token',
    metadata,
    Column('token', String(255), primary_key=True),
    Column('user_id', None,
           ForeignKey('user.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           unique=True, nullable=False),
    Column('expiry', DateTime(), nullable=False, index=True),
    **_table_opts)

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
    **_table_opts)

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
    **_table_opts)

user = Table(
    'user',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('name', Unicode(255), unique=True, nullable=False),
    Column('password', String(255)),
    Column('salt', String(255)),
    **_table_opts)

user_log = Table(
    'user_log',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', None,
           ForeignKey('user.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('date', DateTime(), nullable=False),
    Column('event', Integer, nullable=False),
    Column('remote_addr', String(50), nullable=True),
    **_table_opts)

verify_token = Table(
    'verify_token',
    metadata,
    Column('token', String(255), primary_key=True),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('email_address', Unicode(255), nullable=False),
    Column('expiry', DateTime(), nullable=False, index=True),
    UniqueConstraint('person_id', 'email_address'),
    **_table_opts)
