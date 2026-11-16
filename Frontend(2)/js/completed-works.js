/* Completed works & active project tracking (freelancer) from GET /applications/my */
(function () {
  "use strict";
  var UI = window.UI, Api = window.Api, Data = window.Data;
  var $ = function (id) { return document.getElementById(id); };
  var STEPS = [["pending", "Applied"], ["shortlisted", "Shortlisted"], ["accepted", "Hired"], ["completed", "Delivered"]];

  function stepIndex(s) { return STEPS.map(function (x) { return x[0]; }).indexOf(s); }
  function countLabel(n) { return n + " project" + (n === 1 ? "" : "s"); }
  function projectHref(id) { return "project-details.html?id=" + UI.esc(id); }

  function statCard(key, icon, label, value, foot) {
    return '<div class="panel stat cw-stat cw-stat--' + key + '">' +
      '<div class="cw-stat-top"><span class="cw-stat-icon" aria-hidden="true">' + UI.icon(icon, 18) + '</span><span class="cw-stat-label">' + UI.esc(label) + '</span></div>' +
      '<div class="cw-stat-value">' + UI.esc(String(value)) + '</div>' +
      '<div class="cw-stat-foot">' + UI.esc(foot) + '</div>' +
    '</div>';
  }

  function track(a) {
    var p = Data.appProject(a), idx = stepIndex(a.status);
    var steps = STEPS.map(function (s, i) {
      var complete = i < idx || (i === idx && a.status === "completed");
      var current = i === idx && a.status !== "completed";
      var state = complete ? "is-complete" : current ? "is-current" : "is-upcoming";
      var marker = complete ? UI.icon("check", 12) : current ? '<span class="cw-step-dot-inner"></span>' : String(i + 1);
      var note = complete ? "Complete" : current ? "Current" : "Upcoming";
      return '<div class="cw-step ' + state + '" role="listitem"' + (current ? ' aria-current="step"' : "") + '>' +
        '<span class="cw-step-dot" aria-hidden="true">' + marker + '</span>' +
        '<span class="cw-step-label">' + UI.esc(s[1]) + '</span>' +
        '<span class="cw-step-note">' + note + '</span>' +
      '</div>';
    }).join("");
    var delivery = a.delivery_days ? a.delivery_days + " day" + (Number(a.delivery_days) === 1 ? "" : "s") + " delivery" : "Delivery schedule not set";
    var bid = a.bid_amount != null ? UI.fmtMoney(a.bid_amount, a.currency) : "";
    var client = p.client || "Client details unavailable";
    return '<article class="panel cw-project-card">' +
      '<div class="cw-project-head">' +
        '<div class="cw-project-main">' +
          '<span class="cw-project-icon" aria-hidden="true">' + UI.icon("briefcase", 18) + '</span>' +
          '<div class="cw-project-copy">' +
            '<a class="cw-project-title" href="' + projectHref(p.id) + '">' + UI.esc(p.title) + '</a>' +
            '<div class="cw-project-meta">' +
              '<span>' + UI.icon("building-2", 14) + UI.esc(client) + '</span>' +
              '<span>' + UI.icon("clock", 14) + UI.esc(delivery) + '</span>' +
              (bid ? '<span>' + UI.icon("award", 14) + UI.esc(bid) + ' contract</span>' : '') +
            '</div>' +
          '</div>' +
        '</div>' +
        '<div class="cw-project-side">' + UI.statusBadge(a.status) + '</div>' +
      '</div>' +
      '<div class="cw-progress">' +
        '<div class="cw-progress-head"><span>Delivery progress</span><span>' + Math.max(0, idx + 1) + ' of ' + STEPS.length + ' stages</span></div>' +
        '<div class="cw-steps" role="list" aria-label="Project delivery progress">' + steps + '</div>' +
      '</div>' +
    '</article>';
  }

  function doneCard(a) {
    var p = Data.appProject(a);
    var rating = a.rating ? UI.stars(a.rating) + '<span class="cw-rating-num">' + Number(a.rating).toFixed(1) + '</span>' : '<span class="cw-muted">Not rated yet</span>';
    var earned = a.bid_amount != null ? UI.fmtMoney(a.bid_amount, a.currency) : "—";
    var completed = a.completed_at ? UI.fmtDate(a.completed_at) : "";
    var review = a.review ? '<blockquote class="cw-review">' + UI.icon("quote", 16) + '<p>' + UI.esc(a.review) + '</p></blockquote>' : '<div class="cw-review cw-review-empty">' + UI.icon("message-square", 16) + '<span>No written review was left for this project.</span></div>';
    var client = p.client || "Client details unavailable";
    return '<article class="panel cw-done-card">' +
      '<div class="cw-done-head">' +
        '<div class="cw-done-title-wrap">' +
          '<span class="cw-done-icon" aria-hidden="true">' + UI.icon("badge-check", 18) + '</span>' +
          '<div class="cw-done-copy">' +
            '<a class="cw-card-title" href="' + projectHref(p.id) + '">' + UI.esc(p.title) + '</a>' +
            '<div class="cw-card-meta">' +
              '<span>' + UI.icon("building-2", 14) + UI.esc(client) + '</span>' +
              (completed ? '<span>' + UI.icon("calendar", 14) + 'Completed ' + UI.esc(completed) + '</span>' : '') +
            '</div>' +
          '</div>' +
        '</div>' +
        UI.statusBadge("completed") +
      '</div>' +
      '<div class="cw-done-metrics">' +
        '<div class="cw-metric"><span>Client rating</span><div class="cw-metric-value">' + rating + '</div></div>' +
        '<div class="cw-metric"><span>Earned</span><div class="cw-metric-value">' + UI.esc(earned) + '</div></div>' +
      '</div>' +
      review +
    '</article>';
  }

  function load() {
    $("activeCount").textContent = "—";
    $("doneCount").textContent = "—";
    $("active").className = "cw-card-grid cw-active-grid";
    $("done").className = "cw-card-grid cw-done-grid";
    UI.showLoading($("kpis"), "stats", 4);
    UI.showLoading($("active"), "card", 2);
    UI.showLoading($("done"), "card", 2);

    Api.applications.mine({ limit: 200 }).then(function (r) {
      var apps = Api.asList(r).items;
      var active = apps.filter(function (a) { return a.status === "accepted"; });
      var done = apps.filter(function (a) { return a.status === "completed"; });
      var rated = done.filter(function (a) { return a.rating; });
      var earned = done.reduce(function (s, a) { return s + (Number(a.bid_amount) || 0); }, 0);
      var avg = rated.length ? (rated.reduce(function (s, a) { return s + Number(a.rating); }, 0) / rated.length).toFixed(1) : "—";
      var cards = [
        ["completed", "folder-check", "Completed", done.length, done.length === 1 ? "project delivered" : "projects delivered"],
        ["active", "handshake", "In progress", active.length, active.length === 1 ? "active engagement" : "active engagements"],
        ["rating", "star", "Average rating", avg, rated.length ? rated.length + " rated" : "no ratings yet"],
        ["earned", "trending-up", "Earned (bids)", earned ? UI.fmtMoney(earned, (done[0] && done[0].currency) || "USD") : "—", "from completed work"]
      ];
      $("kpis").removeAttribute("aria-busy");
      $("kpis").innerHTML = cards.map(function (c) { return statCard(c[0], c[1], c[2], c[3], c[4]); }).join("");
      $("activeCount").textContent = countLabel(active.length);
      $("doneCount").textContent = countLabel(done.length);

      if (!active.length) {
        $("active").className = "cw-empty-panel";
        UI.showEmpty($("active"), { icon: "handshake", title: "No active projects", text: "When a client hires you, your active engagement and delivery progress will appear here.", href: "projects.html", action: "Find work" });
      } else {
        $("active").removeAttribute("aria-busy");
        $("active").className = "cw-card-grid cw-active-grid";
        $("active").innerHTML = active.map(track).join("");
      }

      if (!done.length) {
        $("done").className = "cw-empty-panel";
        UI.showEmpty($("done"), { icon: "folder-check", title: "No completed works yet", text: "When a client marks your work as completed, it will appear here with their rating and review.", href: "projects.html", action: "Browse projects" });
      } else {
        $("done").removeAttribute("aria-busy");
        $("done").className = "cw-card-grid cw-done-grid";
        $("done").innerHTML = done.map(doneCard).join("");
      }
    }).catch(function (e) {
      $("kpis").removeAttribute("aria-busy");
      $("kpis").innerHTML = "";
      $("active").className = "cw-empty-panel";
      UI.showError($("active"), e, load);
      $("done").className = "cw-empty-panel";
      UI.showEmpty($("done"), { icon: "folder-check", title: "Completed works unavailable", text: "We couldn't load your delivered projects. Use Try again above to reload." });
    });
  }

  load();
})();
