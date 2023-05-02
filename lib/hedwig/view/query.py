# Copyright (C) 2015-2023 East Asian Observatory
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

import json

import requests

from ..compat import str_to_unicode
from ..config import get_countries
from ..web.util import HTTPError


class QueryView(object):
    cadc_name_resolver = \
        'https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/cadc-target-resolver/find'

    fixed_name_responses = {}

    def __init__(self):
        # Prepare JSON version of the country list.
        self.country_list_json = json.dumps([
            {
                'value': code,
                'text': name,
            }
            for (code, name) in get_countries().items()
        ])

    def get_country_list(self):
        return self.country_list_json

    def get_institution_list(self, db):
        countries = get_countries()
        institutions = []

        for institution in db.search_institution().values():
            text = truncate(institution.name, 25)
            if institution.department:
                text += ', ' + truncate(institution.department, 15)
            if institution.organization:
                text += ', ' + truncate(institution.organization, 15)
            if institution.country:
                text += ', ' + truncate(
                    countries.get(institution.country, 'Unknown country'), 15)

            institutions.append({
                'value': institution.id,
                'text': text,
            })

        return institutions

    @classmethod
    def add_fixed_name_response(
            cls, target, response, format_='json',
            type_='application/json;charset=ISO-8859-1'):
        cls.fixed_name_responses[(target, format_)] = (response, type_, None)

    def resolve_name(self, args):
        """
        Simple proxy for the CADC name resolver service.

        Ideally CADC's service would support HTTPS and CORS so that our
        JavaScript code could access it directly.
        """

        fixed_response = self.fixed_name_responses.get(
            (args.get('target'), args.get('format')))

        if fixed_response is not None:
            return fixed_response

        try:
            r = requests.get(self.cadc_name_resolver, params=args, timeout=15)

            r.raise_for_status()

            return (r.content, str_to_unicode(r.headers['Content-Type']), None)

        except requests.exceptions.RequestException:
            raise HTTPError('Failed to resolve name via CADC.')


def truncate(value, length):
    if value is None:
        return ''

    if len(value) <= length:
        return value

    return value[:length] + '\u2026'
