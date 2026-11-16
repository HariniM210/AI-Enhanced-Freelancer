# Phase 5 Model Evaluation Report

> **Synthetic-data disclaimer:** This report evaluates a Random Forest on a synthetic dataset whose labels were generated from a transparent rubric. The metrics do **not** establish real-world matching accuracy.

## Model

- Model: `RandomForestClassifier`
- Model version: `phase5-rf-v1`
- Trained at (UTC): `2026-11-12T15:26:37.052943+00:00`
- scikit-learn version: `1.9.1`
- Dataset: `ML/dataset/synthetic_freelancer_project_matches.csv`
- Rows: `1500`
- Train/test rows: `1200` / `300`
- Stratified split: `True`

## Label distribution

| Label | Records |
|---|---:|
| Strong Match | 643 |
| Moderate Match | 712 |
| Low Match | 145 |

## Test-set metrics

| Metric | Value |
|---|---:|
| Accuracy | 89.67% |
| Precision (macro) | 87.92% |
| Recall (macro) | 87.89% |
| F1-score (macro) | 87.90% |
| Precision (weighted) | 89.68% |
| Recall (weighted) | 89.67% |
| F1-score (weighted) | 89.67% |

## Per-class test-set metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| Strong Match | 92.19% | 91.47% | 91.83% | 129 |
| Moderate Match | 88.81% | 89.44% | 89.12% | 142 |
| Low Match | 82.76% | 82.76% | 82.76% | 29 |

## Confusion matrix (rows = actual, columns = predicted)

| Actual \ Predicted | Strong Match | Moderate Match | Low Match |
|---|---:|---:|---:|
| Strong Match | 118 | 11 | 0 |
| Moderate Match | 10 | 127 | 5 |
| Low Match | 0 | 5 | 24 |

## 5-fold cross-validation on the training split

| Metric | Mean | Std |
|---|---:|---:|
| accuracy | 91.08% | 2.12% |
| precision_macro | 88.89% | 3.93% |
| recall_macro | 90.06% | 3.27% |
| f1_macro | 89.23% | 3.24% |

## Feature importance

| Feature | Importance |
|---|---:|
| `skills_match_percentage` | 35.85% |
| `required_technology_match` | 23.24% |
| `years_experience` | 12.11% |
| `avg_rating` | 11.35% |
| `category_relevance` | 7.71% |
| `experience_level_compatibility` | 5.19% |
| `work_history_evidence` | 2.30% |
| `portfolio_evidence` | 2.24% |

## Label rubric

- Strong Match: weighted score >= 75.0
- Moderate Match: 50.0 <= weighted score < 75.0
- Low Match: weighted score < 50.0

Feature weights:

| Feature | Weight |
|---|---:|
| `skills_match_percentage` | 30.00% |
| `required_technology_match` | 20.00% |
| `category_relevance` | 15.00% |
| `years_experience` | 10.00% |
| `experience_level_compatibility` | 10.00% |
| `avg_rating` | 10.00% |
| `portfolio_evidence` | 3.00% |
| `work_history_evidence` | 2.00% |

## Reproducibility

```bash
python -m ML.scripts.generate_dataset --count 1500 --seed 42
python -m ML.scripts.train_model
```

The random seed, split, cross-validation folds and model hyperparameters are fixed in the scripts.
