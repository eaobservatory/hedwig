function addTargetRow(newRowNumber) {
    var nid = 'new_' + newRowNumber;
    var newrow = $('#targetrow_template').clone();
    newrow.attr('id', 'targetrow_' + nid);
    newrow.find('[name=name]').attr('name', 'name_' + nid);
    newrow.find('[name=x]').attr('name', 'x_' + nid);
    newrow.find('[name=y]').attr('name', 'y_' + nid);
    newrow.find('[name=system]').attr('name', 'system_' + nid);
    newrow.find('[name=time]').attr('name', 'time_' + nid);
    newrow.find('[name=priority]').attr('name', 'priority_' + nid);
    var deletelink = newrow.find('#delete_template');
    deletelink.attr('id', 'delete_' + nid);
    deletelink.click(function (event) {
        deleteTargetRow(nid);
    });
    var resolvebutton = newrow.find('#resolve_template');
    resolvebutton.attr('id', 'resolve_' + nid);
    resolvebutton.click(function (event) {
        resolveTargetName(nid);
    });
    newrow.appendTo($('table#targets'));
}

function deleteTargetRow(targetid) {
    $('#targetrow_' + targetid).remove();
}

function decimalToDMS(decimal, divisor, dp) {
    var deg = parseFloat(decimal) / divisor;
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

function resolveTargetName(targetid) {
    var targetNameBox = $('[name=name_' + targetid + ']');
    var targetXBox = $('[name=x_' + targetid + ']');
    var targetYBox = $('[name=y_' + targetid + ']');
    var targetSystem = $('[name=system_' + targetid + ']');
    var resolveButton = $('#resolve_' + targetid);
    var targetName = targetNameBox.val();
    resolveButton.prop('disabled', true);
    targetNameBox.prop('disabled', true);
    targetXBox.prop('disabled', true);
    targetYBox.prop('disabled', true);
    targetSystem.prop('disabled', true);
    targetXBox.val('');
    targetYBox.val('');

    $.ajax('/query/nameresolver?' + $.param({'target': targetName, 'format': 'xml'}),
           dataType='xml'
    ).done(function (xml) {
        targetXBox.val(decimalToDMS($(xml).find('ra').text(), 15.0, 2));
        targetYBox.val(decimalToDMS($(xml).find('dec').text(), 1.0, 1));
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

$(document).ready(function () {
    var newRowCounter = 1;

    $('#add_target').click(function (event) {
        addTargetRow(newRowCounter ++);
    });

    $('[id^="delete_"]').click(function (event) {
        var targetid = event.target.id.replace('delete_', '');
        deleteTargetRow(targetid);
    });

    $('[id^="resolve_"]').click(function (event) {
        var targetid = event.target.id.replace('resolve_', '');
        resolveTargetName(targetid);
    });
});
