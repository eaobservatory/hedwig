# Copyright (C) 2014 Science and Technology Facilities Council.
# Copyright (C) 2015 East Asian Observatory.
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

from ConfigParser import SafeConfigParser
from importlib import import_module
import os

from .error import FormattedError
from .db.control import Database
from .db.engine import get_engine

config_file = ('etc', 'insertnamehere.ini')
config = None
database = None
facilities = None


def get_config():
    """
    Read the configuration file.

    Returns a SafeConfigParser object.
    """

    global config

    if config is None:
        dir = get_home()
        file = os.path.join(dir, *config_file)

        if not os.path.exists(file):
            raise FormattedError('config file {0} doesn\'t exist', file)

        config = SafeConfigParser()
        config.read(file)

    return config


def get_database(database_url=None, facility_spec=None):
    """
    Construct a database control object.

    The database URL and facility specifier text (comma-separated string)
    can be given for testing -- otherwise they are read from the configuration.
    """

    global database

    if database is None or facility_spec is not None:
        config = get_config()
        db_parts = [Database]

        if facility_spec is None:
            facility_spec = config.get('application', 'facilities')
        if database_url is None:
            database_url = config.get('database', 'url')

        # Import facility metadata and control modules.
        for name in facility_spec.split(','):
            try:
                parts = name.split('.')

                if len(parts) > 1:
                    # Try looking for "meta" and "control" modules in the same
                    # directory as the module which defines the facility class.
                    import_module('.'.join(parts[:-2] + ['meta']))
                    module = import_module('.'.join(parts[:-2] + ['control']))

                else:
                    # If there are no dots in the facility class, use the
                    # standard location in this packages.
                    import_module(
                        'insertnamehere.facility.{0}.meta'.format(
                            name.lower()))
                    module = import_module(
                        'insertnamehere.facility.{0}.control'.format(
                            name.lower()))

                # Look for a class named <Facility>Part.
                db_parts.append(getattr(module, parts[-1] + 'Part'))

            except ImportError:
                # Not all facilities will define custom metadata and control
                # modules.
                pass

        # Create combined database object using the base database class, plus
        # any facility-specific classes.
        CombinedDatabase = type(b'CombinedDatabase', tuple(db_parts), {})
        database = CombinedDatabase(get_engine(database_url))

    return database


def get_facilities(facility_spec=None):
    """
    Get a list of the facility classes as listed in the configuration file.

    The facility specifier text (comma-separated string) can be given for
    testing -- otherwise it is read from the configuration.
    """

    global facilities

    if facilities is None or facility_spec is not None:
        facilities = []

        if facility_spec is None:
            facility_spec = get_config().get('application', 'facilities')

        for name in facility_spec.split(','):
            try:
                last_dot = name.rindex('.')
                module = import_module(name[:last_dot])
                class_ = getattr(module, name[last_dot + 1:])
            except ValueError:
                # If there were no dots in the class name guess that the module
                # is in the expected directory and has a lower case name.
                module = import_module(
                    'insertnamehere.facility.{0}.view'.format(name.lower()))
                class_ = getattr(module, name)

            facilities.append(class_)

    return facilities


def get_home():
    """
    Determine the application's home directory.
    """

    env = os.environ
    return env.get('INSERTNAMEHERE_DIR', os.getcwd())
