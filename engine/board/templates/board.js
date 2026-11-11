(function () {
  var toast = document.createElement("div");
  toast.className = "toast";
  toast.setAttribute("role", "status");
  document.body.appendChild(toast);
  var timer;
  function show(message) {
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(timer);
    timer = setTimeout(function () { toast.classList.remove("show"); }, 2200);
  }
  function copy(text, done) {
    function fallback() {
      var area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try { document.execCommand("copy"); done(); } catch (e) { show("Copy failed."); }
      document.body.removeChild(area);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else {
      fallback();
    }
  }
  document.body.addEventListener("click", function (event) {
    var button = event.target.closest("[data-copy-text]");
    if (button) {
      event.preventDefault();
      copy(button.getAttribute("data-copy-text"), function () { show("Copied."); });
      return;
    }
    button = event.target.closest("[data-hermes-send]");
    if (button) {
      event.preventDefault();
      var prompt = button.getAttribute("data-hermes-send");
      var status = button.closest(".actions").querySelector(".hermes-status");
      if (window.hermes && typeof window.hermes.send === "function") {
        status.textContent = "Sending to Hermes...";
        window.hermes.send(prompt).then(function (result) {
          status.textContent = "Sent. " + String(result);
        }).catch(function () { status.textContent = "Send failed."; });
      } else {
        copy(prompt, function () {
          show("Copied. Paste it to Hermes.");
          status.textContent = "Copied to clipboard.";
        });
      }
      return;
    }
    button = event.target.closest("[data-toggle-safe-area]");
    if (button) {
      var area = button.closest(".stage").querySelector(".safe");
      if (area) {
        area.classList.toggle("show");
        button.textContent = area.classList.contains("show") ? "Hide safe area" : "Show safe area";
      }
    }
  });
})();
