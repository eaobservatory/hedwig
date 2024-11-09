$(document).ready(function () {
    var table = $('table#affiliation_weight');

    var input_weight = table.find('input[type=number]');
    var total_weight = table.find('span#total_weight');

    var compute_totals = (function () {
        var total = 0.0;

        input_weight.each(function() {
            var this_weight = parseFloat($(this).val());
            if (! isNaN(this_weight)) {
                total += this_weight;
            }
        });

        total_weight.html(total.toFixed(3));
    });

    input_weight.on('change', compute_totals);
    input_weight.on('keyup', compute_totals);
    compute_totals();
});
