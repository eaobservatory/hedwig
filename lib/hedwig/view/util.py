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


def with_call_review(permission):
    """
    Decorator for methods which deal with reviews of all the proposals
    for a given call.

    Assumes that the first arguents are a database object and call ID.
    The wrapped method is called with the database, call record,
    authorization object and authorization cache followed by any remaining
    arguments.

    Note: this currently can only be used to decorate methods of
    facility classes because it uses `self.id_` for the facility ID.
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_method(self, db, call_id, *args, **kwargs):
            try:
                call = db.get_call(facility_id=self.id_, call_id=call_id)
            except NoSuchRecord:
                raise HTTPNotFound('Call not found')

            assert call.id == call_id

            auth_cache = {}
            can = auth.for_call_review(db, call, auth_cache=auth_cache)

            if permission == 'view':
                if not can.view:
                    raise HTTPForbidden('Permission denied for this call.')

            elif permission == 'edit':
                if not can.edit:
                    raise HTTPForbidden(
                        'Edit permission denied for this call.')

            else:
                raise HTTPError('Unknown permission type.')

            return f(self, db, call, can, auth_cache, *args, **kwargs)

        return decorated_method

    return decorator


def with_institution(permission):
    """
    Decorator for methods which deal with institution records.

    Assumes that the first arguments are a database object and institution ID.
    Checks that the uesr has the requested permission and then calls the
    wrapped method with the database, institution and authorization
    object as the first arguments.
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_method(self, db, institution_id, *args, **kwargs):
            try:
                institution = db.get_institution(institution_id)
            except NoSuchRecord:
                raise HTTPNotFound('Institution not found.')

            assert institution.id == institution_id

            can = auth.for_institution(db, institution)

            if permission == 'view':
                if not can.view:
                    raise HTTPForbidden(
                        'Permission denied for this institution.')

            elif permission == 'edit':
                if not can.edit:
                    raise HTTPForbidden(
                        'Edit permission denied for this institution.')

            else:
                raise HTTPError('Unknown permission type.')

            return f(self, db, institution, can, *args, **kwargs)

        return decorated_method

    return decorator


def with_person(permission):
    """
    Decorator for methods which deal with personal profiles.

    Assumes that the first arguments are a database object and person ID.
    Checks that the user has the requested permission and then calls the
    wwrapped method with the database, proposal and authorization
    object as the first arguments.
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_method(self, db, person_id, *args, **kwargs):
            try:
                person = db.get_person(person_id=person_id,
                                       with_institution=True, with_email=True)
            except NoSuchRecord:
                raise HTTPNotFound('Person profile not found.')

            assert person.id == person_id

            if permission == 'none':
                return f(self, db, person, *args, **kwargs)

            else:
                can = auth.for_person(db, person)

                if permission == 'view':
                    if not can.view:
                        raise HTTPForbidden(
                            'Permission denied for this person profile.')

                elif permission == 'edit':
                    if not can.edit:
                        raise HTTPForbidden(
                            'Edit permission denied for this person profile.')

                else:
                    raise HTTPError('Unknown permission type.')

            return f(self, db, person, can, *args, **kwargs)

        return decorated_method

    return decorator


def with_proposal(permission):
    """
    Decorator for methods which deal with proposals.

    Assumes that the first arguments are a database object and proposal ID.
    Then checks that the current user has the requested permission.
    The wrapped method is then called with the database,  proposal and
    authorization objects as the first two arguments.

    "permission" should be one of: "view", "edit", "feedback" or "none".

    * When "feedback" is selected, view authorization to the proposal
      feedback is required.  No authorization object is passed to the
      decorated method, since there is currently no concept of
      editable feedback.

    * When "none" is selected, no authorization object is passed on.

    Note: this currently can only be used to decorate methods of
    facility classes because it uses `self.id_` for the facility ID.
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_method(self, db, proposal_id, *args, **kwargs):
            try:
                proposal = db.get_proposal(self.id_, proposal_id,
                                           with_members=True,
                                           with_reviewers=True)
            except NoSuchRecord:
                raise HTTPNotFound('Proposal not found')

            assert proposal.id == proposal_id

            if permission == 'none':
                return f(self, db, proposal, *args, **kwargs)

            elif permission == 'feedback':
                can = auth.for_proposal_feedback(db, proposal)

                if not can.view:
                    raise HTTPForbidden(
                        'Permission denied for this proposal feedback.')

                return f(self, db, proposal, *args, **kwargs)

            else:
                can = auth.for_proposal(db, proposal)

                if permission == 'view':
                    if not can.view:
                        raise HTTPForbidden(
                            'Permission denied for this proposal.')

                elif permission == 'edit':
                    if not can.edit:
                        raise HTTPForbidden(
                            'Edit permission denied for this proposal.  '
                            'Either you are not listed as an editor, '
                            'or the proposal deadline has passed.')

                else:
                    raise HTTPError('Unknown permission type.')

                return f(self, db, proposal, can, *args, **kwargs)

        return decorated_method

    return decorator


def with_review(permission):
    """
    Decorator for methods which deal with reviews of proposals.

    Assumes that the first arguents are a database object and reviewer ID.
    The wrapped method is called with the database, reviewer record,
    proposal record and authorization object followed by any remaining
    arguments.
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_method(self, db, reviewer_id, *args, **kwargs):
            try:
                reviewer = db.search_reviewer(
                    reviewer_id=reviewer_id,
                    with_review=True, with_review_text=True,
                    with_review_note=True).get_single()
            except NoSuchRecord:
                raise HTTPNotFound('Reviewer record not found')

            assert reviewer.id == reviewer_id

            proposal_id = reviewer.proposal_id

            # Apply facility constraint here -- the proposal will only
            # be found if its facility is self.id_.
            try:
                proposal = db.get_proposal(self.id_, proposal_id,
                                           with_members=True)
            except NoSuchRecord:
                raise HTTPNotFound('Proposal record not found')

            assert proposal.id == proposal_id

            can = auth.for_review(db, reviewer, proposal)

            if permission == 'view':
                if not can.view:
                    raise HTTPForbidden('Permission denied for this review.')

            elif permission == 'edit':
                if not can.edit:
                    raise HTTPForbidden(
                        'Edit permission denied for this review.')

            else:
                raise HTTPError('Unknown permission type.')

            return f(self, db, reviewer, proposal, can, *args, **kwargs)

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
