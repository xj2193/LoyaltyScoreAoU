"""Summarize site-level cross-validation performance by averaging fold AUCs.

This script uses the patient-level out-of-fold predictions produced by
``finetune.py``. AUC is calculated separately within each site and CV fold;
the five fold-specific AUCs are then averaged without weighting by fold size.
"""

from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
PREDICTION_FILE = SCRIPT_DIR / "patient_level_out_of_fold_predictions.csv"
FOLD_OUTPUT_FILE = SCRIPT_DIR / "finetune_per_hpo_fold_auc.csv"
MEAN_OUTPUT_FILE = (
    SCRIPT_DIR / "finetune_per_hpo_all_lookback_years_5fold_mean_auc.csv"
)

PROBABILITY_COLUMNS = {
    "aou": "aou_probability",
    "weighted": "weighted_probability",
    "original": "original_probability",
}

GROUP_COLUMNS = ["lookback_year", "src_hpo_id", "cv_fold"]


def roc_auc_score(y_true, y_score):
    """Calculate binary ROC AUC using the Mann-Whitney rank statistic."""
    y_true = pd.Series(y_true).reset_index(drop=True)
    y_score = pd.Series(y_score).reset_index(drop=True)
    positive = y_true.eq(1)
    negative = y_true.eq(0)
    positive_count = int(positive.sum())
    negative_count = int(negative.sum())

    if positive_count == 0 or negative_count == 0:
        raise ValueError("ROC AUC requires both outcome classes.")

    ranks = y_score.rank(method="average")
    positive_rank_sum = ranks.loc[positive].sum()
    return (
        positive_rank_sum - positive_count * (positive_count + 1) / 2
    ) / (positive_count * negative_count)


def validate_predictions(predictions):
    """Validate columns and the assumptions required for fold-level AUC."""
    required_columns = {
        *GROUP_COLUMNS,
        "visit_label",
        *PROBABILITY_COLUMNS.values(),
    }
    missing_columns = required_columns.difference(predictions.columns)
    if missing_columns:
        raise ValueError(
            "Prediction file is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    if predictions[list(required_columns)].isna().any().any():
        raise ValueError("Required prediction fields contain missing values.")


def calculate_fold_auc(group):
    """Calculate all model AUCs for one site, lookback year, and fold."""
    class_counts = group["visit_label"].value_counts()
    result = {
        "patient_count": len(group),
        "negative_count": int(class_counts.get(0, 0)),
        "positive_count": int(class_counts.get(1, 0)),
    }

    if group["visit_label"].nunique() != 2:
        for model_name in PROBABILITY_COLUMNS:
            result[f"{model_name}_roc_auc"] = float("nan")
        return pd.Series(result)

    for model_name, probability_column in PROBABILITY_COLUMNS.items():
        result[f"{model_name}_roc_auc"] = roc_auc_score(
            group["visit_label"], group[probability_column]
        )

    return pd.Series(result)


def summarize_folds(fold_results):
    """Calculate the unweighted mean and SD of valid fold AUCs per site."""
    auc_columns = [f"{model_name}_roc_auc" for model_name in PROBABILITY_COLUMNS]
    site_columns = ["lookback_year", "src_hpo_id"]

    summary_parts = []
    for auc_column in auc_columns:
        model_name = auc_column.removesuffix("_roc_auc")
        model_summary = (
            fold_results.groupby(site_columns)[auc_column]
            .agg(["mean", "std", "count"])
            .reset_index()
            .rename(columns={
                "mean": f"{model_name}_roc_auc_mean",
                "std": f"{model_name}_roc_auc_sd",
                "count": f"{model_name}_valid_fold_count",
            })
        )
        summary_parts.append(model_summary)

    summary = summary_parts[0]
    for model_summary in summary_parts[1:]:
        summary = summary.merge(model_summary, on=site_columns, how="outer")

    counts = (
        fold_results.groupby(site_columns, as_index=False)
        .agg(
            patient_count=("patient_count", "sum"),
            positive_count=("positive_count", "sum"),
            negative_count=("negative_count", "sum"),
            total_fold_count=("cv_fold", "nunique"),
        )
    )
    return counts.merge(summary, on=site_columns, how="left")


def main():
    predictions = pd.read_csv(PREDICTION_FILE)
    validate_predictions(predictions)

    fold_results = (
        predictions.groupby(GROUP_COLUMNS, sort=True, dropna=False)
        .apply(calculate_fold_auc, include_groups=False)
        .reset_index()
    )
    mean_results = summarize_folds(fold_results)

    fold_results.to_csv(FOLD_OUTPUT_FILE, index=False)
    mean_results.to_csv(MEAN_OUTPUT_FILE, index=False)

    print(f"Saved fold-specific AUCs: {FOLD_OUTPUT_FILE}")
    print(f"Saved unweighted mean fold AUCs: {MEAN_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
