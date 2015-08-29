$(document).ready(function () {
    $('[id^="delete_"]').click(function (event) {
        var memberId = event.target.id.replace('delete_', '');
        $('#memberrow_' + memberId).remove();
    });
});
