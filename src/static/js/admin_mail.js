$(function () {
    $('.selectpicker').selectpicker();
});


function sendAdminMail() {
    let data = {
        subject: $("#subject").val(),
        content: $("#content").val(),
        receiver: $("#receivers").selectpicker("val"),
        additions: $("#additions").selectpicker("val")
    };

    $("#modal-info").text("Loading..")
    $.ajax({
        url: "admin-mail",
        method: "POST",
        data: JSON.stringify(data),
        contentType: 'application/json',
        success: function (message) {
            $("#modal").modal("hide");
            $("#modal-info").text("")
            alert(`${message.sent} mails sent`);
        },
        error: function (message) {
            $("#modal-info").text("Error occurred: " + message["responseJSON"]["message"])
        }
    });
}

