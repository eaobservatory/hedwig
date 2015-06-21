function deleteFigureRow(figureid) {
    $('#figrow_' + figureid).remove();
}

$(document).ready(function () {
    $('[id^="delete_"]').click(function (event) {
        var emailid = event.target.id.replace('delete_', '');
        deleteFigureRow(emailid);
    });
});
