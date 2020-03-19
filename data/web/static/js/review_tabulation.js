$(document).ready(function () {
    var tabulation = $('table#tabulation');

    enable_table_sorting(tabulation, true);
    tabulation.stickyTableHeaders();

    var filter_boxes = $('#filter_decision').find('input[type=checkbox]');

    var filter_table = (function () {
        filter_boxes.each(function () {
            var decision = $(this).data('decision');
            if ($(this).prop('checked')) {
                tabulation.find('tr.decision_' + decision).show();
            } else {
                tabulation.find('tr.decision_' + decision).hide();
            }
        });
    });

    filter_boxes.each(function () {
        $(this).change(filter_table);
    });

    filter_table();
});
