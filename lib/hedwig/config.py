# Copyright (C) 2014 Science and Technology Facilities Council.
# Copyright (C) 2015-2017 East Asian Observatory.
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

from collections import OrderedDict
from importlib import import_module
import os

try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser as ConfigParser

import pycountry

from .compat import make_type
from .error import FormattedError
from .db.engine import get_engine

config_file = ('etc', 'hedwig.ini')
config = None
countries = None
database = None
facilities = None
home_directory = None


def get_config():
    """
    Read the configuration file.

    Returns a ConfigParser object.
    """

    global config

    if config is None:
        dir = get_home()
        file = os.path.join(dir, *config_file)

        if not os.path.exists(file):
            raise FormattedError('config file {} doesn\'t exist', file)

        config = ConfigParser()
        config.read(file)

    return config


def get_countries():
    """
    Get ordered dictionary of 2-letter country codes mapping to
    country names.  This is sorted by country name.
    """

    global countries

    if countries is None:
        # Read country name overrides from the configuration file.
        override = dict(get_config().items('countries'))

        items = []

        for country in pycountry.countries:
            code = country.alpha2
            name = override.get(code.lower())
            if name is None:
                # Try to get the "common_name" if it exists, otherwise use the
                # normal "name" field.
                name = getattr(country, 'common_name', country.name)
            items.append((code, name))

        items.sort(key=lambda x: x[1])

        countries = OrderedDict(items)

    return countries


def get_database(database_url=None, facility_spec=None):
    """
    Construct a database control object.

    The database URL and facility specifier text (comma-separated string)
    can be given for testing -- otherwise they are read from the configuration.
    """

    global database

    if database is None or facility_spec is not None:
        config = get_config()

        if database_url is None:
            database_url = config.get('database', 'url')

        engine_options = {}

        if not database_url.startswith('sqlite'):
            engine_options.update({
                'pool_size': 15,
                'max_overflow': 5,
            })

            if config.get('database', 'pool_size'):
                engine_options['pool_size'] = int(config.get(
                    'database', 'pool_size'))
            if config.get('database', 'pool_overflow'):
                engine_options['max_overflow'] = int(config.get(
                    'database', 'pool_overflow'))

        CombinedDatabase = _get_db_class(facility_spec)
        database = CombinedDatabase(get_engine(database_url, **engine_options))

    return database


def _get_db_class(facility_spec):
    """
    Create a combined database class for the given facilities.
    """

    # Defer import of database modules to avoid circular imports
    # when database modules import from this module.
    from .db.control import Database

    db_parts = []

    if facility_spec is None:
        facility_spec = get_config().get('application', 'facilities')

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
                    'hedwig.facility.{}.meta'.format(name.lower()))
                module = import_module(
                    'hedwig.facility.{}.control'.format(name.lower()))

            # Look for a class named <Facility>Part.
            db_parts.append(getattr(module, parts[-1] + 'Part'))

        except ImportError:
            # Not all facilities will define custom metadata and control
            # modules.
            pass

    # Create combined database object using the base database class, plus
    # any facility-specific classes.  Put the base class last so that
    # facilities can override methods if necessary.
    db_parts.append(Database)
    return make_type('CombinedDatabase', tuple(db_parts), {})


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
            facilities.append(_import_class(name, 'hedwig.facility.{}.view'))

    return facilities


def get_home():
    """
    Determine the application's home directory.
    """

    global home_directory

    if home_directory is not None:
        return home_directory

    return os.environ.get('HEDWIG_DIR', os.getcwd())


def set_home(directory):
    """
    Set the application's home directory.

    This will alter the value returned in subsequent calls to get_home.
    """

    global home_directory

    home_directory = directory


def _import_class(class_name, module_pattern, class_pattern=None):
    """
    Import the given class.

    The class can either be fully specified (full module name, a dot,
    and class name), or the name of a class installed as part of Hedwig.
    In the latter case, the module_pattern argument is used to generate
    the module name (using the lower-case version of the class name)
    and the class_pattern (if given) is used to generate the class name.
    """

    try:
        last_dot = class_name.rindex('.')
    except ValueError:
        last_dot = None

    if last_dot is not None:
        module = import_module(class_name[:last_dot])
        class_ = getattr(module, class_name[last_dot + 1:])

    else:
        # If there were no dots in the class name guess that the module
        # is in the expected directory and has a lower case name.
        module = import_module(module_pattern.format(class_name.lower()))

        if class_pattern is None:
            full_class_name = class_name

        else:
            full_class_name = class_pattern.format(class_name)

        class_ = getattr(module, full_class_name)

    return class_
