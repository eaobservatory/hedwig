$(document).ready(function () {
    var country_select = $('select[name=country_code]');

    $.ajax(country_select.data('country_list'), dataType='json'
    ).done(function (result) {
        settings = {
            'options': result,
            'placeholder': 'Select a country\u2026'
        };

        var selected_value = country_select.data('selected');
        if (selected_value !== '') {
            settings['items'] = [selected_value];
        }

        country_select.children().detach();
        country_select.selectize(settings);

    }).fail(function (jqXHR, textStatus) {
        country_select.children().detach();
        country_select.append($('<option/>', {'text': 'Failed to load', 'value': ''}));
    });
});
