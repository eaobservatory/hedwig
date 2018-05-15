function decimal_to_dms(decimal, divisor, dp) {
    var deg = decimal / divisor;
    var sign = '';

    if (deg < 0) {
        sign = '-';
        deg = Math.abs(deg);
    }

    var int_deg = Math.floor(deg);

    var min = 60.0 * (deg - int_deg);
    var int_min = Math.floor(min);

    var sec = 60.0 * (min - int_min);

    var str_deg = int_deg.toString();
    if (str_deg.length < 2) {
        str_deg = '0' + str_deg;
    }

    var str_min = int_min.toString();
    if (str_min.length < 2) {
        str_min = '0' + str_min;
    }

    var str_sec = sec.toFixed(dp);
    if (sec < 10) {
        str_sec = '0' + str_sec;
    }

    return sign + str_deg + ':' + str_min + ':' + str_sec;
}

function resolve_target_name(nameResolver, targetNameBox, targetXBox, targetYBox, targetSystem, resolveButton) {
    var targetName = targetNameBox.val();
    if (targetName === '') {
        return;
    }

    resolveButton.prop('disabled', true);
    targetNameBox.prop('disabled', true);
    targetXBox.prop('disabled', true);
    targetYBox.prop('disabled', true);
    targetSystem.prop('disabled', true);
    targetXBox.val('');
    targetYBox.val('');

    $.ajax(nameResolver + '?' + $.param({'target': targetName, 'format': 'json'}),
           dataType='json'
    ).done(function (result) {
        targetXBox.val(decimal_to_dms(result['ra'], 15.0, 2));
        targetYBox.val(decimal_to_dms(result['dec'], 1.0, 1));
        targetSystem.val('1');
    }).fail(function (jqXHR, textStatus) {
        alert('Target "' + targetName + '" was not found.');
    }).always(function () {
        targetNameBox.prop('disabled', false);
        targetXBox.prop('disabled', false);
        targetYBox.prop('disabled', false);
        targetSystem.prop('disabled', false);
        resolveButton.prop('disabled', false);
    });
}
