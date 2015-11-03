$(document).ready(function () {
    var tabulation = $('table#tabulation');

    enable_table_sorting(tabulation);
    tabulation.stickyTableHeaders();
});
