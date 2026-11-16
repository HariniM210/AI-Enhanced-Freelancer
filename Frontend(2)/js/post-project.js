/* Client: post a project (POST /projects) with live listing preview. */
(function () {
  "use strict";
  var UI = window.UI, Api = window.Api, REF = window.REF;
  var form = document.getElementById("projectForm");
  var user = UI.Auth.user();

  form.elements.category.innerHTML = '<option value="">Select a category</option>' + REF.categories.map(function (c) { return "<option>" + UI.esc(c) + "</option>"; }).join("");
  form.elements.experience_level.innerHTML = REF.levels.map(function (c) { return "<option>" + c + "</option>"; }).join("");
  var skills = UI.tagInput(document.getElementById("skillsInput"), { suggestions: REF.skills, placeholder: "Add a skill, press Enter", max: 12, label: "Required skills" });
  var tomorrow = new Date(Date.now() + 864e5).toISOString().slice(0, 10);
  form.elements.deadline.min = tomorrow;

  function lines(v) { return v.split("\n").map(function (s) { return s.trim(); }).filter(Boolean); }
  function preview() {
    var f = form.elements;
    var p = { id: "preview", title: f.title.value.trim() || "Your project title", description: f.description.value.trim() || "Your description will appear here as freelancers see it.", category: f.category.value, skills: skills.get(), experience_level: f.experience_level.value,
      budget_min: f.budget_min.value ? Number(f.budget_min.value) : null, budget_max: f.budget_max.value ? Number(f.budget_max.value) : null, currency: f.currency.value, budget_type: f.budget_type.value, deadline: f.deadline.value, client_name: user.company_name || user.name, status: "open" };
    var host = document.getElementById("preview");
    host.innerHTML = UI.jobCard(p, {});
    host.querySelectorAll("a").forEach(function (a) { a.removeAttribute("href"); a.style.pointerEvents = "none"; });
  }
  form.addEventListener("input", preview); form.addEventListener("change", preview); document.getElementById("skillsInput").addEventListener("change", preview); preview();

  var desc = form.elements.description, dc = document.getElementById("descCount");
  desc.addEventListener("input", function () { dc.textContent = desc.value.length; });

  form.addEventListener("submit", function (e) {
    e.preventDefault(); UI.formAlert(form, "");
    var v = UI.validate(form, {
      title: { label: "Project title", required: true, minLength: 10, maxLength: 120 },
      category: { label: "Category", required: true, requiredMessage: "Choose a category." },
      description: { label: "Description", required: true, minLength: 80, maxLength: 5000 },
      budget_min: { label: "Minimum budget", required: true, min: 1 },
      budget_max: { label: "Maximum budget", required: true, min: 1, custom: function (val, all) { return Number(val) < Number(all.budget_min) ? "Maximum can't be lower than the minimum." : ""; } },
      deadline: { label: "Deadline", required: true, custom: function (val) { return val < tomorrow ? "Choose a date in the future." : ""; } }
    });
    var sk = skills.get();
    UI.setError(form, "skills", sk.length ? "" : "Add at least one required skill.");
    if (!v || !sk.length) { if (!sk.length) document.getElementById("skillsInput").querySelector("input").focus(); return; }
    var f = form.elements;
    var payload = { title: v.title, category: v.category, description: v.description, skills: sk, experience_level: f.experience_level.value, budget_type: f.budget_type.value, budget_min: Number(v.budget_min), budget_max: Number(v.budget_max), currency: f.currency.value, deadline: v.deadline, duration: f.duration.value.trim() || undefined, requirements: lines(f.requirements.value) };
    UI.busy(form.querySelector("[type=submit]"), Api.projects.create(payload).then(function (created) {
      UI.toast("Project published.", "success");
      setTimeout(function () { location.href = created && created.id ? "applicants.html?project=" + encodeURIComponent(created.id) : "projects.html?mine=1"; }, 700);
    })).catch(function (err) { UI.showFormError(form, err); });
  });
})();
