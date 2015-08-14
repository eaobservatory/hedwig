$(document).ready(function () {
    $('span.mangled_address').each(function () {
        var el = $(this);
        var mangled = el.data('mangled');
        var mangled_len = mangled.length;
        var addr = '';
        var i;

        for (i = 0; i < mangled_len; i ++) {
            addr = addr + mangled[i];
        }

        el.replaceWith('<a href="mailto:' + addr  + '">' + addr + '</a>');
    });
});
