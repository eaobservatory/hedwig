function addEmailRow(newRowNumber) {
    var nid = 'new_' + newRowNumber;
    var newrow = $('#emailrow_template').clone();
    newrow.attr('id', 'emailrow_' + nid);
    var newemail = newrow.find('[name=email]');
    newemail.attr('name', 'email_' + nid);
    newemail.attr('required', 'required');
    newrow.find('[name=public]').attr('name', 'public_' + nid);
    newrow.find('[name=primary]').attr('value', nid);
    var deletelink = newrow.find('#delete_template');
    deletelink.attr('id', 'delete_' + nid);
    deletelink.click(function (event) {
        deleteEmailRow(nid);
    });
    newrow.appendTo($('table#emailaddresses'));
}

function deleteEmailRow(emailid) {
    var primaryid = $('input[name=primary]:checked').val();
    if (primaryid === emailid) {
        alert('Please select another primary address before removing this address.');
    } else {
        $('#emailrow_' + emailid).remove();
    }
}

$(document).ready(function () {
    var newRowCounter = 1;

    $('#add_email').click(function (event) {
        addEmailRow(newRowCounter ++);
    });

    $('[id^="delete_"]').click(function (event) {
        var emailid = event.target.id.replace('delete_', '');
        deleteEmailRow(emailid);
    });
});
