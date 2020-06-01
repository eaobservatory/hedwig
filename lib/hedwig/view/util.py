# Copyright (C) 2015-2019 East Asian Observatory
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
from ..type.enum import PermissionType
from ..web.util import HTTPError, HTTPForbidden, HTTPNotFound
from ..type.util import with_cache
from . import auth


def count_words(text):
    """
    Counts the number of words in the given text.

    "text" can be a string, or any object with a "text" attribute, such as
    PropsalText.
    """

    if hasattr(text, 'text'):
        text = text.text

    return len(re.split(r'\s+', text))


def float_or_none(value):
    """
    Converts the given string to a float, or returns None if
    it is empty.

    Intended for parsing form selection values where there is
    an undefined value.
    """

    return None if (value == '') else float(value)


def int_or_none(value):
    """
    Converts the given string to an integer, or returns None if
    it is empty.

    Intended for parsing form selection values where there is
    an undefined value.
    """

    return None if (value == '') else int(value)


def str_or_none(value):
    """
    Returns the given string as is, unless it is empty, in
    which case None is returned.
    """

    return None if (value == '') else value


def join_list(words, conjunction='and'):
    """
    Join the words in the given list with commas, ending the list
    with the given conjunction and final word.
    """

    if not words:
        return ''

    if len(words) == 1:
        return words[0]

    return '{} {} {}'.format(
        ', '.join(words[:-1]),
        conjunction,
        words[-1])


def with_call_review(permission):
    """
    Decorator for methods which deal with reviews of all the proposals
    for a given call.

    Assumes that the first arguents are a database object and call ID.
    The wrapped method is called with the database, call record and
    authorization object followed by any remaining arguments.

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

            if permission == PermissionType.VIEW:
                if not can.view:
                    raise HTTPForbidden('Permission denied for this call.')

            elif permission == PermissionType.EDIT:
                if not can.edit:
                    raise HTTPForbidden(
                        'Edit permission denied for this call.')

            else:
                raise HTTPError('Unknown permission type.')

            return f(self, db, call, with_cache(can, auth_cache),
                     *args, **kwargs)

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

            auth_cache = {}
            can = auth.for_institution(db, institution, auth_cache=auth_cache)

            if permission == PermissionType.VIEW:
                if not can.view:
                    raise HTTPForbidden(
                        'Permission denied for this institution.')

            elif permission == PermissionType.EDIT:
                if not can.edit:
                    raise HTTPForbidden(
                        'Edit permission denied for this institution.')

            else:
                raise HTTPError('Unknown permission type.')

            return f(self, db, institution, with_cache(can, auth_cache),
                     *args, **kwargs)

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

            if permission == PermissionType.NONE:
                return f(self, db, person, *args, **kwargs)

            elif permission == PermissionType.UNIVERSAL_VIEW:
                auth_cache = {}
                can = auth.for_person(db, None, auth_cache=auth_cache)

                if not can.view:
                    raise HTTPForbidden(
                        'Permission denied for person profiles.')

                return f(self, db, person, with_cache(can, auth_cache),
                         *args, **kwargs)

            else:
                auth_cache = {}
                can = auth.for_person(db, person, auth_cache=auth_cache)

                if permission == PermissionType.VIEW:
                    if not can.view:
                        raise HTTPForbidden(
                            'Permission denied for this person profile.')

                elif permission == PermissionType.EDIT:
                    if not can.edit:
                        raise HTTPForbidden(
                            'Edit permission denied for this person profile.')

                else:
                    raise HTTPError('Unknown permission type.')

                return f(self, db, person, with_cache(can, auth_cache),
                         *args, **kwargs)

        return decorated_method

    return decorator


def with_proposal(
        permission, indirect_facility=False,
        allow_unaccepted_review=None,
        **get_proposal_kwargs):
    """
    Decorator for methods which deal with proposals.

    Assumes that the first arguments are a database object and proposal ID.
    Then checks that the current user has the requested permission.
    The wrapped method is then called with the database, proposal and
    authorization objects as the first three arguments.

    "permission" should be one of: "VIEW", "EDIT", "FEEDBACK" or "NONE".

    * When "FEEDBACK" is selected, view authorization to the proposal
      feedback is required.

    * When "NONE" is selected, no authorization object is passed on.

    The `allow_unaccepted_review` argument is passed on to `auth.for_proposal`.

    Additional keyword arguments are passed to the get_proposal database
    method.

    Note: this currently can only be used to decorate methods of
    facility classes because it uses `self.id_` for the facility ID.
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_method(self, db, proposal_id, *args, **kwargs):
            facility = (self.facility if indirect_facility else self)
            role_class = facility.get_reviewer_roles()
            auth_cache = {}

            try:
                proposal = db.get_proposal(facility.id_, proposal_id,
                                           with_members=True,
                                           with_reviewers=True,
                                           **get_proposal_kwargs)
            except NoSuchRecord:
                raise HTTPNotFound('Proposal not found')

            assert proposal.id == proposal_id

            if permission == PermissionType.NONE:
                return f(self, db, proposal, *args, **kwargs)

            elif permission == PermissionType.FEEDBACK:
                can = auth.for_proposal_feedback(role_class, db, proposal,
                                                 auth_cache=auth_cache)

                if not can.view:
                    raise HTTPForbidden(
                        'Permission denied for this proposal feedback.')

                return f(self, db, proposal, with_cache(can, auth_cache),
                         *args, **kwargs)

            else:
                can = auth.for_proposal(
                    role_class, db, proposal,
                    auth_cache=auth_cache,
                    allow_unaccepted_review=allow_unaccepted_review)

                if permission == PermissionType.VIEW:
                    if not can.view:
                        raise HTTPForbidden(
                            'Permission denied for this proposal.')

                elif permission == PermissionType.EDIT:
                    if not can.edit:
                        raise HTTPForbidden(
                            'Edit permission denied for this proposal.  '
                            'Either you are not listed as an editor, '
                            'or the proposal deadline has passed.')

                else:
                    raise HTTPError('Unknown permission type.')

                return f(self, db, proposal, with_cache(can, auth_cache),
                         *args, **kwargs)

        return decorated_method

    return decorator


