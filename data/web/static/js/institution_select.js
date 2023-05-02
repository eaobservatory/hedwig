$(document).ready(function () {
    var institution_select = $('select#select_institution');

    $.ajax(institution_select.data('institution_list'), dataType='json'
    ).done(function (result) {
        var excluded = institution_select.data('excluded');
        if (excluded) {
            for (var i = 0; i < result.length; i ++) {
                var institution = result[i];
                if ($.inArray(institution['value'], excluded) !== -1) {
                    institution['disabled'] = true;
                }
            }
        }

        settings = {
            'options': result,
            'placeholder': 'Select an institution\u2026'
        };

        var selected_value = institution_select.data('selected');
        if (selected_value !== '') {
            settings['items'] = [selected_value];
        }

        institution_select.children().detach();
        institution_select.selectize(settings);

    }).fail(function (jqXHR, textStatus) {
        institution_select.children().detach();
        institution_select.append($('<option/>', {'text': 'Failed to load', 'value': ''}));
    });
});
