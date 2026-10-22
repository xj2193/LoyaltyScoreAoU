"""Leave-one-HPO-out validation for the AoU loyalty-score model.

For each eligible HPO, fit on all other eligible HPOs and evaluate on every
patient from the held-out HPO. Then fit a final model on all eligible HPOs.
"""

import os
import sys
import warnings

import numpy as np
import pandas as pd
from google.cloud import bigquery
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import auc, brier_score_loss, precision_recall_curve, roc_auc_score

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import read_config

from delong_test import Delong_test


config = read_config.load_config()
namespaces = config["bigquery"]["namespaces"]
OUTPUT_NAMESPACE = namespaces["output"]
MAPPING_NAMESPACE = namespaces["mappings"]
ID_CROSSWALK_TABLE = config["bigquery"]["tables"]["id_crosswalk"]
COHORT_TABLE = config["analysis_configs"]["COHORT_TABLE"]
COHORT_LABEL_PREFIX = config["analysis_configs"]["COHORT_LABEL_PREFIX"]
ANALYSIS_END_DATE = config["omop_table_configs"]["ANALYSIS_END_DATE"]

FEATURES = [
    "meduse1", "colonoscopy", "paptest", "bmi", "num_dx2",
    "routine_care_2", "mdvisit_pname2", "meduse2", "medicalexam",
    "ed_visit", "num_dx1", "flushot", "a1c", "fecalocculttest",
    "opt2_visit", "pneumococcalvaccine", "mammography",
    "mdvisit_pname3", "inp1_opt1_visit", "psatest",
]

OLD_COEFFICIENT = np.array([
    0.002, 0.064, 0.009, 0.017, 0.037, 0.049, 0.049, 0.074, 0.078,
    0.078, -0.026, 0.102, 0.018, 0.034, 0.05, 0.031, 0.075, 0.087,
    0.091, 0.103,
])
OLD_INTERCEPT = -0.01

PERFORMANCE_COLUMNS = [
    "hpo", "patient_count", "hpo_positive_cases", "hpo_cci_mean",
    "lookback_year", "aou_roc_auc", "aou_pr_auc", "aou_brier_score",
    "aou_ece", "weighted_roc_auc", "weighted_pr_auc",
    "weighted_brier_score", "weighted_ece", "ori_roc_auc", "ori_pr_auc",
    "ori_brier_score", "ori_ece", "delong_z_score_ori_aou",
    "delong_p_value_ori_aou", "delong_z_score_ori_weighted",
    "delong_p_value_ori_weighted", "delong_z_score_aou_weighted",
    "delong_p_value_aou_weighted",
]


def fit_model(X_train, y_train, sample_weight=None):
    model = LogisticRegression(solver="lbfgs", max_iter=500)
    model.fit(X_train, y_train, sample_weight=sample_weight)
    return model


def original_model():
    model = LogisticRegression(solver="lbfgs", max_iter=500)
    model.coef_ = OLD_COEFFICIENT.reshape(1, -1)
    model.intercept_ = np.array([OLD_INTERCEPT])
    model.classes_ = np.array([0, 1])
    return model


def add_sample_weights(train_df):
    """Give every HPO equal total weight within a training set."""
    result = train_df.copy()
    hpo_sizes = result.groupby("src_hpo_id")["src_hpo_id"].transform("size")
    result["sample_weight"] = 1.0 / hpo_sizes
    return result


def expected_calibration_error(y_true, y_prob, n_bins=10):
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    bin_ids = np.minimum((y_prob * n_bins).astype(int), n_bins - 1)

    ece = 0.0
    for bin_id in range(n_bins):
        in_bin = bin_ids == bin_id
        if np.any(in_bin):
            ece += np.mean(in_bin) * abs(
                np.mean(y_true[in_bin]) - np.mean(y_prob[in_bin])
            )
    return ece


def predict_performance(y_test, probabilities):
    roc_auc = roc_auc_score(y_test, probabilities)
    precision, recall, _ = precision_recall_curve(y_test, probabilities)
    pr_auc = auc(recall, precision)
    ece = expected_calibration_error(y_test, probabilities, n_bins=10)
    brier_score = brier_score_loss(y_test, probabilities)
    return roc_auc, pr_auc, brier_score, ece


def preprocess_data(df):
    result = df.copy()
    result["loho_row_id"] = np.arange(len(result))
    result["visit_label"] = np.where(result["last_visit"].notna(), 1, 0)
    return result