def with_review(
        permission, with_invitation=False, allow_unaccepted=None,
        **get_proposal_kwargs):
    """
    Decorator for methods which deal with reviews of proposals.

    Assumes that the first arguents are a database object and reviewer ID.
    The wrapped method is called with the database, reviewer record,
    proposal record and authorization object followed by any remaining
    arguments.

    The `allow_unaccepted` argument is passed on to `auth.for_review`.

    Additional keyword arguments are passed to the get_proposal database
    method.
    """

    def decorator(f):
        @functools.wraps(f)
        def decorated_method(self, db, reviewer_id, *args, **kwargs):
            role_class = self.get_reviewer_roles()

            try:
                reviewer = db.search_reviewer(
                    reviewer_id=reviewer_id,
                    with_review=True, with_review_text=True,
                    with_review_note=True, with_invitation=with_invitation
                ).get_single()
            except NoSuchRecord:
                raise HTTPNotFound('Reviewer record not found')

            assert reviewer.id == reviewer_id

            proposal_id = reviewer.proposal_id

            # Apply facility constraint here -- the proposal will only
            # be found if its facility is self.id_.
            try:
                proposal = db.get_proposal(self.id_, proposal_id,
                                           with_members=True,
                                           **get_proposal_kwargs)
            except NoSuchRecord:
                raise HTTPNotFound('Proposal record not found')

            assert proposal.id == proposal_id

            if permission == PermissionType.NONE:
                return f(self, db, reviewer, proposal, *args, **kwargs)

            else:
                auth_cache = {}
                can = auth.for_review(
                    role_class, db, reviewer, proposal,
                    auth_cache=auth_cache, allow_unaccepted=allow_unaccepted)

                if permission == PermissionType.VIEW:
                    if not can.view:
                        raise HTTPForbidden(
                            'Permission denied for this review.')

                elif permission == PermissionType.EDIT:
                    if not can.edit:
                        raise HTTPForbidden(
                            'Edit permission denied for this review.')

                else:
                    raise HTTPError('Unknown permission type.')

                return f(self, db, reviewer, proposal,
                         with_cache(can, auth_cache), *args, **kwargs)

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
