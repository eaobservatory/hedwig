# Copyright (C) 2018-2023 East Asian Observatory
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

import re

# Basic email address validation pattern, based on the dot-atom "@" dot-atom
# form given in RFC2822.
# Note: atext is all printable ASCII except space and specials: ()<>[]:;@\,."
_atext = r'[-A-Za-z0-9!#$%&\'*+/=?^_`{|}~]'
_dot_atom_text = _atext + r'+(\.' + _atext + r'+)*'
valid_email_address = re.compile(
    r'^' + _dot_atom_text + r'@' + _dot_atom_text + r'$')


def is_valid_email(address):
    return True if valid_email_address.search(address) else False
