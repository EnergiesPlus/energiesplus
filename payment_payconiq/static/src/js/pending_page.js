(function() {
    function loadFeedbackPoll() {
        let url = "/payment/payconiq/feedback/" + String($("input[name='webhookId']").val());
        $.ajax({
            type: "POST",
            url: url,
            success: function(data) {
                window.location = "/payment/process"
            },
            timeout: 500000
        });
    }
    function isIOS(){
        if (/iphone|XBLWP7/i.test(navigator.userAgent.toLowerCase())) {
            return true;
        }
        else
            return false;
    }
    function isAndroid(){
        if (/android|XBLWP7/i.test(navigator.userAgent.toLowerCase())) {
            return true;
        }
        else
            return false;
    }
    loadFeedbackPoll();
})();

function createPayconiqUniversalLink(){
      var deeplinkUrl = $("input[name='deeplinkUrl']").val();
      var returnUrl = "?returnUrl=" + String($("input[name='returnUrl']").val());
      window.location = deeplinkUrl.concat(returnUrl);
}