function addTargetRow(newRowNumber) {
    var nid = 'new_' + newRowNumber;
    var newrow = $('#targetrow_template').clone();
    newrow.attr('id', 'targetrow_' + nid);
    newrow.find('[name=name]').attr('name', 'name_' + nid);
    newrow.find('[name=x]').attr('name', 'x_' + nid);
    newrow.find('[name=y]').attr('name', 'y_' + nid);
    newrow.find('[name=system]').attr('name', 'system_' + nid);
    var deletelink = newrow.find('#delete_template');
    deletelink.attr('id', 'delete_' + nid);
    deletelink.click(function (event) {
        deleteTargetRow(nid);
        event.preventDefault();
    });
    newrow.appendTo($('table#targets'));
}

function deleteTargetRow(targetid) {
    $('#targetrow_' + targetid).remove();
}

$(document).ready(function () {
    var newRowCounter = 1;

    $('#add_target').click(function (event) {
        addTargetRow(newRowCounter ++);
        event.preventDefault();
    });

    $('[id^="delete_"]').click(function (event) {
        var targetid = event.target.id.replace('delete_', '');
        deleteTargetRow(targetid);
        event.preventDefault();
    });
});
