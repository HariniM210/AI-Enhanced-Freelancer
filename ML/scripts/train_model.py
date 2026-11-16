"""Train and evaluate the Phase 5 Random Forest matching model.

Run from the project root after generating the dataset:
    python -m ML.scripts.train_model

Artifacts:
    ML/models/match_model.joblib
    ML/models/model_metadata.json
    ML/reports/evaluation_report.md
    ML/reports/evaluation_metrics.json

All reported metrics are produced by this script from the actual train/test
split. The dataset is synthetic, so the metrics do not establish real-world
matching accuracy.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ML.features import (  # noqa: E402
    FEATURE_COLUMNS,
    LABELS,
    MODEL_VERSION,
    MODERATE_THRESHOLD,
    RUBRIC_WEIGHTS,
    STRONG_THRESHOLD,
)

DEFAULT_DATASET = PROJECT_ROOT / "ML" / "dataset" / "synthetic_freelancer_project_matches.csv"
DEFAULT_MODEL = PROJECT_ROOT / "ML" / "models" / "match_model.joblib"
DEFAULT_METADATA = PROJECT_ROOT / "ML" / "models" / "model_metadata.json"
DEFAULT_REPORT = PROJECT_ROOT / "ML" / "reports" / "evaluation_report.md"
DEFAULT_METRICS = PROJECT_ROOT / "ML" / "reports" / "evaluation_metrics.json"

RANDOM_STATE = 42
TEST_SIZE = 0.20


def load_dataset(path: Path = DEFAULT_DATASET) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {path}. Run python -m ML.scripts.generate_dataset first."
        )
    return pd.read_csv(path)


def validate_dataset(dataframe: pd.DataFrame) -> None:
    required = {"record_id", "match_score", "label", *FEATURE_COLUMNS}
    missing = required - set(dataframe.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")

    if dataframe.empty:
        raise ValueError("Dataset is empty.")

    null_columns = [
        column for column in required if dataframe[column].isna().any()
    ]
    if null_columns:
        raise ValueError(f"Dataset contains null values in: {sorted(null_columns)}")

    unknown_labels = set(dataframe["label"].unique()) - set(LABELS)
    if unknown_labels:
        raise ValueError(f"Dataset contains unknown labels: {sorted(unknown_labels)}")

    if dataframe.duplicated(subset=list(FEATURE_COLUMNS)).any():
        raise ValueError(
            "Dataset contains duplicate feature vectors. Regenerate the dataset."
        )

    if not dataframe["match_score"].between(0, 100).all():
        raise ValueError("match_score must be between 0 and 100.")

    if not dataframe["skills_match_percentage"].between(0, 100).all():
        raise ValueError("skills_match_percentage must be between 0 and 100.")

    if not dataframe["required_technology_match"].between(0, 100).all():
        raise ValueError("required_technology_match must be between 0 and 100.")

    for column in (
        "category_relevance",
        "experience_level_compatibility",
        "portfolio_evidence",
        "work_history_evidence",
    ):
        if not dataframe[column].between(0, 1).all():
            raise ValueError(f"{column} must be between 0 and 1.")

    if not dataframe["avg_rating"].between(0, 5).all():
        raise ValueError("avg_rating must be between 0 and 5.")

    if not dataframe["years_experience"].between(0, 60).all():
        raise ValueError("years_experience must be between 0 and 60.")


def build_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=300,
                    max_depth=12,
                    min_samples_leaf=3,
                    class_weight="balanced_subsample",
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def _metric_bundle(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    labels = list(LABELS)
    per_class_precision, per_class_recall, per_class_f1, support = (
        precision_score(y_true, y_pred, labels=labels, average=None, zero_division=0),
        recall_score(y_true, y_pred, labels=labels, average=None, zero_division=0),
        f1_score(y_true, y_pred, labels=labels, average=None, zero_division=0),
        [int((y_true == label).sum()) for label in labels],
    )
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "precision_macro": round(
            float(precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
            6,
        ),
        "recall_macro": round(
            float(recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
            6,
        ),
        "f1_macro": round(
            float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
            6,
        ),
        "precision_weighted": round(
            float(precision_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0)),
            6,
        ),
        "recall_weighted": round(
            float(recall_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0)),
            6,
        ),
        "f1_weighted": round(
            float(f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0)),
            6,
        ),
        "per_class": {
            label: {
                "precision": round(float(per_class_precision[index]), 6),
                "recall": round(float(per_class_recall[index]), 6),
                "f1": round(float(per_class_f1[index]), 6),
                "support": support[index],
            }
            for index, label in enumerate(labels)
        },
    }


def train_and_evaluate(
    dataframe: pd.DataFrame,
) -> tuple[Pipeline, dict[str, Any]]:
    validate_dataset(dataframe)

    X = dataframe.loc[:, list(FEATURE_COLUMNS)].astype(float).to_numpy()
    y = dataframe["label"].astype(str).to_numpy()

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    metrics = _metric_bundle(y_test, y_pred)
    metrics["confusion_matrix"] = confusion_matrix(
        y_test, y_pred, labels=list(LABELS)
    ).tolist()
    metrics["classification_report"] = classification_report(
        y_test,
        y_pred,
        labels=list(LABELS),
        output_dict=True,
        zero_division=0,
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    cv_result = cross_validate(
        build_pipeline(),
        X_train,
        y_train,
        cv=cv,
        scoring={
            "accuracy": "accuracy",
            "precision_macro": "precision_macro",
            "recall_macro": "recall_macro",
            "f1_macro": "f1_macro",
        },
        n_jobs=1,
        error_score="raise",
    )
    cross_validation = {
        metric: {
            "mean": round(float(np.mean(cv_result[f"test_{metric}"])), 6),
            "std": round(float(np.std(cv_result[f"test_{metric}"])), 6),
            "folds": [round(float(value), 6) for value in cv_result[f"test_{metric}"]],
        }
        for metric in ("accuracy", "precision_macro", "recall_macro", "f1_macro")
    }

    classifier = pipeline.named_steps["classifier"]
    feature_importances = {
        feature: round(float(importance), 6)
        for feature, importance in sorted(
            zip(FEATURE_COLUMNS, classifier.feature_importances_),
            key=lambda item: item[1],
            reverse=True,
        )
    }

    label_distribution = {
        label: int((dataframe["label"] == label).sum()) for label in LABELS
    }

    result = {
        "model_version": MODEL_VERSION,
        "model_type": "RandomForestClassifier",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "sklearn_version": sklearn.__version__,
        "dataset": {
            "path": str(DEFAULT_DATASET.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "rows": int(len(dataframe)),
            "feature_columns": list(FEATURE_COLUMNS),
            "labels": list(LABELS),
            "label_distribution": label_distribution,
            "synthetic": True,
        },
        "split": {
            "test_size": TEST_SIZE,
            "random_state": RANDOM_STATE,
            "train_rows": int(len(X_train)),
            "test_rows": int(len(X_test)),
            "stratified": True,
        },
        "metrics": metrics,
        "cross_validation": cross_validation,
        "feature_importances": feature_importances,
        "rubric": {
            "weights": RUBRIC_WEIGHTS,
            "strong_threshold": STRONG_THRESHOLD,
            "moderate_threshold": MODERATE_THRESHOLD,
            "label_rule": (
                "Strong if score >= 75; Moderate if 50 <= score < 75; "
                "otherwise Low."
            ),
        },
        "disclaimer": (
            "The dataset is synthetic. These metrics measure performance on "
            "synthetic rubric-generated labels and do not establish real-world "
            "freelancer-project matching accuracy."
        ),
    }
    return pipeline, result


def save_artifacts(
    pipeline: Pipeline,
    result: dict[str, Any],
    model_path: Path = DEFAULT_MODEL,
    metadata_path: Path = DEFAULT_METADATA,
    metrics_path: Path = DEFAULT_METRICS,
) -> None:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(pipeline, model_path)
    metadata_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    metrics_path.write_text(
        json.dumps(result["metrics"], indent=2) + "\n", encoding="utf-8"
    )


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def write_report(result: dict[str, Any], report_path: Path = DEFAULT_REPORT) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metrics = result["metrics"]
    labels = list(LABELS)
    confusion = metrics["confusion_matrix"]

    lines = [
        "# Phase 5 Model Evaluation Report",
        "",
        "> **Synthetic-data disclaimer:** This report evaluates a Random Forest "
        "on a synthetic dataset whose labels were generated from a transparent "
        "rubric. The metrics do **not** establish real-world matching accuracy.",
        "",
        "## Model",
        "",
        f"- Model: `{result['model_type']}`",
        f"- Model version: `{result['model_version']}`",
        f"- Trained at (UTC): `{result['trained_at']}`",
        f"- scikit-learn version: `{result['sklearn_version']}`",
        f"- Dataset: `{result['dataset']['path']}`",
        f"- Rows: `{result['dataset']['rows']}`",
        f"- Train/test rows: `{result['split']['train_rows']}` / `{result['split']['test_rows']}`",
        f"- Stratified split: `{result['split']['stratified']}`",
        "",
        "## Label distribution",
        "",
        "| Label | Records |",
        "|---|---:|",
    ]
    for label in labels:
        lines.append(f"| {label} | {result['dataset']['label_distribution'][label]} |")

    lines.extend(
        [
            "",
            "## Test-set metrics",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Accuracy | {_percent(metrics['accuracy'])} |",
            f"| Precision (macro) | {_percent(metrics['precision_macro'])} |",
            f"| Recall (macro) | {_percent(metrics['recall_macro'])} |",
            f"| F1-score (macro) | {_percent(metrics['f1_macro'])} |",
            f"| Precision (weighted) | {_percent(metrics['precision_weighted'])} |",
            f"| Recall (weighted) | {_percent(metrics['recall_weighted'])} |",
            f"| F1-score (weighted) | {_percent(metrics['f1_weighted'])} |",
            "",
            "## Per-class test-set metrics",
            "",
            "| Label | Precision | Recall | F1 | Support |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for label in labels:
        values = metrics["per_class"][label]
        lines.append(
            f"| {label} | {_percent(values['precision'])} | "
            f"{_percent(values['recall'])} | {_percent(values['f1'])} | "
            f"{values['support']} |"
        )

    lines.extend(
        [
            "",
            "## Confusion matrix (rows = actual, columns = predicted)",
            "",
            "| Actual \\ Predicted | " + " | ".join(labels) + " |",
            "|---|" + "|".join(["---:"] * len(labels)) + "|",
        ]
    )
    for index, label in enumerate(labels):
        lines.append(
            f"| {label} | "
            + " | ".join(str(value) for value in confusion[index])
            + " |"
        )

    lines.extend(
        [
            "",
            "## 5-fold cross-validation on the training split",
            "",
            "| Metric | Mean | Std |",
            "|---|---:|---:|",
        ]
    )
    for metric in ("accuracy", "precision_macro", "recall_macro", "f1_macro"):
        values = result["cross_validation"][metric]
        lines.append(
            f"| {metric} | {_percent(values['mean'])} | {_percent(values['std'])} |"
        )

    lines.extend(
        [
            "",
            "## Feature importance",
            "",
            "| Feature | Importance |",
            "|---|---:|",
        ]
    )
    for feature, importance in result["feature_importances"].items():
        lines.append(f"| `{feature}` | {_percent(importance)} |")

    lines.extend(
        [
            "",
            "## Label rubric",
            "",
            f"- Strong Match: weighted score >= {STRONG_THRESHOLD}",
            f"- Moderate Match: {MODERATE_THRESHOLD} <= weighted score < {STRONG_THRESHOLD}",
            f"- Low Match: weighted score < {MODERATE_THRESHOLD}",
            "",
            "Feature weights:",
            "",
            "| Feature | Weight |",
            "|---|---:|",
        ]
    )
    for feature, weight in RUBRIC_WEIGHTS.items():
        lines.append(f"| `{feature}` | {_percent(weight)} |")

    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            "```bash",
            "python -m ML.scripts.generate_dataset --count 1500 --seed 42",
            "python -m ML.scripts.train_model",
            "```",
            "",
            "The random seed, split, cross-validation folds and model "
            "hyperparameters are fixed in the scripts.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    args = parser.parse_args()

    dataframe = load_dataset(args.dataset)
    pipeline, result = train_and_evaluate(dataframe)
    save_artifacts(
        pipeline,
        result,
        model_path=args.model,
        metadata_path=args.metadata,
        metrics_path=args.metrics,
    )
    write_report(result, report_path=args.report)

    metrics = result["metrics"]
    print(f"Trained {result['model_type']} ({result['model_version']})")
    print(f"Accuracy: {_percent(metrics['accuracy'])}")
    print(f"Macro precision: {_percent(metrics['precision_macro'])}")
    print(f"Macro recall: {_percent(metrics['recall_macro'])}")
    print(f"Macro F1: {_percent(metrics['f1_macro'])}")
    print(f"Saved model to {args.model}")
    print(f"Saved metadata to {args.metadata}")
    print(f"Saved evaluation report to {args.report}")


if __name__ == "__main__":
    main()
