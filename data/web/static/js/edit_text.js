function makeWordCount() {
    var wordArea = $('[name="text"]');
    var words = wordArea.val().split(/\s+/).length;
    var wordLimit = parseInt(wordArea.data('wordlimit'), 10);
    var wordCount = $('#text_words');
    wordCount.text(words + ' / ' + wordLimit + ' words');
    if (words > wordLimit) {
        wordCount.removeClass('forminfo_ok').addClass('forminfo_bad');
    } else {
        wordCount.removeClass('forminfo_bad').addClass('forminfo_ok');
    }
}

$(document).ready(function () {
    makeWordCount();
    $('[name="text"]').on('input', makeWordCount);
});
