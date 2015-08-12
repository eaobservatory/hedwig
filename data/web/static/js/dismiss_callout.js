$(document).ready(function () {
    $('#callout_dismiss').click(function (evt) {
        $(this).parent().parent().hide();
        evt.preventDefault();
    });
});
