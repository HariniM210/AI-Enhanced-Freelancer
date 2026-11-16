"""Shared feature engineering for the Phase 5 matching model.

This module is deliberately free of pandas, NumPy, scikit-learn and database
imports so it can be reused by the dataset generator, the training scripts and
the FastAPI service without creating import cycles.

The features use only information available before a hiring decision. No
application status, hiring outcome or future information is used.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional

# ---------------------------------------------------------------------------
# Model contract
# ---------------------------------------------------------------------------

MODEL_VERSION = "phase5-rf-v1"

LABELS: tuple[str, str, str] = (
    "Strong Match",
    "Moderate Match",
    "Low Match",
)

FEATURE_COLUMNS: tuple[str, ...] = (
    "skills_match_percentage",
    "required_technology_match",
    "category_relevance",
    "years_experience",
    "experience_level_compatibility",
    "avg_rating",
    "portfolio_evidence",
    "work_history_evidence",
)

# The rubric is applied to the eight features above. The weights sum to 1.0.
RUBRIC_WEIGHTS: dict[str, float] = {
    "skills_match_percentage": 0.30,
    "required_technology_match": 0.20,
    "category_relevance": 0.15,
    "years_experience": 0.10,
    "experience_level_compatibility": 0.10,
    "avg_rating": 0.10,
    "portfolio_evidence": 0.03,
    "work_history_evidence": 0.02,
}

STRONG_THRESHOLD = 75.0
MODERATE_THRESHOLD = 50.0

# ---------------------------------------------------------------------------
# Skill and category taxonomy
# ---------------------------------------------------------------------------

CATEGORY_SKILLS: dict[str, set[str]] = {
    # Legacy keys are retained so projects created before the expanded
    # category list keep a meaningful category-relevance score.
    "Web Development": {
        "html/css",
        "javascript",
        "typescript",
        "react",
        "vue.js",
        "angular",
        "node.js",
        "tailwind css",
        "git",
    },
    "Mobile Apps": {
        "flutter",
        "kotlin",
        "swift",
        "react native",
        "java",
        "git",
    },
    "Data Science & ML": {
        "python",
        "pandas",
        "numpy",
        "scikit-learn",
        "tensorflow",
        "machine learning",
        "data analysis",
        "sql",
        "tableau",
        "power bi",
    },
    "UI/UX Design": {
        "figma",
        "ui design",
        "ux design",
        "prototyping",
        "wireframing",
        "html/css",
        "git",
    },
    "Backend & APIs": {
        "python",
        "fastapi",
        "django",
        "flask",
        "node.js",
        "mongodb",
        "postgresql",
        "mysql",
        "rest apis",
        "java",
        "git",
    },
    "DevOps & Cloud": {
        "docker",
        "aws",
        "kubernetes",
        "terraform",
        "ci/cd",
        "git",
        "python",
    },
    "Content & Copywriting": {
        "technical writing",
        "copywriting",
        "content writing",
        "seo",
        "editing",
        "git",
    },
    "QA & Testing": {
        "pytest",
        "selenium",
        "jest",
        "qa",
        "automation",
        "testing",
        "python",
        "javascript",
        "git",
    },
    # Expanded Post a Project categories.
    "Mobile App Development": {
        "flutter",
        "kotlin",
        "swift",
        "react native",
        "java",
        "git",
    },
    "AI & Generative AI": {
        "python",
        "tensorflow",
        "pytorch",
        "keras",
        "openai",
        "llm",
        "large language models",
        "prompt engineering",
        "langchain",
        "huggingface",
        "generative ai",
        "machine learning",
        "nlp",
    },
    "Machine Learning & Deep Learning": {
        "python",
        "pandas",
        "numpy",
        "scikit-learn",
        "tensorflow",
        "pytorch",
        "keras",
        "machine learning",
        "deep learning",
        "nlp",
        "computer vision",
        "data analysis",
    },
    "Data Science & Analytics": {
        "python",
        "pandas",
        "numpy",
        "sql",
        "tableau",
        "power bi",
        "data analysis",
        "statistics",
        "r",
        "excel",
    },
    "Cybersecurity": {
        "cybersecurity",
        "security",
        "penetration testing",
        "ethical hacking",
        "kali linux",
        "siem",
        "soc",
        "cryptography",
        "network security",
        "owasp",
    },
    "Cloud Computing": {
        "aws",
        "azure",
        "gcp",
        "cloud computing",
        "docker",
        "kubernetes",
        "terraform",
        "serverless",
    },
    "Backend Development & APIs": {
        "python",
        "fastapi",
        "django",
        "flask",
        "node.js",
        "mongodb",
        "postgresql",
        "mysql",
        "rest apis",
        "graphql",
        "microservices",
        "java",
        "git",
    },
    "Frontend Development": {
        "html/css",
        "javascript",
        "typescript",
        "react",
        "vue.js",
        "angular",
        "tailwind css",
        "next.js",
        "git",
    },
    "Full Stack Development": {
        "html/css",
        "javascript",
        "typescript",
        "react",
        "node.js",
        "python",
        "fastapi",
        "django",
        "flask",
        "mongodb",
        "postgresql",
        "rest apis",
        "git",
    },
    "DevOps & Cloud Engineering": {
        "docker",
        "aws",
        "azure",
        "gcp",
        "kubernetes",
        "terraform",
        "ci/cd",
        "ansible",
        "jenkins",
        "linux",
        "git",
        "python",
    },
    "Software Testing & QA": {
        "pytest",
        "selenium",
        "jest",
        "cypress",
        "playwright",
        "qa",
        "automation",
        "testing",
        "python",
        "javascript",
        "git",
    },
    "Blockchain & Web3": {
        "blockchain",
        "web3",
        "solidity",
        "ethereum",
        "smart contracts",
        "rust",
        "crypto",
        "nft",
    },
    "Game Development": {
        "unity",
        "unreal engine",
        "c++",
        "c#",
        "game design",
        "blender",
        "godot",
    },
    "Database Management": {
        "sql",
        "mongodb",
        "postgresql",
        "mysql",
        "oracle",
        "sql server",
        "redis",
        "database",
        "data modeling",
    },
    "Embedded Systems & IoT": {
        "c",
        "c++",
        "embedded",
        "arduino",
        "raspberry pi",
        "iot",
        "firmware",
        "microcontroller",
        "rtos",
    },
    "Networking & IT Support": {
        "networking",
        "tcp/ip",
        "cisco",
        "linux",
        "windows server",
        "it support",
        "troubleshooting",
        "dns",
        "vpn",
    },
    "Automation & RPA": {
        "automation",
        "rpa",
        "uipath",
        "power automate",
        "python",
        "selenium",
        "scripting",
        "zapier",
    },
    "Content Writing & Copywriting": {
        "technical writing",
        "copywriting",
        "content writing",
        "blog writing",
        "seo",
        "editing",
        "git",
    },
    "Digital Marketing & SEO": {
        "seo",
        "sem",
        "google analytics",
        "digital marketing",
        "social media",
        "content marketing",
        "ppc",
        "email marketing",
    },
    "Graphic Design": {
        "graphic design",
        "adobe photoshop",
        "illustrator",
        "indesign",
        "branding",
        "canva",
        "figma",
    },
    "Video Editing & Animation": {
        "video editing",
        "adobe premiere",
        "after effects",
        "animation",
        "motion graphics",
        "davinci resolve",
        "blender",
    },
    "Business & Consulting": {
        "business analysis",
        "consulting",
        "project management",
        "strategy",
        "agile",
        "scrum",
        "stakeholder management",
        "excel",
    },
    "Other": set(),
}

# Normalize common spellings so "REST API" and "REST APIs" are the same
# evidence. Only public skill names are normalized; nothing is inferred from
# private user fields.
SKILL_ALIASES: dict[str, str] = {
    "rest api": "rest apis",
    "restful api": "rest apis",
    "restful apis": "rest apis",
    "html": "html/css",
    "css": "html/css",
    "html5": "html/css",
    "css3": "html/css",
    "js": "javascript",
    "ts": "typescript",
    "node": "node.js",
    "nodejs": "node.js",
    "postgres": "postgresql",
    "mongo": "mongodb",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "tf": "tensorflow",
    "tailwind": "tailwind css",
    "cicd": "ci/cd",
    "ci cd": "ci/cd",
    "reactjs": "react",
    "react.js": "react",
    "vue": "vue.js",
    "vuejs": "vue.js",
    "qa testing": "qa",
    "test automation": "automation",
}

EXPERIENCE_LEVELS: tuple[str, ...] = ("Entry", "Intermediate", "Expert")
_EXPERIENCE_LEVEL_VALUE = {
    "entry": 0,
    "intermediate": 1,
    "expert": 2,
}


def normalize_skill(value: Any) -> str:
    """Return a stable, lower-case skill token."""
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" .,;:()[]{}")
    return SKILL_ALIASES.get(text, text)


def normalize_skill_list(values: Optional[Iterable[Any]]) -> set[str]:
    """Normalize a list of skills and drop blanks and duplicates."""
    return {
        token
        for token in (normalize_skill(value) for value in (values or []))
        if token
    }


def _skill_display_map(values: Optional[Iterable[Any]]) -> dict[str, str]:
    """Map normalized skill tokens back to their original display text."""
    mapping: dict[str, str] = {}
    for value in values or []:
        token = normalize_skill(value)
        display = str(value).strip()
        if token and display and token not in mapping:
            mapping[token] = display
    return mapping


def _display_names(tokens: Iterable[str], mapping: dict[str, str]) -> list[str]:
    return sorted(
        (mapping.get(token, token) for token in tokens),
        key=str.casefold,
    )


def experience_level_for_years(years: int) -> str:
    """Infer a level when the profile does not store one."""
    if years < 2:
        return "Entry"
    if years < 5:
        return "Intermediate"
    return "Expert"


def _level_value(level: Any) -> Optional[int]:
    return _EXPERIENCE_LEVEL_VALUE.get(str(level or "").strip().lower())


def _text_blob(*values: Any) -> str:
    """Lower-case text used for structured work-history evidence."""
    parts = [str(value) for value in values if value is not None]
    return " ".join(parts).lower()


def _skills_mentioned_in_text(skills: set[str], text: str) -> set[str]:
    """Find required skills mentioned in free text using token boundaries."""
    hits: set[str] = set()
    for skill in skills:
        if not skill:
            continue
        # Use a boundary-aware search so "react" does not match "reactive".
        pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
        if re.search(pattern, text):
            hits.add(skill)
    return hits


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def extract_match_features(
    freelancer: Optional[dict[str, Any]],
    project: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Extract the eight model features plus human-readable evidence.

    Missing or optional profile fields are treated as absent evidence. The
    function never raises for a missing skills list, portfolio, work history,
    rating or experience level.
    """
    profile = freelancer or {}
    project_data = project or {}

    freelancer_skills = normalize_skill_list(profile.get("skills"))
    project_skills = normalize_skill_list(project_data.get("skills"))
    project_skill_display = _skill_display_map(project_data.get("skills"))
    project_category = str(project_data.get("category") or "").strip()

    # 1. Direct skill overlap. The numeric features use normalized tokens;
    # the human-readable lists preserve the project's original spelling.
    matched_skills = _display_names(
        project_skills & freelancer_skills, project_skill_display
    )
    missing_skills = _display_names(
        project_skills - freelancer_skills, project_skill_display
    )
    skills_match_percentage = (
        100.0 * len(matched_skills) / len(project_skills)
        if project_skills
        else 0.0
    )

    # 2. Portfolio evidence from structured technologies and text.
    portfolio = profile.get("portfolio") or []
    portfolio_technologies: set[str] = set()
    portfolio_matches = 0
    for item in portfolio:
        if not isinstance(item, dict):
            continue
        technologies = normalize_skill_list(item.get("technologies"))
        text = _text_blob(
            item.get("title"),
            item.get("description"),
            item.get("url"),
        )
        item_evidence = technologies | _skills_mentioned_in_text(
            project_skills, text
        )
        portfolio_technologies |= technologies
        if project_skills & item_evidence:
            portfolio_matches += 1
    portfolio_evidence = (
        min(1.0, portfolio_matches / 2.0) if portfolio else 0.0
    )

    # 3. Work-history evidence from structured role/company/description text.
    work_history = profile.get("work_history") or []
    work_history_terms: set[str] = set()
    work_history_matches = 0
    for item in work_history:
        if not isinstance(item, dict):
            continue
        text = _text_blob(
            item.get("role"),
            item.get("company"),
            item.get("period"),
            item.get("description"),
        )
        hits = _skills_mentioned_in_text(project_skills, text)
        work_history_terms |= hits
        if hits:
            work_history_matches += 1
    work_history_evidence = (
        min(1.0, work_history_matches / 2.0) if work_history else 0.0
    )

    # 4. Required technology match uses direct skills plus portfolio/work
    # evidence. This is intentionally different from the direct skills ratio.
    technology_evidence = (
        freelancer_skills | portfolio_technologies | work_history_terms
    )
    matched_technologies = _display_names(
        project_skills & technology_evidence, project_skill_display
    )
    missing_technologies = _display_names(
        project_skills - technology_evidence, project_skill_display
    )
    required_technology_match = (
        100.0 * len(matched_technologies) / len(project_skills)
        if project_skills
        else 0.0
    )

    # 5. Category relevance from public skills, portfolio and work evidence.
    category_terms = CATEGORY_SKILLS.get(project_category, set())
    all_evidence = freelancer_skills | portfolio_technologies | work_history_terms
    category_hits = len(all_evidence & category_terms)
    category_relevance = (
        min(1.0, category_hits / 3.0) if category_terms else 0.0
    )

    # 6. Experience. Missing years are treated as zero; the level falls back to
    # the same rule used by the authentication service.
    years_experience = _clamp(_safe_int(profile.get("years_experience")), 0, 60)
    freelancer_level = str(
        profile.get("experience_level")
        or experience_level_for_years(years_experience)
    ).strip()
    project_level = project_data.get("experience_level")
    freelancer_level_value = _level_value(freelancer_level)
    project_level_value = _level_value(project_level)
    if freelancer_level_value is None or project_level_value is None:
        experience_level_compatibility = 0.5
    else:
        experience_level_compatibility = 1.0 - (
            abs(freelancer_level_value - project_level_value) / 2.0
        )
    experience_level_compatibility = _clamp(
        experience_level_compatibility, 0.0, 1.0
    )

    # 7. Rating. Missing ratings are zero, not an assumed average.
    avg_rating = _clamp(_safe_float(profile.get("avg_rating")), 0.0, 5.0)

    return {
        "skills_match_percentage": round(skills_match_percentage, 2),
        "required_technology_match": round(required_technology_match, 2),
        "category_relevance": round(category_relevance, 4),
        "years_experience": years_experience,
        "experience_level_compatibility": round(
            experience_level_compatibility, 4
        ),
        "avg_rating": round(avg_rating, 2),
        "portfolio_evidence": round(portfolio_evidence, 4),
        "work_history_evidence": round(work_history_evidence, 4),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "required_technologies": _display_names(
            project_skills, project_skill_display
        ),
        "matched_technologies": matched_technologies,
        "missing_technologies": missing_technologies,
        "required_technology_count": len(project_skills),
        "matched_technology_count": len(matched_technologies),
        "project_category": project_category,
        # ``experience_level`` is a frontend-compatibility alias for the
        # freelancer's level; both keys are public profile information.
        "experience_level": freelancer_level,
        "freelancer_experience_level": freelancer_level,
        "project_experience_level": (
            str(project_level) if project_level is not None else None
        ),
    }


