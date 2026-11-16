/* Centralized API service. Every network call in the app goes through this file.
   Nothing here fabricates data: failures are surfaced as ApiError instances. */
(function () {
  "use strict";
  var CFG = window.APP_CONFIG;

  /* ---------- Session (token + user) ---------- */
  var Session = {
    get: function () { try { return JSON.parse(localStorage.getItem(CFG.SESSION_KEY)) || null; } catch (e) { return null; } },
    set: function (s) { try { localStorage.setItem(CFG.SESSION_KEY, JSON.stringify(s)); } catch (e) { /* ignore */ } },
    clear: function () { try { localStorage.removeItem(CFG.SESSION_KEY); } catch (e) { /* ignore */ } },
    token: function () { var s = this.get(); return s && s.token; },
    user: function () { var s = this.get(); return s && s.user; }
  };

  /* ---------- Error type ---------- */
  function ApiError(message, opts) {
    opts = opts || {};
    this.name = "ApiError";
    this.message = message;
    this.status = opts.status || 0;
    this.isNetwork = !!opts.isNetwork;
    this.isTimeout = !!opts.isTimeout;
    this.fields = opts.fields || {};
  }
  ApiError.prototype = Object.create(Error.prototype);

  /* FastAPI returns {detail: "text"} or {detail: [{loc:[...], msg:"..."}]} */
  function parseDetail(body) {
    var out = { message: "", fields: {} };
    if (!body) return out;
    var d = body.detail !== undefined ? body.detail : body.message;
    if (typeof d === "string") out.message = d;
    else if (Array.isArray(d)) {
      d.forEach(function (e) {
        var loc = (e.loc || []).filter(function (p) { return p !== "body"; });
        var key = loc[loc.length - 1];
        if (key !== undefined) out.fields[key] = e.msg;
      });
      out.message = d.map(function (e) { return e.msg; }).join(". ");
    }
    return out;
  }

  /* Mongo-style _id -> id, applied recursively so UI code can rely on `id`. */
  function normalize(v) {
    if (Array.isArray(v)) return v.map(normalize);
    if (v && typeof v === "object") {
      var o = {};
      Object.keys(v).forEach(function (k) { o[k === "_id" ? "id" : k] = normalize(v[k]); });
      return o;
    }
    return v;
  }

  function buildQuery(q) {
    if (!q) return "";
    var p = new URLSearchParams();
    Object.keys(q).forEach(function (k) {
      var v = q[k];
      if (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length)) return;
      p.set(k, Array.isArray(v) ? v.join(",") : v);
    });
    var s = p.toString();
    return s ? "?" + s : "";
  }

  /* ---------- Core request ---------- */
  function request(method, path, opts) {
    opts = opts || {};
    var controller = new AbortController();
    var timeout = opts.timeout || CFG.REQUEST_TIMEOUT_MS;
    var timer = setTimeout(function () { controller.abort(); }, timeout);
    var headers = { Accept: "application/json" };
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    var token = Session.token();
    if (token && opts.auth !== false) headers.Authorization = "Bearer " + token;

    return fetch(CFG.API_BASE_URL + path + buildQuery(opts.query), {
      method: method,
      headers: headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: controller.signal
    }).then(function (res) {
      clearTimeout(timer);
      return res.text().then(function (text) {
        var data = null;
        if (text) { try { data = JSON.parse(text); } catch (e) { data = null; } }
        if (!res.ok) {
          var d = parseDetail(data);
          if (res.status === 401 && opts.auth !== false && Session.token()) {
            Session.clear();
            var next = encodeURIComponent(location.pathname.split("/").pop() + location.search);
            location.href = "login.html?expired=1&next=" + next;
          }
          var msg = d.message || ({
            400: "The server rejected this request.", 401: "You need to sign in to continue.",
            403: "You don't have permission to do that.", 404: "We couldn't find what you were looking for.",
            409: "That conflicts with existing data.", 422: "Some of the submitted details are invalid.",
            500: "The server hit an unexpected error.", 502: "The AI service is temporarily unavailable.", 503: "The service is temporarily unavailable."
          }[res.status] || "Request failed (" + res.status + ").");
          throw new ApiError(msg, { status: res.status, fields: d.fields });
        }
        return normalize(data);
      });
    }).catch(function (err) {
      clearTimeout(timer);
      if (err instanceof ApiError) throw err;
      if (err && err.name === "AbortError") throw new ApiError("The server took too long to respond.", { isTimeout: true, isNetwork: true });
      throw new ApiError("Unable to connect to the server.", { isNetwork: true });
    });
  }

  /* Normalises list responses: either a bare array or {items|results|data, total}. */
  function asList(res) {
    if (Array.isArray(res)) return { items: res, total: res.length };
    var items = (res && (res.items || res.results || res.data)) || [];
    return { items: items, total: typeof res.total === "number" ? res.total : items.length };
  }

  var matchCache = {};

  /* ---------- Endpoint contract (see docs/API_INTEGRATION.md) ---------- */
  var Api = {
    base: CFG.API_BASE_URL,
    ApiError: ApiError, Session: Session, asList: asList,

    auth: {
      register: function (payload) { return request("POST", "/auth/register", { body: payload, auth: false }); },
      login: function (email, password) { return request("POST", "/auth/login", { body: { email: email, password: password }, auth: false }); }
    },
    freelancers: {
      list: function (query) { return request("GET", "/freelancers", { query: query }); },
      get: function (id) { return request("GET", "/freelancers/" + encodeURIComponent(id)); },
      updateProfile: function (payload) { return request("PUT", "/freelancers/profile", { body: payload }); }
    },
    projects: {
      create: function (payload) { return request("POST", "/projects", { body: payload }); },
      list: function (query) { return request("GET", "/projects", { query: query }); },
      get: function (id) { return request("GET", "/projects/" + encodeURIComponent(id)); }
    },
    applications: {
      create: function (payload) { return request("POST", "/applications", { body: payload }); },
      mine: function (query) { return request("GET", "/applications/my", { query: query }); },
      withdraw: function (id) {
        return request("POST", "/applications/" + encodeURIComponent(id) + "/withdraw");
      },
      updateStatus: function (id, status, extra) {
        return request("PUT", "/applications/" + encodeURIComponent(id) + "/status", { body: Object.assign({ status: status }, extra || {}) });
      }
    },
    ml: {
      predictMatch: function (freelancerId, projectId, force) {
        var key = freelancerId + ":" + projectId;
        if (!force && matchCache[key]) return Promise.resolve(matchCache[key]);
        return request("POST", "/ml/predict-match", { body: { freelancer_id: freelancerId, project_id: projectId } })
          .then(function (r) { matchCache[key] = r; return r; });
      }
    },
    ai: {
      generateProposal: function (payload) { return request("POST", "/ai/generate-proposal", { body: payload, timeout: CFG.AI_TIMEOUT_MS }); },
      generateSummary: function (payload) { return request("POST", "/ai/generate-summary", { body: payload, timeout: CFG.AI_TIMEOUT_MS }); }
    }
  };
  window.Api = Api;
})();
