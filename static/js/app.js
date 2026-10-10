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

// Entry form: "+15 / +30" chips add minutes to their field.
document.addEventListener("click", function (event) {
  var chip = event.target.closest("[data-add]");
  if (!chip) return;
  var input = document.getElementById(chip.getAttribute("data-target"));
  if (!input) return;
  var total = (parseInt(input.value, 10) || 0) + parseInt(chip.getAttribute("data-add"), 10);
  var max = parseInt(input.getAttribute("max"), 10);
  input.value = isNaN(max) ? total : Math.min(total, max);
});

// Entry form: picking a date opens that day's entry.
document.addEventListener("change", function (event) {
  var picker = event.target.closest("[data-entry-date]");
  if (!picker || !picker.value) return;
  window.location.href = picker.getAttribute("data-entry-date").replace("0000-00-00", picker.value);
});

// Ask before deleting.
document.addEventListener("submit", function (event) {
  var message = event.target.getAttribute("data-confirm");
  if (message && !window.confirm(message)) event.preventDefault();
});

// Filters: a select marked data-autosubmit submits its form when changed.
document.addEventListener("change", function (event) {
  if (event.target.matches("[data-autosubmit]")) event.target.form.submit();
});

// Sortable tables: tap a heading to sort by that column; tap again to reverse.
document.addEventListener("click", function (event) {
  var header = event.target.closest("table[data-sortable] th[data-sort]");
  if (!header) return;
  var table = header.closest("table");
  var body = table.tBodies[0];
  var index = Array.prototype.indexOf.call(header.parentNode.children, header);
  var numeric = header.getAttribute("data-sort") === "number";
  var current = header.getAttribute("aria-sort");
  var ascending = current ? current === "descending" : !numeric;
  var rows = Array.prototype.slice.call(body.rows).filter(function (row) { return row.cells.length > index; });
  rows.sort(function (a, b) {
    var x = a.cells[index].textContent.trim();
    var y = b.cells[index].textContent.trim();
    var result = numeric ? (parseFloat(x) || 0) - (parseFloat(y) || 0) : x.localeCompare(y);
    return ascending ? result : -result;
  });
  rows.forEach(function (row) { body.appendChild(row); });
  table.querySelectorAll("th[aria-sort]").forEach(function (other) { other.removeAttribute("aria-sort"); });
  header.setAttribute("aria-sort", ascending ? "ascending" : "descending");
});
