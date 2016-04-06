function addAffiliationRow(newRowNumber) {
    var nid = 'new_' + newRowNumber;
    var newrow = $('#affiliationrow_template').clone();
    newrow.attr('id', 'affiliationrow_' + nid);
    var newname = newrow.find('[name=name]');
    newname.attr('name', 'name_' + nid);
    newname.attr('required', 'required');
    newrow.find('[name=hidden]').attr('name', 'hidden_' + nid);
    newrow.find('[name=type]').attr('name', 'type_' + nid);
    var deletelink = newrow.find('#delete_template');
    deletelink.attr('id', 'delete_' + nid);
    deletelink.click(function (event) {
        deleteAffiliationRow(nid);
    });
    newrow.appendTo($('table#affiliations'));
}

function deleteAffiliationRow(affiliationid) {
    $('#affiliationrow_' + affiliationid).remove();
}

$(document).ready(function () {
    var newRowCounter = 1;

    $('#add_affiliation').click(function (event) {
        addAffiliationRow(newRowCounter ++);
    });

    $('[id^="delete_"]').click(function (event) {
        var affiliationid = event.target.id.replace('delete_', '');
        deleteAffiliationRow(affiliationid);
    });
});
