/* Client dashboard: GET /projects?mine=true, GET /applications/my, GET /freelancers */
(function () {
  "use strict";
  var UI = window.UI, Api = window.Api, Data = window.Data, user = UI.Auth.user();
  var $ = function (id) { return document.getElementById(id); };
  $("hello").textContent = Data.greeting() + ", " + Data.firstName(user.name);

  function load() {
    UI.showLoading($("statRow"), "stats", 4);
    UI.showLoading($("projTable"), "list", 3);
    UI.showLoading($("topApplicants"), "list", 2);
    UI.showLoading($("talent"), "list", 2);
    Promise.allSettled([Api.projects.list({ mine: "true", limit: 50 }), Api.applications.mine({ limit: 200 }), Api.freelancers.list({ limit: 5, sort: "rating" })]).then(function (r) {
      var projects = [], apps = [], pTotal = 0;
      var pOk = r[0].status === "fulfilled", aOk = r[1].status === "fulfilled";
      if (pOk) { var pl = Api.asList(r[0].value); projects = pl.items; pTotal = pl.total; }
      if (aOk) apps = Api.asList(r[1].value).items;

      if (pOk && aOk) {
        var by = Data.byStatus(apps);
        $("statRow").innerHTML = [
          ["briefcase", "Posted projects", pTotal, projects.filter(function (p) { return (p.status || "open") === "open"; }).length + " open for proposals"],
          ["users", "Total applications", apps.length, by.pending + " to review"],
          ["handshake", "Active hiring", by.accepted, by.shortlisted + " shortlisted"],
          ["badge-check", "Completed", by.completed, "projects delivered"]
        ].map(function (s) { return '<div class="panel stat"><div class="k">' + UI.icon(s[0], 16) + s[1] + '</div><div class="v">' + s[2] + '</div><div class="s">' + s[3] + "</div></div>"; }).join("");
        $("heroSub").textContent = by.pending ? by.pending + " application" + (by.pending === 1 ? " is" : "s are") + " waiting for your review." : "You're all caught up on applicants.";
        renderPipeline(by);
      } else {
        var e = (pOk ? r[1] : r[0]).reason; UI.showError($("statRow"), e, load); $("statRow").style.display = "block";
        $("heroSub").textContent = "We couldn't reach the server, so some figures are unavailable."; $("pipeline").innerHTML = "";
      }

      if (!pOk) UI.showError($("projTable"), r[0].reason, load);
      else if (!projects.length) UI.showEmpty($("projTable"), { icon: "briefcase", title: "You haven't posted a project yet", text: "Describe what you need and qualified freelancers will start sending proposals.", href: "post-project.html", action: "Post your first project" });
      else renderProjects(projects, apps);

      if (!aOk) UI.showError($("topApplicants"), r[1].reason, load);
      else renderTop(apps, projects);

      if (r[2].status === "rejected") UI.showError($("talent"), r[2].reason, load);
      else renderTalent(Api.asList(r[2].value).items);
    });
  }

  function renderPipeline(by) {
    var rows = [["Pending review", by.pending, "#a8730f"], ["Shortlisted", by.shortlisted, "#2f5f8f"], ["Hired", by.accepted, "#1f7a55"], ["Completed", by.completed, "#0e6b6b"]];
    var max = Math.max.apply(null, rows.map(function (x) { return x[1]; }).concat([1]));
    $("pipeline").innerHTML = rows.map(function (x) {
      return '<div class="match-bar pipeline-row"><span>' + x[0] + '</span><div class="progress"><i style="width:' + (x[1] / max * 100) + "%;background:" + x[2] + '"></i></div><span class="num">' + x[1] + "</span></div>";
    }).join("");
  }

  function renderProjects(projects, apps) {
    var counts = {}; apps.forEach(function (a) { var id = Data.appProject(a).id; counts[id] = (counts[id] || 0) + 1; });
    $("projTable").removeAttribute("aria-busy");
    $("projTable").innerHTML = '<div class="table-wrap dash-table-wrap"><table class="table"><thead><tr><th>Project</th><th>Status</th><th>Applicants</th><th>Budget</th><th>Posted</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>' +
      projects.slice(0, 6).map(function (p) {
        var n = p.applications_count != null ? p.applications_count : counts[p.id] || 0;
        return '<tr><td class="project-cell"><div class="cell-user"><div><div class="t"><a href="project-details.html?id=' + UI.esc(p.id) + '" title="' + UI.esc(p.title) + '">' + UI.esc(p.title) + '</a></div><div class="small muted project-category">' + UI.esc(p.category || "") + '</div></div></div></td><td class="status-cell" data-label="Status">' + UI.statusBadge(p.status || "open") + '</td><td class="num applicants-cell" data-label="Applicants">' + n + '</td><td class="num budget-cell" data-label="Budget">' + UI.esc(UI.budget(p).text) + '</td><td class="small muted posted-cell" data-label="Posted">' + UI.relTime(p.created_at) + '</td><td class="actions-cell"><div class="row-actions"><a class="btn btn-secondary btn-sm" href="applicants.html?project=' + UI.esc(p.id) + '">Manage</a></div></td></tr>';
      }).join("") + "</tbody></table></div>" + (projects.length > 6 ? '<div class="pager dash-pager"><span>Showing 6 of ' + projects.length + '</span><a href="projects.html?mine=1">View all projects</a></div>' : "");
  }

  function renderTop(apps, projects) {
    var pending = apps.filter(function (a) { return a.status === "pending" || a.status === "shortlisted"; })
      .sort(function (a, b) { return new Date(b.created_at || 0) - new Date(a.created_at || 0); }).slice(0, 4);
    if (!pending.length) return UI.showEmpty($("topApplicants"), { icon: "users", title: "No applicants to review", text: "New proposals will appear here with their ML match prediction.", href: "post-project.html", action: "Post a project" });
    $("topApplicants").removeAttribute("aria-busy");
    $("topApplicants").innerHTML = '<ul class="list">' + pending.map(function (a, i) {
      var f = Data.appFreelancer(a), p = Data.appProject(a);
      return '<li class="dashboard-applicant">' + UI.avatar(f.name, "sm") + '<div class="grow"><a class="title" href="profile.html?id=' + UI.esc(f.id) + '">' + UI.esc(f.name) + '</a><span class="small muted applicant-project">for ' + UI.esc(p.title) + '</span><div class="match-slot" data-slot="' + i + '"></div></div><a class="btn btn-ghost btn-sm applicant-review" href="applicants.html?project=' + UI.esc(p.id) + '">Review</a></li>';
    }).join("") + "</ul>";
    pending.forEach(function (a, i) {
      var run = UI.matchChip($("topApplicants").querySelector('[data-slot="' + i + '"]'), Data.appFreelancer(a).id, Data.appProject(a).id, Data.appFreelancer(a).name);
      if (run) run();
    });
  }

  function renderTalent(list) {
    if (!list.length) return UI.showEmpty($("talent"), { icon: "users", title: "No freelancers to show yet", text: "Top-rated freelancers will be listed here." });
    $("talent").removeAttribute("aria-busy");
    $("talent").innerHTML = '<ul class="list">' + list.slice(0, 5).map(function (f) {
      return '<li>' + UI.avatar(f.name, "", f.avatar_url) + '<div class="grow"><a class="title" href="profile.html?id=' + UI.esc(f.id) + '">' + UI.esc(f.name) + '</a><span class="small muted talent-headline">' + UI.esc(f.headline || "") + "</span></div>" + (f.avg_rating ? '<span class="small num talent-rating">' + UI.icon("star", 14).replace('fill="none"', 'fill="#a8730f"') + Number(f.avg_rating).toFixed(1) + "</span>" : "") + "</li>";
    }).join("") + "</ul>";
  }
  load();
})();
