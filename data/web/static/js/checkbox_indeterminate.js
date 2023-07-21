$(document).ready(function () {
    $('input.checkbox_indeterminate').each(function () {
        var checkbox = $(this);
        var current_state = 2;
        if (checkbox.val() === 'indeterminate') {
            checkbox.prop('checked', true);
            checkbox.prop('indeterminate', true);
            checkbox.val('indeterminate');
        } else {
            current_state = checkbox.prop('checked') ? 1 : 0;
        }
        checkbox.click(function (event) {
            switch (current_state) {
                case 0:
                    current_state = 1;
                    checkbox.prop('indeterminate', false);
                    checkbox.prop('checked', true);
                    checkbox.val('yes');
                    break;
                case 1:
                    current_state = 2;
                    checkbox.prop('checked', true);
                    checkbox.prop('indeterminate', true);
                    checkbox.val('indeterminate');
                    break;
                case 2:
                    current_state = 0;
                    checkbox.prop('indeterminate', false);
                    checkbox.prop('checked', false);
                    checkbox.val('yes');
                    break;
            }
        });
    });
});
