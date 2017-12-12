$(document).ready(function () {
    var inst_select = $('select[name=inst]');
    var filt_select = $('select[name=filt]');
    var type_select = $('select[name=type]');

    var check_inst_opt = (function () {
        var inst_selected = inst_select.find(':selected').val();
        var invalid_filter_selected = false;

        filt_select.children().each(function () {
            var filt_opt = $(this);
            var filt_inst = filt_opt.data('instruments');
            var is_disabled = (! filt_inst[inst_selected]);

            if (is_disabled && filt_opt.prop('selected')) {
                invalid_filter_selected = true;
            }

            filt_opt.prop('disabled', is_disabled);
        });

        if (invalid_filter_selected) {
            filt_select.children().each(function () {
                var filt_opt = $(this);
                if (! filt_opt.prop('disabled')) {
                    filt_select.val(filt_opt.val());
                    return false;
                }
            });
        }
    });

    var check_type_opt = (function () {
        var type_selected = type_select.find(':selected').val();

        var is_extended = (type_selected === 'ext');

        $('input[name=seeing]').prop('disabled', is_extended);
        $('input[name=aper]').prop('disabled', is_extended);

        disable_futile_labels();
    });

    type_select.change(check_type_opt);
    inst_select.change(check_inst_opt);

    check_inst_opt();
    check_type_opt();
});
