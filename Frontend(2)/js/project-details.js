/* Project details + application form (GET /projects/{id}, POST /applications, POST /ml/predict-match) */
(function () {
  "use strict";
  var UI = window.UI, Api = window.Api, Data = window.Data;
  var user = UI.Auth.user(), role = user && user.role, id = UI.qs("id");
  var $ = function (i) { return document.getElementById(i); };
  var project = null;

  if (!id) return UI.showEmpty($("view"), { icon: "search", title: "No project selected", text: "Open a project from the marketplace to see its details.", href: "projects.html", action: "Browse projects" });

  function load() {
    UI.showLoading($("view"), "card", 3);
    var reqs = [Api.projects.get(id)];
    if (role === "freelancer") { reqs.push(Api.applications.mine({ limit: 200 }).catch(function () { return null; })); reqs.push(Api.freelancers.get(user.id).catch(function () { return null; })); }
    Promise.all(reqs).then(function (r) {
      project = r[0];
      var existing = r[1] ? Api.asList(r[1]).items.filter(function (a) { return Data.appProject(a).id === project.id; })[0] : null;
      render(existing, r[2]);
    }).catch(function (e) { UI.showError($("view"), e, load); });
  }

  function render(existing, profile) {
    var p = project, b = UI.budget(p), mySkills = (profile && profile.skills) || [];
    document.title = p.title + " · " + window.APP_CONFIG.APP_NAME;
    var isOwner = role === "client" && (p.client_id === user.id || p.owner_id === user.id || p.client_id === undefined);
    var list = function (arr) { return arr && arr.length ? '<ul class="check-list">' + arr.map(function (x) { return "<li>" + UI.icon("check", 16) + "<span>" + UI.esc(x) + "</span></li>"; }).join("") + "</ul>" : ""; };

    var side = "";
    if (role === "freelancer") {
      side = '<div class="panel" id="matchPanel"><div class="panel-head"><h3>' + UI.icon("brain-circuit", 18) + 'Your match</h3></div><div class="panel-body" id="matchBody"></div></div>';
    }
    var applyBlock;
    if (!role) applyBlock = '<div class="panel panel-body"><h3>Interested in this project?</h3><p class="small text-2" style="margin:6px 0 16px">Sign in as a freelancer to apply and see how well you match.</p><a class="btn btn-primary btn-block" href="login.html?next=' + encodeURIComponent("project-details.html?id=" + p.id) + '">Sign in to apply</a><a class="btn btn-ghost btn-block" style="margin-top:8px" href="register.html?role=freelancer">Create freelancer account</a></div>';
    else if (role === "client") applyBlock = '<div class="panel panel-body"><h3>' + (isOwner ? "Manage this project" : "Client view") + '</h3><p class="small text-2" style="margin:6px 0 16px">' + (isOwner ? "Review proposals, compare match predictions and hire." : "Only freelancers can apply to projects.") + "</p>" + (isOwner ? '<a class="btn btn-primary btn-block" href="applicants.html?project=' + UI.esc(p.id) + '">' + UI.icon("users", 16) + "View applicants</a>" : "") + "</div>";
    else if (existing) applyBlock = '<div class="panel panel-body"><div style="display:flex;justify-content:space-between;align-items:center"><h3>Your application</h3>' + UI.statusBadge(existing.status) + '</div><p class="small text-2" style="margin:8px 0 14px">Submitted ' + UI.relTime(existing.created_at) + '.</p><a class="btn btn-secondary btn-block" href="applications.html">' + UI.icon("file-text", 16) + "Track in My applications</a></div>";
    else if ((p.status || "open") !== "open") applyBlock = '<div class="panel panel-body"><h3>Not accepting proposals</h3><p class="small text-2" style="margin-top:6px">This project is ' + UI.esc((p.status || "").replace("_", " ")) + ".</p></div>";
    else applyBlock = '<form class="panel" id="applyForm" novalidate><div class="panel-head"><h3>' + UI.icon("send", 18) + 'Apply for this project</h3></div><div class="panel-body">' +
      '<div class="field"><div style="display:flex;justify-content:space-between;align-items:center"><label for="cover">Cover letter</label><a class="small" href="ai-proposal.html?project=' + UI.esc(p.id) + '">' + UI.icon("wand-sparkles", 13) + ' Draft with AI</a></div><textarea class="textarea" id="cover" name="cover_letter" rows="8" placeholder="Explain how you would approach this project and why your experience fits."></textarea><span class="hint"><span id="coverCount">0</span> / 2000 characters</span></div>' +
      '<div class="form-row"><div class="field"><label for="bid">Your bid (' + UI.esc(p.currency || "USD") + ')</label><input class="input num" id="bid" name="bid_amount" type="number" min="1" step="any" inputmode="decimal"></div><div class="field"><label for="days">Delivery (days)</label><input class="input num" id="days" name="delivery_days" type="number" min="1" step="1"></div></div>' +
      '<button class="btn btn-primary btn-block" type="submit">Submit application</button><p class="tiny muted" style="margin-top:10px;text-align:center">The client will see your profile and match prediction.</p></div></form>';

    $("view").removeAttribute("aria-busy");
    $("view").innerHTML = '<nav class="crumbs" aria-label="Breadcrumb"><a href="projects.html">Projects</a>' + UI.icon("chevron-right", 14) + "<span>" + UI.esc(p.category || "Project") + "</span></nav>" +
      '<div class="detail"><div><div class="detail-head"><div style="display:flex;gap:8px;align-items:center">' + UI.statusBadge(p.status || "open") + (p.category ? '<span class="badge">' + UI.esc(p.category) + "</span>" : "") + "</div><h1>" + UI.esc(p.title) + '</h1><div class="job-meta">' +
      (p.client_name ? "<span>" + UI.icon("building-2", 15) + UI.esc(p.client_name) + "</span>" : "") + (p.created_at ? "<span>" + UI.icon("clock", 15) + "Posted " + UI.relTime(p.created_at) + "</span>" : "") + (p.location ? "<span>" + UI.icon("map-pin", 15) + UI.esc(p.location) + "</span>" : "") + (p.applications_count != null ? "<span>" + UI.icon("users", 15) + p.applications_count + " proposals</span>" : "") + "</div></div>" +
      '<div class="panel panel-body"><h2 style="font-size:1.25rem;margin-bottom:14px">About this project</h2><div class="prose">' + UI.esc(p.description) + "</div>" +
      (p.requirements && p.requirements.length ? '<div class="section-title">Requirements</div>' + list(p.requirements) : "") +
      (p.deliverables && p.deliverables.length ? '<div class="section-title">Deliverables</div>' + list(p.deliverables) : "") +
      '<div class="section-title">Skills &amp; technologies</div>' + UI.skillTags(p.skills, mySkills) + (mySkills.length ? '<p class="tiny muted" style="margin-top:10px">Highlighted skills are ones on your profile.</p>' : "") + "</div></div>" +
      '<aside class="stack sticky">' + '<div class="panel panel-body"><div class="job-budget num" style="font-size:1.75rem">' + UI.esc(b.text) + '<small>' + b.sub + '</small></div><div class="divider"></div><dl class="kv" style="margin:0">' +
      (p.deadline ? "<div><dt>Deadline</dt><dd>" + UI.fmtDate(p.deadline) + "</dd></div>" : "") + (p.duration ? "<div><dt>Duration</dt><dd>" + UI.esc(p.duration) + "</dd></div>" : "") + (p.experience_level ? "<div><dt>Experience level</dt><dd>" + UI.esc(p.experience_level) + "</dd></div>" : "") + (p.client_name ? "<div><dt>Client</dt><dd>" + UI.esc(p.client_name) + "</dd></div>" : "") + "</dl></div>" + applyBlock + side + "</aside></div>";

    if (role === "freelancer") runMatch();
    var form = $("applyForm");
    if (form) wireForm(form);
    if (location.hash === "#apply" && form) { form.scrollIntoView({ behavior: "smooth", block: "center" }); }
  }

  function runMatch() {
    var body = $("matchBody");
    body.innerHTML = '<div class="skel skel-line w80"></div><div class="skel skel-line w60"></div><div class="skel skel-line w40"></div>';
    Api.ml.predictMatch(user.id, project.id).then(function (r) { body.innerHTML = UI.matchPanel(r); })
      .catch(function (e) {
        body.innerHTML = '<div class="state error" style="padding:8px 0"><h3>Match unavailable</h3><p>' + UI.esc(e.isNetwork ? "The prediction service couldn't be reached." : e.message) + '</p><button class="btn btn-secondary btn-sm" id="retryMatch">' + UI.icon("refresh-cw", 14) + "Retry</button></div>";
        $("retryMatch").addEventListener("click", runMatch);
      });
  }

  function wireForm(form) {
    try {
      var d = JSON.parse(localStorage.getItem("craftline.useProposal") || "null");
      if (d && d.projectId === project.id) { form.elements.cover_letter.value = d.text; localStorage.removeItem("craftline.useProposal"); UI.toast("AI-drafted proposal loaded. Review it before submitting.", "success"); }
    } catch (e) { /* ignore */ }
    var cnt = $("coverCount"), ta = form.elements.cover_letter;
    function upd() { cnt.textContent = ta.value.length; } ta.addEventListener("input", upd); upd();
    form.addEventListener("submit", function (e) {
      e.preventDefault(); UI.formAlert(form, "");
      var v = UI.validate(form, {
        cover_letter: { label: "Cover letter", required: true, minLength: 50, maxLength: 2000, message: "" },
        bid_amount: { label: "Bid", required: true, min: 1 },
        delivery_days: { label: "Delivery time", required: true, min: 1, max: 730 }
      });
      if (!v) return;
      UI.busy(form.querySelector("[type=submit]"), Api.applications.create({ project_id: project.id, cover_letter: v.cover_letter, bid_amount: Number(v.bid_amount), delivery_days: Number(v.delivery_days) }).then(function () {
        UI.toast("Application submitted.", "success");
        setTimeout(function () { location.href = "applications.html"; }, 700);
      })).catch(function (err) { UI.showFormError(form, err); });
    });
  }
  load();
})();
