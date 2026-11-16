# Feature Documentation — Phase 5 Matching Model

## Model inputs

The Random Forest receives exactly eight numeric features, in this order:

1. `skills_match_percentage`
2. `required_technology_match`
3. `category_relevance`
4. `years_experience`
5. `experience_level_compatibility`
6. `avg_rating`
7. `portfolio_evidence`
8. `work_history_evidence`

The order is stored in `ML/features.py::FEATURE_COLUMNS` and in the model
metadata. Training and serving both use `feature_vector()` so the order cannot
drift.

## Definitions and extraction

| Feature | Range | Definition | Source | Missing handling |
|---|---:|---|---|---|
| `skills_match_percentage` | 0–100 | Direct overlap between normalized freelancer skills and project skills. | `freelancer.skills`, `project.skills` | Empty skill lists produce `0.0`. |
| `required_technology_match` | 0–100 | Share of required technologies found in direct skills, portfolio technologies, or work-history text. | Public profile skills, portfolio, work history; project skills | Missing evidence contributes nothing. |
| `category_relevance` | 0–1 | How much of the freelancer's public evidence belongs to the project category's skill taxonomy. `min(1, category_hits / 3)`. | Public skills, portfolio technologies, work-history text; `project.category` | Unknown category or no category evidence produces `0.0`. |
| `years_experience` | 0–60 | Freelancer years of experience. | `freelancer.years_experience` | Missing/invalid values become `0`. |
| `experience_level_compatibility` | 0–1 | `1 - abs(freelancer_level - project_level) / 2`, where Entry=0, Intermediate=1, Expert=2. | Freelancer level or a level inferred from years; project level | Missing level uses `0.5` neutral compatibility. |
| `avg_rating` | 0–5 | Public average rating. | `freelancer.avg_rating` | Missing rating is `0.0`, never imputed with a positive value. |
| `portfolio_evidence` | 0–1 | `min(1, matching_portfolio_items / 2)`. An item matches when its structured technologies or text mention a required project skill. | `freelancer.portfolio` | No portfolio produces `0.0`. |
| `work_history_evidence` | 0–1 | `min(1, matching_work_entries / 2)`. An entry matches when its role, company, period or description mentions a required project skill. | `freelancer.work_history` | No work history produces `0.0`. |

## Human-readable evidence returned by the API

These fields are derived from the same public data and are returned for
explainability. They are **not** extra model inputs:

- `matched_skills`: required project skills directly present on the profile.
- `missing_skills`: required project skills not directly present.
- `required_technologies`: normalized project skills with their original
  display spelling.
- `matched_technologies`: required technologies supported by direct skills,
  portfolio or work-history evidence.
- `missing_technologies`: required technologies without supporting evidence.
- `required_technology_count` / `matched_technology_count`: counts used to
  compute the technology-match percentage.
- `project_category`, `experience_level`, `freelancer_experience_level`,
  `project_experience_level`: display context.
- `experience_level` is a frontend-compatible alias for the freelancer's level.

## Skill normalization

Skills are normalized for comparison only:

- lower-cased and whitespace-collapsed;
- common aliases mapped, for example `REST API` → `rest apis`,
  `NodeJS` → `node.js`, `HTML5` → `html/css`, `sklearn` → `scikit-learn`;
- duplicates removed.

The API keeps the project's original spelling in response lists so the UI can
display `FastAPI` and `MongoDB` rather than normalized tokens.

## Category taxonomy

The taxonomy is defined in `ML/features.py::CATEGORY_SKILLS` and follows the
25 Post a Project categories in `Frontend(2)/js/ui.js::REF.categories`:

- Web Development
- Mobile App Development
- AI & Generative AI
- Machine Learning & Deep Learning
- Data Science & Analytics
- Cybersecurity
- Cloud Computing
- Backend Development & APIs
- Frontend Development
- Full Stack Development
- DevOps & Cloud Engineering
- UI/UX Design
- Software Testing & QA
- Blockchain & Web3
- Game Development
- Database Management
- Embedded Systems & IoT
- Networking & IT Support
- Automation & RPA
- Content Writing & Copywriting
- Digital Marketing & SEO
- Graphic Design
- Video Editing & Animation
- Business & Consulting
- Other

Legacy keys for pre-expansion categories (`Mobile Apps`, `Data Science & ML`,
`Backend & APIs`, `DevOps & Cloud`, `Content & Copywriting`, `QA & Testing`)
are retained so existing projects keep a meaningful category-relevance score.
The synthetic training dataset still uses its original eight categories; the
expanded keys are serving-time taxonomy for newly posted projects. `Other`
intentionally has no taxonomy terms, so its category relevance is `0.0`.

Category relevance is based only on public evidence. It does not use client
identity, application status, or hiring outcomes.

## Label rubric

The labels are generated by a transparent weighted rubric, not by random
assignment:

| Feature | Weight |
|---|---:|
| `skills_match_percentage` | 30% |
| `required_technology_match` | 20% |
| `category_relevance` | 15% |
| `years_experience` | 10% |
| `experience_level_compatibility` | 10% |
| `avg_rating` | 10% |
| `portfolio_evidence` | 3% |
| `work_history_evidence` | 2% |

`years_experience` is capped at 10 years for scoring, and `avg_rating` is
normalized to 0–1. The weighted score is in 0–100.

The backend exposes this same calculation as `rubric_score` for each live
freelancer–project pair. It is a deterministic fit score computed from the
extracted features, not the Random Forest probability and not necessarily the
predicted label. The predicted label remains the model output, while
`confidence` reports the predicted-class probability.

| Score | Label |
|---|---|
| `>= 75` | Strong Match |
| `50 <= score < 75` | Moderate Match |
| `< 50` | Low Match |

## Data-leakage controls

- Application status, hiring outcome, client decisions and any post-decision
  data are excluded from features and labels.
- `match_score` is used only to derive the label; it is not a model input.
- The train/test split is stratified and performed before fitting.
- The `SimpleImputer` lives inside the scikit-learn pipeline, so it is fitted
  only on training data during cross-validation.
- Cross-validation uses fresh pipeline clones and reports fold-level metrics.
- The synthetic latent "fit" variable used by the generator is not saved as a
  model input and is not used directly as a label.
