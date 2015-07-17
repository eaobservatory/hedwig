$(document).ready(function () {
    var mf_checkbox = $('[name=mf]');

    mf_checkbox.change(function () {
        var mf_checked = mf_checkbox.prop('checked');
        var pix850 = $('[name=pix850]');
        var pix450 = $('[name=pix450]');
        pix850.prop('disabled', mf_checked);
        pix450.prop('disabled', mf_checked);

        if (mf_checked) {
            pix850.val(pix850.data('default'));
            pix450.val(pix450.data('default'));
        }
    });
});
