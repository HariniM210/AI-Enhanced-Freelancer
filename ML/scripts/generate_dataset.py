"""Generate the synthetic freelancer-project matching dataset.

The dataset is deliberately synthetic. It is created by sampling realistic
public profile/project fields, extracting the same eight features used by the
backend, and applying the transparent rubric in ``ML.features``. Labels are
therefore feature-driven, not arbitrary random values.

Usage (from the project root):
    python -m ML.scripts.generate_dataset
    python -m ML.scripts.generate_dataset --count 1500 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ML.features import (  # noqa: E402
    FEATURE_COLUMNS,
    LABELS,
    compute_match_score,
    experience_level_for_years,
    extract_match_features,
    label_for_score,
)

DEFAULT_COUNT = 1500
DEFAULT_SEED = 42
DEFAULT_OUTPUT = PROJECT_ROOT / "ML" / "dataset" / "synthetic_freelancer_project_matches.csv"
DEFAULT_SUMMARY = PROJECT_ROOT / "ML" / "dataset" / "dataset_summary.json"

SKILL_POOL = [
    "Python",
    "JavaScript",
    "TypeScript",
    "HTML/CSS",
    "React",
    "Vue.js",
    "Angular",
    "Node.js",
    "FastAPI",
    "Django",
    "Flask",
    "MongoDB",
    "PostgreSQL",
    "MySQL",
    "scikit-learn",
    "TensorFlow",
    "Pandas",
    "NumPy",
    "Docker",
    "AWS",
    "Kubernetes",
    "Terraform",
    "Figma",
    "UI Design",
    "UX Design",
    "Prototyping",
    "Wireframing",
    "Flutter",
    "Kotlin",
    "Swift",
    "React Native",
    "Java",
    "REST APIs",
    "Git",
    "Tailwind CSS",
    "Technical Writing",
    "Copywriting",
    "Content Writing",
    "SEO",
    "Editing",
    "Pytest",
    "Selenium",
    "Jest",
    "QA",
    "Automation",
    "Testing",
    "Machine Learning",
    "Data Analysis",
    "SQL",
    "Tableau",
    "Power BI",
    "CI/CD",
]

CATEGORY_POOLS: dict[str, list[str]] = {
    "Web Development": [
        "HTML/CSS",
        "JavaScript",
        "TypeScript",
        "React",
        "Vue.js",
        "Angular",
        "Node.js",
        "Tailwind CSS",
        "Git",
    ],
    "Mobile Apps": [
        "Flutter",
        "Kotlin",
        "Swift",
        "React Native",
        "Java",
        "Git",
    ],
    "Data Science & ML": [
        "Python",
        "Pandas",
        "NumPy",
        "scikit-learn",
        "TensorFlow",
        "Machine Learning",
        "Data Analysis",
        "SQL",
        "Tableau",
        "Power BI",
    ],
    "UI/UX Design": [
        "Figma",
        "UI Design",
        "UX Design",
        "Prototyping",
        "Wireframing",
        "HTML/CSS",
        "Git",
    ],
    "Backend & APIs": [
        "Python",
        "FastAPI",
        "Django",
        "Flask",
        "Node.js",
        "MongoDB",
        "PostgreSQL",
        "MySQL",
        "REST APIs",
        "Java",
        "Git",
    ],
    "DevOps & Cloud": [
        "Docker",
        "AWS",
        "Kubernetes",
        "Terraform",
        "CI/CD",
        "Git",
        "Python",
    ],
    "Content & Copywriting": [
        "Technical Writing",
        "Copywriting",
        "Content Writing",
        "SEO",
        "Editing",
        "Git",
    ],
    "QA & Testing": [
        "Pytest",
        "Selenium",
        "Jest",
        "QA",
        "Automation",
        "Testing",
        "Python",
        "JavaScript",
        "Git",
    ],
}

ROLE_NAMES = ["Developer", "Engineer", "Consultant", "Designer", "Analyst"]
COMPANIES = ["Acme", "Northwind", "Globex", "Initech", "Umbrella", "Craftline Labs"]


def _sample_skills(
    rng: random.Random,
    project_skills: list[str],
    fit: float,
) -> list[str]:
    """Create a freelancer skill set correlated with the latent fit level."""
    skills: set[str] = set()
    for skill in project_skills:
        if rng.random() < min(0.97, 0.08 + 0.88 * fit):
            skills.add(skill)

    for _ in range(rng.randint(2, 8)):
        skills.add(rng.choice(SKILL_POOL))

    return sorted(skills)


def _make_portfolio(
    rng: random.Random,
    category: str,
    project_skills: list[str],
    fit: float,
) -> list[dict[str, Any]]:
    count = rng.choices([0, 1, 2, 3, 4], weights=[0.15, 0.25, 0.30, 0.20, 0.10])[0]
    portfolio: list[dict[str, Any]] = []
    for index in range(count):
        technologies: set[str] = set()
        for skill in project_skills:
            if rng.random() < 0.12 + 0.80 * fit:
                technologies.add(skill)
        for _ in range(rng.randint(1, 3)):
            technologies.add(rng.choice(SKILL_POOL))
        tech_list = sorted(technologies)
        portfolio.append(
            {
                "title": f"{category} delivery {index + 1}",
                "description": "Delivered work using " + ", ".join(tech_list) + ".",
                "url": f"https://example.invalid/portfolio/{index + 1}",
                "technologies": tech_list,
            }
        )
    return portfolio


def _make_work_history(
    rng: random.Random,
    project_skills: list[str],
    fit: float,
) -> list[dict[str, Any]]:
    count = rng.choices([0, 1, 2, 3], weights=[0.20, 0.35, 0.30, 0.15])[0]
    history: list[dict[str, Any]] = []
    for _ in range(count):
        mentioned = [
            skill for skill in project_skills if rng.random() < 0.15 + 0.75 * fit
        ]
        description = (
            "Worked with " + ", ".join(mentioned) + "."
            if mentioned
            else "General software delivery and collaboration."
        )
        start = rng.randint(2014, 2023)
        end = rng.randint(start + 1, 2025)
        history.append(
            {
                "role": rng.choice(ROLE_NAMES),
                "company": rng.choice(COMPANIES),
                "period": f"{start} - {end}",
                "description": description,
            }
        )
    return history


def generate_records(count: int = DEFAULT_COUNT, seed: int = DEFAULT_SEED) -> list[dict[str, Any]]:
    """Generate unique synthetic records using the shared feature extractor."""
    rng = random.Random(seed)
    records: list[dict[str, Any]] = []
    seen_vectors: set[tuple[float, ...]] = set()
    attempts = 0
    max_attempts = max(count * 100, 1000)

    while len(records) < count and attempts < max_attempts:
        attempts += 1
        category = rng.choice(list(CATEGORY_POOLS))
        category_pool = CATEGORY_POOLS[category]
        project_skill_count = rng.randint(2, min(7, len(category_pool)))
        project_skills = rng.sample(category_pool, project_skill_count)

        # Occasionally mix in a cross-category technology, as real projects do.
        if rng.random() < 0.15:
            extra = rng.choice(SKILL_POOL)
            if extra not in project_skills:
                project_skills.append(extra)

        project_level = rng.choice(["Entry", "Intermediate", "Expert"])

        # Latent fit drives the correlation between features. It is not a model
        # input and is not used directly to label a record.
        fit = rng.betavariate(2.2, 2.2)

        freelancer_skills = _sample_skills(rng, project_skills, fit)
        years_experience = int(
            max(0.0, min(25.0, round(rng.gauss(1.0 + 14.0 * fit, 3.0))))
        )

        # Most levels are consistent with experience, but some profiles are
        # inconsistent, as in real data.
        if rng.random() < 0.75:
            freelancer_level = experience_level_for_years(years_experience)
        else:
            freelancer_level = rng.choice(["Entry", "Intermediate", "Expert"])

        # Some profiles have no rating yet. A missing rating is represented as
        # 0.0 and is not imputed with a positive value.
        if rng.random() < 0.12:
            avg_rating = 0.0
        else:
            avg_rating = round(
                max(0.0, min(5.0, rng.gauss(2.0 + 2.6 * fit, 0.7))), 2
            )

        portfolio = _make_portfolio(rng, category, project_skills, fit)
        work_history = _make_work_history(rng, project_skills, fit)

        freelancer = {
            "skills": freelancer_skills,
            "years_experience": years_experience,
            "experience_level": freelancer_level,
            "avg_rating": avg_rating,
            "portfolio": portfolio,
            "work_history": work_history,
        }
        project = {
            "skills": project_skills,
            "category": category,
            "experience_level": project_level,
        }

        features = extract_match_features(freelancer, project)
        score = compute_match_score(features)
        label = label_for_score(score)
        vector_key = tuple(round(float(features[column]), 4) for column in FEATURE_COLUMNS)

        # Avoid duplicate or nearly identical feature rows. The feature vector
        # is rounded to four decimals for this check.
        if vector_key in seen_vectors:
            continue
        seen_vectors.add(vector_key)

        record: dict[str, Any] = {
            "record_id": f"syn-{len(records) + 1:04d}",
        }
        record.update({column: features[column] for column in FEATURE_COLUMNS})
        record.update(
            {
                "match_score": score,
                "label": label,
                "project_category": category,
                "freelancer_experience_level": features[
                    "freelancer_experience_level"
                ],
                "project_experience_level": project_level,
            }
        )
        records.append(record)

    if len(records) < count:
        raise RuntimeError(
            f"Generated only {len(records)} unique records out of {count} requested "
            f"after {attempts} attempts."
        )

    return records


def build_summary(records: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    dataframe = pd.DataFrame(records)
    label_counts = {label: int((dataframe["label"] == label).sum()) for label in LABELS}
    ranges = {
        column: {
            "min": float(dataframe[column].min()),
            "max": float(dataframe[column].max()),
            "mean": round(float(dataframe[column].mean()), 4),
        }
        for column in FEATURE_COLUMNS
    }
    return {
        "dataset_name": "synthetic_freelancer_project_matches",
        "synthetic": True,
        "seed": seed,
        "rows": len(dataframe),
        "feature_columns": list(FEATURE_COLUMNS),
        "label_column": "label",
        "labels": list(LABELS),
        "label_distribution": label_counts,
        "feature_ranges": ranges,
        "duplicate_feature_vectors": int(
            dataframe.duplicated(subset=list(FEATURE_COLUMNS)).sum()
        ),
        "disclaimer": (
            "Synthetic data only. Metrics on this dataset do not establish "
            "real-world matching accuracy."
        ),
    }


def write_dataset(
    records: list[dict[str, Any]],
    output_path: Path = DEFAULT_OUTPUT,
    summary_path: Path = DEFAULT_SUMMARY,
    seed: int = DEFAULT_SEED,
) -> pd.DataFrame:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe = pd.DataFrame(records)
    dataframe.to_csv(output_path, index=False)
    summary = build_summary(records, seed)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return dataframe


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()

    records = generate_records(count=args.count, seed=args.seed)
    dataframe = write_dataset(
        records,
        output_path=args.output,
        summary_path=args.summary,
        seed=args.seed,
    )
    print(f"Wrote {len(dataframe)} synthetic records to {args.output}")
    print("Label distribution:")
    print(dataframe["label"].value_counts().to_string())
    print(f"Wrote dataset summary to {args.summary}")


if __name__ == "__main__":
    main()
