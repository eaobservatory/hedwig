# Copyright (C) 2016-2020 East Asian Observatory.
# All Rights Reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, division, print_function, \
    unicode_literals

import logging

from flask import request as _flask_request
from flask_weasyprint import HTML as FWP_HTML, make_url_fetcher
from weasyprint import HTML as WP_HTML, CSS

from ..error import FormattedError
from ..web.util import parse_multipart_response
from .flask import PDFWriterFlask

# Suppress warnings from weasyprint (e.g. those about CSS properties which
# it does not recognize).
logging.getLogger('weasyprint').setLevel(logging.ERROR)


class PDFWriterWeasyPrint(PDFWriterFlask):
    def _request_pdf(self, url, person_id=None, section=False):
        # Set up request environment.
        session_extra = {
            'pdf_as_svg': True,
        }

        if section:
            session_extra['allow_section'] = True

        environ = self._prepare_environ(
            session_extra=session_extra)

        # Set up additional stylesheets.
        stylesheets = []
        stylesheets.append(CSS(string='@page {size: letter;}'))

        # Perform the request to generate the PDF using WeasyPrint.
        with self._fixed_auth(person_id), self.app.request_context(environ):
            if not section:
                return FWP_HTML(url).write_pdf(stylesheets=stylesheets)

            # When processing a page in sections, we need to not use the
            # Flask-WeasyPrint wrapper layer so that we can check the MIME
            # type of each section to decide whether to process it with
            # WeasyPrint or output it directly.
            pdfs = []
            base_url = _flask_request.url
            url_fetcher = make_url_fetcher()

            response = url_fetcher(
                '{}{}/section'.format(base_url, url))

            for (mime_type, data) in parse_multipart_response(
                    response['string']):
                if mime_type == 'application/pdf':
                    pdfs.append(data)

                elif mime_type == 'text/html':
                    pdfs.append(
                        WP_HTML(
                            string=data,
                            base_url=base_url,
                            url_fetcher=url_fetcher
                        ).write_pdf(stylesheets=stylesheets))

                else:
                    raise FormattedError(
                        'Section request returned unexpected MIME type {}',
                        mime_type)

            return pdfs
