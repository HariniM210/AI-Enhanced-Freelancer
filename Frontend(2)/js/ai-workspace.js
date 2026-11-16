/* AI workspace for proposals and profile summaries.
   POST /ai/generate-proposal, POST /ai/generate-summary — output comes only from the backend LLM. */
(function () {
  "use strict";
  var UI = window.UI, Api = window.Api, REF = window.REF, CFG = window.APP_CONFIG;
  var mode = document.body.getAttribute("data-mode"), user = UI.Auth.user();
  var $ = function (i) { return document.getElementById(i); };
  var form = $("aiForm"), editor = $("draft"), profile = null, project = null, skillsCtl = null, lastPayload = null;
  var isProposal = mode === "proposal";

  /* ---------- Local drafts (this browser only) ---------- */
  function drafts() { try { return JSON.parse(localStorage.getItem(CFG.DRAFTS_KEY)) || []; } catch (e) { return []; } }
  function putDrafts(d) { try { localStorage.setItem(CFG.DRAFTS_KEY, JSON.stringify(d.slice(0, 20))); return true; } catch (e) { UI.toast("Browser storage is unavailable, so the draft couldn't be saved.", "error"); return false; } }
  function renderDrafts() {
    var list = drafts().filter(function (d) { return d.type === mode && d.owner === user.id; }), host = $("drafts");
    host.innerHTML = list.length ? list.map(function (d, i) { return '<button type="button" class="saved-item" data-i="' + i + '"><b>' + UI.esc(d.title) + "</b><span>Saved " + UI.relTime(d.at) + "</span></button>"; }).join("") : '<p class="small muted">Drafts you save appear here. They are stored only in this browser.</p>';
    host.querySelectorAll("[data-i]").forEach(function (b) { b.addEventListener("click", function () { setDraft(list[+b.dataset.i].text); UI.toast("Draft loaded.", "success"); }); });
  }

  /* ---------- Editor states ---------- */
  function count() { var w = editor.value.trim() ? editor.value.trim().split(/\s+/).length : 0; $("wc").textContent = w + " words · " + editor.value.length + " characters"; }
  function toggleTools(on) { document.querySelectorAll("[data-needs-draft]").forEach(function (b) { b.disabled = !on; }); }
  function setDraft(text) { $("emptyState").hidden = true; $("loadingState").hidden = true; $("errorState").hidden = true; $("editorWrap").hidden = false; editor.value = text; count(); toggleTools(true); editor.focus(); }
  function setLoading() { $("emptyState").hidden = true; $("errorState").hidden = true; $("editorWrap").hidden = true; $("loadingState").hidden = false; }
  function setError(e) {
    $("loadingState").hidden = true; $("editorWrap").hidden = true; $("emptyState").hidden = true; $("errorState").hidden = false;
    /* Preserve the backend's safe, actionable detail (for example a 503
       permission/configuration message) instead of replacing it. */
    UI.showError($("errorState"), e, function () { generate(); });
  }

  function generate() {
    UI.formAlert(form, "");
    var payload = build(); if (!payload) return;
    lastPayload = payload; setLoading();
    var btn = form.querySelector("[type=submit]"); btn.disabled = true;
    (isProposal ? Api.ai.generateProposal(payload) : Api.ai.generateSummary(payload)).then(function (r) {
      var text = r && (r.proposal || r.summary || r.content || r.text || r.generated_text);
      if (!text) throw new Api.ApiError("The server returned an empty response (expected a proposal, summary, content or text field).");
      setDraft(text); UI.toast("Draft generated. Review and edit before using it.", "success");
    }).catch(setError).finally(function () { btn.disabled = false; });
  }

  function build() {
    var f = form.elements;
    if (isProposal) {
      var v = UI.validate(form, { project_id: { label: "Project", required: true, requiredMessage: "Choose the project you're applying to." }, delivery_days: { label: "Delivery time", min: 1, max: 730 }, bid_amount: { label: "Bid", min: 1 } });
      if (!v) return null;
      return { project_id: v.project_id, freelancer_id: user.id, tone: f.tone.value, length: f.length.value, highlights: f.highlights.value.trim() || undefined, bid_amount: v.bid_amount ? Number(v.bid_amount) : undefined, delivery_days: v.delivery_days ? Number(v.delivery_days) : undefined };
    }
    var s = UI.validate(form, { headline: { label: "Headline", required: true, minLength: 3 }, years_experience: { label: "Years of experience", required: true, min: 0, max: 60 } });
    var sk = skillsCtl.get(); UI.setError(form, "skills", sk.length ? "" : "Add at least one skill.");
    if (!s || !sk.length) return null;
    return { freelancer_id: user.id, headline: s.headline, years_experience: Number(s.years_experience), skills: sk, highlights: f.highlights.value.trim() || undefined, tone: f.tone.value, length: f.length.value, audience: f.audience.value };
  }

  /* ---------- Toolbar actions ---------- */
  $("copyBtn").addEventListener("click", function () {
    var t = editor.value; if (!t) return;
    (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(function () { UI.toast("Copied to clipboard.", "success"); }).catch(function () { editor.select(); try { document.execCommand("copy"); UI.toast("Copied to clipboard.", "success"); } catch (e) { UI.toast("Couldn't copy. Select the text and copy it manually.", "error"); } });
  });
  $("saveDraftBtn").addEventListener("click", function () {
    if (!editor.value.trim()) return;
    var d = drafts(); d.unshift({ type: mode, owner: user.id, title: (isProposal ? (project && project.title) || "Proposal draft" : "Profile summary") + " · " + new Date().toLocaleDateString(), text: editor.value, at: new Date().toISOString() });
    if (putDrafts(d)) { UI.toast("Draft saved in this browser.", "success"); renderDrafts(); }
  });
  $("regenBtn").addEventListener("click", function () { generate(); });
  editor.addEventListener("input", count);
  var primary = $("primaryBtn");
  if (isProposal) primary.addEventListener("click", function () {
    var pid = form.elements.project_id.value; if (!pid || !editor.value.trim()) return;
    try { localStorage.setItem("craftline.useProposal", JSON.stringify({ projectId: pid, text: editor.value })); } catch (e) { return UI.toast("Browser storage is unavailable.", "error"); }
    location.href = "project-details.html?id=" + encodeURIComponent(pid) + "#apply";
  });
  else primary.addEventListener("click", function () {
    var text = editor.value.trim(); if (!text) return;
    UI.busy(primary, Api.freelancers.updateProfile({ summary: text }).then(function () { UI.toast("Summary saved to your profile.", "success"); })).catch(function (e) { UI.toast(e.isNetwork ? "Can't reach the server. Your profile was not changed." : e.message, "error"); });
  });

  form.addEventListener("submit", function (e) { e.preventDefault(); generate(); });

  /* ---------- Setup ---------- */
  function init() {
    toggleTools(false); renderDrafts();
    $("tone").innerHTML = ["Professional", "Friendly", "Confident", "Concise"].map(function (t) { return "<option>" + t + "</option>"; }).join("");
    if (!isProposal) {
      skillsCtl = UI.tagInput($("skillsAI"), { suggestions: REF.skills, placeholder: "Add a skill, press Enter", label: "Key skills", max: 15 });
    }
    var reqs = [Api.freelancers.get(user.id).catch(function () { return null; })];
    if (isProposal) reqs.push(Api.projects.list({ status: "open", limit: 100 }).catch(function (e) { return e; }));
    Promise.all(reqs).then(function (r) {
      profile = r[0];
      if (!isProposal) {
        if (profile) { form.elements.headline.value = profile.headline || ""; form.elements.years_experience.value = profile.years_experience != null ? profile.years_experience : ""; skillsCtl.set(profile.skills || []); }
        else UI.toast("Couldn't load your profile to pre-fill this form.", "error");
        return;
      }
      var sel = form.elements.project_id;
      if (r[1] instanceof Error) { sel.innerHTML = '<option value="">Projects unavailable</option>'; $("projectHint").textContent = r[1].isNetwork ? "Can't reach the server to load projects." : r[1].message; return; }
      var list = Api.asList(r[1]).items;
      sel.innerHTML = '<option value="">Select a project…</option>' + list.map(function (p) { return '<option value="' + UI.esc(p.id) + '">' + UI.esc(p.title) + "</option>"; }).join("");
      var pre = UI.qs("project"); if (pre) { sel.value = pre; if (sel.value !== pre) Api.projects.get(pre).then(function (p) { sel.insertAdjacentHTML("beforeend", '<option value="' + UI.esc(p.id) + '">' + UI.esc(p.title) + "</option>"); sel.value = p.id; showProject(p); }).catch(function () {}); }
      sel.addEventListener("change", function () { showProject(list.filter(function (p) { return p.id === sel.value; })[0]); });
      if (sel.value) showProject(list.filter(function (p) { return p.id === sel.value; })[0]);
    });
  }
  function showProject(p) {
    project = p || null; var h = $("projectHint");
    h.innerHTML = p ? UI.esc(UI.budget(p).text) + (p.deadline ? " · due " + UI.fmtDate(p.deadline) : "") + (p.skills && p.skills.length ? " · " + UI.esc(p.skills.slice(0, 4).join(", ")) : "") : "The proposal is written for this project and your profile.";
  }
  init();
})();
