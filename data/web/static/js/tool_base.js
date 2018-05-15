$(document).ready(function () {
    var resolveButton = $('#resolve');
    if (resolveButton.length) {
        var nameResolver = resolveButton.data('resolver');
        var targetNameBox = $('[name=name]');
        var targetXBox = $('[name=x]');
        var targetYBox = $('[name=y]');
        var targetSystem = $('[name=system]');

        resolveButton.click(function () {
            resolve_target_name(nameResolver, targetNameBox, targetXBox, targetYBox, targetSystem, resolveButton);
        });
    }
});
