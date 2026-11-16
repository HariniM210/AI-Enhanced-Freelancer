/* Phase 6 regression tests for the existing AI page contract.
 *
 * Run with Node's built-in test runner:
 *   node --test "Frontend(2)/tests/ai.test.js"
 *
 * No browser or npm dependencies are required.
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

test("AI API helpers target the approved Phase 6 endpoints", () => {
  const api = read(path.join("js", "api.js"));

  assert.match(api, /"\/ai\/generate-proposal"/);
  assert.match(api, /"\/ai\/generate-summary"/);
  assert.match(api, /CFG\.AI_TIMEOUT_MS/);
});

test("AI requests use the dedicated long timeout", () => {
  const config = read(path.join("js", "config.js"));

  assert.match(config, /AI_TIMEOUT_MS:\s*90000/);
});

test("AI pages are freelancer-only and load the shared workspace", () => {
  for (const page of ["ai-proposal.html", "ai-summary.html"]) {
    const html = read(page);
    assert.match(html, /data-access="freelancer"/);
    assert.match(html, /data-scripts="ai-workspace\.js"/);
  }
});

test("AI workspace keeps generation, review and saving explicit", () => {
  const workspace = read(path.join("js", "ai-workspace.js"));

  assert.match(workspace, /Api\.ai\.generateProposal/);
  assert.match(workspace, /Api\.ai\.generateSummary/);
  assert.match(workspace, /Api\.freelancers\.updateProfile/);
  assert.match(workspace, /project-details\.html/);
  assert.doesNotMatch(workspace, /Api\.applications\.create/);
});

test("AI workspace surfaces the backend's safe error detail", () => {
  const workspace = read(path.join("js", "ai-workspace.js"));

  assert.doesNotMatch(workspace, /The AI model couldn't be reached by the backend/);
  assert.match(workspace, /UI\.showError\(\$\("errorState"\), e,/);
});

test("frontend source contains no Gemini key or client-side API key", () => {
  const files = [];
  const extensions = new Set([".js", ".html", ".css"]);

  function walk(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === "tests") continue;
      const fullPath = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (extensions.has(path.extname(entry.name).toLowerCase())) {
        files.push(fullPath);
      }
    }
  }

  walk(FRONTEND_DIR);

  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    assert.doesNotMatch(text, /GEMINI_API_KEY/);
    assert.doesNotMatch(text, /AIza[0-9A-Za-z_-]{20,}/);
    assert.doesNotMatch(text, /\bapiKey\b/);
  }
});
