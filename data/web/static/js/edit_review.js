$(document).ready(function () {
    var doneCheckbox = $('input[name="done"]');
    var submitButton = $('input[name="submit"]');

    var check_done = (function () {
        var is_done = doneCheckbox.prop('checked');
        submitButton.val(is_done ? 'Save and mark as done' : 'Save as a draft');
        $('input.req_if_done').prop('required', is_done);
    });

    doneCheckbox.change(check_done);
    check_done();
});
