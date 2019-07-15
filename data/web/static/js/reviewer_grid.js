$(document).ready(function () {
    var table = $('table#reviewer_grid');
    table.stickyTableHeaders();

    var nroles = table.data('nroles');

    var assign_radio = table.find('input[type=radio]');
    var assign_check = table.find('input[type=checkbox]');
    var assign_hidden = table.find('input[type=hidden]');

    if (nroles > 1) {
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
    }

    var total_person = table.find('span[id^="total_person_"]');
    var total_proposal = table.find('span[id^="total_proposal_"]');

    if (0 < (total_person.length + total_proposal.length)) {
        var compute_totals = (function () {
            var re_unique = new RegExp('^rev_\\d+_\\d+$');
            total_person.each(function () {
                var span = $(this);
                var person_id = span.attr('id').replace('total_person_', '');
                var total = assign_check.filter(':checked').filter('[name$="_' + person_id + '"]').length;
                total += assign_radio.filter(':checked').filter('[value="' + person_id + '"]').length;

                var re_non_unique = new RegExp('^rev_\\d+_\\d+_' + person_id + '$');
                assign_hidden.each(function() {
                    var hidden = $(this);
                    var name = hidden.attr('name');
                    if (name.match(re_unique)) {
                        if (hidden.val() === person_id) {
                            total += 1;
                        }
                    } else if (name.match(re_non_unique)) {
                        total += 1;
                    }
                });

                span.html(total);
            });


            total_proposal.each(function () {
                var span = $(this);
                var role_prop_id = span.attr('id').replace('total_proposal_', '');
                var total = assign_check.filter(':checked').filter('[name^="rev_' + role_prop_id + '_"]').length;
                total += assign_radio.filter(':checked').filter('[name="rev_' + role_prop_id + '"]').not('[value=""]').length;
                total += assign_hidden.filter('[name^="rev_' + role_prop_id + '_"]').length;
                total += assign_hidden.filter('[name="rev_' + role_prop_id + '"]').length;
                span.html(total);
            });
        });

        assign_radio.change(compute_totals);
        assign_check.change(compute_totals);
        compute_totals();
    }
});
