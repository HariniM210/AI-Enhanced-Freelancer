/* Frontend regression tests for the ML match presentation.
 *
 * Run with Node's built-in test runner:
 *   node --test "Frontend(2)/tests/ui-match.test.js"
 *
 * No browser or npm dependencies are required. ui.js is evaluated in a small
 * vm context so the real readMatch/matchPanel/matchChip implementation is
 * exercised, not a copy.
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const UI_PATH = path.join(__dirname, "..", "js", "ui.js");

function loadUI(api) {
  const window = {
    APP_CONFIG: { API_BASE_URL: "http://127.0.0.1:8000" },
    Api: api || {}
  };
  const context = vm.createContext({
    window,
    console,
    setTimeout,
    clearTimeout
  });
  vm.runInContext(fs.readFileSync(UI_PATH, "utf8"), context, {
    filename: UI_PATH
  });
  return window.UI;
}

function fakeSlot() {
  let html = "";
  const slot = {
    firstChild: null,
    get innerHTML() {
      return html;
    },
    set innerHTML(value) {
      html = value;
      slot.firstChild = { addEventListener: function () {} };
    }
  };
  return slot;
}

const lowResult = {
  label: "Low Match",
  rubric_score: 48.2,
  confidence: 0.66,
  match_percentage: 66,
  probabilities: { strong: 0.14, moderate: 0.2, low: 0.66 },
  features: {
    skills_match_percentage: 25,
    years_experience: 1,
    experience_level: "Entry",
    category_relevance: 0.2,
    avg_rating: 2
  }
};

test("readMatch uses rubric_score for fit and keeps confidence separate", function () {
  const match = loadUI().readMatch(lowResult);

  assert.equal(match.label, "Low Match");
  assert.equal(match.key, "low");
  assert.equal(match.pct, 48.2);
  assert.equal(match.rubricScore, 48.2);
  assert.equal(Math.round(match.confidencePct), 66);
});

test("readMatch never treats match_percentage as a fit score", function () {
  const match = loadUI().readMatch({
    label: "Strong Match",
    confidence: 0.56,
    match_percentage: 56
  });

  assert.equal(match.pct, null);
  assert.equal(match.rubricScore, null);
  assert.equal(Math.round(match.confidencePct), 56);
});

test("matchPanel displays the label, rubric fit and model confidence", function () {
  const html = loadUI().matchPanel(lowResult);

  assert.match(html, /Low Match/);
  assert.match(html, /Rubric fit score 48%/);
  assert.match(html, /<dt>Model confidence<\/dt><dd>66%<\/dd>/);
});

test("matchPanel falls back to label and confidence without a rubric score", function () {
  const html = loadUI().matchPanel({
    label: "Strong Match",
    confidence: 0.56,
    match_percentage: 56
  });

  assert.match(html, /Strong Match/);
  assert.match(html, /Rubric fit unavailable/);
  assert.match(html, /<dt>Model confidence<\/dt><dd>56%<\/dd>/);
  assert.doesNotMatch(html, /56% fit/);
});

test("matchChip renders label, fit and confidence from the same mapping", async function () {
  const UI = loadUI({
    ml: {
      predictMatch: function () {
        return Promise.resolve(lowResult);
      }
    }
  });
  const slot = fakeSlot();

  const run = UI.matchChip(slot, "freelancer-1", "project-1", "Test project");
  assert.equal(typeof run, "function");
  run();
  await new Promise(function (resolve) {
    setImmediate(resolve);
  });

  assert.match(slot.innerHTML, /Low Match/);
  assert.match(slot.innerHTML, /48% fit/);
  assert.match(slot.innerHTML, /66% conf/);
  assert.match(
    slot.innerHTML,
    /aria-label="Low Match, rubric fit 48 percent, model confidence 66 percent"/
  );
});
