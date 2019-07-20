# Copyright (C) 2019 East Asian Observatory
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

from collections import defaultdict
from statistics import mean, pstdev


def table_mean_stdev(table, rows, columns, scale_factor=1.0):
    row_values = defaultdict(list)
    column_values = defaultdict(list)

    for row_id in rows.keys():
        row = table.get(row_id)
        if row is None:
            continue
        for column_id in columns.keys():
            value = row.get(column_id)
            if value is None:
                continue
            value *= scale_factor
            row_values[row_id].append(value)
            column_values[column_id].append(value)

    row_mean = {}
    row_stdev = {}
    column_mean = {}
    column_stdev = {}

    for (row_id, row) in row_values.items():
        row_mean[row_id] = this_row_mean = mean(row)
        row_stdev[row_id] = pstdev(row, this_row_mean)

    for (column_id, column) in column_values.items():
        column_mean[column_id] = this_column_mean = mean(column)
        column_stdev[column_id] = pstdev(column, this_column_mean)

    return (row_mean, row_stdev, column_mean, column_stdev)
