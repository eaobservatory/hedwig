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

import functools
import re

from ..error import NoSuchRecord
from ..web.util import HTTPError, HTTPForbidden, HTTPNotFound
from . import auth


def count_words(text):
    """
    Counts the number of words in the given text.

    "text" can be a string, or any object with a "text" attribute, such as
    PropsalText.
    """

    if hasattr(text, 'text'):
        text = text.text

    return len(re.split('\s+', text))


def organise_collection(class_, updated_records, added_records):
    """
    Constuct new record collection, of the given class, from the
    list of "updated_records" (whose ids we should preserve) and
    the list of "added_records" (which should be assigned temporary
    ids beyond those of the "updated_records").

    "added_records" are assumed to have ids of at least 1, such
    that they can be added to the maximum record id found amongst
    the "updated_records".
    """

    records = class_(map((lambda x: (x, updated_records[x])),
                         sorted(updated_records.keys())))

    # Number the newly-added records upwards from the existing max.
    max_record = max(records.keys()) if records else 0

    for id_ in sorted(added_records.keys()):
        new_id = max_record + id_
        records[new_id] = added_records[id_]._replace(id=new_id)

    return records


def with_proposal(permission):
    """
    Decorator for methods which deal with proposals.

    Assumes that the first arguments are a database object and proposal ID.
    Then checks that the current user has the requested permission.
    The wrapped method is then called with the database,  proposal and
    authorization objects as the first two arguments.

    "permission" should be one of: "view", "edit" or "none".

    Note: this currently can only be used to decorate methods of
    facility classes because it uses self.id_ for the facility ID.
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_method(self, db, proposal_id, *args, **kwargs):
            try:
                proposal = db.get_proposal(self.id_, proposal_id,
                                           with_members=True)
            except NoSuchRecord:
                raise HTTPNotFound('Proposal not found')

            assert proposal.id == proposal_id

            can = auth.for_proposal(db, proposal)

            if permission == 'view':
                if not can.view:
                    raise HTTPForbidden('Permission denied for this proposal.')

            elif permission == 'edit':
                if not can.edit:
                    raise HTTPForbidden(
                        'Edit permission denied for this proposal.  '
                        'Either you are not listed as an editor, '
                        'or the proposal deadline has passed.')

            elif permission =='none':
                # Do not perform any permission check.
                pass

            else:
                raise HTTPError('Unknown permission type.')

            return f(self, db, proposal, can, *args, **kwargs)

        return decorated_method

    return decorator


def with_verified_admin(f):
    """
    Method decorator which double-checks administrative access.

    Assumes that the method takes the database control object as
    its first positional argument.
    """

    @functools.wraps(f)
    def decorated(self, db, *args, **kwargs):
        if not auth.can_be_admin(db):
            raise HTTPForbidden('Could not verify administrative access.')

        return f(self, db, *args, **kwargs)

    return decorated


def parse_time(input_time):
    """
    Accepts a time string, either as a decimal number of hours,
    or as hours:minutes:seconds, and returns a float in hours.
    """

    if ':' in input_time:
        input_time_part = input_time.split(':', 2)

        return (
            int(input_time_part[0]) +
            (int(input_time_part[1]) / 60.0) +
            (float(
                input_time_part[2] if len(input_time_part) > 2
                else 0.0)) / 3600.0)
    else:
        return float(input_time)
