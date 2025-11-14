$(document).ready(function () {
    $('table.review_group_membership').each(function () {
        var membership = $(this);
        enable_table_sorting(membership, false);
    });
});
