$(document).ready(function () {
    $('span.copy_text').each(function () {
        var element = $(this);
        var copy_text = element.html();

        var button = $('<a href="#"></a>');
        var icon = $('<span class="fa-solid fa-copy"></span>');
        button.append(icon);

        element.append(' ');
        element.append(button);

        button.on('click', function (event) {
            navigator.clipboard.writeText(copy_text).then(function() {
                icon.removeClass('fa-copy');
                icon.addClass('fa-check');
            }, function() {
                icon.removeClass('fa-copy');
                icon.addClass('fa-x');
            });
            setTimeout(function () {
                icon.removeClass('fa-check');
                icon.removeClass('fa-x');
                icon.addClass('fa-copy');
            }, 1000);
            event.preventDefault();
        });
    });
});
