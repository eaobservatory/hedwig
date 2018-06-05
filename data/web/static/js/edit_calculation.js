$(document).ready(function () {
    var proposal_id = $('[name=proposal_id]');
    var original_proposal = $('[name=for_proposal_id]').val();
    var proposal_checkbox = $('[name=calculation_overwrite]');


    var reviewer_id = $('[name=reviewer_id]');
    var original_reviewer = $('[name=for_reviewer_id]').val();
    var review_checkbox = $('[name=review_calculation_overwrite]');

    var check_same_proposal = (function (overwrite_checkbox, id_field, id_value) {
        var is_same_proposal = (id_field.val() === id_value);
        overwrite_checkbox.prop('disabled', ! is_same_proposal);
        if (! is_same_proposal) {
            overwrite_checkbox.prop('checked', false);
        }

        disable_futile_labels();
    });

    var check_proposal_overwrite = (function () {
        check_same_proposal(proposal_checkbox, proposal_id, original_proposal);
    });

    var check_review_overwrite = (function () {
        check_same_proposal(review_checkbox, reviewer_id, original_reviewer);
    });

    reviewer_id.change(check_review_overwrite);
    proposal_id.change(check_proposal_overwrite);

    check_proposal_overwrite();
    check_review_overwrite();
});
