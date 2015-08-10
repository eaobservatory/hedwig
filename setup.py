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

from distutils.core import setup
import os
import sys

sys.path.append('lib')
from hedwig.version import version

with open('README.rst') as f:
    long_description = f.read()

setup(
    name='hedwig',
    version=version,
    description='Hedwig proposal submission system',
    long_description=long_description,
    url='https://github.com/eaobservatory/hedwig',
    package_dir={'': 'lib'},
    packages=['.'.join(x[0].split(os.path.sep)[1:])
              for x in os.walk('lib') if '__init__.py' in x[2]],
    scripts=['scripts/hedwigctl'])
