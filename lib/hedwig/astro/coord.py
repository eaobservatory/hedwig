# Copyright (C) 2015-2024 East Asian Observatory
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

from astropy import coordinates
from astropy.units import degree, hourangle, UnitsError

from ..error import UserError


class CoordSystem(object):
    """
    Coordinate system enumeration class.
    """

    ICRS = 1
    GAL = 2

    SystemInfo = namedtuple('SystemInfo',
                            ('name', 'frame', 'unit', 'decimal'))

    _info = OrderedDict((
        (ICRS, SystemInfo('ICRS',     coordinates.ICRS,
                          (hourangle, degree), False)),
        (GAL,  SystemInfo('Galactic', coordinates.Galactic,
                          (degree,    degree), True))
    ))

    @classmethod
    def is_valid(cls, system):
        """
        Determine whether a coordinate system number is part of this
        enumeration.
        """

        return system in cls._info

    @classmethod
    def get_options(cls):
        """
        Returns an OrderedDict of names by system number.
        """

        return OrderedDict([(s, i.name) for (s, i) in cls._info.items()])

    @classmethod
    def get_name(cls, system):
        """
        Get the displayable name of a coordinate system.
        """

        if system is None:
            return 'None'

        return cls._info[system].name

    @classmethod
    def _get_info(cls, system):
        """
        Get the information tuple for a coordinate system.

        This is a semi-private method -- only the functions in this
        module ought to use it as the details of the tuple can change.
        """

        return cls._info[system]


def parse_coord(system, x, y, name):
    """
    Parse coordinate information (strings) as entered by a user
    and return an astropy SkyCoord object.

    The target name is taken just for use in error messages: parsing
    errors are raised as UserError and include the target name to help
    the user track down the problem.
    """

    # Check the coordinate system is valid and get its information.
    try:
        info = CoordSystem._get_info(system)
    except KeyError:
        raise UserError('Coordinate system for "{}" not recognized.', name)

    # If 'x' or 'y' looks like a plain floating point number, consider it
    # to be degrees.
    try:
        x = float(x) * degree
    except ValueError:
        pass

    try:
        y = float(y) * degree
    except ValueError:
        pass

    # Finally create the coordinate object.
    try:
        return coordinates.SkyCoord(x, y, unit=info.unit, frame=info.frame)
    except coordinates.RangeError as e:
        raise UserError(
            'Could not parse coordinates for "{}": {!s} (range error)',
            name, e)
    except ValueError as e:
        raise UserError(
            'Could not parse coordinates for "{}": {!s} (value error)',
            name, e)
    except UnitsError as e:
        raise UserError(
            'Could not parse coordinates for "{}": {!s} (units error)',
            name, e)
    except Exception as e:
        raise UserError(
            'Could not parse coordinates for "{}": {!s} (unexpected error)',
            name, e)


def format_coord(system, coord):
    """
    Format coordinates for display.
    """

    info = CoordSystem._get_info(system)
    assert isinstance(coord.frame, info.frame)

    sph = coord.spherical

    kwargs = {'pad': True}

    if info.decimal:
        kwargs['decimal'] = True
    else:
        kwargs['sep'] = ':'

    return (sph.lon.to_string(unit=info.unit[0], alwayssign=False, **kwargs),
            sph.lat.to_string(unit=info.unit[1], alwayssign=True, **kwargs))


def coord_to_dec_deg(coord):
    """
    Convert a coordinate to a pair of floating point numbers in degrees.
    """

    return (coord.spherical.lon.deg, coord.spherical.lat.deg)


def coord_from_dec_deg(system, x_deg, y_deg):
    """
    Convert a pair of numbers in degress back to a coordinate object.
    """

    info = CoordSystem._get_info(system)

    return coordinates.SkyCoord(x_deg, y_deg, unit=degree, frame=info.frame)


def concatenate_coord_objects(objects):
    """
    Convert a list of `TargetObject` instances to a single coordinate object.
    """

    # Concatenate manually rather than astropy.coordinates.concatenate
    # for improved performance.
    target_ra = []
    target_dec = []
    for object_ in objects:
        object_ = object_.coord.icrs
        target_ra.append(object_.ra.degree)
        target_dec.append(object_.dec.degree)

    return coordinates.SkyCoord(
        target_ra, target_dec, unit=degree, frame=coordinates.ICRS)
