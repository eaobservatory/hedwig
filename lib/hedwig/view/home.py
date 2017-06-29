# Copyright (C) 2015-2017 East Asian Observatory
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

from ..config import get_config
from ..web.util import session


class HomeView(object):
    def home(self, facilities):
        return {
            'facilities': facilities,
            'show_admin_links': session.get('is_admin', False),
        }

    def contact_page(self):
        # NB: shares email address with the one used in the email footer.
        # If this is not OK they could have separate configuration entries.
        email = get_config().get('email', 'footer_email')

        return {
            'title': 'Contact Us',
            'email_address': email,
        }
