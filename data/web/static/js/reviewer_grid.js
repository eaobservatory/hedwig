$(document).ready(function () {
    var table = $('table#reviewer_grid');
    table.stickyTableHeaders();

    var nroles = table.data('nroles');
    if (! (nroles > 1)) {
        return;
    }

    var assign_radio = table.find('input[type=radio]');
    var assign_check = table.find('input[type=checkbox]');

    var disable_duplicate_control = (function () {
        var control = $(this);
        var other = control.siblings('input');
        control.prop('disabled', other.is(':checked') || other.is('[type=hidden]'));
    });

    var disable_duplicates = (function () {
        assign_radio.not('.unassigned').each(disable_duplicate_control);
        assign_check.not('.unassigned').each(disable_duplicate_control);
    });

    assign_radio.change(disable_duplicates);
    assign_check.change(disable_duplicates);
    disable_duplicates();
});
