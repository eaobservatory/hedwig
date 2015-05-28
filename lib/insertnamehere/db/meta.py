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

from sqlalchemy.schema import Column, ForeignKey, MetaData, Table, \
    UniqueConstraint

from sqlalchemy.types import Boolean, DateTime, Integer, String, Unicode

metadata = MetaData()

_table_opts = {
    'mysql_engine': 'InnoDB',
    'mysql_charset': 'utf8',
}

affiliation = Table(
    'affiliation',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('facility_id', None,
           ForeignKey('facility.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('name', Unicode(31), nullable=False),
    Column('hidden', Boolean, default=False, nullable=False),
    UniqueConstraint('facility_id', 'name'),
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
    UniqueConstraint('semester_id', 'queue_id'),
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
    **_table_opts)

invitation = Table(
    'invitation',
    metadata,
    Column('token', String(255), primary_key=True),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           unique=True, nullable=False),
    Column('expiry', DateTime(), nullable=False),
    **_table_opts)

member = Table(
    'member',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('person_id', None,
           ForeignKey('person.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('pi', Boolean, nullable=False),
    Column('editor', Boolean, nullable=False),
    Column('observer', Boolean, nullable=False),
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

proposal = Table(
    'proposal',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('call_id', None,
           ForeignKey('call.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('number', Integer, nullable=False),
    Column('title', Unicode(255), nullable=False),
    UniqueConstraint('call_id', 'number'),
    **_table_opts)

queue = Table(
    'queue',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('facility_id', None,
           ForeignKey('facility.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('name', Unicode(31), nullable=False),
    UniqueConstraint('facility_id', 'name'),
    **_table_opts)

reset_token = Table(
    'reset_token',
    metadata,
    Column('token', String(255), primary_key=True),
    Column('user_id', None,
           ForeignKey('user.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           unique=True, nullable=False),
    Column('expiry', DateTime(), nullable=False),
    **_table_opts)

semester = Table(
    'semester',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('facility_id', None,
           ForeignKey('facility.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('name', Unicode(31), nullable=False),
    UniqueConstraint('facility_id', 'name'),
    **_table_opts)

user = Table(
    'user',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('name', Unicode(255), unique=True, nullable=False),
    Column('password', String(255)),
    Column('salt', String(255)),
    **_table_opts)
