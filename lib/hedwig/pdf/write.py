# Copyright (C) 2016-2023 East Asian Observatory.
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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from ..error import FormattedError


class PDFWriter(object):
    """
    Base class for Hedwig PDF writers.
    """

    def __init__(self, db, app, base_url, page_size):
        """
        Construct PDF writer object.
        """

        self.db = db
        self.app = app
        self.base_url = base_url
        self.page_size = page_size

    def proposal(self, proposal_id):
        """
        Request PDF representation of a proposal.

        Should be overridden by subclasses.
        """

        raise FormattedError('Not implemented')

    def reviews(self, proposal_id):
        """
        Request PDF representation of reviews of a proposal.

        Should be overridden by subclasses.
        """

        raise FormattedError('Not implemented')
