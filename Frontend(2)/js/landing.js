/* Landing page: live project discovery (GET /projects). Marketing copy is static; project data is not. */
(function () {
  "use strict";
  var UI = window.UI, Api = window.Api, REF = window.REF;
  var host = document.getElementById("discover"), chips = document.getElementById("cats");
  var all = [], cat = "";

  chips.innerHTML = ['All'].concat(REF.categories).map(function (c) { return '<button class="cat" aria-pressed="' + (c === "All") + '" data-c="' + (c === "All" ? "" : UI.esc(c)) + '">' + UI.esc(c) + "</button>"; }).join("");
  chips.addEventListener("click", function (e) {
    var b = e.target.closest(".cat"); if (!b) return;
    cat = b.dataset.c; chips.querySelectorAll(".cat").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); }); render();
  });

  function render() {
    var list = all.filter(function (p) { return !cat || p.category === cat; }).slice(0, 6);
    if (!all.length) return UI.showEmpty(host, { icon: "compass", title: "No open projects yet", text: "Be the first to post one — freelancers are ready to respond.", href: "register.html?role=client", action: "Post a project" });
    if (!list.length) return UI.showEmpty(host, { icon: "search", title: "Nothing open in " + cat, text: "Try another category or browse everything.", href: "projects.html", action: "Browse all projects" });
    host.removeAttribute("aria-busy");
    host.innerHTML = '<div class="job-list">' + list.map(function (p) { return UI.jobCard(p, { actions: '<a class="btn btn-secondary btn-sm" href="project-details.html?id=' + UI.esc(p.id) + '">View project</a>' }); }).join("") + "</div>";
  }
  function load() {
    UI.showLoading(host, "card", 3);
    Api.projects.list({ status: "open", limit: 24, sort: "recent" }).then(function (r) { all = Api.asList(r).items; render(); }).catch(function (e) { UI.showError(host, e, load); });
  }
  load();
})();
