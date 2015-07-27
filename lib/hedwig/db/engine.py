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

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from os import getpid

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool
from sqlalchemy.exc import DisconnectionError


@event.listens_for(Engine, 'connect')
def engine_connect(dbapi_connection, connection_record):
    """
    Listener for engine connections.

    * Enable foreign key constraints if the engine is SQLite.
    * Record the associated PID.
    """

    connection_record.info['pid'] = getpid()

    # Is there a better way to detect the engine type?
    if type(dbapi_connection).__module__.startswith('sqlite'):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@event.listens_for(Engine, 'checkout')
def engine_checkout(dbapi_connection, connection_record, connection_proxy):
    """
    Listener for engine check-outs.

    * Checks that we have the same PID as we did at connection time.

    (Based on the example in the "Connection Pooling" section of the
    SQLAlchemy documentation.)
    """

    if connection_record.info['pid'] != getpid():
        connection_record.connection = connection_proxy.connection = None
        raise DisconnectionError('Connection belongs to another PID')


@event.listens_for(Pool, 'checkout')
def pool_checkout(dbapi_connection, connection_record, connection_proxy):
    """
    Listener for pool check-outs.

    * Checks that the connection is alive.

    (Based on the pessimistic example in the "Connection Pooling" section
    of the SQLAlchemy documentation.)
    """

    cursor = dbapi_connection.cursor()

    try:
        cursor.execute('SELECT 1')

    except:
        raise DisconnectionError('Connection not responding')

    finally:
        try:
            cursor.close()
        except:
            pass


def get_engine(url, **kwargs):
    """Creates an SQLAchemmy database engine object for the given URL."""

    return create_engine(url, pool_recycle=3600,
                         echo=False, **kwargs)
