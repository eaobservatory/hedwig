$(document).ready(function() {
    var decision_accept = $('[name=decision_accept]');
    var decision_exempt = $('[name=decision_exempt]');

    var check_exempt_opt = (function() {
        var is_accepted = decision_accept.prop('checked');
        decision_exempt.prop('disabled', (! is_accepted));
        if (! is_accepted) {
            decision_exempt.prop('checked', false);
        }

        disable_futile_labels();
    });

    decision_accept.change(check_exempt_opt);

    check_exempt_opt();
});
