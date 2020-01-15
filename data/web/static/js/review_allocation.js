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
    var default_bins = ra_bins.map(function () {return 0.0});

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

    Chart.scaleService.updateScaleDefaults('linear', {
        ticks: {
            min: 0
        }
    });

    alloc_chart = new Chart(alloc_canvas.get(0).getContext('2d'), {
        type: 'bar',
        data: {
            labels: ra_bins,
        },
        options: {
            responsive: false,
            legend: {
                position: 'right'
            },
            scales: {
                xAxes: [{
                    stacked: true
                }],
                yAxes: [{
                    stacked: true
                }]
            },
            animation: {
                duration: 0
            },
            hover: {
                animationDuration: 0
            },
            responsiveAnimationDuration: 0
        }
    });

    // Define how to generate the data for the chart.

    var update_chart = (function () {
        while (alloc_chart.data.datasets.length > 0) {
            alloc_chart.data.datasets.pop();
        }

        var colors = colors_other;
        var color = -1;
        var i;

        proposals.forEach(function (proposal) {
            var category_data = default_bins.slice();
            for (i = 0; i < default_bins.length; i ++) {
                category_data[i] += proposal.ra[i] * proposal.time;
            }

            color = (color + 1) % colors.length;
            alloc_chart.data.datasets.push({
                label: proposal.code,
                backgroundColor: colors[color],
                data: category_data,
            });
        });

        alloc_chart.update();
    });

    // Create the refresh button.

    var refresh_button = $('<button id="refresh">Refresh</button>');
    alloc.append($('<p></p>').append(refresh_button));

    var refresh_url = alloc.data('refresh');

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

    // Update the chart for the first time.

    update_chart();
});
