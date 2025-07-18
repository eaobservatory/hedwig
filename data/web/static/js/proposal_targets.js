$(document).ready(function () {
    var table = $('table#target_table');

    if (table.length === 1) {
        var table_body = table.find('tbody').first();

        // Put original system decimal values into sortinfo 'x' and 'y' and enable sorting.
        if (table_body.children('tr').length > 1) {
            table_body.children('tr').each(function () {
                var this_row = $(this);
                var systems = this_row.data('systems');
                if (systems !== null) {
                    var selected_system = systems[this_row.data('sortinfo').system];
                    var sortinfo = this_row.data('sortinfo');
                    sortinfo['x'] = selected_system[2];
                    sortinfo['y'] = selected_system[3];
                }
            });

            enable_table_sorting(table, false);
        } else {
            table.find('thead').find('th').removeClass('sortable');
        }

        // Enable system buttons in footer.
        var system_buttons = table.find('tfoot').find('button[id^=system]');
        system_buttons.each(function () {
            var this_button = $(this);
            var system_name = this_button.text();
            var system_id = this_button.attr('id').replace('system_', '');

            this_button.on('click', function (evt) {
                table_body.children('tr').each(function () {
                    var this_row = $(this);
                    var systems = this_row.data('systems');
                    if (systems !== null) {
                        var cell_system = this_row.find('td[data-column="system"]');
                        if (cell_system.data('original') === undefined) {
                            cell_system.data('original', cell_system.text());
                        }

                        var selected_system;
                        if (system_id === 'original') {
                            cell_system.text(cell_system.data('original'));
                            selected_system = systems[this_row.data('sortinfo').system];
                        }
                        else {
                            cell_system.text(system_name);
                            selected_system = systems[system_id];
                        }

                        this_row.find('td[data-column="x"]').text(selected_system[0]);
                        this_row.find('td[data-column="y"]').text(selected_system[1]);

                        var sortinfo = this_row.data('sortinfo');
                        sortinfo['x'] = selected_system[2];
                        sortinfo['y'] = selected_system[3];
                    }
                });

                system_buttons.prop('disabled', false);
                this_button.prop('disabled', true);
            });

            if (system_id === 'original') {
                this_button.prop('disabled', true);
            }
        });
    }
});
