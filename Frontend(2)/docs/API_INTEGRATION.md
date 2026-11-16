# API Integration Guide
Base URL: `http://127.0.0.1:8000` (configurable). JSON in/out. Authenticated calls send `Authorization: Bearer <access_token>`.
The frontend converts Mongo `_id` to `id` automatically. List endpoints may return a bare array **or** `{ "items": [...], "total": n }`.
Errors: FastAPI shape `{ "detail": "message" }` or the 422 list `{ "detail": [{ "loc": ["body","email"], "msg": "…" }] }` (field errors are shown inline). A `401` signs the user out.

## CORS (FastAPI)
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5500","http://localhost:5500"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
```

## Auth
**POST /auth/register**
```json
{ "name":"Aarav Sharma","email":"a@x.com","password":"Passw0rd1","role":"freelancer",
  "headline":"Full-stack developer","years_experience":3 }          // freelancer
{ "name":"Priya Nair","email":"p@x.com","password":"Passw0rd1","role":"client","company_name":"Northwind" }  // client
```
Response: same as login (preferred) **or** the created user — then the frontend logs in automatically.

**POST /auth/login** `{ "email","password" }` →
```json
{ "access_token":"…","token_type":"bearer","user":{"id":"…","name":"…","email":"…","role":"freelancer|client","company_name":"…"} }
```
For freelancers, `user.id` must equal the freelancer profile id used by `/freelancers/{id}`.

## Freelancers
**GET /freelancers** — query: `limit`, `sort=rating`, optional `skills`, `q`. → list of freelancer objects.
**GET /freelancers/{id}**
```json
{ "id":"…","name":"…","headline":"…","summary":"…","location":"…","availability":"Available now",
  "skills":["Python","FastAPI"],"years_experience":3,"experience_level":"Entry|Intermediate|Expert",
  "hourly_rate":25,"currency":"USD","avg_rating":4.6,"reviews_count":5,"completed_projects":4,"avatar_url":null,
  "portfolio":[{"title":"","description":"","url":"https://…","technologies":[""]}],
  "work_history":[{"role":"","company":"","period":"2022 – 2024","description":""}] }
```
**PUT /freelancers/profile** — body: any subset of the fields above (the AI page sends only `{ "summary": "…" }`). Returns the updated profile (or any object).

## Projects
**POST /projects**
```json
{ "title":"","category":"Backend Development & APIs","description":"","skills":["Python"],"experience_level":"Intermediate",
  "budget_type":"fixed|hourly","budget_min":1200,"budget_max":2000,"currency":"USD","deadline":"2026-12-20",
  "duration":"6 weeks","requirements":["…"] }
```
`category` values come from `REF.categories` in `js/ui.js`. The backend keeps
category validation permissive (1–80 characters), so all current categories and
legacy project category names remain valid. Returns the created project (needs
`id`). `client_id`/`client_name` come from the token.
**GET /projects** — query: `status=open`, `mine=true` (client's own projects), `limit`, `sort=recent`. Search/filter/sort also run client-side on the loaded list.
**GET /projects/{id}** → project object:
`id,title,description,category,skills[],budget_min,budget_max,currency,budget_type,deadline,duration,experience_level,status("open|in_progress|completed|closed"),client_id,client_name,location,requirements[],deliverables[],created_at,applications_count`.

## Applications
**POST /applications** `{ "project_id","cover_letter","bid_amount","delivery_days" }` (freelancer from token).
**GET /applications/my** — role-aware: a freelancer gets *their* applications; a client gets applications *received on their projects*. Query `limit`.
```json
{ "id":"…","project_id":"…","project_title":"…","client_name":"…","freelancer_id":"…",
  "freelancer":{"name":"","headline":"","skills":[],"avg_rating":4.6,"years_experience":3,"avatar_url":null},
  "status":"pending|shortlisted|accepted|rejected|withdrawn|completed",
  "cover_letter":"…","bid_amount":1500,"currency":"USD","delivery_days":21,
  "rating":5,"review":"…","created_at":"…","updated_at":"…","completed_at":"…" }
