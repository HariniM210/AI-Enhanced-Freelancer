/* Runtime configuration.
   Backend base URL resolution order:
   1. localStorage "craftline.apiBase"  (set it from the browser console or Settings dialog)
   2. window.__API_BASE_URL__            (define in a <script> before config.js for deployments)
   3. http://127.0.0.1:8000              (local FastAPI default)
   No API keys or credentials belong in frontend code. */
(function () {
  var stored = null;
  try { stored = localStorage.getItem("craftline.apiBase"); } catch (e) { /* storage blocked */ }
  window.APP_CONFIG = Object.freeze({
    APP_NAME: "Craftline",
    API_BASE_URL: (stored || window.__API_BASE_URL__ || "https://craftline-backend.onrender.com").replace(/\/+$/, ""),
    REQUEST_TIMEOUT_MS: 20000,
    AI_TIMEOUT_MS: 90000,
    SESSION_KEY: "craftline.session",
    DRAFTS_KEY: "craftline.drafts"
  });
})();
