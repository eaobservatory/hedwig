function deleteFigureRow(figureid) {
    $('#figrow_' + figureid).remove();
}

$(document).ready(function () {
    $('[id^="delete_"]').click(function (event) {
        var figureid = event.target.id.replace('delete_', '');
        deleteFigureRow(figureid);
    });
});
