$(document).ready(function () {
    var proposal_id = $('[name=proposal_id]');
    var original_proposal = $('[name=for_proposal_id]').val();
    var overwrite_checkbox = $('[name=overwrite]');

    var check_same_proposal = (function () {
        var is_same_proposal = (proposal_id.val() === original_proposal);
        overwrite_checkbox.prop('disabled', ! is_same_proposal);
        if (! is_same_proposal) {
            overwrite_checkbox.prop('checked', false);
        }

        disable_futile_labels();
    });

    proposal_id.change(check_same_proposal);
    check_same_proposal();
});
