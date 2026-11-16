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
