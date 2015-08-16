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

    var timerRunning = 0;
    var timerDuration = ((wordLimit > 250) ? 2000 : 500);

    wordArea.on('input', function () {
        if (! timerRunning) {
            timerRunning = 1;
            setTimeout((function () {
                timerRunning = 0;
                makeWordCount();
            }), timerDuration);
        }
    });
});
