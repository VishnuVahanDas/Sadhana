// "More" bottom sheet.
document.addEventListener("click", function (event) {
  var sheet = document.getElementById("more-sheet");
  if (!sheet) return;
  if (event.target.closest("[data-more-toggle]")) {
    var open = sheet.classList.toggle("hidden") === false;
    document.querySelectorAll("[data-more-toggle]").forEach(function (button) {
      button.setAttribute("aria-expanded", open ? "true" : "false");
    });
  } else if (event.target.closest("[data-more-close]")) {
    sheet.classList.add("hidden");
  }
});

// Toasts fade away on their own.
setTimeout(function () {
  document.querySelectorAll("[data-toast]").forEach(function (toast) {
    toast.remove();
  });
}, 5000);
