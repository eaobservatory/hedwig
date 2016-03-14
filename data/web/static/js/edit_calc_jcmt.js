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

    var pos_unit_span = $('#calc_unit_pos');
    var pos_type_select = $('[name=pos_type]');

    var check_pos_type_opt = (function() {
        if (pos_type_select.find(':selected').data('no_unit')) {
            pos_unit_span.hide();
        } else {
            pos_unit_span.show();
        }
    });

    pos_type_select.change(check_pos_type_opt);

    check_pos_type_opt();
});
