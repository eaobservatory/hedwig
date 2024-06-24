$(document).ready(function () {
    var person_select = $('select#select_person');

    $.ajax(person_select.data('person_list'), dataType='json'
    ).done(function (result) {
        var excluded = person_select.data('excluded');
        if (excluded) {
            for (var i = 0; i < result.length; i ++) {
                var person = result[i];
                if ($.inArray(person['value'], excluded) !== -1) {
                    person['disabled'] = true;
                }
            }
        }

        settings = {
            'options': result,
            'placeholder': 'Select a person\u2026',
            'searchField': ['text_full', 'text_abbr']
        };

        var selected_value = person_select.data('selected');
        if (selected_value !== '') {
            settings['items'] = [selected_value];
        }

        person_select.children().detach();
        person_select.selectize(settings);

    }).fail(function (jqXHR, textStatus) {
        person_select.children().detach();
        person_select.append($('<option/>', {'text': 'Failed to load', 'value': ''}));
    });
});
