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

from .db.meta import email, institution, member, person, proposal, queue, \
    semester
from .error import NoSuchRecord, MultipleRecords, UserError

Email = namedtuple(
    'Email',
    map(lambda x: x.name, email.columns))

Institution = namedtuple(
    'Institution',
    map(lambda x: x.name, institution.columns))

InstitutionInfo = namedtuple(
    'InstitutionInfo',
    ['id', 'name'])

Member = namedtuple(
    'Member',
    map(lambda x: x.name, member.columns))

Person = namedtuple(
    'Person',
    map(lambda x: x.name, person.columns) +
    ['email', 'institution', 'proposals'])

Proposal = namedtuple(
    'Proposal',
    map(lambda x: x.name, proposal.columns) + ['members'])

Semester = namedtuple(
    'Semester',
    map(lambda x: x.name, semester.columns))

Queue = namedtuple(
    'Queue',
    map(lambda x: x.name, queue.columns))


class ResultCollection(OrderedDict):
    def get_single(self):
        n = len(self)
        if n == 0:
            raise NoSuchRecord('can not get single record: no results')
        elif n > 1:
            raise MultipleRecords('can not get single record: many results')
        else:
            # WARNING: Python-2 only.
            return self.values()[0]


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
