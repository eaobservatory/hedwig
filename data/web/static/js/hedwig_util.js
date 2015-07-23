function disable_futile_labels() {
    $('label').each(function () {
        var label = $(this);
        label.toggleClass('for_disabled',
            ! (label.nextAll('input:enabled, select:enabled').length > 0));
    });
}
