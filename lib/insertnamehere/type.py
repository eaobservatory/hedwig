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

from .db.meta import email, institution, member, person, proposal

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
    map(lambda x: x.name, person.columns) + ['email', 'institution'])

Proposal = namedtuple(
    'Proposal',
    map(lambda x: x.name, proposal.columns) + ['member'])


class EmailCollection(OrderedDict):
    def get_primary(self):
        for email in self.values():
            if email.primary:
                return email

        raise KeyError('no primary address')


class MemberCollection(OrderedDict):
    def get_pi(self):
        for member in self.values():
            if member.pi:
                return member

        raise KeyError('no pi member')
