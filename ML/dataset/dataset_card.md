# Synthetic Dataset Card — Freelancer–Project Matching

## Identity

- **Name:** `synthetic_freelancer_project_matches`
- **File:** `ML/dataset/synthetic_freelancer_project_matches.csv`
- **Rows:** 1,500
- **Random seed:** 42
- **Generator:** `ML/scripts/generate_dataset.py`
- **Synthetic:** **Yes**

> **Important limitation:** This dataset is synthetic. It was created to make the
> Phase 5 training pipeline reproducible and academically explainable. Metrics
> measured on it do **not** establish real-world freelancer–project matching
> accuracy.

## Why the dataset is synthetic

The project does not yet contain enough historical, labelled hiring outcomes to
train a supervised model honestly. Using application status or hiring outcomes
as labels would also leak future information. The dataset therefore uses public
profile/project fields, extracts the same features used by the backend, and
applies a transparent rubric to create the three labels.

## Generation command

```bash
python -m ML.scripts.generate_dataset --count 1500 --seed 42
```

The generator creates unique feature vectors. A feature vector rounded to four
decimal places is rejected if it has already been used, so the saved dataset has
`duplicate_feature_vectors = 0`.

## Columns

| Column | Type | Meaning |
|---|---|---|
| `record_id` | string | Stable synthetic identifier such as `syn-0001`. |
| `skills_match_percentage` | float 0–100 | Direct overlap between freelancer skills and project skills. |
| `required_technology_match` | float 0–100 | Required technologies supported by direct skills, portfolio technologies, or work-history text. |
| `category_relevance` | float 0–1 | Presence of project-category technologies in the freelancer's public evidence. |
| `years_experience` | integer 0–60 | Freelancer years of experience. |
| `experience_level_compatibility` | float 0–1 | Compatibility between freelancer and project experience levels. |
| `avg_rating` | float 0–5 | Freelancer average rating; `0.0` means no rating is available. |
| `portfolio_evidence` | float 0–1 | Proportion of portfolio items that show relevant technologies. |
| `work_history_evidence` | float 0–1 | Proportion of work-history entries that mention relevant technologies. |
| `match_score` | float 0–100 | Transparent weighted rubric score. Used to derive the label, never a model input. |
| `label` | string | `Strong Match`, `Moderate Match`, or `Low Match`. |
| `project_category` | string | Metadata for documentation and analysis; not a model input. |
| `freelancer_experience_level` | string | Metadata; the numeric compatibility feature is the model input. |
| `project_experience_level` | string | Metadata; the numeric compatibility feature is the model input. |

The eight numeric feature columns are the only model inputs. The evidence lists
shown by the API (`matched_skills`, `missing_skills`, etc.) are generated from
the same data but are not additional model inputs.

## Label distribution

| Label | Rows | Share |
|---|---:|---:|
| Strong Match | 643 | 42.9% |
| Moderate Match | 712 | 47.5% |
| Low Match | 145 | 9.7% |

The distribution follows the rubric thresholds and the sampled feature
distribution. It is not forced to be exactly balanced.

## Feature ranges

| Feature | Min | Max | Mean |
|---|---:|---:|---:|
| `skills_match_percentage` | 0.0 | 100.0 | 55.55 |
| `required_technology_match` | 0.0 | 100.0 | 89.94 |
| `category_relevance` | 0.0 | 1.0 | 0.94 |
| `years_experience` | 0.0 | 23.0 | 7.93 |
| `experience_level_compatibility` | 0.0 | 1.0 | 0.54 |
| `avg_rating` | 0.0 | 5.0 | 2.90 |
| `portfolio_evidence` | 0.0 | 1.0 | 0.69 |
| `work_history_evidence` | 0.0 | 1.0 | 0.57 |

The machine-readable summary is stored in
`ML/dataset/dataset_summary.json`.

## Intended use

- Reproducible training and evaluation of the Phase 5 Random Forest.
- Demonstrating feature engineering, leakage prevention, and evaluation
  methodology for the academic project.
- Regression testing of the shared feature extractor.

## Not intended for

- Claiming real-world hiring accuracy.
- Replacing human review or client judgment.
- Making employment decisions without human oversight.
- Training a production model without real, consented, labelled data.
