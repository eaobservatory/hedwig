function addCloseRow(newRowNumber) {
    var nid = 'new_' + newRowNumber;
    var newrow = $('#mid_close_row_template').clone();
    newrow.attr('id', 'mid_close_row_' + nid);
    var newdate_date = newrow.find('[name=date_date]');
    newdate_date.attr('name', 'date_date_' + nid);
    newdate_date.attr('required', 'required');
    var newdate_time = newrow.find('[name=date_time]');
    newdate_time.attr('name', 'date_time_' + nid);
    newdate_time.attr('required', 'required');
    var deletelink = newrow.find('#delete_template');
    deletelink.attr('id', 'delete_' + nid);
    deletelink.click(function (event) {
        deleteCloseRow(nid);
    });
    newrow.appendTo($('table#mid_close'));
}

function deleteCloseRow(mid_close_id) {
    $('#mid_close_row_' + mid_close_id).remove();
}

$(document).ready(function () {
    var newRowCounter = 1;

    $('#add_mid_close').click(function (event) {
        addCloseRow(newRowCounter ++);
    });

    $('[id^="delete_"]').click(function (event) {
        var mid_close_id = event.target.id.replace('delete_', '');
        deleteCloseRow(mid_close_id);
    });
});
