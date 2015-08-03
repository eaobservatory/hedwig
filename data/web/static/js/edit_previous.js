function updatePublicationType() {
    doUpdatePublicationType($(this));
}

function doUpdatePublicationType(type_select) {
    type_select.next().attr('placeholder', type_select.children(':selected').data('placeholder'));
}

function addPreviousRow(newRowNumber) {
    var nid = 'new_' + newRowNumber;
    var newrow = $('#previousrow_template').clone();
    newrow.attr('id', 'previousrow_' + nid);
    var newcode = newrow.find('[name=code]');
    newcode.attr('name', 'code_' + nid);
    newcode.attr('required', 'required');
    newrow.find('[name=continuation]').attr('name', 'continuation_' + nid);

    var i;
    for (i = 0; i < 6; i ++) {
        var type_select = newrow.find('[name=pub_type_' + i + ']');
        type_select.attr('name', 'pub_type_' + i + '_' + nid);
        type_select.change(updatePublicationType);
        newrow.find('[name=publication_' + i + ']').attr('name', 'publication_' + i + '_' + nid);
    }
    var deletelink = newrow.find('#delete_template');
    deletelink.attr('id', 'delete_' + nid);
    deletelink.click(function (event) {
        deletePreviousRow(nid);
    });
    newrow.appendTo($('table#previousproposals'));
}

function deletePreviousRow(previousid) {
    $('#previousrow_' + previousid).remove();
}

$(document).ready(function () {
    var newRowCounter = 1;

    $('#add_previous').click(function (event) {
        addPreviousRow(newRowCounter ++);
    });

    $('[id^="delete_"]').click(function (event) {
        var previousid = event.target.id.replace('delete_', '');
        deletePreviousRow(previousid);
    });

    $('select[name^=pub_type_]').each(function () {
        var type_select = $(this);
        doUpdatePublicationType(type_select);
        type_select.change(updatePublicationType);
    });

    if ($('table#previousproposals tr').length === 1) {
        addPreviousRow(newRowCounter ++);
    }
});
