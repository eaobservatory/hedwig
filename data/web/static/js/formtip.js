$(document).ready(function () {
    $('div.formtip').prepend('<a>?</a>');

    $('div.formtip > div').prepend('<a>&times;</a>');

    $('div.formtip > a').click(function (evt) {
        $(this).next().toggle();
        evt.preventDefault();
    });

    $('div.formtip > div > a').click(function (evt) {
        $(this).parent().hide();
        evt.preventDefault();
    });
});
