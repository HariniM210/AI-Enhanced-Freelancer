# CraftLine AI — Phase 6

## MongoDB Atlas connection

The backend reads `MONGODB_URI` from the project-root `.env` (see
`.env.example`). Atlas requires TLS, and the connecting public IP must be in
the cluster's **Network Access** list. Free/M0 clusters also pause after
inactivity.

Run the sanitized health check from the project root:

```bash
python -m Backend.scripts.check_db
python -m Backend.scripts.check_db --verbose
python -m Backend.scripts.check_db --probe-tls
python -m Backend.scripts.check_db --json
```

The script never prints the connection string, username, password, or cluster
hostnames. It reports a stable failure category:

- `tls_handshake_rejected` with `TLSV1_ALERT_INTERNAL_ERROR` / `SSL alert 80`
  means Atlas rejected the handshake before sending a certificate. This is
  normally caused by the current public IP not being in **Network Access**
  (including an expired temporary entry) or by a paused cluster. It is not a
  Python, OpenSSL, PyMongo, or CA-bundle problem.
- `tls_certificate_error` means certificate verification failed. Fix the CA
  store or remove the TLS-intercepting proxy/VPN. Never disable verification.
- `dns_error`, `authentication_error`, `timeout`, and other categories are
  reported separately with next steps.

To resolve `tls_handshake_rejected`:

1. Run `check_db` and note the **Current public IP** it prints.
2. In Atlas, open **Network Access** and add that IP as a permanent
   `x.x.x.x/32` entry. If your ISP rotates your public IP, re-add the new
   address (or use a stable egress IP for deployments).
3. Open **Clusters** and resume the cluster if it is paused.
4. Re-run `python -m Backend.scripts.check_db`.

Do not set `tlsAllowInvalidCertificates`, `tlsInsecure`, or
`tlsAllowInvalidHostnames` in `MONGODB_URI`. `GET /health` and `GET /health/db`
include safe `error_category` and `hint` fields when the database is
unavailable.

## Generative AI writing tools

Phase 6 adds two Gemini-backed writing tools for authenticated freelancers:

| Method | Path | Access | Purpose |
|---|---|---|---|
| `POST` | `/ai/generate-proposal` | Freelancer | Generate an editable proposal for an open project. |
| `POST` | `/ai/generate-summary` | Freelancer | Generate an editable profile summary from stored profile data. |

The browser sends only ids and writing preferences. The backend loads the
freelancer profile and project from MongoDB, whitelists public fields, and
builds the prompt itself. Proposal generation never creates an application;
summary generation never updates the profile. Both outputs are returned as
editable drafts and require an explicit frontend action before use.

### Configuration

Add these values to the root `.env` (never to frontend files):

```bash
GEMINI_API_KEY=replace-with-your-gemini-api-key
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_TIMEOUT_MS=60000
```

`GEMINI_API_KEY` is only read by the backend. It is hidden from settings
`repr()` output, never logged, and never returned in API responses. The API
maps Gemini rate limits to `429`, upstream/empty responses to `502`, missing
configuration, an unavailable model, or rejected credentials/project access to
`503`, and timeouts to `504`. Requests for closed projects return `409`; unknown
profiles or projects return `404`; a mismatched `freelancer_id` returns `403`.

Google AI Studio now issues `AQ.` authentication keys as well as legacy
`AIza` keys. The backend passes either format through unchanged; do not add
key-format checks. A `503` response whose detail says the credentials were
rejected means the key itself may be valid but its Google project lacks Gemini
API access. Check the key's project in AI Studio and enable the Gemini API free
tier or billing. If you changed `.env` after starting the backend, restart the
process because settings are cached for the process lifetime.

If the backend log reports `Gemini model/API endpoint not found (code=404...)`,
the configured model has been retired or is unavailable to the key's project.
The warning includes Google's bounded, redacted explanation. Verify a current
model with a minimal request in AI Studio, update `GEMINI_MODEL`, and restart
the backend. Google has retired `gemini-2.5-flash` for new users; this project
uses the verified `gemini-3.5-flash-lite` replacement.

### Security and limits

- JWT authentication and the existing `require_role("freelancer")` check are
  preserved.
- A supplied `freelancer_id` must match the JWT identity.
- Profile and project context is reduced to an explicit public-field
  whitelist and bounded before prompting.
- User highlights and stored profile text are delimited as untrusted data with
  explicit prompt-injection instructions.
- Generated proposals are capped at 2,000 characters and summaries at 1,200
  characters. Inputs are length-limited by the request models.
- Prompts, API keys and private user information are never logged.

## ML-Based Freelancer–Project Matching

Phase 5 adds a Random Forest classifier that predicts a three-class match between
a freelancer and a project:

- Strong Match
- Moderate Match
- Low Match

> **Synthetic-data disclaimer:** The training dataset is synthetic and its
> labels are generated by a transparent rubric. The evaluation metrics do not
> establish real-world matching accuracy.

### Run the ML pipeline

```bash
python -m ML.scripts.generate_dataset --count 1500 --seed 42
python -m ML.scripts.train_model
```

Artifacts:

- `ML/dataset/synthetic_freelancer_project_matches.csv`
- `ML/models/match_model.joblib`
- `ML/models/model_metadata.json`
- `ML/reports/evaluation_report.md`
- `ML/reports/evaluation_metrics.json`
- `ML/reports/feature_documentation.md`
- `ML/reports/methodology.md`
- `ML/notebooks/phase5_model_training.ipynb`

### API endpoints

| Method | Path | Access | Purpose |
|---|---|---|---|
| `POST` | `/ml/predict-match` | Authenticated | Predict one freelancer–project match. |
| `GET` | `/ml/projects/{project_id}/matches` | Owning client | Rank public freelancers for a project. |

Example request:

```json
{
  "freelancer_id": "66f1a2b3c4d5e6f7a8b9c0d4",
  "project_id": "66f1a2b3c4d5e6f7a8b9c0d2"
}
```

The response includes the predicted label, a deterministic rubric fit score,
class probabilities, predicted-class confidence, the internal expected ranking
score, model version, skills overlap, matched and missing skills, and the
extracted feature values. The legacy `match_percentage` field is deprecated and
is only `confidence * 100`; it is not a match-quality score. See `ML/README.md`
and the Swagger docs at `/docs` for the full schema.

### Model summary

- Algorithm: `RandomForestClassifier`
- Version: `phase5-rf-v1`
- Features: 8 numeric features derived from public profile/project data
- Training rows: 1,500 synthetic records (seed 42)
- Train/test split: stratified 80/20
- Cross-validation: 5-fold stratified on the training split
- Actual test accuracy: **89.67%**
- Actual macro F1: **87.90%**

These metrics are measured on synthetic rubric-generated labels. They are not a
claim of real-world matching accuracy.

### Tests

```bash
python -m pytest Backend/tests -v
node --test "Frontend(2)/tests/*.test.js"
```

The backend tests use the in-memory `mongomock` database and mock Gemini, so
they never consume API quota. The frontend tests use Node's built-in test
runner and do not require npm dependencies. They do not contact MongoDB Atlas,
Gemini, or any paid external service.
