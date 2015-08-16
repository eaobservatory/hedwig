function deleteMemberRow(memberId) {
    var piId = $('input[name=pi]:checked').val();
    if (piId === memberId) {
        alert('Please select someone else to be the PI before removing this member.');
    } else {
        $('#memberrow_' + memberId).remove();
    }
}

$(document).ready(function () {
    $('[id^="delete_"]').click(function (event) {
        var memberId = event.target.id.replace('delete_', '');
        deleteMemberRow(memberId);
    });
});
