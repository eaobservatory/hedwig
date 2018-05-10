$(document).ready(function () {
    var rx_select = $('select[name=rx]');
    var mm_select = $('select[name=mm]');

    var freq_res_select = $('select[name=acsis_mode]');
    var freq_res_box = $('input[name=res]');
    var freq_res_unit = $('select[name=res_unit]');

    var line_catalog = null;
    var species_select = $('select[name=species]');
    var transition_select = $('select[name=trans]');

    var freq_box = $('input[name=freq]');
    var rv_box = $('input[name=rv]');
    var rv_sys_box = $('select[name=rv_sys]');
    var rv_unit_span = $('#calc_unit_rv');

    var check_rx_opt = (function () {
        var rx = rx_select.find(':selected');
        var is_array = rx.data('is_array');
        var dual_pol_available = rx.data('dual_pol_available');
        var ssb_available = rx.data('ssb_available');
        var dsb_available = rx.data('dsb_available');

        $('input[name=dual_pol]').prop('disabled', ! dual_pol_available);

        if (! dual_pol_available) {
            $('input[name=dual_pol]').prop('checked', false);
        }

        $('input[name=sb][value=ssb]').prop('disabled', ! ssb_available);
        $('input[name=sb][value=dsb]').prop('disabled', ! dsb_available);

        if (ssb_available && ! dsb_available) {
            $('input[name=sb][value=ssb]').prop('checked', true);
        } else if (dsb_available && ! ssb_available) {
            $('input[name=sb][value=dsb]').prop('checked', true);
        }

        freq_res_select.children().each(function () {
            var acsis_mode = $(this);
            var is_disabled = (acsis_mode.data('array_only') && ! is_array);

            if (acsis_mode.prop('selected') && is_disabled) {
                freq_res_select.val(acsis_mode.prev().val());
                check_freq_res();
            };

            acsis_mode.prop('disabled', is_disabled);
        });

        check_mode_opt();

        check_radial_vel();
    });

    var check_sep_off = (function () {
        var sw_mode = $('input[name=sw]:checked').val();

        var sep_off_disabled = (
            (sw_mode === 'frsw') ||
            (mm_select.val() === 'raster') ||
            (mm_select.val() === 'grid' && sw_mode === 'pssw'));

        $('input[name=sep_off]').prop('disabled', sep_off_disabled);

        if (sep_off_disabled) {
            $('input[name=sep_off]').prop('checked', false);
        }

        disable_futile_labels();
    });

    var check_mode_opt = (function () {
        var rx = rx_select.find(':selected');
        var rx_name = rx.val();
        var is_array = rx.data('is_array');
        var is_grid = (mm_select.val() === 'grid');
        var is_jiggle = (mm_select.val() === 'jiggle');
        var is_raster = (mm_select.val() === 'raster');

        $('input[name=n_pt]').prop('disabled', (! is_grid));
        $('select[name=n_pt_jiggle]').prop('disabled', (! is_jiggle) || is_array);

        $('input[name=dim_x]').prop('disabled', ! is_raster);
        $('input[name=dim_y]').prop('disabled', ! is_raster);
        $('input[name=dx]').prop('disabled', (! is_raster) || is_array);
        $('input[name=dy]').prop('disabled', (! is_raster) || is_array);
        $('input[name=basket]').prop('disabled', ! is_raster);

        $('select[name^=dy_spacing_]').prop('disabled', true);

        if (is_raster && is_array) {
            $('select[name=dy_spacing_' + rx_name + ']').prop('disabled', false);
            $('input[name=dx]').val(rx.data('pixel_size'));
            $('input[name=dy]').val(rx.data('pixel_size'));
        }

        if (! is_raster) {
            $('input[name=basket]').prop('checked', false);
        }

        $('select[name^=n_pt_jiggle_]').prop('disabled', true);

        if (is_jiggle && is_array) {
            $('select[name=n_pt_jiggle_' + rx_name + ']').prop('disabled', false);
        }

        var mm = mm_select.find(':selected');
        var bmsw_allowed = mm.data('bmsw_allowed');
        var pssw_allowed = mm.data('pssw_allowed');
        var frsw_allowed = mm.data('frsw_allowed');

        var sw_mode_radio = $('input[name=sw]');
        sw_mode_radio.filter('[value=bmsw]').prop('disabled', ! bmsw_allowed);
        sw_mode_radio.filter('[value=pssw]').prop('disabled', ! pssw_allowed);
        sw_mode_radio.filter('[value=frsw]').prop('disabled', ! frsw_allowed);

        if (sw_mode_radio.filter(':checked').prop('disabled')) {
            sw_mode_radio.filter(':enabled').prop('checked', true);
        }

        check_sep_off();
    });

    rx_select.change(check_rx_opt);
    mm_select.change(check_mode_opt);
    $('input[name=sw]').change(check_sep_off);

    $('select[name^=n_pt_jiggle]').change(function () {
        $('input[name=n_pt]').val(this.value);
    });

    var check_freq_res = (function () {
        var is_res_other = (freq_res_select.val() === 'other');
        freq_res_box.prop('disabled', ! is_res_other);
        freq_res_unit.prop('disabled', ! is_res_other);
        if (! is_res_other) {
            freq_res_box.val(freq_res_select.find(':selected').data('resolution'));
            freq_res_unit.val('MHz');
        }
    });

    freq_res_select.change(check_freq_res);

    var check_transition_availability = (function () {
        var freq_min = freq_box.attr('min');
        var freq_max = freq_box.attr('max');

        transition_select.children().each(function () {
            var transition = $(this);
            var freq = transition.data('freq');
            transition.prop('disabled', (freq < freq_min) || (freq > freq_max));
        });
    });

    var check_radial_vel = (function() {
        var rv_sys = rv_sys_box.find(':selected');
        if (rv_sys.data('no_unit')) {
            rv_unit_span.hide();
        } else {
            rv_unit_span.show();
        }

        var rv_sys_name = rv_sys.val();
        var rv = parseFloat(rv_box.val());

        var c = 299792.458;
        var redshift = 0.0;
        if (rv_sys_name === 'z') {
            redshift = rv;
        } else if (rv_sys_name === 'opt') {
            redshift = rv / c;
        } else if (rv_sys_name === 'rad') {
            redshift = rv / (c - rv);
        }

        var rx = rx_select.find(':selected');
        var freq_min = Math.round(1000.0 * rx.data('f_min') * (1.0 + redshift)) / 1000.0;
        var freq_max = Math.round(1000.0 * rx.data('f_max') * (1.0 + redshift)) / 1000.0;
        freq_box.attr('min', freq_min);
        freq_box.attr('max', freq_max);
        $('span#freq_min').text(freq_min);
        $('span#freq_max').text(freq_max);

        check_transition_availability();
    });

    rv_sys_box.change(check_radial_vel);

    rv_box.change(check_radial_vel);

    check_rx_opt();

    var update_transition_list = (function () {
        if (line_catalog === null) {
            return;
        }

        transition_select.children().detach();

        var species = species_select.val();

        if (species === '') {
            transition_select.append($('<option/>', {'text': 'Other', 'value': ''}));
            freq_box.prop('disabled', false);
            return;
        }

        var transitions = line_catalog[species];

        if (transitions === undefined) {
            transition_select.append($('<option/>', {'text': 'Species not recognized', 'value': ''}));
            freq_box.prop('disabled', false);
            return;
        }

        freq_box.prop('disabled', true);

        var options = [];

        for (var i = 0; i < transitions.length; i ++) {
            var entry = transitions[i];
            var transition = entry[0];
            var freq = entry[1];

            options.push($('<option/>', {
                'text': transition,
                'value': transition
            }).data('freq', freq));
        }

        transition_select.append(options);

        check_transition_availability();

        var transition_avail = transition_select.find(':enabled');
        if (transition_avail.length) {
            transition_select.val(transition_avail.val());
        }
    });

    var apply_transition_selection = (function () {
        var transition = transition_select.find(':selected');

        if (transition.val() === '') {
            return;
        }

        freq_box.val(transition.data('freq'));
    });

    var check_species_selection = (function () {
        update_transition_list();
        apply_transition_selection();
    });

    species_select.change(check_species_selection);
    transition_select.change(apply_transition_selection);

    $.ajax(species_select.data('line-catalog'), dataType='json'
    ).done(function (result) {
        species_select.children().detach();
        line_catalog = {};

        var options = [$('<option/>', {'text': 'Other', 'value': ''})];

        for (var i = 0; i < result.length; i ++) {
            var entry = result[i];
            var species = entry[0];
            var transitions = entry[1];

            line_catalog[species] = transitions;

            options.push($('<option/>', {'text': species, 'value': species}));
        }

        species_select.append(options);

        var species_selected = species_select.data('selected');
        if (species_selected !== '') {
            species_select.val(species_selected);
        }

        update_transition_list();

        var transition_selected = transition_select.data('selected');
        if (transition_selected !== '') {
            transition_select.val(transition_selected);
        }

        if (freq_box.val() === '') {
            apply_transition_selection();
        }

    }).fail(function (jqXHR, textStatus) {
        species_select.children().detach();
        transition_select.children().detach();
        species_select.append($('<option/>', {'text': 'Failed to load', 'value': ''}));
        transition_select.append($('<option/>', {'text': 'Failed to load', 'value': ''}));
    });
});
