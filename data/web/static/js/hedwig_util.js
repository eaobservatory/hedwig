function disable_futile_labels() {
    $('label').each(function () {
        var label = $(this);
        label.toggleClass('for_disabled',
            ! (label.nextAll('input:enabled, select:enabled').length > 0));
    });
}

function enable_table_sorting(table, alter_url) {
    var sort_headings = table.find('th.sortable');
    var table_body = table.find('tbody').first();
    var last_sorted_by = null;
    var sort_direction = -1;

    var reset_button = table.find('button[data-sort_reset]');

    var apply_sort_column = (function (sort_key) {
        var arr = [];
        var i;

        last_sorted_by = sort_key;

        table_body.children('tr').each(function () {
            arr.push({row: this, value: $(this).data('sortinfo')[sort_key]});
        });

        arr.sort(function (a, b) {
            if (a.value === b.value) {
                return 0;
            }
            if (a.value === null && b.value !== null) {
                return 1;
            }
            if (b.value === null && a.value !== null) {
                return -1;
            }
            return (sort_direction * (a.value < b.value ? -1 : 1));
        });

        for (i in arr) {
            table_body.append($(arr[i].row).detach());
        }

        sort_direction = - sort_direction;

        sort_headings.removeClass('sorted_asc').addClass('sortable');
        sort_headings.removeClass('sorted_desc').addClass('sortable');
        sort_headings.each(function () {
            var heading = $(this);
            if (heading.data('sortkey') === sort_key) {
                heading.removeClass('sortable').addClass((sort_direction < 0 ) ? 'sorted_asc' : 'sorted_desc');
            }
        });
    });

    var enable_sort_column = (function (heading) {
        var sort_key = heading.data('sortkey');
        var default_sort_order = 1;
        var sort_total = false;

        if (heading.hasClass('sortreverse')) {
            default_sort_order = -1;
        }

        if (heading.hasClass('sortedalready')) {
            last_sorted_by = sort_key;
        }

        if (heading.hasClass('sorttotal')) {
            sort_total = true;
        }

        heading.click(function () {
            if (sort_key !== last_sorted_by) {
                sort_direction = default_sort_order;
            }

            apply_sort_column(sort_key);

            reset_button.prop('disabled', false);

            if (alter_url) {
                var params = new URLSearchParams();
                if (! sort_total) {
                    var prevparams = new URLSearchParams(window.location.search);
                    prevparams.forEach(function (value, key) {
                        if (value !== sort_key) {
                            params.append(key, value);
                        }
                    });
                }
                params.append((sort_direction < 0 ? 'sortasc' : 'sortdesc'), sort_key);
                window.history.replaceState(
                    null, 'Sort by ' + sort_key + (sort_direction < 0 ? ' ascending' : ' descending)'),
                    window.location.pathname + '?' + params.toString());
            }
        });
    });

    if (reset_button.length === 1) {
        reset_button.click(function () {
            sort_direction = 1;

            var sort_key = reset_button.data('sort_reset');
            apply_sort_column(sort_key);

            reset_button.prop('disabled', true);

            if (alter_url) {
                window.history.replaceState(
                    null, 'Restore original ordering',
                    window.location.pathname);
            }
        });
    }

    sort_headings.each(function () {
        enable_sort_column($(this));
    });

    if (alter_url) {
        var params = new URLSearchParams(window.location.search);
        var sort_applied = false;
        params.forEach(function (value, key) {
            if (key === 'sortasc') {
                sort_applied = true;
                sort_direction = 1;
                apply_sort_column(value);
            } else if (key === 'sortdesc') {
                sort_applied = true;
                sort_direction = -1;
                apply_sort_column(value);
            }
        });

        reset_button.prop('disabled', ! sort_applied);
    } else {
        reset_button.prop('disabled', true);
    }
}

function enable_table_col_sorting(table) {
    var sort_headings = table.find('th.col_sortable');
    var last_sorted_by = null;
    var sort_direction = -1;

    var enable_sort_column = (function (heading) {
        var sort_key = heading.data('col_sortkey');
        var default_sort_order = 1;

        if (heading.hasClass('col_sortreverse')) {
            default_sort_order = -1;
        }

        if (heading.hasClass('col_sortedalready')) {
            last_sorted_by = sort_key;
        }

        heading.click(function () {
            if (sort_key !== last_sorted_by) {
                last_sorted_by = sort_key;
                sort_direction = default_sort_order;
            }

            var arr = [];
            var unsorted = [];
            var i = 0;

            table.find('tr').first().children().each(function (i) {
                var col = $(this);
                var sort_info = col.data('col_sortinfo');

                if (sort_info !== undefined) {
                    arr.push({col: i, value: sort_info[sort_key]});
                } else if (arr.length == 0) {
                    unsorted.push(i);
                }
            });

            arr.sort(function (a, b) {
                if (a.value === b.value) {
                    return 0;
                }
                if (a.value === null && b.value !== null) {
                    return 1;
                }
                if (b.value === null && a.value !== null) {
                    return -1;
                }
                return (sort_direction * (a.value < b.value ? -1 : 1));
            });

            table.find('tr').each(function () {
                var row = $(this);
                var cells = row.children();
                var sorted = [];

                for (i in unsorted) {
                    sorted.push(cells.eq(unsorted[i]).detach());
                }

                for (i in arr) {
                    sorted.push(cells.eq(arr[i].col).detach());
                }

                row.prepend(sorted);
            });

            sort_direction = - sort_direction;

            sort_headings.removeClass('col_sorted_asc').addClass('col_sortable');
            sort_headings.removeClass('col_sorted_desc').addClass('col_sortable');
            heading.removeClass('col_sortable').addClass((sort_direction < 0 ) ? 'col_sorted_asc' : 'col_sorted_desc');
        });
    });

    sort_headings.each(function () {
        enable_sort_column($(this));
    });
}
