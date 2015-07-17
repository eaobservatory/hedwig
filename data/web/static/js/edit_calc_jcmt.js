$(document).ready(function () {
    var tau_select = $('[name=tau_band]');
    var tau_box = $('[name=tau_value]');

    tau_select.change(function () {
        var is_tau_other = (tau_select.val() === 'other');
        tau_box.prop('disabled', ! is_tau_other);
        if (! is_tau_other) {
            tau_box.val(tau_select.find(':selected').data('representative'));
        }
    });
});
