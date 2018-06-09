function reassign_sort_order(table) {
    var sort_order_max = 0;

    table.find('tr').each(function () {
        var sort_order_el = $(this).find('input[name^=sort_order]');
        if (sort_order_el.length > 0) {
            var sort_order = parseInt(sort_order_el.val());

            if (sort_order > sort_order_max) {
                sort_order_max = sort_order;
            } else {
                sort_order_max ++;
                sort_order_el.val(sort_order_max.toString());
            }
        }
    });
}

function enable_table_drag_row(table, row) {
    var row_id = row.attr('id');
    var grip = row.find('.draggrip');

    var clear_all_dragbelow = (function () {
        table.find('tr').each(function () {
            $(this).removeClass('dragbelow');
        });
    });

    if (grip.length && (typeof row_id !== 'undefined')) {
        grip.attr('draggable', true);

        grip.on('dragstart', function (evt) {
            row.addClass('dragged');
            var transfer = evt.originalEvent.dataTransfer;
            transfer.setData('text/plain', row_id);
            transfer.setDragImage(row.get(0), 10, 10);
        });

        grip.on('dragend', function (evt) {
            row.removeClass('dragged');
            clear_all_dragbelow();
        });
    }

    row.on('dragover', function (evt) {
        evt.originalEvent.dataTransfer.dropEffect = 'move';
        return false; // prevent default
    });

    row.on('dragenter', function (evt) {
        clear_all_dragbelow();
        row.addClass('dragbelow');
    });

    row.on('drop', function(evt) {
        var moved = evt.originalEvent.dataTransfer.getData('text/plain');

        if (row_id !== moved) {
            row.after($('#' + moved).detach());

            reassign_sort_order(table);
        }

        return false; // stop propagation
    });
}

function enable_table_drag(table) {
    table.find('tr').each(function () {
        enable_table_drag_row(table, $(this));
    });
}
