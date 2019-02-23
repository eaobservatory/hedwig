$(document).ready(function() {
    var old_proposal = $('[name=proposal_id]');

    if (old_proposal.length) {
        var member_copy = $('[name=member_copy]');
        var queue_id = member_copy.data('queue_id');

        var check_old_proposal = (function() {
            var is_same_queue = (old_proposal.find(':selected').data('queue_id') === queue_id);
            member_copy.prop('disabled', (! is_same_queue));
            if (! is_same_queue) {
                member_copy.prop('checked', false);
            }
        });

        old_proposal.change(check_old_proposal);

        check_old_proposal();
    }
});
