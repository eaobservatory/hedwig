function disable_futile_labels() {
    $('label').each(function () {
        var label = $(this);
        label.toggleClass('for_disabled',
            ! (label.nextAll('input:enabled, select:enabled').length > 0));
    });
}

function enable_table_sorting(table) {
    var table_body = table.find('tbody').first();
    var last_sorted_by = null;
    var sort_direction = -1;

    var enable_sort_column = (function (heading) {
        var sort_key = heading.data('sortkey');
        var default_sort_order = 1;

        if (heading.hasClass('sortreverse')) {
            default_sort_order = -1;
        }

        if (heading.hasClass('sortedalready')) {
            last_sorted_by = sort_key;
        }

        heading.click(function () {
            if (sort_key !== last_sorted_by) {
                last_sorted_by = sort_key;
                sort_direction = default_sort_order;
            }

            var arr = [];
            var i;

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
        });
    });

    table.find('th.sortable').each(function () {
        enable_sort_column($(this));
    });
}
