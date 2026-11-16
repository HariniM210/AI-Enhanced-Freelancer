/* Regression tests for the client applicant shortlist/hire/decline contract.
 *
 * Run with Node's built-in test runner:
 *   node --test "Frontend(2)/tests/applications.test.js"
 *
 * These are source-contract tests; no browser or npm dependencies are needed.
 */

"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const FRONTEND_DIR = path.join(__dirname, "..");

function read(relativePath) {
  return fs.readFileSync(path.join(FRONTEND_DIR, relativePath), "utf8");
}

test("applicants page exposes shortlist, hire and decline actions", () => {
  const applicants = read(path.join("js", "applicants.js"));

  assert.match(applicants, /\["shortlisted", "Shortlisted"\]/);
  assert.match(applicants, /b\("shortlisted", "Shortlist"/);
  assert.match(applicants, /b\("accepted", "Hire"/);
  assert.match(applicants, /b\("rejected", "Decline"/);
});

test("shortlisted applicants can be hired or declined", () => {
  const applicants = read(path.join("js", "applicants.js"));

  assert.match(
    applicants,
    /a\.status === "shortlisted"[\s\S]*?b\("accepted", "Hire"[\s\S]*?b\("rejected", "Decline"/
  );
});

test("status badges and filters include the shortlisted state", () => {
  const ui = read(path.join("js", "ui.js"));
  const css = read(path.join("css", "components.css"));

  assert.match(ui, /shortlisted: "Shortlisted"/);
  assert.match(ui, /accepted: "Hired"/);
  assert.match(css, /\.badge\.shortlisted/);
});

test("application status updates use the backend PUT alias", () => {
  const api = read(path.join("js", "api.js"));

  assert.match(
    api,
    /updateStatus:[\s\S]*?request\("PUT", "\/applications\/"[\s\S]*?\/status"/
  );
});

test("withdrawal uses the dedicated POST endpoint", () => {
  const api = read(path.join("js", "api.js"));
  const applications = read(path.join("js", "applications.js"));

  assert.match(
    api,
    /withdraw:\s*function\s*\(id\)\s*\{[\s\S]*?request\("POST", "\/applications\/" \+ encodeURIComponent\(id\) \+ "\/withdraw"\)/
  );
  assert.match(applications, /Api\.applications\.withdraw\(a\.id\)/);
  assert.doesNotMatch(applications, /updateStatus\(/);
  assert.doesNotMatch(applications, /\/status/);
  assert.match(
    applications,
    /a\.status === "pending" \|\| a\.status === "shortlisted" \? '<button class="btn btn-danger btn-sm" data-withdraw="/
  );
  assert.match(
    applications,
    /Are you sure you want to withdraw your application\? The client will no longer consider your application for this project\./
  );
  assert.match(applications, /Application withdrawn successfully/);
  assert.match(applications, /a\.status = \(updated && updated\.status\) \|\| "withdrawn"/);
  assert.match(applications, /UI\.busy\(b, request\.finally/);
  assert.match(applications, /UI\.toast\(\(e && e\.message\)/);
});

test("withdraw sends POST /applications/{id}/withdraw with the bearer token", async () => {
  const vm = require("node:vm");
  const apiSource = read(path.join("js", "api.js"));
  const calls = [];
  const sessionKey = "craftline.session";
  const storage = new Map([
    [sessionKey, JSON.stringify({ token: "freelancer-token", user: { id: "f1", role: "freelancer" } })]
  ]);
  const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    URLSearchParams,
    AbortController,
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, String(value)); },
      removeItem(key) { storage.delete(key); }
    },
    location: { pathname: "/applications.html", search: "", href: "" },
    fetch(url, options) {
      calls.push({ url, options });
      return Promise.resolve({
        ok: true,
        status: 200,
        text() {
          return Promise.resolve(JSON.stringify({
            id: "app-1",
            status: "withdrawn",
            withdrawn_at: "2026-11-16T14:00:00+00:00"
          }));
        }
      });
    }
  };
  sandbox.window = {
    APP_CONFIG: {
      API_BASE_URL: "http://127.0.0.1:8000",
      SESSION_KEY: sessionKey,
      REQUEST_TIMEOUT_MS: 20000
    }
  };
  vm.runInNewContext(apiSource, sandbox);

  const updated = await sandbox.window.Api.applications.withdraw("app/1");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].url, "http://127.0.0.1:8000/applications/app%2F1/withdraw");
  assert.equal(calls[0].options.headers.Authorization, "Bearer freelancer-token");
  assert.equal(calls[0].options.body, undefined);
  assert.equal(updated.status, "withdrawn");
  assert.equal(updated.withdrawn_at, "2026-11-16T14:00:00+00:00");

  calls.length = 0;
  sandbox.fetch = function (url, options) {
    calls.push({ url, options });
    return Promise.resolve({
      ok: false,
      status: 409,
      text() {
        return Promise.resolve(JSON.stringify({
          detail: "Only pending or shortlisted applications can be withdrawn."
        }));
      }
    });
  };
  await assert.rejects(
    () => sandbox.window.Api.applications.withdraw("app-1"),
    (error) => {
      assert.equal(error.message, "Only pending or shortlisted applications can be withdrawn.");
      assert.equal(error.status, 409);
      return true;
    }
  );
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].url, "http://127.0.0.1:8000/applications/app-1/withdraw");
});

test("withdraw button sends POST /applications/{id}/withdraw, not PUT /status", async () => {
  const vm = require("node:vm");
  const calls = [];
  const sessionKey = "craftline.session";
  const storage = new Map([
    [sessionKey, JSON.stringify({ token: "freelancer-token", user: { id: "f1", role: "freelancer" } })]
  ]);
  function el(id) {
    const node = {
      id,
      value: "",
      listeners: {},
      withdrawClicks: [],
      setAttribute() {},
      removeAttribute() {},
      addEventListener(type, fn) { (node.listeners[type] = node.listeners[type] || []).push(fn); },
      querySelector() { return {}; },
      querySelectorAll(sel) {
        const html = node.innerHTML || "";
        if (sel === "button") {
          return [...html.matchAll(/data-tab="([^"]+)"/g)].map((m) => ({
            dataset: { tab: m[1] },
            addEventListener() {}
          }));
        }
        if (sel === "[data-view]") {
          return [...html.matchAll(/data-view="(\d+)"/g)].map((m) => ({
            dataset: { view: m[1] },
            addEventListener() {}
          }));
        }
        if (sel === "[data-withdraw]") {
          return [...html.matchAll(/data-withdraw="(\d+)"/g)].map((m) => {
            const button = {
              dataset: { withdraw: m[1] },
              disabled: false,
              isConnected: true,
              innerHTML: "Withdraw",
              addEventListener(_type, fn) { node.withdrawClicks.push(fn); }
            };
            return button;
          });
        }
        return [];
      }
    };
    node.innerHTML = "";
    return node;
  }
  const elements = { q: el("q"), tabs: el("tabs"), table: el("table") };
  const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    URLSearchParams,
    AbortController,
    Promise,
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, String(value)); },
      removeItem(key) { storage.delete(key); }
    },
    location: { pathname: "/applications.html", search: "", href: "" },
    document: { getElementById(id) { return elements[id] || null; } },
    fetch(url, options) {
      calls.push({ url, options });
      return Promise.resolve({
        ok: true,
        status: 200,
        text() {
          return Promise.resolve(JSON.stringify({
            id: "app-1",
            status: "withdrawn",
            withdrawn_at: "2026-11-16T14:00:00+00:00"
          }));
        }
      });
    }
  };
  sandbox.window = sandbox;
  sandbox.window.APP_CONFIG = {
    API_BASE_URL: "http://127.0.0.1:8000",
    SESSION_KEY: sessionKey,
    REQUEST_TIMEOUT_MS: 20000
  };
  vm.runInNewContext(read(path.join("js", "data.js")), sandbox);
  vm.runInNewContext(read(path.join("js", "api.js")), sandbox);
  sandbox.window.UI = {
    Auth: { user: () => ({ id: "f1", role: "freelancer" }) },
    esc: (s) => String(s == null ? "" : s),
    fmtMoney: (n) => "$" + n,
    fmtDate: (d) => String(d),
    statusBadge: (s) => '<span class="badge ' + s + '">' + s + "</span>",
    showLoading() {},
    showError(_el, e) { throw e; },
    showEmpty() {},
    matchChip() {},
    modal() {},
    toast() {},
    confirm: () => Promise.resolve(true),
    busy(_button, promise) { return promise; }
  };
  sandbox.window.Api.applications.mine = function () {
    return Promise.resolve({ items: [
      { id: "app-1", status: "pending", bid_amount: 100, currency: "USD", created_at: "2026-11-01", project_id: "p1", project_title: "Site", client_name: "Ada", cover_letter: "Hello" }
    ] });
  };
  vm.runInNewContext(read(path.join("js", "applications.js")), sandbox);
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert.equal(elements.table.withdrawClicks.length, 1);
  elements.table.withdrawClicks[0]();
  await new Promise((resolve) => setTimeout(resolve, 30));

  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].url, "http://127.0.0.1:8000/applications/app-1/withdraw");
  assert.equal(calls[0].options.headers.Authorization, "Bearer freelancer-token");
  assert.equal(calls[0].options.body, undefined);
  assert.equal(calls.some((call) => String(call.url).includes("/status")), false);
  assert.equal(elements.table.innerHTML.includes('class="badge withdrawn"') || elements.table.innerHTML.includes(">withdrawn<"), true);
});

test("client active applicants exclude withdrawn applications", () => {
  const applicants = read(path.join("js", "applicants.js"));
  const dashboard = read(path.join("js", "dash-client.js"));

  assert.match(applicants, /a\.status !== "withdrawn"/);
  assert.match(applicants, /a\.status === "withdrawn"\) return ""/);
  assert.match(applicants, /a\.status === "withdrawn"/);
  assert.match(dashboard, /a\.status !== "withdrawn"/);
});
