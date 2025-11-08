$(document).ready(function () {
    var members = $('table#group_members');

    members.stickyTableHeaders();
    enable_table_sorting(members, false);
});
