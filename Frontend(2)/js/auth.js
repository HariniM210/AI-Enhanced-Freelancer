/* Login + registration (POST /auth/login, POST /auth/register) */
(function () {
  "use strict";
  var UI = window.UI, Api = window.Api;

  function safeNext() {
    var n = UI.qs("next");
    return n && /^[\w-]+\.html(\?[\w=&%.-]*)?$/.test(n) ? n : null;
  }
  function wirePasswordToggles() {
    document.querySelectorAll("[data-reveal]").forEach(function (b) {
      b.addEventListener("click", function () {
        var input = document.getElementById(b.getAttribute("data-reveal")), show = input.type === "password";
        input.type = show ? "text" : "password";
        b.setAttribute("aria-label", show ? "Hide password" : "Show password");
        b.innerHTML = UI.icon(show ? "eye-off" : "eye", 18);
      });
    });
  }

  /* ---------- Login ---------- */
  var loginForm = document.getElementById("loginForm");
  if (loginForm) {
    if (UI.qs("expired")) UI.formAlert(loginForm, "Your session expired. Please sign in again.");
    loginForm.addEventListener("submit", function (e) {
      e.preventDefault();
      UI.formAlert(loginForm, "");
      var v = UI.validate(loginForm, { email: { label: "Email", required: true, email: true }, password: { label: "Password", required: true } });
      if (!v) return;
      UI.busy(loginForm.querySelector("[type=submit]"), Api.auth.login(v.email, v.password).then(function (res) {
        var user = UI.Auth.save(res);
        location.href = safeNext() || UI.Auth.home(user.role);
      })).catch(function (err) {
        UI.formAlert(loginForm, err.isNetwork ? "Can't reach the server at " + window.APP_CONFIG.API_BASE_URL + ". Make sure the backend is running." : err.status === 401 ? "Incorrect email or password." : err.message);
      });
    });
  }

  /* ---------- Register ---------- */
  var regForm = document.getElementById("registerForm");
  if (regForm) {
    var role = UI.qs("role") === "client" ? "client" : "freelancer";
    var seg = document.getElementById("roleSwitch"), asideTitle = document.getElementById("asideTitle"), asideList = document.getElementById("asideList");
    var COPY = {
      freelancer: { title: "Do your best work, for people who value it.", points: ["Build a profile that shows what you've actually shipped", "See how well you fit a project before you apply", "Draft a tailored proposal in under a minute"], heading: "Create your freelancer account", sub: "Free to join. Start applying to projects today." },
      client: { title: "Hire people who fit the brief, not just the keywords.", points: ["Post a project and receive focused proposals", "Compare applicants with a transparent match score", "Track every hire from first message to final delivery"], heading: "Create your client account", sub: "Post your first project in about five minutes." }
    };
    function setRole(r) {
      role = r;
      seg.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.role === r ? "true" : "false"); });
      document.querySelectorAll("[data-for]").forEach(function (n) { n.hidden = n.getAttribute("data-for") !== r; });
      document.getElementById("regHeading").textContent = COPY[r].heading;
      document.getElementById("regSub").textContent = COPY[r].sub;
      asideTitle.textContent = COPY[r].title;
      asideList.innerHTML = COPY[r].points.map(function (p) { return "<li>" + UI.icon("check", 18) + "<span>" + p + "</span></li>"; }).join("");
      history.replaceState(null, "", "?role=" + r);
    }
    seg.querySelectorAll("button").forEach(function (b) { b.addEventListener("click", function () { setRole(b.dataset.role); }); });
    setRole(role);

    regForm.addEventListener("submit", function (e) {
      e.preventDefault();
      UI.formAlert(regForm, "");
      var rules = {
        name: { label: "Full name", required: true, minLength: 2, maxLength: 80 },
        email: { label: "Email", required: true, email: true },
        password: { label: "Password", required: true, minLength: 8, custom: function (v) { return /[A-Za-z]/.test(v) && /\d/.test(v) ? "" : "Use at least one letter and one number."; } },
        confirm: { label: "Confirm password", required: true, matches: "password", message: "Passwords don't match." },
        terms: { required: true, requiredMessage: "Please accept the terms to continue." }
      };
      if (role === "freelancer") {
        rules.headline = { label: "Professional title", required: true, minLength: 3, maxLength: 80 };
        rules.years_experience = { label: "Years of experience", required: true, min: 0, max: 60 };
      } else rules.company_name = { label: "Company or organisation", required: true, minLength: 2 };
      var v = UI.validate(regForm, rules);
      if (!v) return;
      var payload = { name: v.name, email: v.email, password: v.password, role: role };
      if (role === "freelancer") { payload.headline = v.headline; payload.years_experience = Number(v.years_experience); }
      else payload.company_name = v.company_name;

      UI.busy(regForm.querySelector("[type=submit]"), Api.auth.register(payload).then(function (res) {
        if (res && (res.access_token || res.token)) return res;
        return Api.auth.login(payload.email, payload.password);   // backend returned only the created user
      }).then(function (res) {
        var user = UI.Auth.save(res);
        location.href = user.role === "client" ? "client-dashboard.html" : "profile.html?welcome=1";
      })).catch(function (err) { UI.showFormError(regForm, err); });
    });
  }
  wirePasswordToggles();
})();