def compute_match_score(features: dict[str, Any]) -> float:
    """Apply the transparent label rubric and return a 0-100 score.

    ``features`` must be the eight numeric values returned by
    :func:`extract_match_features`. The backend exposes this result as
    ``rubric_score``: a deterministic fit score, not a model probability and
    not the predicted class. Missing optional values are handled as absent
    evidence by the same normalisation used during training.
    """
    years_score = min(_safe_float(features.get("years_experience")), 10.0) / 10.0
    rating_score = _clamp(_safe_float(features.get("avg_rating")), 0.0, 5.0) / 5.0
    score = (
        RUBRIC_WEIGHTS["skills_match_percentage"]
        * _safe_float(features.get("skills_match_percentage"))
        + RUBRIC_WEIGHTS["required_technology_match"]
        * _safe_float(features.get("required_technology_match"))
        + RUBRIC_WEIGHTS["category_relevance"]
        * _safe_float(features.get("category_relevance"))
        * 100.0
        + RUBRIC_WEIGHTS["years_experience"] * years_score * 100.0
        + RUBRIC_WEIGHTS["experience_level_compatibility"]
        * _safe_float(features.get("experience_level_compatibility"))
        * 100.0
        + RUBRIC_WEIGHTS["avg_rating"] * rating_score * 100.0
        + RUBRIC_WEIGHTS["portfolio_evidence"]
        * _safe_float(features.get("portfolio_evidence"))
        * 100.0
        + RUBRIC_WEIGHTS["work_history_evidence"]
        * _safe_float(features.get("work_history_evidence"))
        * 100.0
    )
    return round(_clamp(score, 0.0, 100.0), 2)


def label_for_score(score: float) -> str:
    """Map a rubric score to one of the three required classes."""
    if score >= STRONG_THRESHOLD:
        return "Strong Match"
    if score >= MODERATE_THRESHOLD:
        return "Moderate Match"
    return "Low Match"


def feature_vector(features: dict[str, Any]) -> list[float]:
    """Return the model input vector in the trained feature order."""
    return [float(features[column]) for column in FEATURE_COLUMNS]
