# Copyright (C) 2024 East Asian Observatory
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

import sqlalchemy

from ..compat import split_version

sqlalchemy_version = split_version(sqlalchemy.__version__)


if sqlalchemy_version < (1, 4):
    from sqlalchemy.sql import select
    from sqlalchemy.sql.expression import case

    def scalar_subquery(select):
        """
        In newer SQLAlchemy apply the `scalar_subquery` method of a selectable.

        This implementation does nothing, for versions pre-dating the
        introduction of this method.
        """

        return select

    def row_as_dict(row):
        """
        Convert a row to a dictionary which can be modified.

        Constructs the dictionary using the row's `items` method.
        """

        return dict(row.items())

    def row_as_mapping(row):
        """
        Convert the row to a form suitable for use as function `**kwargs`.

        This implementation does nothing, as the row itself can be used.
        """

        return row

else:
    from sqlalchemy.sql import select as _sqlalchemy_select
    from sqlalchemy.sql.expression import case as _sqlalchemy_case

    def select(columns):
        """
        Wrapper for the new version of the `select` function.

        .. note::
            The software should be updated to use the new syntax,
            with the version < 1.4 case providing a wrapper instead.
        """

        assert isinstance(columns, list)
        return _sqlalchemy_select(*columns)

    def case(whens, else_):
        """
        Wrapper for the new version of the `case` function.

        .. note::
            The software should be updated to use the new syntax,
            with the version < 1.4 case providing a wrapper instead.
        """

        assert isinstance(whens, list)
        return _sqlalchemy_case(*whens, else_=else_)

    def scalar_subquery(select):
        """
        Applies the `scalar_subquery` method of a selectable.
        """

        return select.scalar_subquery()

    def row_as_dict(row):
        """
        Convert a row to a dictionary which can be modified.

        This implementation simply calls the row's `_asdict` method.
        """

        return row._asdict()

    def row_as_mapping(row):
        """
        Convert the row to a form suitable for use as function `**kwargs`.

        This uses the row's `_mapping` attribute.
        """

        return row._mapping
