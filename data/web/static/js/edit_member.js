function deleteMemberRow(memberId) {
    $('#memberrow_' + memberId).remove();
}

$(document).ready(function () {
    $('[id^="delete_"]').click(function (event) {
        var memberId = event.target.id.replace('delete_', '');
        deleteMemberRow(memberId);
    });
});
