$(document).ready(function () {
    var table = $('table#statistics');
    table.stickyTableHeaders();

    enable_table_sorting(table);
    enable_table_col_sorting(table);
});
