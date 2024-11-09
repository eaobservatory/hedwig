$(document).ready(function () {
    var table = $('table#time_available');

    var input_time = table.find('input[type=number]');
    var total_time = table.find('span#total_time');

    var compute_totals = (function () {
        var total = 0.0;

        input_time.each(function() {
            var this_time = parseFloat($(this).val());
            if (! isNaN(this_time)) {
                total += this_time;
            }
        });

        total_time.html(total.toFixed(3));
    });

    input_time.on('change', compute_totals);
    input_time.on('keyup', compute_totals);
    compute_totals();
});
