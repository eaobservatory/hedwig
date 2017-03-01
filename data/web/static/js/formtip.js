$(document).ready(function () {
    $('div.formtip').prepend('<a>?</a>');

    $('div.formtip > div').prepend('<a>&times;</a>');

    $('div.formtip > a').click(function (evt) {
        var formtip = $(this).next();
        if (formtip.is(':visible')) {
            formtip.hide();
        } else {
            $('div.formtip > div').hide();
            formtip.show();
        }
        evt.preventDefault();
    });

    $('div.formtip > div > a').click(function (evt) {
        $(this).parent().hide();
        evt.preventDefault();
    });
});
