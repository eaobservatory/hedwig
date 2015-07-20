$(document).ready(function () {
    var rx_select = $('select[name=rx]');
    var mm_select = $('select[name=mm]');

    var check_rx_opt = (function () {
        var rx = rx_select.find(':selected');
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

        var freq_box = $('input[name=freq]');
        var freq_min = rx.data('f_min');
        var freq_max = rx.data('f_max')
        freq_box.attr('min', freq_min);
        freq_box.attr('max', freq_max);
        $('span#freq_min').text(freq_min);
        $('span#freq_max').text(freq_max);

        check_mode_opt();
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

    check_rx_opt();
});
