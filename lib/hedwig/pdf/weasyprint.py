# Copyright (C) 2016 East Asian Observatory.
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

from flask_weasyprint import HTML

from .flask import PDFWriterFlask


class PDFWriterWeasyPrint(PDFWriterFlask):
    def _request_pdf(self, url, person_id=None):
        # Set up request environment.
        environ = self._prepare_environ(person_id)

        # Perform the request to generate the PDF using WeasyPrint.
        with self.app.request_context(environ):
            return HTML(url).write_pdf()
