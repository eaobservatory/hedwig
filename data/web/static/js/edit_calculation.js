$(document).ready(function () {
    var proposal_id = $('[name=proposal_id]');
    var calculation_proposal = $('[name=calculation_proposal]').val();
    var overwrite_checkbox = $('[name=overwrite]');

    proposal_id.change(function () {
        var is_same_proposal = (proposal_id.val() === calculation_proposal);
        overwrite_checkbox.prop('disabled', ! is_same_proposal);
        if (! is_same_proposal) {
            overwrite_checkbox.prop('checked', false);
        }

        disable_futile_labels();
    });
});
