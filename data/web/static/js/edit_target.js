function addTargetRow(newRowNumber) {
    var nid = 'new_' + newRowNumber;
    var newrow = $('#targetrow_template').clone();
    newrow.attr('id', 'targetrow_' + nid);
    newrow.find('[name=name]').attr('name', 'name_' + nid);
    newrow.find('[name=x]').attr('name', 'x_' + nid);
    newrow.find('[name=y]').attr('name', 'y_' + nid);
    newrow.find('[name=system]').attr('name', 'system_' + nid);
    newrow.find('[name=time]').attr('name', 'time_' + nid);
    newrow.find('[name=priority]').attr('name', 'priority_' + nid);
    var deletelink = newrow.find('#delete_template');
    deletelink.attr('id', 'delete_' + nid);
    deletelink.click(function (event) {
        deleteTargetRow(nid);
    });
    var resolvebutton = newrow.find('#resolve_template');
    resolvebutton.attr('id', 'resolve_' + nid);
    resolvebutton.click(function (event) {
        resolveTargetName(nid);
    });
    newrow.appendTo($('table#targets'));
}

function deleteTargetRow(targetid) {
    $('#targetrow_' + targetid).remove();
}

function resolveTargetName(targetid) {
    var nameResolver = $('table#targets').data('resolver');
    var targetNameBox = $('[name=name_' + targetid + ']');
    var targetXBox = $('[name=x_' + targetid + ']');
    var targetYBox = $('[name=y_' + targetid + ']');
    var targetSystem = $('[name=system_' + targetid + ']');
    var resolveButton = $('#resolve_' + targetid);

    resolve_target_name(nameResolver, targetNameBox, targetXBox, targetYBox, targetSystem, resolveButton);
}

$(document).ready(function () {
    var newRowCounter = 1;

    $('#add_target').click(function (event) {
        addTargetRow(newRowCounter ++);
    });

    $('[id^="delete_"]').click(function (event) {
        var targetid = event.target.id.replace('delete_', '');
        deleteTargetRow(targetid);
    });

    $('[id^="resolve_"]').click(function (event) {
        var targetid = event.target.id.replace('resolve_', '');
        resolveTargetName(targetid);
    });

    if ($('table#targets tr').length === 1) {
        addTargetRow(newRowCounter ++);
    }
});
