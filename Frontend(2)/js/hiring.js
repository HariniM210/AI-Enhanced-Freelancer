/* Client: hiring management & project tracking. Accepted → Completed (PUT /applications/{id}/status). */
(function () {
  "use strict";
  var UI = window.UI, Api = window.Api, Data = window.Data;
  var $ = function (i) { return document.getElementById(i); };
  var apps = [], tab = "accepted";

  function render() {
    var by = Data.byStatus(apps);
    $("tabs").innerHTML = [["accepted", "Active hires", by.accepted], ["completed", "Completed", by.completed]].map(function (t) { return '<button role="tab" aria-selected="' + (tab === t[0]) + '" data-tab="' + t[0] + '">' + t[1] + '<span class="count">' + t[2] + "</span></button>"; }).join("");
    $("tabs").querySelectorAll("button").forEach(function (b) { b.addEventListener("click", function () { tab = b.dataset.tab; render(); }); });
    var list = apps.filter(function (a) { return a.status === tab; }), host = $("list");
    var spend = apps.filter(function (a) { return a.status === "accepted" || a.status === "completed"; }).reduce(function (s, a) { return s + (Number(a.bid_amount) || 0); }, 0);
    $("kpis").innerHTML = [["handshake", "Active hires", by.accepted, "in progress"], ["badge-check", "Completed", by.completed, "delivered"], ["indian-rupee", "Committed spend", spend ? UI.fmtMoney(spend, (apps[0] && apps[0].currency) || "USD") : "—", "from accepted bids"]]
      .map(function (s) { return '<div class="panel stat"><div class="k">' + UI.icon(s[0], 16) + s[1] + '</div><div class="v">' + s[2] + '</div><div class="s">' + s[3] + "</div></div>"; }).join("");
    if (!list.length) return UI.showEmpty(host, tab === "accepted" ? { icon: "handshake", title: "No active hires", text: "Hire a freelancer from your applicants and track their delivery here.", href: "applicants.html", action: "Review applicants" } : { icon: "badge-check", title: "Nothing completed yet", text: "Projects you mark as completed will be archived here." });
    host.removeAttribute("aria-busy");
    host.innerHTML = '<div class="table-wrap"><table class="table"><thead><tr><th>Freelancer</th><th>Project</th><th>Agreed bid</th><th>Delivery</th><th>' + (tab === "completed" ? "Rating" : "Status") + '</th><th></th></tr></thead><tbody>' + list.map(function (a, i) {
      var f = Data.appFreelancer(a), p = Data.appProject(a);
      return '<tr><td><div class="cell-user">' + UI.avatar(f.name, "sm") + '<div><div class="t"><a href="profile.html?id=' + UI.esc(f.id) + '">' + UI.esc(f.name) + '</a></div><div class="small muted">' + UI.esc(f.headline) + '</div></div></div></td><td><a href="project-details.html?id=' + UI.esc(p.id) + '">' + UI.esc(p.title) + '</a></td><td class="num">' + (a.bid_amount != null ? UI.fmtMoney(a.bid_amount, a.currency) : "—") + '</td><td class="small">' + (a.delivery_days ? a.delivery_days + " days" : "—") + "</td><td>" + (tab === "completed" ? (a.rating ? UI.stars(a.rating) : '<span class="small muted">Not rated</span>') : UI.statusBadge(a.status)) + '</td><td><div class="row-actions">' + (tab === "accepted" ? '<button class="btn btn-primary btn-sm" data-done="' + i + '">' + UI.icon("check", 14) + "Mark completed</button>" : "") + "</div></td></tr>";
    }).join("") + "</tbody></table></div>";
    host.querySelectorAll("[data-done]").forEach(function (b) { b.addEventListener("click", function () { complete(list[+b.dataset.done]); }); });
  }

  function complete(a) {
    var f = Data.appFreelancer(a), p = Data.appProject(a);
    var m = UI.modal({ title: "Complete project", body: '<p class="text-2" style="margin-bottom:16px">Confirm that <b>' + UI.esc(f.name) + '</b> has delivered <b>' + UI.esc(p.title) + '</b>. This will archive the project in your completed work.</p>', footer: '<button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" data-ok>Mark completed</button>' });
    var ok = m.el.querySelector("[data-ok]");
    ok.addEventListener("click", function () {
        // Prompt for rating and optional review when completing
        var rating = parseInt(prompt('Enter a rating (1-5 stars) for this freelancer:', '5'), 10);
        if (isNaN(rating) || rating < 1 || rating > 5) {
          UI.toast('Invalid rating. Completion cancelled.', 'error');
          return;
        }
        var review = prompt('Enter an optional review (or leave blank):', '');
        var extra = { rating: rating };
        if (review) extra.review = review;
        UI.busy(ok, Api.applications.updateStatus(a.id, "completed", extra).then(function (updated) {
          Object.assign(a, updated || {});
          a.status = "completed";
          m.close();
          UI.toast("Project marked as completed.", "success");
          render();
        })).catch(function (e) { UI.toast(e.isNetwork ? "Can't reach the server. Nothing was saved." : e.message, "error"); });
    });
  }

  function load() {
    UI.showLoading($("list"), "list", 3);
    Api.applications.mine({ limit: 500 }).then(function (r) { apps = Api.asList(r).items; render(); }).catch(function (e) { $("kpis").innerHTML = ""; $("tabs").innerHTML = ""; UI.showError($("list"), e, load); });
  }
  load();
})();
