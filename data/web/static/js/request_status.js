$(document).ready(function () {
    var status_box = $('div#request_status');
    var query_url = status_box.data('query_url');
    var redirect_url = status_box.data('redirect_url');

    var status_field = $('<td>Loading&hellip;</td>');
    var countdown_field = $('<td colspan="2" class="countdown"></td>');

    var create_panel = (function () {
        status_box.empty();

        var table = $('<table class="request_status"></table>');
        status_box.append(table);

        var row = $('<tr><th>Request status</th></tr>');
        row.append(status_field);

        table.append(row);

        row = $('<tr></tr>');
        row.append(countdown_field);

        table.append(row);
    });

    create_panel();

    var update_status = (function (request) {
        status_field.text(request.state_name);

        if (request.is_ready) {
            if (redirect_url === undefined) {
                redirect_url = request.redirect_url;
            }
            window.location.href = redirect_url;
        } else if (request.is_pre_ready) {
            schedule_countdown();
        }
    });

    var query_status = (function () {
        status_field.html('Checking&hellip;');

        $.ajax(
            query_url, dataType='json'
        ).done(function (result) {
            update_status(result);
        }).fail(function (jqXHR, textStatus) {
            status_field.text('Unable to check status.');
        });
    });

    var countdown_timer = 10;

    var update_countdown = (function () {
        countdown_field.html(' &bull; '.repeat(countdown_timer));
    });

    var countdown_check = (function() {
        countdown_timer --;

        if (countdown_timer < 1) {
            countdown_timer = 10;
            query_status();
        }
        else {
            schedule_countdown();
        }

        update_countdown();
    });

    var schedule_countdown = (function () {
        setTimeout(countdown_check, 1000);
    });

    update_countdown();
    update_status(status_box.data('dynamic'));
});
