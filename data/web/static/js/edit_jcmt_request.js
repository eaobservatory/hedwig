function addRequestRow(newRowNumber) {
    var nid = 'new_' + newRowNumber;
    var newrow = $('#requestrow_template').clone();
    newrow.attr('id', 'requestrow_' + nid);
    newrow.find('[name=instrument]').attr('name', 'instrument_' + nid);
    newrow.find('[name=weather]').attr('name', 'weather_' + nid);
    newrow.find('[name=time]').attr('name', 'time_' + nid);
    var deletelink = newrow.find('#delete_template');
    deletelink.attr('id', 'delete_' + nid);
    deletelink.click(function (event) {
        deleteRequestRow(nid);
    });
    newrow.appendTo($('table#requests'));
}

function deleteRequestRow(requestid) {
    $('#requestrow_' + requestid).remove();
}

$(document).ready(function () {
    var newRowCounter = $('#requesttable_template').data('newcounter');

    $('#add_request').click(function (event) {
        addRequestRow(newRowCounter ++);
    });

    $('[id^="delete_"]').click(function (event) {
        var requestid = event.target.id.replace('delete_', '');
        deleteRequestRow(requestid);
    });

    if ($('table#requests tr').length === 1) {
        addRequestRow(newRowCounter ++);
    }
});
