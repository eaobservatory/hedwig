function deleteCalculationRow(calcid) {
    $('#calcrow_' + calcid).remove();
}

$(document).ready(function () {
    $('[id^="delete_"]').click(function (event) {
        var calcid = event.target.id.replace('delete_', '');
        deleteCalculationRow(calcid);
    });

    enable_table_drag($('table#calculations'));
});
