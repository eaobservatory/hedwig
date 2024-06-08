$(document).ready(function () {
    // Color configuration.

    var colors_decision = ['#ffff00', '#00aa00', '#888888', '#ff0000'];
    var colors_scale = ['#ccccff', '#9999ff', '#6666ff', '#3333ff', '#0000ff', '#000088', '#000000'];
    var colors_other = ['#ff0000', '#00aa00', '#0000ff', '#ffff00', '#008888', '#000000'];

    // Read initial data and define how to merge the fixed and dynamic part.

    var alloc = $('div#allocation');

    var proposals = alloc.data('proposals');
    var categories = alloc.data('categories');
    var ra_bins = alloc.data('ra_bins');
    var default_bins = ra_bins.map(function () {return 0.0;});

    var merge_proposal_info = (function (dynamic) {
        for (var i in proposals) {
            var proposal = proposals[i];
            var proposal_id = proposal['id'];
            var proposal_category = proposal['category'];

            if (proposal_id in dynamic) {
                var proposal_dynamic = dynamic[proposal_id];
                for (var property in proposal_dynamic) {
                    if (property === 'category') {
                        var category_dynamic = proposal_dynamic[property];
                        for (var category_name in category_dynamic) {
                            if (category_dynamic.hasOwnProperty(category_name)) {
                                proposal_category[category_name] = category_dynamic[category_name];
                            }
                        }
                    } else if (proposal_dynamic.hasOwnProperty(property)) {
                        proposal[property] = proposal_dynamic[property];
                    }
                }
            }
        }
    });

    merge_proposal_info(alloc.data('dynamic'));

    // Create the chart itself.

    var alloc_canvas = $('<canvas id="mycanvas" width="1000" height="500"></canvas>');
    alloc.empty().append(alloc_canvas);

    Chart.defaults.scales.linear.min = 0;

    var alloc_chart = new Chart(alloc_canvas.get(0).getContext('2d'), {
        type: 'bar',
        data: {
            labels: ra_bins
        },
        options: {
            responsive: false,
            plugins: {
                legend: {
                    position: 'right'
                }
            },
            scales: {
                x: {
                    stacked: true,
                    title: {
                        display: true,
                        text: 'RA / h'
                    }
                },
                y: {
                    stacked: true,
                    title: {
                        display: true,
                        text: 'Time / h'
                    }
                }
            },
            animation: {
                duration: 0,
                active: {
                    duration: 0
                },
                resize: {
                    duration: 0
                }
            },
        }
    });

    // Create the refresh button.

    var refresh_button = $('<button id="refresh">Refresh</button>');
    alloc.append($('<p></p>').append(refresh_button));

    var refresh_url = alloc.data('refresh');

    // Create the selection controls.

    var controls = $('<form></form>');
    var row_header = $('<tr></tr>');
    var row_group = $('<tr></tr>');
    var row_filter = $('<tr></tr>');

    categories.forEach(function (category) {
        row_header.append($('<th></th>').text(category.name));

        var radio = $('<input type="radio" name="group" />');
        radio.prop('value', category.code);
        radio.data('is_scale', (!! category.is_scale));
        radio.data('default', category['default']);
        var group = $('<span>Group by</span>');
        group.prepend(radio);
        row_group.append($('<td></td>').append(group));

        var filters = $('<td></td>');
        category.values.forEach(function (value) {
            var checkbox = $('<input type="checkbox" />');
            checkbox.prop('name', 'filter_' + category.code + '_' + value[0]);
            checkbox.val(value[0]);
            checkbox.data('category', category.code);
            var filter = $('<span></span>').text(value[1]);
            filter.prepend(checkbox);
            filters.append(filter);
            filters.append($('<br />'));
        });
        row_filter.append(filters);
    });

    row_header.append('<th>Proposal</th>');
    row_group.append('<td><span><input type="radio" name="group" value="proposal" />Group by</span></td>');
    row_filter.append('<td>&nbsp;</td>');

    alloc.append(controls.append($('<table></table>').append([row_header, row_group, row_filter])));

    var prev_category = null;

    var update_controls = (function () {
        var all_filters = controls.find('input[type=checkbox]');
        var new_category = controls.find('input[type=radio]').filter(':checked').first().val();
        controls.find('input[type=radio]').each(function () {
            var radio = $(this);
            var category = radio.val();
            var default_filter = radio.data('default');
            var filters = all_filters.filter(function () {return $(this).data('category') === category;});

            if (radio.prop('checked')) {
                filters.prop('disabled', true);
                filters.prop('checked', false);
            } else {
                filters.prop('disabled', false);
                if ((prev_category === null) || (prev_category === category)) {
                    if (typeof default_filter !== 'undefined') {
                        filters.each(function () {
                            var filter = $(this);
                            filter.prop('checked', (default_filter.indexOf(filter.val()) > -1));
                        });
                    } else {
                        filters.prop('checked', true);
                    }
                }
            }
        });

        prev_category = new_category;
    });

    // Define how to generate the data for the chart.

    var update_chart = (function () {
        while (alloc_chart.data.datasets.length > 0) {
            alloc_chart.data.datasets.pop();
        }

        var radio = controls.find('input[type=radio]').filter(':checked').first();
        var group = radio.val();

        var colors = colors_other;
        var color_always_inc = false;
        if (group === 'decision') {
            colors = colors_decision;
            color_always_inc = true;
        } else if (radio.data('is_scale')) {
            colors = colors_scale;
            color_always_inc = true;
        }

        // Prepare grouping categories.

        var groups = new Map();

        if (group === 'proposal') {
            proposals.forEach(function (proposal) {
                groups.set(proposal.id, {
                    title: proposal.code,
                    ra: default_bins.slice()
                });
            });
        } else {
            categories.forEach(function (category) {
                if (category.code === group) {
                    category.values.forEach(function (value) {
                        groups.set(value[0], {
                            title: value[1],
                            ra: default_bins.slice()
                        });
                    });
                }
            });
        }

        // Prepare filtering options.

        var all_filters = controls.find('input[type=checkbox]');

        var filters = {};

        if (group !== 'decision') {
            checkboxes = all_filters.filter(function () {
                return $(this).data('category') === 'decision';
            });
            if (checkboxes.not(':checked').length > 0) {
                var options = {};
                checkboxes.filter(':checked').each(function () {
                    options[$(this).val()] = true;
                });
                filters['decision'] = options;
            }
        }
        categories.forEach(function (category_obj) {
            var category = category_obj.code;
            if (category !== group) {
                checkboxes = all_filters.filter(function () {
                    return $(this).data('category') === category;
                });
                if (checkboxes.not(':checked').length > 0) {
                    var options = {};
                    checkboxes.filter(':checked').each(function () {
                        options[$(this).val()] = true;
                    });
                    filters[category] = options;
                }
            }
        });

        // Iterate over proposals and add data to categories.

        proposals.forEach(function (proposal) {
            var category_weight = {};
            var filter_weight = 1.0;

            // Get weighing for each of the categories being grouped by.

            if (group === 'proposal') {
                category_weight[proposal.id] = 1.0;
            } else if (group === 'decision') {
                category_weight[proposal.decision] = 1.0;
            } else {
                category_weight = proposal.category[group];
            }

            // Get filtering weight from other categories.
            for (var filter in filters) {
                if (filters.hasOwnProperty(filter)) {
                    var allowed = filters[filter];

                    if (filter === 'decision') {
                        if (! allowed[proposal.decision]) {
                            filter_weight = 0.0;
                        }
                    }
                    else {
                        var this_filter_weight = 0.0;
                        var this_category = proposal.category[filter];

                        for (var value in this_category) {
                            if (this_category.hasOwnProperty(value)) {
                                if (allowed[value]) {
                                    this_filter_weight += this_category[value];
                                }
                            }
                        }

                        filter_weight *= this_filter_weight;
                    }
                }
            }

            // Accumulate time in each RA bin.

            if (filter_weight > 0.0) {
                var scale = proposal.time * filter_weight;

                for (var category_code in category_weight) {
                    if (category_weight.hasOwnProperty(category_code)) {
                        var weight = category_weight[category_code];
                        var category = groups.get(category_code);

                        if ((typeof category !== 'undefined') && (weight > 0.0)) {
                            for (var i = 0; i < default_bins.length; i ++) {
                                category.ra[i] += proposal.ra[i] * scale * weight;
                            }
                        }
                    }
                }
            }
        });

        // Add non-empty categories to the chart.

        var color = -1;
        for (let [code, category] of groups) {
            if (color_always_inc) {
                color = (color + 1) % colors.length;
            }
            if (category.ra.some(function (x) {return x > 0.0;})) {
                if (! color_always_inc) {
                    color = (color + 1) % colors.length;
                }
                alloc_chart.data.datasets.push({
                    label: category.title,
                    backgroundColor: colors[color],
                    data: category.ra
                });
            }
        }

        alloc_chart.update();
    });

    // Initialize controls and set up event handlers.

    refresh_button.click(function () {
        refresh_button.prop('disabled', true);

        $.ajax(
            refresh_url, dataType='json'
        ).done(function (result) {
            merge_proposal_info(result);
            update_chart();
        }).fail(function (jqXHR, textStatus) {
            alert('Unable to fetch updated information.');
        }).always(function () {
            refresh_button.prop('disabled', false);
        });
    });

    controls.find('input[type=radio]').first().prop('checked', true);

    update_controls();

    controls.find('input[type=radio]').change(function () {
        update_controls();
        update_chart();
    });

    controls.find('input[type=checkbox]').change(function () {
        update_chart();
    });

    // Update the chart for the first time.

    update_chart();
});
