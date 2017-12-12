# Copyright (C) 2017 East Asian Observatory
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

from sqlalchemy.schema import Column, ForeignKey, Index, MetaData, Table, \
    UniqueConstraint

from sqlalchemy.types import Boolean, DateTime, Float, Integer, \
    Unicode, UnicodeText

from ...db.meta import metadata, table_opts


ukirt_allocation = Table(
    'ukirt_allocation',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('instrument', Integer, nullable=False),
    Column('brightness', Integer, nullable=False),
    Column('time', Float, nullable=False),
    UniqueConstraint('proposal_id', 'instrument', 'brightness'),
    **table_opts)

ukirt_request = Table(
    'ukirt_request',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('instrument', Integer, nullable=False),
    Column('brightness', Integer, nullable=False),
    Column('time', Float, nullable=False),
    UniqueConstraint('proposal_id', 'instrument', 'brightness'),
    **table_opts)
