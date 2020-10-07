$(document).ready(function () {
    var semesterSelect = $('[name="semester_id"]').first();
    var queueSelect = $('[name="queue_id"]').first();
    var queueWarning = $('#queue_warning').first();
    var callList = [];

    var check_semester_queue = (function () {
        var semesterId = parseInt(semesterSelect.val());
        var queueId = parseInt(queueSelect.val());
        var callExists = false;
        var i;

        for (i = 0; i < callList.length; i ++) {
            if ((semesterId === callList[i][0]) && (queueId === callList[i][1])) {
                callExists = true;
            }
        }

        if (callExists) {
            queueWarning.show();
        } else {
            queueWarning.hide();
        }
    });

    if (semesterSelect.length && queueSelect.length && queueWarning.length) {
        callList = semesterSelect.data('existing');
        semesterSelect.change(check_semester_queue);
        queueSelect.change(check_semester_queue);
        check_semester_queue();
    }

    var separateBox = $('[name="separate"]').first();

    var check_preamble_visibility = (function () {
        if (separateBox.prop('checked')) {
            $('#item_preamble').show();
            $('#item_preamble_format').show();
        } else {
            $('#item_preamble').hide();
            $('#item_preamble_format').hide();
        }
    });

    separateBox.change(check_preamble_visibility);
    check_preamble_visibility();
});
