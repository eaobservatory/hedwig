$(document).ready(function () {
    var wordArea = $('[name="text"]').first();
    var wordLimit = parseInt(wordArea.data('wordlimit'), 10);
    var wordCount = $('#text_words').first();

    var makeWordCount = (function () {
        var words = wordArea.val().split(/\s+/).length;
        wordCount.text(words + ' / ' + wordLimit + ' words');
        if (words > wordLimit) {
            wordCount.removeClass('forminfo_ok').addClass('forminfo_bad');
        } else {
            wordCount.removeClass('forminfo_bad').addClass('forminfo_ok');
        }
    });

    makeWordCount();

    $('[name="text"]').on('input', makeWordCount);
});
