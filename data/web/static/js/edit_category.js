function addCategoryRow(newRowNumber) {
    var nid = 'new_' + newRowNumber;
    var newrow = $('#categoryrow_template').clone();
    newrow.attr('id', 'categoryrow_' + nid);
    var newname = newrow.find('[name=name]');
    newname.attr('name', 'name_' + nid);
    newname.attr('required', 'required');
    newrow.find('[name=abbr]').attr('name', 'abbr_' + nid);
    newrow.find('[name=hidden]').attr('name', 'hidden_' + nid);
    var deletelink = newrow.find('#delete_template');
    deletelink.attr('id', 'delete_' + nid);
    deletelink.click(function (event) {
        deleteCategoryRow(nid);
    });
    newrow.appendTo($('table#categories'));
}

function deleteCategoryRow(categoryid) {
    $('#categoryrow_' + categoryid).remove();
}

$(document).ready(function () {
    var newRowCounter = 1;

    $('#add_category').click(function (event) {
        addCategoryRow(newRowCounter ++);
    });

    $('[id^="delete_"]').click(function (event) {
        var categoryid = event.target.id.replace('delete_', '');
        deleteCategoryRow(categoryid);
    });
});
