$(document).ready(function () {
    $('div.rst_doc img').each(function () {
        var image = $(this);
        var image_href = image.attr('src').replace('.png', '_large.png');
        image.wrap('<a href="' + image_href + '"></a>');
    });
});
