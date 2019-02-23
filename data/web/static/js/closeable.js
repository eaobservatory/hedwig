$(document).ready(function () {
    $('div.closeable').prepend('<p class="closer"><a>&times;</a></p>');

    $('div.closeable > p.closer > a').click(function (evt) {
        $(this).parent().parent().hide();
        evt.preventDefault();
    });
});
