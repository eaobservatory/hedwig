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

from sqlalchemy.schema import Column, ForeignKey, Index, MetaData, Table, \
    UniqueConstraint

from sqlalchemy.types import Boolean, DateTime, Float, Integer, \
    Unicode, UnicodeText

from ...db.meta import metadata, table_opts


def _request_cols():
    return [
        Column('proposal_id', None,
               ForeignKey('proposal.id', onupdate='RESTRICT',
                          ondelete='RESTRICT'),
               nullable=False),
        Column('instrument', Integer, nullable=False),
        Column('ancillary', Integer, nullable=False),
        Column('weather', Integer, nullable=False),
        Column('time', Float, nullable=False),
        UniqueConstraint('proposal_id', 'instrument', 'ancillary', 'weather'),
    ]


jcmt_allocation = Table(
    'jcmt_allocation',
    metadata,
    Column('id', Integer, primary_key=True),
    *_request_cols(),
    **table_opts)

jcmt_available = Table(
    'jcmt_available',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('call_id', None,
           ForeignKey('call.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           nullable=False),
    Column('weather', Integer, nullable=False),
    Column('time', Float, nullable=False),
    UniqueConstraint('call_id', 'weather'),
    **table_opts)

jcmt_options = Table(
    'jcmt_options',
    metadata,
    Column('proposal_id', None,
           ForeignKey('proposal.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           primary_key=True, nullable=False),
    Column('target_of_opp', Boolean, nullable=False),
    Column('daytime', Boolean, nullable=False),
    Column('time_specific', Boolean, nullable=False),
    Column('polarimetry', Boolean, nullable=False),
    **table_opts)

jcmt_request = Table(
    'jcmt_request',
    metadata,
    Column('id', Integer, primary_key=True),
    *_request_cols(),
    **table_opts)

jcmt_review = Table(
    'jcmt_review',
    metadata,
    Column('reviewer_id', None,
           ForeignKey('reviewer.id', onupdate='RESTRICT', ondelete='RESTRICT'),
           primary_key=True, nullable=False),
    Column('expertise', Integer, nullable=True),
    # Detailed information for external reviews:
    Column('review_aims', UnicodeText, nullable=True),
    Column('review_goals', UnicodeText, nullable=True),
    Column('review_difficulties', UnicodeText, nullable=True),
    Column('rating_justification', Integer, nullable=True),
    Column('review_details', UnicodeText, nullable=True),
    Column('review_obj_inst', UnicodeText, nullable=True),
    Column('review_telescope', UnicodeText, nullable=True),
    Column('rating_technical', Integer, nullable=True),
    Column('rating_urgency', Integer, nullable=True),
    Column('review_format', Integer, nullable=True),
    **table_opts)