def eligible_hpos(df):
    """Return eligible HPOs and a report describing every exclusion."""
    eligible = []
    eligibility_rows = []
    for hpo_id, hpo_df in df.dropna(subset=["src_hpo_id"]).groupby("src_hpo_id"):
        class_counts = hpo_df["visit_label"].value_counts()
        positive_count = int(class_counts.get(1, 0))
        negative_count = int(class_counts.get(0, 0))
        is_eligible = min(positive_count, negative_count) >= 2

        if is_eligible:
            eligible.append(hpo_id)
            exclusion_reason = ""
        else:
            exclusion_reason = "Each outcome class requires at least 2 observations"
            print(
                f"Skipping HPO {hpo_id}: each class needs at least 2 "
                f"observations; counts={class_counts.to_dict()}"
            )

        eligibility_rows.append({
            "hpo": hpo_id,
            "patient_count": len(hpo_df),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "minority_class_count": min(positive_count, negative_count),
            "eligible": is_eligible,
            "exclusion_reason": exclusion_reason,
        })

    return eligible, pd.DataFrame(eligibility_rows)


def safe_delong(y_true, first_probabilities, second_probabilities):
    """Return missing values if DeLong's variance is not estimable."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            z_score, p_value = Delong_test(
                y_true, first_probabilities, second_probabilities
            )
    except (AssertionError, FloatingPointError, ValueError, ZeroDivisionError):
        return np.nan, np.nan

    if not np.isfinite(z_score) or not np.isfinite(p_value):
        return np.nan, np.nan
    return z_score, p_value


def evaluate_leave_one_hpo_out(df, feature_list, lookback_year):
    """Train on all but one HPO and evaluate on the held-out HPO."""
    included_hpos, eligibility_df = eligible_hpos(df)
    eligibility_df["lookback_year"] = lookback_year
    if len(included_hpos) < 2:
        raise ValueError("Leave-one-HPO-out validation requires at least two eligible HPOs.")

    analysis_df = (
        df[df["src_hpo_id"].isin(included_hpos)].copy().reset_index(drop=True)
    )
    original = original_model()
    rows = []
    prediction_rows = []

    for held_out_hpo in included_hpos:
        print(f"Holding out HPO {held_out_hpo}")
        train_df = analysis_df[analysis_df["src_hpo_id"] != held_out_hpo]
        test_df = analysis_df[analysis_df["src_hpo_id"] == held_out_hpo]
        weighted_train_df = add_sample_weights(train_df)

        y_train = train_df["visit_label"]
        if y_train.nunique() != 2:
            raise ValueError(
                f"Training data has only one class after holding out {held_out_hpo}."
            )

        unweighted_model = fit_model(train_df[feature_list], y_train)
        weighted_model = fit_model(
            weighted_train_df[feature_list],
            weighted_train_df["visit_label"],
            weighted_train_df["sample_weight"],
        )

        X_test = test_df[feature_list]
        y_test = test_df["visit_label"]
        aou_prob = unweighted_model.predict_proba(X_test)[:, 1]
        weighted_prob = weighted_model.predict_proba(X_test)[:, 1]
        # The original model is initialized from coefficients rather than fit,
        # so use an array to avoid sklearn's feature-name warning.
        original_prob = original.predict_proba(X_test.to_numpy())[:, 1]

        id_columns = [
            column for column in
            ["loho_row_id", "patient_num_pid", "patient_num_rid", "src_hpo_id"]
            if column in test_df.columns
        ]
        held_out_predictions = test_df[id_columns + ["visit_label"]].copy()
        held_out_predictions["hpo"] = held_out_hpo
        held_out_predictions["lookback_year"] = lookback_year
        held_out_predictions["aou_probability"] = aou_prob
        held_out_predictions["weighted_probability"] = weighted_prob
        held_out_predictions["original_probability"] = original_prob
        prediction_rows.append(held_out_predictions)

        aou_metrics = predict_performance(y_test, aou_prob)
        weighted_metrics = predict_performance(y_test, weighted_prob)
        original_metrics = predict_performance(y_test, original_prob)

        ori_aou = safe_delong(y_test, original_prob, aou_prob)
        ori_weighted = safe_delong(y_test, original_prob, weighted_prob)
        aou_weighted = safe_delong(y_test, aou_prob, weighted_prob)

        rows.append({
            "hpo": held_out_hpo,
            "patient_count": len(test_df),
            "hpo_positive_cases": int(y_test.sum()),
            "hpo_cci_mean": test_df["cci_score"].mean(),
            "lookback_year": lookback_year,
            "aou_roc_auc": aou_metrics[0],
            "aou_pr_auc": aou_metrics[1],
            "aou_brier_score": aou_metrics[2],
            "aou_ece": aou_metrics[3],
            "weighted_roc_auc": weighted_metrics[0],
            "weighted_pr_auc": weighted_metrics[1],
            "weighted_brier_score": weighted_metrics[2],
            "weighted_ece": weighted_metrics[3],
            "ori_roc_auc": original_metrics[0],
            "ori_pr_auc": original_metrics[1],
            "ori_brier_score": original_metrics[2],
            "ori_ece": original_metrics[3],
            "delong_z_score_ori_aou": ori_aou[0],
            "delong_p_value_ori_aou": ori_aou[1],
            "delong_z_score_ori_weighted": ori_weighted[0],
            "delong_p_value_ori_weighted": ori_weighted[1],
            "delong_z_score_aou_weighted": aou_weighted[0],
            "delong_p_value_aou_weighted": aou_weighted[1],
        })

    performance_df = pd.DataFrame(rows, columns=PERFORMANCE_COLUMNS)
    prediction_df = pd.concat(prediction_rows, ignore_index=True)

    if prediction_df["loho_row_id"].duplicated().any():
        raise ValueError(
            "At least one observation received multiple leave-one-HPO-out predictions."
        )
    if set(prediction_df["loho_row_id"]) != set(analysis_df["loho_row_id"]):
        raise ValueError(
            "Leave-one-HPO-out predictions do not cover every eligible observation exactly once."
        )
    probability_columns = [
        "aou_probability", "weighted_probability", "original_probability"
    ]
    if prediction_df[probability_columns].isna().any().any():
        raise ValueError(
            "Missing values were found in the leave-one-HPO-out probabilities."
        )

    # Fit deployable models once on the complete LOHO-eligible population.
    full_weighted_df = add_sample_weights(analysis_df)
    final_model = fit_model(analysis_df[feature_list], analysis_df["visit_label"])
    final_weighted_model = fit_model(
        full_weighted_df[feature_list],
        full_weighted_df["visit_label"],
        full_weighted_df["sample_weight"],
    )
    return (
        performance_df,
        prediction_df,
        eligibility_df,
        final_model,
        final_weighted_model,
    )


def query_lookback_data(client, lookback_year):
    query = f"""
    SELECT ms.src_hpo_id, ls.*, cci.score AS cci_score
    FROM `{OUTPUT_NAMESPACE}.{COHORT_TABLE}` AS ls
    LEFT JOIN `{ID_CROSSWALK_TABLE}` AS rid_pid
      ON ls.patient_num_rid = rid_pid.research_id
    LEFT JOIN `{MAPPING_NAMESPACE}.site_maskings` AS sm
      ON ls.src_id = sm.src_id
    LEFT JOIN `{OUTPUT_NAMESPACE}.mask_site_id` AS ms
      ON sm.hpo_id = ms.src_hpo_id
    LEFT JOIN `{OUTPUT_NAMESPACE}.charlson_comorbidity_score_per_person` AS cci
      ON ls.patient_num_pid = cci.person_id
     AND cci.lookback_year = '{lookback_year}years'
    WHERE ls.cohort_name = '{COHORT_LABEL_PREFIX}_{ANALYSIS_END_DATE}_{lookback_year}years'
    """
    return client.query(query).to_dataframe()


def main():
    client = bigquery.Client()
    performance_results = []
    prediction_results = []
    eligibility_results = []
    coefficient_results = []

    for lookback_year in range(1, 8):
        data = preprocess_data(query_lookback_data(client, lookback_year))
        (
            performance,
            predictions,
            eligibility,
            final_model,
            final_weighted_model,
        ) = evaluate_leave_one_hpo_out(data, FEATURES, lookback_year)
        performance_results.append(performance)
        prediction_results.append(predictions)
        eligibility_results.append(eligibility)

        coefficient_results.append(pd.DataFrame({
            "lookback_year": lookback_year,
            "feature": FEATURES,
            "old_coeff": OLD_COEFFICIENT,
            "aou_coeff": final_model.coef_[0],
            "weighted_aou_coeff": final_weighted_model.coef_[0],
            "original_odds": np.exp(OLD_COEFFICIENT),
            "aou_odds": np.exp(final_model.coef_[0]),
            "weighted_aou_odds": np.exp(final_weighted_model.coef_[0]),
        }))

    pd.concat(performance_results, ignore_index=True).to_csv(
        "finetune_per_hpo_all_lookback_years_leave_one_hpo_out.csv",
        index=False,
    )
    pd.concat(prediction_results, ignore_index=True).to_csv(
        "patient_level_leave_one_hpo_out_predictions.csv",
        index=False,
    )
    pd.concat(eligibility_results, ignore_index=True).to_csv(
        "leave_one_hpo_out_eligibility.csv",
        index=False,
    )
    pd.concat(coefficient_results, ignore_index=True).to_csv(
        "coeff_all_lookback_years_leave_one_hpo_out.csv",
        index=False,
    )


if __name__ == "__main__":
    main()
