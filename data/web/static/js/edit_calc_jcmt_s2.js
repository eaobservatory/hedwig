$(document).ready(function () {
    var map_select = $('[name=map]');
    var samp_select = $('[name=samp]');

    var check_samp_opt = (function () {
        var map = map_select.find(':selected');
        var samp = samp_select.val();

        var pix850 = $('[name=pix850]');
        var pix450 = $('[name=pix450]');

        var pix_disabled = true;

        if (samp === 'map') {
            pix850.val(map.data('pix850'));
            pix450.val(map.data('pix450'));

        } else if (samp === 'mf') {
            pix850.val('');
            pix450.val('');

        } else if (samp === 'custom') {
            pix_disabled = false;
        }

        pix850.prop('disabled', pix_disabled);
        pix450.prop('disabled', pix_disabled);

        disable_futile_labels();
    });

    map_select.change(check_samp_opt);
    samp_select.change(check_samp_opt);

    check_samp_opt();
});
