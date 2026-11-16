/* Profile: view any freelancer (GET /freelancers/{id}) or edit your own (PUT /freelancers/profile). */
(function () {
  "use strict";
  var UI = window.UI, Api = window.Api, Data = window.Data, REF = window.REF;
  var user = UI.Auth.user(), role = user && user.role;
  var id = UI.qs("id") || (role === "freelancer" ? user.id : null);
  var own = role === "freelancer" && id === user.id;
  var $ = function (i) { return document.getElementById(i); };
  var profile = null, editing = false, skillsCtl = null;

  if (!id) return UI.showEmpty($("view"), { icon: "user", title: "No profile selected", text: "Open a freelancer from your applicants or the dashboard to view their profile.", href: role === "client" ? "client-dashboard.html" : "projects.html", action: "Go back" });

  function load() {
    UI.showLoading($("view"), "card", 3);
    Api.freelancers.get(id).then(function (p) { profile = p; editing = own && (!!UI.qs("welcome") || !p.summary); renderView(); }).catch(function (e) { UI.showError($("view"), e, load); });
  }

  function portfolioHtml(p) {
    return (p.portfolio || []).length ? '<div class="portfolio">' + p.portfolio.map(function (x) {
      return "<article><h4>" + UI.esc(x.title) + (x.url ? '<a class="small" href="' + UI.esc(x.url) + '" target="_blank" rel="noopener noreferrer">' + UI.icon("external-link", 14) + " View</a>" : "") + "</h4><p>" + UI.esc(x.description || "") + "</p>" + UI.skillTags(x.technologies || []) + "</article>";
    }).join("") + "</div>" : '<p class="small muted">No portfolio projects added yet.</p>';
  }
  function historyHtml(p) {
    return (p.work_history || []).length ? '<ul class="timeline" style="padding-right:0">' + p.work_history.map(function (w) {
      return '<li><span class="dot">' + UI.icon("briefcase", 14) + '</span><div><b>' + UI.esc(w.role) + '</b><div class="small muted">' + UI.esc(w.company || "") + (w.period ? " · " + UI.esc(w.period) : "") + "</div>" + (w.description ? '<p class="small text-2" style="margin-top:4px">' + UI.esc(w.description) + "</p>" : "") + "</div></li>";
    }).join("") + "</ul>" : '<p class="small muted">No experience listed yet.</p>';
  }

  function renderView() {
    var p = profile, c = Data.completion(p);
    document.title = (p.name || "Profile") + " · " + window.APP_CONFIG.APP_NAME;
    $("view").removeAttribute("aria-busy");
    $("view").innerHTML = '<div class="panel profile-hero">' + UI.avatar(p.name, "lg", p.avatar_url) + '<div class="grow"><div class="eyebrow">' + (own ? "Your profile" : "Freelancer") + "</div><h1 style=\"margin:6px 0 4px\">" + UI.esc(p.name) + '</h1><p class="text-2">' + UI.esc(p.headline || "No headline yet") + '</p><div class="job-meta" style="margin-bottom:0">' +
      (p.location ? "<span>" + UI.icon("map-pin", 14) + UI.esc(p.location) + "</span>" : "") + (p.availability ? "<span>" + UI.icon("clock", 14) + UI.esc(p.availability) + "</span>" : "") + (p.hourly_rate ? "<span>" + UI.icon("indian-rupee", 14) + UI.fmtMoney(p.hourly_rate, p.currency) + " / hr</span>" : "") + "</div>" +
      '<div class="profile-stats"><div><b>' + (p.avg_rating ? Number(p.avg_rating).toFixed(1) : "—") + "</b><span>Average rating" + (p.reviews_count ? " (" + p.reviews_count + ")" : "") + "</span></div><div><b>" + (p.completed_projects != null ? p.completed_projects : "—") + "</b><span>Projects completed</span></div><div><b>" + (p.years_experience != null ? p.years_experience : "—") + "</b><span>Years experience</span></div>" + (p.experience_level ? "<div><b>" + UI.esc(p.experience_level) + "</b><span>Level</span></div>" : "") + "</div></div>" +
      (own ? '<div><button class="btn btn-secondary" id="editBtn">' + UI.icon("pencil", 16) + "Edit profile</button></div>" : "") + "</div>" +
      '<div class="grid split-wide" style="margin-top:20px"><div class="stack"><section class="panel"><div class="panel-head"><h3>About</h3>' + (own ? '<a class="btn btn-ghost btn-sm" href="ai-summary.html">' + UI.icon("wand-sparkles", 14) + "Generate with AI</a>" : "") + '</div><div class="panel-body">' + (p.summary ? '<div class="prose">' + UI.esc(p.summary) + "</div>" : '<p class="muted small">' + (own ? "Add a summary so clients know who you are." : "This freelancer hasn't written a summary yet.") + "</p>") + "</div></section>" +
      '<section class="panel"><div class="panel-head"><h3>Portfolio</h3></div><div class="panel-body">' + portfolioHtml(p) + '</div></section></div><div class="stack"><section class="panel"><div class="panel-head"><h3>Skills &amp; expertise</h3></div><div class="panel-body">' + ((p.skills || []).length ? UI.skillTags(p.skills) : '<p class="small muted">No skills listed.</p>') + "</div></section>" +
      '<section class="panel"><div class="panel-head"><h3>Experience</h3></div><div class="panel-body">' + historyHtml(p) + "</div></section>" +
      (own ? '<section class="panel panel-body"><div style="display:flex;justify-content:space-between"><b>Profile strength</b><span class="num">' + c.score + '%</span></div><div class="progress" style="margin:10px 0 12px"><i style="width:' + c.score + '%"></i></div>' + (c.checks.filter(function (x) { return !x.ok; }).length ? '<ul class="check-list">' + c.checks.filter(function (x) { return !x.ok; }).slice(0, 4).map(function (x) { return "<li>" + UI.icon("circle-alert", 15) + "<span>" + x.label + "</span></li>"; }).join("") + "</ul>" : '<p class="small muted">Everything is filled in.</p>') + "</section>" : "") + "</div></div>";
    if (own) $("editBtn").addEventListener("click", function () { editing = true; renderEdit(); });
    if (editing) renderEdit();
  }

  function repeatRow(kind, o) {
    o = o || {};
    var f = kind === "portfolio" ? [["title", "Project title", o.title], ["url", "Link", o.url], ["description", "Description", o.description]] : [["role", "Role", o.role], ["company", "Company", o.company], ["period", "Period (e.g. 2022 – 2024)", o.period]];
    return '<div class="repeat-row" data-kind="' + kind + '">' + f.map(function (x) { return '<div class="field"><input class="input" data-k="' + x[0] + '" placeholder="' + x[1] + '" aria-label="' + x[1] + '" value="' + UI.esc(x[2] || "") + '"></div>'; }).join("") + '<button type="button" class="btn btn-ghost btn-icon" data-remove aria-label="Remove">' + UI.icon("trash-2", 16) + "</button></div>";
  }

  function renderEdit() {
    var p = profile;
    $("view").innerHTML = '<form class="stack" id="profileForm" novalidate><div class="panel form-section"><h3>Basics</h3><p class="hint">This is the first thing clients see.</p>' +
      '<div class="form-row"><div class="field"><label for="name">Full name</label><input class="input" id="name" name="name" value="' + UI.esc(p.name) + '"></div><div class="field"><label for="headline">Professional headline</label><input class="input" id="headline" name="headline" placeholder="Full-stack developer · Python &amp; JavaScript" value="' + UI.esc(p.headline) + '"></div></div>' +
      '<div class="form-row"><div class="field"><label for="location">Location</label><input class="input" id="location" name="location" placeholder="City, Country" value="' + UI.esc(p.location) + '"></div><div class="field"><label for="availability">Availability</label><select class="select" id="availability" name="availability">' + ["Available now", "Available in 2 weeks", "Part-time only", "Not available"].map(function (o) { return "<option" + (p.availability === o ? " selected" : "") + ">" + o + "</option>"; }).join("") + "</select></div></div>" +
      '<div class="form-row"><div class="field"><label for="years_experience">Years of experience</label><input class="input num" id="years_experience" name="years_experience" type="number" min="0" max="60" value="' + (p.years_experience != null ? p.years_experience : "") + '"></div><div class="field"><label for="experience_level">Experience level</label><select class="select" id="experience_level" name="experience_level">' + REF.levels.map(function (o) { return "<option" + (p.experience_level === o ? " selected" : "") + ">" + o + "</option>"; }).join("") + '</select></div></div><div class="form-row"><div class="field" style="margin:0"><label for="hourly_rate">Hourly rate (USD)</label><input class="input num" id="hourly_rate" name="hourly_rate" type="number" min="1" value="' + (p.hourly_rate || "") + '"></div></div></div>' +
      '<div class="panel form-section"><h3>Skills</h3><p class="hint">Skills are used for match predictions. Add the technologies you use most.</p><div class="field" style="margin:0" data-field="skills"><div id="skillsEdit"></div></div></div>' +
      '<div class="panel form-section"><div style="display:flex;justify-content:space-between;align-items:center"><div><h3>Profile summary</h3><p class="hint" style="margin:0">A short paragraph about your experience and strengths.</p></div><a class="btn btn-secondary btn-sm" href="ai-summary.html">' + UI.icon("wand-sparkles", 14) + "Generate with AI</a></div><div class=\"field\" style=\"margin:16px 0 0\"><textarea class=\"textarea\" name=\"summary\" rows=\"5\" maxlength=\"1200\" aria-label=\"Profile summary\">" + UI.esc(p.summary) + "</textarea></div></div>" +
      '<div class="panel form-section"><h3>Portfolio</h3><p class="hint">Showcase work you\'re proud of.</p><div id="portfolioRows">' + (p.portfolio || []).map(function (x) { return repeatRow("portfolio", x); }).join("") + '</div><button type="button" class="btn btn-secondary btn-sm" data-add="portfolio">' + UI.icon("plus", 14) + "Add project</button></div>" +
      '<div class="panel form-section"><h3>Experience</h3><div id="historyRows" style="margin-top:12px">' + (p.work_history || []).map(function (x) { return repeatRow("history", x); }).join("") + '</div><button type="button" class="btn btn-secondary btn-sm" data-add="history">' + UI.icon("plus", 14) + "Add role</button></div>" +
      '<div style="display:flex;gap:10px;justify-content:flex-end;position:sticky;bottom:0;padding:14px 0;background:linear-gradient(transparent,var(--bg) 30%)"><button type="button" class="btn btn-secondary" id="cancelBtn">Cancel</button><button type="submit" class="btn btn-primary">Save profile</button></div></form>';
    skillsCtl = UI.tagInput($("skillsEdit"), { initial: p.skills || [], suggestions: REF.skills, placeholder: "Add a skill, press Enter", max: 25, label: "Skills" });
    var form = $("profileForm");
    form.querySelectorAll("[data-add]").forEach(function (b) { b.addEventListener("click", function () { var host = $(b.dataset.add === "portfolio" ? "portfolioRows" : "historyRows"); host.insertAdjacentHTML("beforeend", repeatRow(b.dataset.add)); UI.hydrate(host); host.lastChild.querySelector("input").focus(); }); });
    form.addEventListener("click", function (e) { var r = e.target.closest("[data-remove]"); if (r) r.closest(".repeat-row").remove(); });
    $("cancelBtn").addEventListener("click", function () { editing = false; renderView(); });
    form.addEventListener("submit", function (e) {
      e.preventDefault(); UI.formAlert(form, "");
      var v = UI.validate(form, { name: { label: "Name", required: true, minLength: 2 }, headline: { label: "Headline", required: true, minLength: 3, maxLength: 100 }, years_experience: { label: "Years of experience", required: true, min: 0, max: 60 }, hourly_rate: { label: "Hourly rate", min: 1 } });
      var skills = skillsCtl.get(); UI.setError(form, "skills", skills.length < 1 ? "Add at least one skill." : "");
      if (!v || !skills.length) return;
      function rows(kind) { return Array.prototype.map.call(form.querySelectorAll('.repeat-row[data-kind="' + kind + '"]'), function (r) { var o = {}; r.querySelectorAll("[data-k]").forEach(function (i) { o[i.dataset.k] = i.value.trim(); }); return o; }); }
      var portfolio = rows("portfolio").filter(function (x) { return x.title; });
      var bad = portfolio.filter(function (x) { return x.url && !/^https?:\/\//i.test(x.url); });
      if (bad.length) return UI.formAlert(form, "Portfolio links must start with http:// or https://.");
      var f = form.elements;
      var payload = { name: v.name, headline: v.headline, location: f.location.value.trim(), availability: f.availability.value, years_experience: Number(v.years_experience), experience_level: f.experience_level.value, hourly_rate: v.hourly_rate ? Number(v.hourly_rate) : null, skills: skills, summary: f.summary.value.trim(), portfolio: portfolio, work_history: rows("history").filter(function (x) { return x.role; }) };
      UI.busy(form.querySelector("[type=submit]"), Api.freelancers.updateProfile(payload).then(function (saved) {
        profile = Object.assign({}, profile, payload, saved && typeof saved === "object" ? saved : {});
        var s = Api.Session.get(); if (s) { s.user.name = profile.name; Api.Session.set(s); }
        editing = false; UI.toast("Profile saved.", "success"); renderView(); window.scrollTo({ top: 0, behavior: "smooth" });
      })).catch(function (err) { UI.showFormError(form, err); window.scrollTo({ top: 0, behavior: "smooth" }); });
    });
    UI.hydrate($("view"));
  }
  load();
})();
