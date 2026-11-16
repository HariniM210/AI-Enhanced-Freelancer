/* Project marketplace: GET /projects, then search / filter / sort on the loaded data. */
(function () {
  "use strict";
  var UI = window.UI, Api = window.Api, Data = window.Data, REF = window.REF;
  var user = UI.Auth.user(), role = user && user.role, mine = role === "client" && !!UI.qs("mine");
  var $ = function (id) { return document.getElementById(id); };
  var all = [], mySkills = [], shown = 10, PAGE = 10, appliedIds = [];

  if (mine) { $("pageTitle").textContent = "My projects"; $("pageSub").textContent = "Everything you've posted, with the status of each hiring process."; $("crumbCurrent").textContent = "My projects"; }
  else if (role === "client") $("pageSub").textContent = "See what other clients are posting. Use the filters to narrow it down.";
  if (role === "client") { $("headActions").innerHTML = '<a class="btn btn-primary" href="post-project.html">' + UI.icon("plus", 16) + "Post a project</a>"; }

  $("fCategory").innerHTML = '<option value="">All categories</option>' + REF.categories.map(function (c) { return "<option>" + UI.esc(c) + "</option>"; }).join("");
  $("fLevel").innerHTML = '<option value="">Any level</option>' + REF.levels.map(function (c) { return "<option>" + c + "</option>"; }).join("");
  var skillFilter = UI.tagInput($("fSkills"), { suggestions: REF.skills, placeholder: "e.g. Python", label: "Filter by skill" });
  if (UI.qs("category")) $("fCategory").value = UI.qs("category");
  if (UI.qs("q")) $("q").value = UI.qs("q");

  function filtered() {
    var q = $("q").value.trim().toLowerCase(), cat = $("fCategory").value, lvl = $("fLevel").value;
    var min = parseFloat($("fMin").value), max = parseFloat($("fMax").value), sk = skillFilter.get().map(function (s) { return s.toLowerCase(); });
    var openOnly = $("fOpen").checked;
    var out = all.filter(function (p) {
      if (q && (p.title + " " + p.description + " " + (p.skills || []).join(" ") + " " + (p.category || "")).toLowerCase().indexOf(q) < 0) return false;
      if (cat && p.category !== cat) return false;
      if (lvl && p.experience_level !== lvl) return false;
      var hi = p.budget_max != null ? p.budget_max : p.budget, lo = p.budget_min != null ? p.budget_min : p.budget;
      if (!isNaN(min) && hi != null && hi < min) return false;
      if (!isNaN(max) && lo != null && lo > max) return false;
      if (sk.length && !(p.skills || []).some(function (s) { return sk.indexOf(s.toLowerCase()) > -1; })) return false;
      if (openOnly && !mine && (p.status || "open") !== "open") return false;
      return true;
    });
    var sort = $("sort").value;
    out.sort(function (a, b) {
      if (sort === "budget") return (b.budget_max || b.budget || 0) - (a.budget_max || a.budget || 0);
      if (sort === "deadline") return new Date(a.deadline || "2999-01-01") - new Date(b.deadline || "2999-01-01");
      if (sort === "skills" && mySkills.length) return Data.overlap(mySkills, b.skills).length - Data.overlap(mySkills, a.skills).length;
      return new Date(b.created_at || 0) - new Date(a.created_at || 0);
    });
    return out;
  }

  function actionsFor(p) {
    if (role === "freelancer") {
      if (appliedIds.indexOf(p.id) > -1) return '<span class="badge accepted">' + UI.icon("check", 12) + "Applied</span>";
      return (p.status || "open") === "open" ? '<a class="btn btn-primary btn-sm" href="project-details.html?id=' + UI.esc(p.id) + '#apply">Apply now</a>' : "";
    }
    if (mine) return '<a class="btn btn-secondary btn-sm" href="applicants.html?project=' + UI.esc(p.id) + '">Manage applicants</a>';
    if (!role) return '<a class="btn btn-secondary btn-sm" href="login.html?next=' + encodeURIComponent("project-details.html?id=" + p.id) + '">Sign in to apply</a>';
    return '<a class="btn btn-secondary btn-sm" href="project-details.html?id=' + UI.esc(p.id) + '">View</a>';
  }

  function render() {
    var list = filtered(), host = $("results");
    $("count").textContent = list.length + (list.length === 1 ? " project" : " projects") + (all.length !== list.length ? " of " + all.length : "");
    if (!all.length) return UI.showEmpty(host, mine ? { icon: "briefcase", title: "No projects posted yet", text: "When you post a project it will be listed here.", href: "post-project.html", action: "Post a project" } : { icon: "compass", title: "No projects are open right now", text: "Check back soon — new work is posted every day." });
    if (!list.length) { host.innerHTML = '<div class="state"><div class="state-ico">' + UI.icon("search", 22) + '</div><h3>No projects match these filters</h3><p>Try removing a filter or searching for a broader term.</p><button class="btn btn-secondary btn-sm" id="clearEmpty">Clear all filters</button></div>'; $("clearEmpty").addEventListener("click", clearAll); return; }
    host.removeAttribute("aria-busy");
    host.innerHTML = '<div class="job-list">' + list.slice(0, shown).map(function (p) { return UI.jobCard(p, { actions: actionsFor(p), mySkills: mySkills }); }).join("") + "</div>" +
      (list.length > shown ? '<div style="text-align:center;margin-top:20px"><button class="btn btn-secondary" id="more">Show ' + Math.min(PAGE, list.length - shown) + " more</button></div>" : "");
    var cards = host.querySelectorAll(".job");
    list.slice(0, shown).forEach(function (p, i) {
      if (role === "freelancer" && (p.status || "open") === "open") UI.matchChip(cards[i].querySelector(".match-slot"), user.id, p.id, p.title);
    });
    var more = $("more"); if (more) more.addEventListener("click", function () { shown += PAGE; render(); });
  }
  function clearAll() { $("q").value = ""; $("fCategory").value = ""; $("fLevel").value = ""; $("fMin").value = ""; $("fMax").value = ""; skillFilter.set([]); $("fOpen").checked = true; shown = PAGE; render(); }

  ["q", "fCategory", "fLevel", "fMin", "fMax", "sort", "fOpen"].forEach(function (id) { $(id).addEventListener(id === "q" || id === "fMin" || id === "fMax" ? "input" : "change", function () { shown = PAGE; render(); }); });
  $("fSkills").addEventListener("change", function () { shown = PAGE; render(); });
  $("clear").addEventListener("click", clearAll);
  $("searchForm").addEventListener("submit", function (e) { e.preventDefault(); render(); });
  $("openFilters").addEventListener("click", function () { $("filters").classList.toggle("open"); });

  function load() {
    UI.showLoading($("results"), "card", 4);
    var reqs = [Api.projects.list(mine ? { mine: "true", limit: 100 } : { status: "open", limit: 100 })];
    if (role === "freelancer") { reqs.push(Api.freelancers.get(user.id).catch(function () { return null; })); reqs.push(Api.applications.mine({ limit: 200 }).catch(function () { return null; })); }
    Promise.all(reqs).then(function (r) {
      all = Api.asList(r[0]).items;
      if (r[1]) mySkills = r[1].skills || [];
      if (r[2]) appliedIds = Api.asList(r[2]).items.map(function (a) { return Data.appProject(a).id; });
      if (mySkills.length) $("sort").insertAdjacentHTML("beforeend", '<option value="skills">Best skill overlap</option>');
      render();
    }).catch(function (e) { UI.showError($("results"), e, load); $("count").textContent = ""; });
  }
  load();
})();
