/* Shared UI layer: icons, app shell, state components, formatting, validation. */
(function () {
  "use strict";
  var CFG = window.APP_CONFIG, Api = window.Api;

  /* ---------- Basics ---------- */
  function esc(v) {
    return String(v === undefined || v === null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function icon(name, size) {
    var p = (window.ICONS || {})[name] || "";
    size = size || 18;
    return '<svg class="ico" width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + p + "</svg>";
  }
  function hydrate(root) {
    (root || document).querySelectorAll("[data-icon]").forEach(function (el) {
      el.insertAdjacentHTML("afterbegin", icon(el.getAttribute("data-icon"), +el.getAttribute("data-size") || 16));
      el.removeAttribute("data-icon");
    });
  }
  function qs(name) { return new URLSearchParams(location.search).get(name); }
  function initials(name) {
    return String(name || "?").trim().split(/\s+/).slice(0, 2).map(function (w) { return w[0]; }).join("").toUpperCase();
  }
  function avatar(name, cls, src) {
    var c = "c" + (1 + (String(name || "").length % 4));
    if (src) return '<img class="avatar ' + (cls || "") + '" src="' + esc(src) + '" alt="">';
    return '<span class="avatar ' + (cls || "") + " " + c + '" aria-hidden="true">' + esc(initials(name)) + "</span>";
  }
  function slug(s) { return String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, ""); }

  /* ---------- Formatting ---------- */
  function fmtMoney(n, currency) {
    if (n === undefined || n === null || n === "" || isNaN(n)) return "";
    try { return new Intl.NumberFormat(undefined, { style: "currency", currency: currency || "USD", maximumFractionDigits: 0 }).format(n); }
    catch (e) { return (currency || "$") + Number(n).toLocaleString(); }
  }
  function budget(p) {
    var c = p.currency, hourly = p.budget_type === "hourly";
    var lo = p.budget_min, hi = p.budget_max, single = p.budget;
    var text = "Budget not set";
    if (lo != null && hi != null && lo !== hi) text = fmtMoney(lo, c) + " – " + fmtMoney(hi, c);
    else if (lo != null || hi != null || single != null) text = fmtMoney(lo != null ? lo : hi != null ? hi : single, c);
    return { text: text, sub: hourly ? "per hour" : "fixed price" };
  }
  function fmtDate(d) {
    if (!d) return "—";
    var x = new Date(d); if (isNaN(x)) return "—";
    return x.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  }
  function relTime(d) {
    if (!d) return "";
    var x = new Date(d); if (isNaN(x)) return "";
    var s = Math.round((Date.now() - x.getTime()) / 1000);
    if (s < 60) return "just now";
    var m = Math.round(s / 60); if (m < 60) return m + " min ago";
    var h = Math.round(m / 60); if (h < 24) return h + " hr ago";
    var dd = Math.round(h / 24); if (dd < 30) return dd + (dd === 1 ? " day ago" : " days ago");
    return fmtDate(d);
  }
  function pct(v) { return Math.max(0, Math.min(100, Math.round(v))); }
  function stars(rating) {
    var r = Math.round(Number(rating) || 0), out = "";
    for (var i = 1; i <= 5; i++) out += '<span class="' + (i <= r ? "" : "off") + '">' + icon("star", 14).replace('fill="none"', 'fill="currentColor"') + "</span>";
    return '<span class="stars" role="img" aria-label="' + (Number(rating) || 0).toFixed(1) + ' out of 5">' + out + "</span>";
  }

  /* ---------- Toasts / Modal ---------- */
  function toast(message, type) {
    var host = document.querySelector(".toasts");
    if (!host) { host = document.createElement("div"); host.className = "toasts"; host.setAttribute("role", "status"); host.setAttribute("aria-live", "polite"); document.body.appendChild(host); }
    var t = document.createElement("div");
    t.className = "toast " + (type || "");
    t.innerHTML = icon(type === "error" ? "circle-alert" : type === "success" ? "circle-check" : "info", 18) + "<span>" + esc(message) + "</span>";
    host.appendChild(t);
    setTimeout(function () { t.style.opacity = "0"; t.style.transition = "opacity .3s"; setTimeout(function () { t.remove(); }, 300); }, type === "error" ? 6000 : 3500);
  }
  function modal(opts) {
    var ov = document.createElement("div");
    ov.className = "overlay";
    ov.innerHTML = '<div class="modal ' + (opts.wide ? "wide" : "") + '" role="dialog" aria-modal="true" aria-label="' + esc(opts.title) + '">' +
      '<div class="modal-head"><h3>' + esc(opts.title) + '</h3><button class="btn btn-ghost btn-icon btn-sm" data-close aria-label="Close">' + icon("x") + "</button></div>" +
      '<div class="modal-body">' + (opts.body || "") + "</div>" + (opts.footer ? '<div class="modal-foot">' + opts.footer + "</div>" : "") + "</div>";
    document.body.appendChild(ov);
    var prev = document.activeElement;
    function close() { document.removeEventListener("keydown", onKey); ov.remove(); if (prev && prev.focus) prev.focus(); }
    function onKey(e) { if (e.key === "Escape") close(); }
    document.addEventListener("keydown", onKey);
    ov.addEventListener("click", function (e) { if (e.target === ov || e.target.closest("[data-close]")) close(); });
    var first = ov.querySelector("input,textarea,select,button.btn-primary,button.btn-danger") || ov.querySelector("button");
    if (first) first.focus();
    return { el: ov, close: close };
  }
  function confirmDialog(o) {
    return new Promise(function (resolve) {
      var m = modal({
        title: o.title, body: '<p class="text-2">' + o.body + "</p>",
        footer: '<button class="btn btn-secondary" data-close>Cancel</button><button class="btn ' + (o.danger ? "btn-danger" : "btn-primary") + '" data-ok>' + esc(o.confirm || "Confirm") + "</button>"
      });
      var done = false;
      m.el.querySelector("[data-ok]").addEventListener("click", function () { done = true; m.close(); resolve(true); });
      m.el.addEventListener("click", function (e) { if (!done && (e.target === m.el || e.target.closest("[data-close]"))) resolve(false); });
    });
  }

  /* ---------- Loading / error / empty states ---------- */
  function skeleton(kind, n) {
    n = n || 3; var out = "";
    if (kind === "stats") { for (var a = 0; a < n; a++) out += '<div class="panel stat"><div class="skel skel-line w40"></div><div class="skel" style="height:30px;width:50%;margin-top:14px"></div></div>'; return out; }
    for (var i = 0; i < n; i++) out += '<div class="skel-block" ' + (kind === "card" ? 'style="border:1px solid var(--line);border-radius:12px;background:var(--surface)"' : "") + '><div class="skel skel-line w60"></div><div class="skel skel-line w80"></div><div class="skel skel-line w40"></div></div>';
    return out;
  }
  function showLoading(el, kind, n) { el.setAttribute("aria-busy", "true"); el.innerHTML = skeleton(kind, n); }
  function showError(el, err, retry) {
    el.removeAttribute("aria-busy");
    var net = err && err.isNetwork;
    el.innerHTML = '<div class="state error" role="alert"><div class="state-ico">' + icon(net ? "wifi-off" : "triangle-alert", 22) + "</div><h3>" +
      (net ? "Can't reach the server" : "Something went wrong") + "</h3><p>" +
      (net ? "The API at <code>" + esc(CFG.API_BASE_URL) + "</code> isn't responding. Check that the FastAPI backend is running and CORS allows this origin." : esc(err && err.message ? err.message : "Please try again.")) +
      "</p>" + (retry ? '<button class="btn btn-secondary btn-sm" data-retry>' + icon("refresh-cw", 14) + "Try again</button>" : "") + "</div>";
    var b = el.querySelector("[data-retry]"); if (b) b.addEventListener("click", retry);
  }
  function showEmpty(el, o) {
    el.removeAttribute("aria-busy");
    el.innerHTML = '<div class="state"><div class="state-ico">' + icon(o.icon || "inbox", 22) + "</div><h3>" + esc(o.title) + "</h3>" + (o.text ? "<p>" + esc(o.text) + "</p>" : "") +
      (o.href ? '<a class="btn btn-primary btn-sm" href="' + esc(o.href) + '">' + esc(o.action) + "</a>" : "") + "</div>";
  }
  function busy(btn, promise) {
    var html = btn.innerHTML; btn.disabled = true;
    btn.innerHTML = icon("loader-circle", 16).replace('class="ico"', 'class="ico spin"') + "<span>Working…</span>";
    return promise.finally(function () { btn.disabled = false; btn.innerHTML = html; });
  }

  /* ---------- Domain components ---------- */
  var STATUS = { pending: "Pending", shortlisted: "Shortlisted", accepted: "Hired", rejected: "Declined", withdrawn: "Withdrawn", completed: "Completed", open: "Open", in_progress: "In progress", closed: "Closed" };
  function statusBadge(s) { s = s || "pending"; return '<span class="badge ' + esc(s) + '">' + esc(STATUS[s] || s) + "</span>"; }
  function skillTags(list, highlight) {
    return '<div class="tags">' + (list || []).map(function (s) {
      return '<span class="tag ' + (highlight && highlight.indexOf(s) > -1 ? "hit" : "") + '">' + esc(s) + "</span>";
    }).join("") + "</div>";
  }

  function jobCard(p, o) {
    o = o || {}; var b = budget(p);
    return '<article class="job"><div><h3><a href="project-details.html?id=' + esc(p.id) + '">' + esc(p.title) + "</a></h3>" +
      '<div class="job-meta">' +
      (p.category ? "<span>" + icon("layers", 14) + esc(p.category) + "</span>" : "") +
      (p.deadline ? "<span>" + icon("calendar", 14) + "Due " + fmtDate(p.deadline) + "</span>" : "") +
      (p.experience_level ? "<span>" + icon("award", 14) + esc(p.experience_level) + "</span>" : "") +
      (p.client_name ? "<span>" + icon("building-2", 14) + esc(p.client_name) + "</span>" : "") + "</div>" +
      '<p class="job-desc">' + esc(p.description) + "</p>" + skillTags((p.skills || []).slice(0, 6), o.mySkills) + "</div>" +
      '<div class="job-side"><div class="job-budget num">' + esc(b.text) + "<small>" + b.sub + "</small></div><div>" + (o.actions || "") + "</div></div>" +
      '<div class="job-foot">' + statusBadge(p.status || "open") +
      (p.created_at ? "<span>Posted " + relTime(p.created_at) + "</span>" : "") +
      (p.applications_count != null ? "<span>" + p.applications_count + " proposal" + (p.applications_count === 1 ? "" : "s") + "</span>" : "") +
      '<span class="match-slot" style="margin-left:auto"></span></div></article>';
  }

  /* --- ML match presentation: model label, rubric fit score, confidence separately --- */
  function readMatch(r) {
    var label = r.label || r.match_label || r.prediction || r.classification || "";
    var key = /strong/i.test(label) ? "strong" : /moderate/i.test(label) ? "moderate" : /low/i.test(label) ? "low" : "";
    var rubric = r.rubric_score != null ? Number(r.rubric_score) : null;
    if (rubric !== null && !isFinite(rubric)) rubric = null;
    var confidence = r.confidence != null ? Number(r.confidence) : r.match_percentage != null ? Number(r.match_percentage) / 100 : null;
    if (confidence !== null && !isFinite(confidence)) confidence = null;
    var confidencePct = confidence != null ? confidence * (confidence <= 1 ? 100 : 1) : null;
    var probs = null;
    if (r.probabilities && typeof r.probabilities === "object") {
      probs = { strong: 0, moderate: 0, low: 0 };
      Object.keys(r.probabilities).forEach(function (k) { var kk = /strong/i.test(k) ? "strong" : /moderate/i.test(k) ? "moderate" : /low/i.test(k) ? "low" : null; if (kk) probs[kk] = Number(r.probabilities[k]); });
      var sum = probs.strong + probs.moderate + probs.low;
      if (sum <= 1.5) { probs.strong *= 100; probs.moderate *= 100; probs.low *= 100; }
    }
    return { key: key, label: label || "Match", pct: rubric, rubricScore: rubric, confidencePct: confidencePct, probs: probs, f: r.features || r.details || {}, raw: r };
  }
  function matchPanel(result) {
    var m = readMatch(result), f = m.f, facts = [];
    function add(k, v) { if (v !== undefined && v !== null && v !== "") facts.push("<div><dt>" + k + "</dt><dd>" + esc(v) + "</dd></div>"); }
    if (m.confidencePct != null) add("Model confidence", pct(m.confidencePct) + "%");
    var sk = f.skills_match_percentage != null ? f.skills_match_percentage : f.skills_match;
    if (sk != null) add("Skills match", pct(sk <= 1 ? sk * 100 : sk) + "%");
    if (f.years_experience != null) add("Experience", f.years_experience + " yr" + (f.years_experience == 1 ? "" : "s"));
    if (f.experience_level) add("Level", f.experience_level);
    if (f.category_relevance != null) add("Category fit", pct(f.category_relevance <= 1 ? f.category_relevance * 100 : f.category_relevance) + "%");
    if (f.avg_rating != null) add("Past ratings", Number(f.avg_rating).toFixed(1) + " / 5");
    var techs = f.required_technologies || f.relevant_technologies || [];
    var fitLabel = m.pct == null ? "Rubric fit unavailable" : "Rubric fit score " + pct(m.pct) + "%";
    var html = '<div class="match ' + m.key + '"><div class="match-top"><div class="match-ring" role="img" aria-label="' + esc(fitLabel) + '" style="--p:' + (m.pct == null ? 0 : pct(m.pct)) + '"><span>' + (m.pct == null ? "–" : pct(m.pct) + "%") + "</span></div>" +
      '<div><div class="eyebrow" style="color:var(--muted)">Predicted match</div><div class="match-label">' + esc(m.label) + '</div><div class="tiny muted">Random Forest label · rubric fit score</div></div></div>';
    if (m.probs) {
      html += '<div class="match-bars" aria-label="Class probabilities">' + ["strong", "moderate", "low"].map(function (k) {
        return '<div class="match-bar ' + k + '"><span>' + k[0].toUpperCase() + k.slice(1) + '</span><div class="progress"><i style="width:' + pct(m.probs[k]) + '%"></i></div><span class="num">' + pct(m.probs[k]) + "%</span></div>";
      }).join("") + "</div>";
    }
    if (facts.length) html += '<dl class="match-facts" style="margin:0">' + facts.join("") + "</dl>";
    if ((f.matched_skills || []).length || (f.missing_skills || []).length) {
      html += '<div><div class="match-sub">Skills overlap</div><div class="tags">' + (f.matched_skills || []).map(function (s) { return '<span class="tag hit">' + icon("check", 12) + esc(s) + "</span>"; }).join("") +
        (f.missing_skills || []).map(function (s) { return '<span class="tag miss">' + esc(s) + "</span>"; }).join("") + "</div></div>";
    }
    if (techs.length) html += '<div><div class="match-sub">Relevant technologies</div>' + skillTags(techs, f.matched_skills) + "</div>";
    return html + "</div>";
  }
  /* Lazy match chip: calls the backend only when the user asks. */
  function matchChip(slot, freelancerId, projectId, name) {
    if (!freelancerId || !projectId) return;
    slot.innerHTML = '<button type="button" class="match-chip">' + icon("brain-circuit", 14) + "Check match</button>";
    function run() {
      slot.innerHTML = '<span class="match-chip" aria-busy="true">' + icon("loader-circle", 14).replace('class="ico"', 'class="ico spin"') + "Analysing…</span>";
      Api.ml.predictMatch(freelancerId, projectId).then(function (r) {
        var m = readMatch(r);
        var fit = m.pct != null ? " · " + pct(m.pct) + "% fit" : "";
        var conf = m.confidencePct != null ? '<span class="match-conf"> · ' + pct(m.confidencePct) + "% conf.</span>" : "";
        var title = "View match details";
        if (m.pct != null || m.confidencePct != null) {
          title = (m.pct != null ? "Rubric fit: " + pct(m.pct) + "%. " : "") + (m.confidencePct != null ? "Model confidence: " + pct(m.confidencePct) + "%." : "");
        }
        var aria = m.label + (m.pct != null ? ", rubric fit " + pct(m.pct) + " percent" : "") + (m.confidencePct != null ? ", model confidence " + pct(m.confidencePct) + " percent" : "");
        slot.innerHTML = '<button type="button" class="match-chip ' + m.key + '" style="cursor:pointer" title="' + esc(title) + '" aria-label="' + esc(aria) + '">' + esc(m.label) + fit + conf + "</button>";
        slot.firstChild.addEventListener("click", function () { modal({ title: "Match analysis" + (name ? " — " + name : ""), body: matchPanel(r) }); });
      }).catch(function (e) {
        slot.innerHTML = '<button type="button" class="match-chip" title="' + esc(e.message) + '">' + icon("refresh-cw", 14) + (e.isNetwork ? "Server offline · retry" : "Retry match") + "</button>";
        slot.firstChild.addEventListener("click", run);
      });
    }
    slot.firstChild.addEventListener("click", run);
    return run;
  }

  /* ---------- Tag input ---------- */
  function tagInput(host, o) {
    o = o || {}; var tags = (o.initial || []).slice(), listId = "dl-" + Math.random().toString(36).slice(2, 7);
    host.classList.add("tag-input");
    host.innerHTML = '<input type="text" placeholder="' + esc(o.placeholder || "Type and press Enter") + '" aria-label="' + esc(o.label || "Add item") + '"' + (o.suggestions ? ' list="' + listId + '"' : "") + ">" +
      (o.suggestions ? '<datalist id="' + listId + '">' + o.suggestions.map(function (s) { return '<option value="' + esc(s) + '">'; }).join("") + "</datalist>" : "");
    var input = host.querySelector("input");
    function render() {
      host.querySelectorAll(".tag").forEach(function (n) { n.remove(); });
      tags.forEach(function (t, i) {
        var s = document.createElement("span"); s.className = "tag hit";
        s.innerHTML = esc(t) + '<button type="button" aria-label="Remove ' + esc(t) + '">' + icon("x", 12) + "</button>";
        s.querySelector("button").addEventListener("click", function () { tags.splice(i, 1); render(); host.dispatchEvent(new Event("change")); });
        host.insertBefore(s, input);
      });
    }
    function add(v) {
      v = v.trim().replace(/,$/, ""); if (!v) return;
      if (tags.some(function (t) { return t.toLowerCase() === v.toLowerCase(); }) || (o.max && tags.length >= o.max)) { input.value = ""; return; }
      tags.push(v); input.value = ""; render(); host.dispatchEvent(new Event("change"));
    }
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(input.value); }
      else if (e.key === "Backspace" && !input.value && tags.length) { tags.pop(); render(); host.dispatchEvent(new Event("change")); }
    });
    input.addEventListener("blur", function () { add(input.value); });
    host.addEventListener("click", function () { input.focus(); });
    render();
    return { get: function () { return tags.slice(); }, set: function (a) { tags = (a || []).slice(); render(); } };
  }

  /* ---------- Form validation ---------- */
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  function fieldOf(form, name) { var el = form.elements[name]; return el && (el.closest ? el.closest(".field") : null); }
  function setError(form, name, msg) {
    var f = fieldOf(form, name) || form.querySelector('[data-field="' + name + '"]'); if (!f) return;
    var e = f.querySelector(".field-error");
    if (!e) { e = document.createElement("span"); e.className = "field-error"; e.setAttribute("role", "alert"); f.appendChild(e); }
    e.textContent = msg || ""; f.classList.toggle("has-error", !!msg);
    var inp = form.elements[name]; if (inp && inp.setAttribute) inp.setAttribute("aria-invalid", msg ? "true" : "false");
  }
  /* rules: { fieldName: {label, required, email, minLength, maxLength, min, max, matches, pattern, message, custom(value, values)} } */
  function validate(form, rules) {
    var values = {}, firstBad = null;
    Object.keys(rules).forEach(function (name) {
      var el = form.elements[name]; if (!el) return;
      values[name] = el.type === "checkbox" ? el.checked : (el.value || "").trim();
    });
    Object.keys(rules).forEach(function (name) {
      var r = rules[name], v = values[name], label = r.label || name, msg = "";
      if (r.required && (v === "" || v === false || v === undefined)) msg = r.requiredMessage || (el(form, name).type === "checkbox" ? "Please accept to continue." : label + " is required.");
      else if (v !== "" && v !== false) {
        if (r.email && !EMAIL_RE.test(v)) msg = "Enter a valid email address, like name@company.com.";
        else if (r.minLength && v.length < r.minLength) msg = label + " must be at least " + r.minLength + " characters.";
        else if (r.maxLength && v.length > r.maxLength) msg = label + " must be under " + r.maxLength + " characters.";
        else if (r.min !== undefined && Number(v) < r.min) msg = label + " must be at least " + r.min + ".";
        else if (r.max !== undefined && Number(v) > r.max) msg = label + " must be " + r.max + " or less.";
        else if (r.matches && v !== values[r.matches]) msg = r.message || "Values don't match.";
        else if (r.pattern && !r.pattern.test(v)) msg = r.message || label + " looks invalid.";
        else if (r.custom) msg = r.custom(v, values) || "";
      }
      setError(form, name, msg);
      if (msg && !firstBad) firstBad = name;
    });
    Array.prototype.forEach.call(form.elements, function (e) {
      if (e.name && rules[e.name] && !e._v) { e._v = 1; e.addEventListener("input", function () { setError(form, e.name, ""); }); e.addEventListener("change", function () { setError(form, e.name, ""); }); }
    });
    if (firstBad) { var t = form.elements[firstBad]; if (t && t.focus) t.focus(); return null; }
    return values;
  }
  function el(form, name) { return form.elements[name] || {}; }
  /* Apply server-side field errors (FastAPI 422) onto the form. */
  function applyServerErrors(form, err) {
    var applied = false;
    Object.keys(err.fields || {}).forEach(function (k) { if (form.elements[k]) { setError(form, k, err.fields[k]); applied = true; } });
    return applied;
  }
  function formAlert(form, msg) {
    var a = form.querySelector(".form-alert");
    if (!a) { a = document.createElement("div"); a.className = "form-alert"; a.setAttribute("role", "alert"); form.insertBefore(a, form.firstChild); }
    a.innerHTML = icon("circle-alert", 18) + "<span>" + esc(msg || "") + "</span>"; a.classList.toggle("show", !!msg);
  }
  function showFormError(form, err) {
    if (applyServerErrors(form, err)) { formAlert(form, "Please correct the highlighted fields."); }
    else formAlert(form, err.isNetwork ? "Can't reach the server at " + CFG.API_BASE_URL + ". Your changes were not saved." : err.message);
  }

  /* ---------- Auth ---------- */
  var Auth = {
    user: function () { return Api.Session.user(); },
    loggedIn: function () { return !!Api.Session.token(); },
    home: function (role) { return role === "client" ? "client-dashboard.html" : "freelancer-dashboard.html"; },
    save: function (res) {
      var token = res.access_token || res.token;
      var user = res.user || res.profile;
      if (!token || !user) throw new Api.ApiError("Unexpected login response from the server (expected access_token and user).");
      user.id = user.id || user.user_id;
      Api.Session.set({ token: token, user: user });
      return user;
    },
    logout: function () { Api.Session.clear(); location.href = "login.html"; }
  };

  /* ---------- App shell ---------- */
  var NAV = {
    freelancer: [
      { label: "Workspace", items: [["freelancer-dashboard.html", "Dashboard", "layout-dashboard"], ["projects.html", "Browse projects", "search"], ["applications.html", "My applications", "file-text"], ["completed-works.html", "Completed works", "folder-check"]] },
      { label: "Profile & AI tools", items: [["profile.html", "My profile", "user"], ["ai-proposal.html", "Proposal generator", "wand-sparkles"], ["ai-summary.html", "Profile summary", "pen-line"]] }
    ],
    client: [
      { label: "Hiring", items: [["client-dashboard.html", "Dashboard", "layout-dashboard"], ["post-project.html", "Post a project", "plus"], ["projects.html?mine=1", "My projects", "briefcase"], ["applicants.html", "Applicants", "users"], ["hiring.html", "Hiring & tracking", "handshake"]] },
      { label: "Explore", items: [["projects.html", "Marketplace", "compass"]] }
    ]
  };
  function currentKey() {
    var f = location.pathname.split("/").pop() || "index.html";
    return f === "projects.html" && qs("mine") ? "projects.html?mine=1" : f;
  }
  function brand(href) { return '<a class="brand" href="' + (href || "index.html") + '"><span class="brand-mark">' + icon("layers-2", 16) + "</span>" + CFG.APP_NAME + "</a>"; }

  function apiSettings() {
    var m = modal({
      title: "Backend connection",
      body: '<p class="text-2 small" style="margin-bottom:14px">Set the base URL of the FastAPI server. This is stored only in this browser.</p><div class="field" style="margin:0"><label for="apiBase">API base URL</label><input class="input" id="apiBase" value="' + esc(CFG.API_BASE_URL) + '" placeholder="http://127.0.0.1:8000"><span class="hint">Default: http://127.0.0.1:8000</span></div>',
      footer: '<button class="btn btn-ghost" data-reset>Reset to default</button><button class="btn btn-primary" data-save>Save &amp; reload</button>'
    });
    m.el.querySelector("[data-save]").addEventListener("click", function () {
      var v = m.el.querySelector("#apiBase").value.trim();
      if (!/^https?:\/\//i.test(v)) { toast("Enter a URL starting with http:// or https://", "error"); return; }
      localStorage.setItem("craftline.apiBase", v.replace(/\/+$/, "")); location.reload();
    });
    m.el.querySelector("[data-reset]").addEventListener("click", function () { localStorage.removeItem("craftline.apiBase"); location.reload(); });
  }

  function mountApp(user) {
    var main = document.getElementById("main"), role = user.role === "client" ? "client" : "freelancer", key = currentKey();
    var nav = NAV[role].map(function (g) {
      return '<div class="nav-group"><div class="nav-label">' + g.label + "</div>" + g.items.map(function (i) {
        return '<a class="nav-link" href="' + i[0] + '"' + (i[0] === key ? ' aria-current="page"' : "") + ">" + icon(i[2], 18) + i[1] + "</a>";
      }).join("") + "</div>";
    }).join("");
    var shell = document.createElement("div"); shell.className = "shell";
    shell.innerHTML = '<aside class="sidebar" id="sidebar" aria-label="Primary">' + brand(Auth.home(role)) + "<nav>" + nav + "</nav>" +
      '<button class="nav-link" style="background:none;border:0;cursor:pointer;width:100%;font-size:.75rem;color:#8896a3;margin-top:auto" data-api>' + icon("link", 14) + '<span style="overflow:hidden;text-overflow:ellipsis">API · ' + esc(CFG.API_BASE_URL.replace(/^https?:\/\//, "")) + "</span></button>" +
      '<div class="sidebar-foot" style="margin-top:8px">' + avatar(user.name, "") + '<div class="who"><b>' + esc(user.name || user.email) + "</b><span>" + role + '</span></div><button data-logout aria-label="Sign out" title="Sign out">' + icon("log-out", 18) + "</button></div></aside>" +
      '<div class="scrim" id="scrim"></div><div class="main"><header class="topbar">' + brand(Auth.home(role)) + '<button class="btn btn-ghost btn-icon" id="menuBtn" aria-label="Open menu" aria-controls="sidebar">' + icon("menu", 22) + '</button></header><div class="content" id="content"></div></div>';
    main.parentNode.insertBefore(shell, main);
    shell.querySelector("#content").appendChild(main);
    var sb = shell.querySelector("#sidebar"), sc = shell.querySelector("#scrim");
    function toggle(open) { sb.classList.toggle("open", open); sc.classList.toggle("show", open); }
    shell.querySelector("#menuBtn").addEventListener("click", function () { toggle(!sb.classList.contains("open")); });
    sc.addEventListener("click", function () { toggle(false); });
    shell.querySelector("[data-logout]").addEventListener("click", Auth.logout);
    shell.querySelector("[data-api]").addEventListener("click", apiSettings);
  }
  function mountPublic(user) {
    var main = document.getElementById("main");
    var nav = document.createElement("header"); nav.className = "pubnav";
    nav.innerHTML = '<div class="wrap">' + brand("index.html") +
      '<nav class="links" id="pubLinks" aria-label="Primary"><a href="projects.html">Browse projects</a><a href="index.html#how">How it works</a><a href="index.html#ai">AI matching</a><a href="index.html#stories">Stories</a></nav>' +
      '<div class="cta">' + (user ? '<a class="btn btn-primary btn-sm" href="' + Auth.home(user.role) + '">Go to dashboard</a>' : '<a class="btn btn-ghost btn-sm" href="login.html">Sign in</a><a class="btn btn-primary btn-sm" href="register.html">Get started</a>') +
      '<button class="btn btn-ghost btn-icon burger" aria-label="Menu" aria-controls="pubLinks">' + icon("menu", 22) + "</button></div></div>";
    document.body.insertBefore(nav, document.body.firstChild);
    nav.querySelector(".burger").addEventListener("click", function () { nav.querySelector("#pubLinks").classList.toggle("open"); });
    window.addEventListener("scroll", function () { nav.classList.toggle("scrolled", window.scrollY > 8); }, { passive: true });
    if (main && main.classList.contains("wrap-page")) main.classList.add("wrap");
  }

  /* data-access: freelancer | client | auth | open | guest | public */
  function mount() {
    var access = document.body.getAttribute("data-access") || "public", user = Auth.user(), ok = Auth.loggedIn() && user;
    var file = location.pathname.split("/").pop() || "index.html";
    if (access === "guest" && ok) { location.replace(Auth.home(user.role)); return false; }
    if ((access === "auth" || access === "freelancer" || access === "client") && !ok) { location.replace("login.html?next=" + encodeURIComponent(file + location.search)); return false; }
    if ((access === "freelancer" || access === "client") && user.role !== access) { location.replace(Auth.home(user.role)); return false; }
    if (ok && (access === "auth" || access === "freelancer" || access === "client" || access === "open")) mountApp(user);
    else if (access === "open") mountPublic(null);
    else if (access === "public") mountPublic(ok ? user : null);
    var t = document.body.getAttribute("data-title"); if (t) document.title = t + " · " + CFG.APP_NAME;
    hydrate(document);
    return true;
  }

  window.UI = {
    esc: esc, icon: icon, hydrate: hydrate, qs: qs, avatar: avatar, initials: initials, slug: slug,
    fmtMoney: fmtMoney, budget: budget, fmtDate: fmtDate, relTime: relTime, pct: pct, stars: stars,
    toast: toast, modal: modal, confirm: confirmDialog, skeleton: skeleton,
    showLoading: showLoading, showError: showError, showEmpty: showEmpty, busy: busy,
    statusBadge: statusBadge, skillTags: skillTags, jobCard: jobCard,
    readMatch: readMatch, matchPanel: matchPanel, matchChip: matchChip, tagInput: tagInput,
    validate: validate, setError: setError, formAlert: formAlert, showFormError: showFormError,
    apiSettings: apiSettings, Auth: Auth, mount: mount
  };
  window.Auth = Auth;

  /* Shared reference data used by forms and filters */
  window.REF = {
    // Post a Project categories. Keep this list in sync with the category
    // taxonomy in ML/features.py and the project API documentation.
    categories: [
      "Web Development",
      "Mobile App Development",
      "AI & Generative AI",
      "Machine Learning & Deep Learning",
      "Data Science & Analytics",
      "Cybersecurity",
      "Cloud Computing",
      "Backend Development & APIs",
      "Frontend Development",
      "Full Stack Development",
      "DevOps & Cloud Engineering",
      "UI/UX Design",
      "Software Testing & QA",
      "Blockchain & Web3",
      "Game Development",
      "Database Management",
      "Embedded Systems & IoT",
      "Networking & IT Support",
      "Automation & RPA",
      "Content Writing & Copywriting",
      "Digital Marketing & SEO",
      "Graphic Design",
      "Video Editing & Animation",
      "Business & Consulting",
      "Other"
    ],
    levels: ["Entry", "Intermediate", "Expert"],
    skills: ["Python", "JavaScript", "TypeScript", "HTML/CSS", "React", "Node.js", "FastAPI", "Django", "Flask", "MongoDB", "PostgreSQL", "MySQL", "scikit-learn", "TensorFlow", "Pandas", "Docker", "AWS", "Figma", "Flutter", "Kotlin", "Swift", "Java", "REST APIs", "Git", "Tailwind CSS", "Technical Writing"]
  };
})();
