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
from itertools import groupby

from ..config import get_config
from ..error import NoSuchRecord
from ..type import ProposalWithCode
from ..web.util import HTTPNotFound, mangle_email_address


def prepare_home(application_name, facilities):
    return {
        'title': application_name,
        'facilities': facilities.values(),
    }


def prepare_dashboard(db, person_id, facilities, administrative=False):
    if administrative:
        try:
            person = db.get_person(person_id=person_id)
            title = '{}: Dashboard'.format(person.name)
        except NoSuchRecord:
            raise HTTPNotFound('Person not found.')
    else:
        person = None
        title = 'Personal Dashboard'

    proposals = db.search_proposal(person_id=person_id)

    facility_proposals = OrderedDict()

    for id_, ps in groupby(proposals.values(), lambda x: x.facility_id):
        facility = facilities[id_]
        facility_proposals[facility.name] = [
            ProposalWithCode(*p, code=facility.view.make_proposal_code(db, p),
                             facility_code=facility.code)
            for p in ps]

    return {
        'title': title,
        'proposals': facility_proposals,
        'person': person,
    }


def prepare_contact_page():
    # NB: shares email address with the one used in the email footer.
    # If this is not OK they could have separate configuration entries.
    email = get_config().get('email', 'footer_email')

    return {
        'title': 'Contact Us',
        'email_address': mangle_email_address(email),
    }
