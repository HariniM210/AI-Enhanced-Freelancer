# Craftline — Frontend
Frontend for the **AI-Enhanced Freelancer Works Platform**. Plain HTML5, CSS3 and vanilla JavaScript — no frameworks, no build step.
The backend (FastAPI + MongoDB Atlas + ML + LLM) is developed separately; this app only talks to it through `js/api.js`.

## Run locally
1. Start the FastAPI backend (default `http://127.0.0.1:8000`) with CORS enabled for the origin you serve the frontend from (see `docs/API_INTEGRATION.md`).
2. Serve the `Frontend(2)` folder with any static server:
   ```bash
   cd "Frontend(2)"
   python -m http.server 5500
   ```
3. Open `http://127.0.0.1:5500/index.html`. For the Post a Project page, open
   `http://127.0.0.1:5500/post-project.html`.

> **Stale copy warning:** Do not serve the sibling `Documents/Frontend` folder.
> It is an older frontend without the expanded category list. Serve
> `C:\Users\harin\OneDrive\Documents\AI-Enhanced-Freelancer\Frontend(2)`.

Script tags load `js/ui.js?v=2`. If a browser still shows an older page after
these files change, restart the static server and hard-refresh once (`Ctrl+F5`).

Opening files with `file://` is not recommended (CORS and `localStorage` behave inconsistently).

## Configure the backend URL
Resolution order (`js/config.js`):
1. `localStorage["craftline.apiBase"]` — set from the **API · host** button at the bottom of the sidebar.
2. `window.__API_BASE_URL__` — define in a `<script>` before `config.js` for deployments.
3. Default: `http://127.0.0.1:8000`.

No API keys, LLM keys or database credentials exist in this code. They belong only in the backend.

## Behaviour when the backend is down
Nothing is mocked. Every data region shows skeleton loading, then either real data, an empty state, or a
"Can't reach the server" error with a **Try again** button. Forms show an inline error and never report a save that did not happen.

## Pages
| File | Purpose | Access |
|---|---|---|
| `index.html` | Landing page (live project discovery) | public |
| `register.html?role=freelancer\|client` | Freelancer & client registration | guest |
| `login.html` | Sign in | guest |
| `freelancer-dashboard.html` | Welcome, profile completion, recommendations, application status, AI tools, completed works | freelancer |
| `client-dashboard.html` | Project overview, applicants, ML matches, hiring pipeline, top freelancers | client |
| `profile.html` (`?id=` to view others) | Profile view/edit, portfolio, experience | signed in |
| `projects.html` (`?mine=1` for clients) | Marketplace: search, filters, sort | open |
| `project-details.html?id=` | Project details, **Apply for project** form, match panel | open |
| `applications.html` | My applications, withdraw | freelancer |
| `completed-works.html` | In-progress tracking + delivered work | freelancer |
| `post-project.html` | Post a project with live preview | client |
| `applicants.html?project=` | Manage applicants: hire / shortlist / decline, ML match | client |
| `hiring.html` | Hiring management, mark complete + rate | client |
| `ai-proposal.html` | AI proposal generator (edit, copy, save, use in application) | freelancer |
| `ai-summary.html` | AI profile summary generator (edit, copy, save to profile) | freelancer |

Pages 10 (Apply), 14 (Hiring) and 15 (Completed works / tracking) from the brief live in `project-details.html#apply`, `hiring.html` and `completed-works.html`.

## Structure
```
Frontend(2)/
  *.html            pages (all share css/base, components, layout; public pages add landing.css)
  css/              base.css (tokens, forms, buttons) · components.css · layout.css · landing.css
  js/
    config.js       base URL & runtime config
    api.js          the ONLY place that calls fetch(): ApiError, session, every endpoint
    icons.js        bundled Lucide icons (local, ISC licence)
    ui.js           app shell/sidebar, toasts, modals, validation, match panel, states
    data.js         pure helpers (profile completion, status counts)
    boot.js         mounts shell + auth guard, then loads page scripts
    <page>.js       one script per page
  assets/           favicon.svg, fonts/ (Inter, Fraunces — self-hosted, OFL)
  docs/API_INTEGRATION.md
```

## Notes
- Sessions: `access_token` + `user` are kept in `localStorage` (`craftline.session`). A `401` clears it and returns to login.
- Saved AI drafts are stored **in this browser only** (`craftline.drafts`); "Save to profile" calls `PUT /freelancers/profile`.
- Landing-page testimonials are sample copy — replace with real quotes before launch.
- Accessibility: labelled controls, visible focus, `aria-live` regions, reduced-motion support, keyboard-closable dialogs.
