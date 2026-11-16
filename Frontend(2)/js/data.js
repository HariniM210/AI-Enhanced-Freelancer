/* Pure helpers for reading backend objects consistently (no network, no fake data). */
(function () {
  "use strict";
  var Data = {
    appProject: function (a) {
      var p = a.project || {};
      return { id: a.project_id || p.id, title: a.project_title || p.title || "Untitled project", client: a.client_name || p.client_name || "", budget: p, raw: p };
    },
    appFreelancer: function (a) {
      var f = a.freelancer || {};
      return { id: a.freelancer_id || f.id, name: a.freelancer_name || f.name || "Freelancer", headline: a.freelancer_headline || f.headline || "", raw: f };
    },
    overlap: function (mine, required) {
      var set = (mine || []).map(function (s) { return s.toLowerCase(); });
      return (required || []).filter(function (s) { return set.indexOf(s.toLowerCase()) > -1; });
    },
    /* Profile completion from real profile fields. */
    completion: function (p) {
      p = p || {};
      var checks = [
        { key: "headline", label: "Add a professional headline", ok: !!p.headline, w: 15 },
        { key: "summary", label: "Write a profile summary", ok: !!(p.summary && p.summary.length > 40), w: 20, link: "ai-summary.html" },
        { key: "skills", label: "List at least 3 skills", ok: (p.skills || []).length >= 3, w: 20 },
        { key: "years", label: "Set years of experience", ok: p.years_experience != null && p.years_experience !== "", w: 10 },
        { key: "rate", label: "Set your hourly rate", ok: !!p.hourly_rate, w: 10 },
        { key: "location", label: "Add your location", ok: !!p.location, w: 5 },
        { key: "portfolio", label: "Add a portfolio project", ok: (p.portfolio || []).length >= 1, w: 20 }
      ];
      var score = checks.reduce(function (s, c) { return s + (c.ok ? c.w : 0); }, 0);
      return { score: score, checks: checks };
    },
    byStatus: function (apps) {
      var c = { pending: 0, shortlisted: 0, accepted: 0, rejected: 0, completed: 0, withdrawn: 0 };
      apps.forEach(function (a) { if (c[a.status] !== undefined) c[a.status]++; });
      return c;
    },
    firstName: function (n) { return String(n || "there").split(/\s+/)[0]; },
    greeting: function () { var h = new Date().getHours(); return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"; }
  };
  window.Data = Data;
})();
