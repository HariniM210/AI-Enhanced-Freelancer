/* My applications: GET /applications/my, POST /applications/{id}/withdraw */
(function () {
  "use strict";
  var UI = window.UI, Api = window.Api, Data = window.Data, user = UI.Auth.user();
  var $ = function (i) { return document.getElementById(i); };
  var apps = [], tab = "all", withdrawing = {};
  var TABS = [["all", "All"], ["pending", "Pending"], ["shortlisted", "Shortlisted"], ["accepted", "Hired"], ["rejected", "Declined"], ["withdrawn", "Withdrawn"], ["completed", "Completed"]];

  function render() {
    var by = Data.byStatus(apps), q = $("q").value.trim().toLowerCase();
    $("tabs").innerHTML = TABS.map(function (t) {
      var n = t[0] === "all" ? apps.length : by[t[0]];
      return '<button role="tab" aria-selected="' + (tab === t[0]) + '" data-tab="' + t[0] + '">' + t[1] + '<span class="count">' + n + "</span></button>";
    }).join("");
    $("tabs").querySelectorAll("button").forEach(function (b) { b.addEventListener("click", function () { tab = b.dataset.tab; render(); }); });
    var list = apps.filter(function (a) { return (tab === "all" || a.status === tab) && (!q || (Data.appProject(a).title + " " + Data.appProject(a).client).toLowerCase().indexOf(q) > -1); })
      .sort(function (a, b) { return new Date(b.created_at || 0) - new Date(a.created_at || 0); });
    var host = $("table");
    if (!apps.length) return UI.showEmpty(host, { icon: "send", title: "You haven't applied to anything yet", text: "Find a project that fits your skills and send your first proposal.", href: "projects.html", action: "Browse projects" });
    if (!list.length) return UI.showEmpty(host, { icon: "search", title: "No applications here", text: q ? "Nothing matches your search." : "No applications have this status yet." });
    host.removeAttribute("aria-busy");
    host.innerHTML = '<div class="table-wrap"><table class="table"><thead><tr><th>Project</th><th>Your bid</th><th>Submitted</th><th>Status</th><th>Match</th><th></th></tr></thead><tbody>' + list.map(function (a, i) {
      var p = Data.appProject(a);
      return '<tr><td><div class="t" style="font-weight:600"><a href="project-details.html?id=' + UI.esc(p.id) + '">' + UI.esc(p.title) + '</a></div><div class="small muted">' + UI.esc(p.client) + '</div></td><td class="num">' + (a.bid_amount != null ? UI.fmtMoney(a.bid_amount, a.currency || p.raw.currency) : "—") + '</td><td class="small">' + UI.fmtDate(a.created_at) + "</td><td>" + UI.statusBadge(a.status) + '</td><td data-slot="' + i + '"></td><td><div class="row-actions"><button class="btn btn-ghost btn-sm" data-view="' + i + '">Proposal</button>' + (a.status === "pending" || a.status === "shortlisted" ? '<button class="btn btn-danger btn-sm" data-withdraw="' + i + '">Withdraw</button>' : "") + "</div></td></tr>";
    }).join("") + "</tbody></table></div>";
    list.forEach(function (a, i) { var s = host.querySelector('[data-slot="' + i + '"]'); UI.matchChip(s, user.id, Data.appProject(a).id, Data.appProject(a).title); });
    host.querySelectorAll("[data-view]").forEach(function (b) { b.addEventListener("click", function () {
      var a = list[+b.dataset.view]; UI.modal({ title: "Your proposal — " + Data.appProject(a).title, wide: true, body: '<div class="prose" style="max-height:50vh;overflow:auto">' + UI.esc(a.cover_letter || a.proposal || "No proposal text was returned.") + "</div>" });
    }); });
    host.querySelectorAll("[data-withdraw]").forEach(function (b) {
      b.addEventListener("click", function () {
        var a = list[+b.dataset.withdraw];
        if (!a || withdrawing[a.id] || (a.status !== "pending" && a.status !== "shortlisted")) return;
        withdrawing[a.id] = true;
        b.disabled = true;
        UI.confirm({
          title: "Withdraw application?",
          body: "Are you sure you want to withdraw your application? The client will no longer consider your application for this project.",
          confirm: "Withdraw",
          danger: true
        }).then(function (ok) {
          if (!ok) {
            withdrawing[a.id] = false;
            if (b.isConnected) b.disabled = false;
            return;
          }
          var request = Api.applications.withdraw(a.id).then(function (updated) {
            a.status = (updated && updated.status) || "withdrawn";
            if (updated && updated.withdrawn_at) a.withdrawn_at = updated.withdrawn_at;
            if (tab !== "all" && tab !== "withdrawn") tab = "all";
            UI.toast("Application withdrawn successfully", "success");
            render();
          }, function (e) {
            UI.toast((e && e.message) || "Application could not be withdrawn.", "error");
          });
          UI.busy(b, request.finally(function () { withdrawing[a.id] = false; }));
        });
      });
    });
  }

  function load() {
    UI.showLoading($("table"), "list", 4);
    Api.applications.mine({ limit: 200 }).then(function (r) { apps = Api.asList(r).items; render(); }).catch(function (e) { $("tabs").innerHTML = ""; UI.showError($("table"), e, load); });
  }
  $("q").addEventListener("input", function () { if (apps.length) render(); });
  load();
})();
