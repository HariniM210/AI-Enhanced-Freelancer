/* Regression tests for the shared project category list.
 *
 * Run with Node's built-in test runner:
 *   node --test "Frontend(2)/tests/categories.test.js"
 */

"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const FRONTEND_DIR = path.join(__dirname, "..");
const UI_PATH = path.join(FRONTEND_DIR, "js", "ui.js");
const POST_PROJECT_PATH = path.join(FRONTEND_DIR, "js", "post-project.js");
const PROJECTS_PATH = path.join(FRONTEND_DIR, "js", "projects.js");
const LANDING_PATH = path.join(FRONTEND_DIR, "js", "landing.js");
const POST_PROJECT_HTML_PATH = path.join(FRONTEND_DIR, "post-project.html");

const EXPECTED_CATEGORIES = [
  "Web Development",
  "Mobile App Development",
  "AI & Generative AI",
  "Machine Learning & Deep Learning",
  "Data Science & Analytics",
  "Cybersecurity",
  "Cloud Computing",
  "Backend Development & APIs",
  "Frontend Development",
  "Full Stack Development",
  "DevOps & Cloud Engineering",
  "UI/UX Design",
  "Software Testing & QA",
  "Blockchain & Web3",
  "Game Development",
  "Database Management",
  "Embedded Systems & IoT",
  "Networking & IT Support",
  "Automation & RPA",
  "Content Writing & Copywriting",
  "Digital Marketing & SEO",
  "Graphic Design",
  "Video Editing & Animation",
  "Business & Consulting",
  "Other"
];

function loadWindow() {
  const window = {
    APP_CONFIG: { API_BASE_URL: "http://127.0.0.1:8000" },
    Api: {}
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
  return window;
}

test("REF.categories contains the full Post a Project list in order", function () {
  const categories = Array.from(loadWindow().REF.categories);

  assert.deepEqual(categories, EXPECTED_CATEGORIES);
  assert.equal(new Set(categories).size, categories.length);
  assert.equal(categories[categories.length - 1], "Other");
});

test("all categories fit the backend's category length validation", function () {
  for (const category of EXPECTED_CATEGORIES) {
    assert.ok(category.length >= 1);
    assert.ok(category.length <= 80);
  }
});

test("Post a Project, marketplace filter and landing chips use REF.categories", function () {
  assert.match(
    fs.readFileSync(POST_PROJECT_PATH, "utf8"),
    /REF\.categories\.map/
  );
  assert.match(fs.readFileSync(PROJECTS_PATH, "utf8"), /REF\.categories\.map/);
  assert.match(fs.readFileSync(LANDING_PATH, "utf8"), /REF\.categories/);
});

test("every page loads the versioned shared ui.js", function () {
  const htmlFiles = fs
    .readdirSync(FRONTEND_DIR)
    .filter((name) => name.endsWith(".html"));

  assert.ok(htmlFiles.includes("post-project.html"));
  for (const file of htmlFiles) {
    const html = fs.readFileSync(path.join(FRONTEND_DIR, file), "utf8");
    assert.match(
      html,
      /<script src="js\/ui\.js\?v=[^"]+"><\/script>/,
      `${file} must load js/ui.js with a cache-busting query`
    );
  }
});

test("Post a Project loads the shared UI before the page script", function () {
  const html = fs.readFileSync(POST_PROJECT_HTML_PATH, "utf8");

  assert.match(html, /<script src="js\/ui\.js\?v=2"><\/script>/);
  assert.match(html, /<script src="js\/boot\.js" data-scripts="post-project\.js"><\/script>/);
});