```
(`freelancer_name`/`freelancer_headline` flat fields are also accepted.)
**PUT /applications/{id}/status** `{ "status":"shortlisted|accepted|rejected|withdrawn|completed" }`; for `completed` the body also carries `"rating":1-5` and optional `"review"`. Freelancers may only set `withdrawn`; clients the rest.

## Machine learning
**POST /ml/predict-match** `{ "freelancer_id":"…","project_id":"…" }` →
```json
{ "label":"Strong Match",                      // Random Forest predicted class
  "rubric_score":95.6,                          // deterministic 0–100 fit score from live features
  "confidence":0.9142,                          // predicted-class probability (0–1)
  "match_percentage":91.42,                     // deprecated alias for confidence * 100
  "expected_match_score":94.21,                 // internal ranking score, not a calibrated probability
  "probabilities":{"strong":0.9142,"moderate":0.0715,"low":0.0143},   // optional; 0–1 or 0–100
  "features":{ "skills_match_percentage":75,"years_experience":3,"experience_level":"Intermediate",
    "category_relevance":0.9,"avg_rating":4.6,
    "matched_skills":["Python","FastAPI"],"missing_skills":["MongoDB"],
    "required_technologies":["Python","FastAPI","MongoDB"] } }
```
`label` is always the model's predicted class. `rubric_score` is the fit score
shown in match chips and panels. `confidence` is displayed separately as the
model's predicted-class probability. `match_percentage` is retained only for
older clients and must not be shown as a fit score. Every field except `label`
is optional; the match panel renders only what is returned. Nothing is
predicted in the browser.

## Generative AI

Both endpoints require a freelancer bearer token. The backend loads the
freelancer profile and project from MongoDB; the browser sends only ids and
writing preferences. `freelancer_id` is optional, but when supplied it must
match the JWT identity. The project must have `status: "open"`.

**POST /ai/generate-proposal**

```json
{
  "project_id": "66f1a2b3c4d5e6f7a8b9c0d2",
  "freelancer_id": "66f1a2b3c4d5e6f7a8b9c0d4",
  "tone": "Professional",
  "length": "medium",
  "highlights": "Mention the FastAPI migration work.",
  "bid_amount": 1500,
  "delivery_days": 21
}
```

→ `{ "proposal": "…" }`

**POST /ai/generate-summary**

```json
{
  "freelancer_id": "66f1a2b3c4d5e6f7a8b9c0d4",
  "headline": "Full-stack developer",
  "years_experience": 3,
  "skills": ["Python", "FastAPI", "MongoDB"],
  "highlights": "Delivered two production APIs.",
  "tone": "Professional",
  "length": "medium",
  "audience": "clients"
}
```

→ `{ "summary": "…" }`

The stored MongoDB profile is the source of truth for summaries. The
`headline`, `years_experience` and `skills` fields are accepted for
compatibility but are not treated as authoritative. Output is editable text:
proposal generation never creates an application, and summary generation never
updates the profile. Saving or submitting remains an explicit frontend action.
Generated proposals are capped at 2,000 characters and summaries at 1,200
characters. The frontend also accepts `content`, `text` or `generated_text`
response fields.

Error handling: `401` authentication required, `403` freelancer role or
identity mismatch, `404` profile/project not found, `409` project not open,
`422` invalid input, `429` Gemini rate limit, `502` upstream or empty response,
`503` missing Gemini configuration, unavailable model, or rejected credentials/project access, `504` Gemini timeout. The browser
uses a 90-second AI timeout.

## Not in the original contract (assumptions to implement or adjust)
`mine=true` on `/projects`, role-aware `/applications/my`, `rating`/`review` on status update, and query params above. If you prefer dedicated endpoints, change them only in `js/api.js`.
