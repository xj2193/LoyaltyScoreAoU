from google.cloud import bigquery
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc, brier_score_loss
import numpy as np
import pandas as pd
from delong_test import Delong_test
import sys
import os
import warnings

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import read_config

config = read_config.load_config()
namespaces = config['bigquery']['namespaces']
OUTPUT_NAMESPACE = namespaces['output']
MAPPING_NAMESPACE = namespaces['mappings']
ID_CROSSWALK_TABLE = config['bigquery']['tables']['id_crosswalk']
COHORT_TABLE = config['analysis_configs']['COHORT_TABLE']
COHORT_LABEL_PREFIX = config['analysis_configs']['COHORT_LABEL_PREFIX']
ANALYSIS_END_DATE = config['omop_table_configs']['ANALYSIS_END_DATE']

features = ['meduse1', 'colonoscopy', 'paptest', 'bmi', 'num_dx2', 'routine_care_2', 'mdvisit_pname2', 'meduse2',
            'medicalexam', 'ed_visit', 'num_dx1', 'flushot', 'a1c', 'fecalocculttest', 'opt2_visit',
            'pneumococcalvaccine', 'mammography', 'mdvisit_pname3', 'inp1_opt1_visit', 'psatest']

OLD_COEFFICIENT = list([
    0.002,
    0.064,
    0.009,
    0.017,
    0.037,
    0.049,
    0.049,
    0.074,
    0.078,
    0.078,
    -0.026,
    0.102,
    0.018,
    0.034,
    0.05,
    0.031,
    0.075,
    0.087,
    0.091,
    0.103])

OLD_INTERCEPT = -0.01

labels = ['meduse1', 'colonoscopy', 'paptest', 'bmi', 'num_dx2', 'routine_care_2', 'mdvisit_pname2', 'meduse2',
          'medicalexam', 'ed_visit', 'num_dx1', 'flushot', 'a1c', 'fecalocculttest', 'opt2_visit',
          'pneumococcalvaccine', 'mammography', 'mdvisit_pname3', 'inp1_opt1_visit', 'psatest']


def aou_finetune(X_train, y_train, w_train):
    """
    Finetune the model using entire AoU data
    :param X_train: Training features
    :param y_train: Training labels
    :return: aou_model to evaluate the performance
    """
    aou_model = LogisticRegression(solver='lbfgs', max_iter=500)
    if w_train is not None:
        aou_model.fit(X_train, y_train, sample_weight=w_train)
    else:
        aou_model.fit(X_train, y_train)
    return aou_model


def ori_finetune():
    """
    Finetune the model with original coefficients and intercept
    :return: aou_model to evaluate the performance
    """
    ori_model = LogisticRegression(solver='lbfgs', max_iter=500)
    ori_model.coef_ = np.array(OLD_COEFFICIENT).reshape(1, -1)
    ori_model.intercept_ = np.array([OLD_INTERCEPT])
    ori_model.classes_ = np.array([0, 1])

    return ori_model


def sample_weights(train_df):
    train_site_sizes = train_df.groupby('src_hpo_id').size()
    weight_dict = {hpo_id: 1.0 / count for hpo_id, count in train_site_sizes.items()}
    return weight_dict


def expected_calibration_error(y_true, y_prob, n_bins=10):
    """
    Calculates the Expected Calibration Error (ECE) given the true labels and predicted probabilities.

    Parameters:
    y_true: Array-like, true labels.
    y_prob: Array-like, predicted probabilities.
    n_bins: Number of bins to use for calibration.

    Returns:
    float, ECE value.
    """

    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]

    ece = 0.0
    for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
        in_bin = np.logical_and(y_prob > bin_lower, y_prob <= bin_upper)
        if np.any(in_bin):
            bin_frac = np.mean(in_bin)
            bin_acc = np.mean(y_true[in_bin])
            bin_conf = np.mean(y_prob[in_bin])
            ece += bin_frac * np.abs(bin_acc - bin_conf)

    return ece


def predict_performance(y_test, y_aou_probs):
    # fpr, tpr, thresholds = roc_curve(y_test, y_aou_probs)
    roc_auc = roc_auc_score(y_test, y_aou_probs)
    precision, recall, _ = precision_recall_curve(y_test, y_aou_probs)
    pr_auc = auc(recall, precision)

    # prob_true, prob_pred = calibration_curve(y_test, y_aou_probs, n_bins=10)
    ece = expected_calibration_error(y_test, y_aou_probs, n_bins=10)

    aou_brier_score = brier_score_loss(y_test, y_aou_probs)
    return roc_auc, precision, recall, pr_auc, ece, aou_brier_score


def safe_delong(y_true, first_probabilities, second_probabilities):
    """Run DeLong's test, returning NaN when its variance is not estimable."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            z_score, p_value = Delong_test(
                y_true,
                first_probabilities,
                second_probabilities,
            )
    except (
        AssertionError,
        FloatingPointError,
        np.linalg.LinAlgError,
        ValueError,
        ZeroDivisionError,
    ):
        return np.nan, np.nan

    if not np.isfinite(z_score) or not np.isfinite(p_value):
        return np.nan, np.nan

    return z_score, p_value


def preprocess_data(df):
    df = df.copy()
    # Preserve a stable row identifier so that we can verify that every
    # eligible observation receives exactly one out-of-fold prediction.
    df['oof_row_id'] = np.arange(len(df))
    hpo_count = {}
    hpo_positive_count = {}
    hpo_cci = {}
    df['visit_label'] = np.where(df['last_visit'].notnull(), 1, 0)
    for hpo in df['src_hpo_id'].unique():
        hpo_df = df[df['src_hpo_id'] == hpo]
        hpo_count[hpo] = hpo_df.shape[0]
        hpo_positive_count[hpo] = hpo_df[hpo_df['visit_label'] == 1].shape[0]
        hpo_cci[hpo] = hpo_df['cci_score'].mean()
    return df, hpo_count, hpo_positive_count, hpo_cci


def hpo_split(df):
    print('Splitting data into training and testing using 5 fold cross-validation')

    cv_splits = 5
    cv = StratifiedKFold(
        n_splits=cv_splits,
        shuffle=True,
        random_state=42
        )
    train_test_dict = {
        fold: {'train': [], 'test': []}
        for fold in range(cv_splits)
    }

    eligible_hpos = []
    for hpo_id in df['src_hpo_id'].dropna().unique():
        print(f"Splitting data for HPO {hpo_id}")

        hpo_data = df[df['src_hpo_id'] == hpo_id]
        hpo_y = hpo_data['visit_label']
        if hpo_y.nunique() == 2 and hpo_y.value_counts().min() >= cv_splits:
            #train_hpo, test_hpo = train_test_split(hpo_data, test_size=0.3, stratify=hpo_y, random_state=42)
            eligible_hpos.append(hpo_id)
            for fold, (train_index, test_index) in enumerate(
                cv.split(hpo_data, hpo_y)
            ):
                train_test_dict[fold]['train'].append(
                    hpo_data.iloc[train_index]
                )
                train_test_dict[fold]['test'].append(
                    hpo_data.iloc[test_index]
                )
        else:
            print(
                f"Skipping HPO {hpo_id}: each class needs at least "
                f"{cv_splits} observations; "
                f"counts={hpo_y.value_counts().to_dict()}"
            )

    for fold in range(cv_splits):
        train_df = pd.concat(
            train_test_dict[fold]['train'],
            ignore_index=True
        )
        test_df = pd.concat(
            train_test_dict[fold]['test'],
            ignore_index=True
        )

        train_df['sample_weight'] = (
            train_df['src_hpo_id']
            .map(sample_weights(train_df))
        )

        train_test_dict[fold]['train'] = train_df
        train_test_dict[fold]['test'] = test_df

    combined_train_df = (
        df[df['src_hpo_id'].isin(eligible_hpos)]
        .copy()
        .reset_index(drop=True)
    )

    combined_train_df['sample_weight'] = (
        combined_train_df['src_hpo_id']
        .map(sample_weights(combined_train_df))
    )

    return train_test_dict, combined_train_df


def finetune(train_test_dict, combined_train_df, feature_list, hpo_count_dict,
             hpo_positive_count_dict, hpo_cci_dict, lookback_year):
    """Fit each fold and evaluate pooled patient-level OOF predictions.

    Each eligible observation is scored only by the model fitted without that
    observation. Metrics are then calculated once per HPO after predictions
    from all five held-out folds have been concatenated.
    """
    oof_results = []

    for cv_fold, train_test in train_test_dict.items():
        X_train = train_test['train'][feature_list]
        y_train = train_test['train']['visit_label']
        w_train = train_test['train']['sample_weight']

        ori_model = ori_finetune()
        aou_model = aou_finetune(X_train, y_train, None)
        weighted_aou_model = aou_finetune(X_train, y_train, w_train)

        test_df = train_test['test'].copy()
        X_test = test_df[feature_list]
        test_df['aou_probability'] = aou_model.predict_proba(X_test)[:, 1]
        test_df['weighted_probability'] = weighted_aou_model.predict_proba(X_test)[:, 1]
        # The original model is initialized from coefficients instead of fit
        # with feature names, so pass an array to avoid sklearn warnings.
        test_df['original_probability'] = ori_model.predict_proba(
            X_test.to_numpy()
        )[:, 1]
        test_df['cv_fold'] = cv_fold
        test_df['lookback_year'] = lookback_year

        id_columns = [
            column for column in
            ['oof_row_id', 'patient_num_pid', 'patient_num_rid', 'src_hpo_id']
            if column in test_df.columns
        ]
        oof_results.append(
            test_df[id_columns + [
                'visit_label', 'lookback_year', 'cv_fold',
                'aou_probability', 'weighted_probability',
                'original_probability',
            ]]
        )

    oof_df = pd.concat(oof_results, ignore_index=True)

    if oof_df['oof_row_id'].duplicated().any():
        raise ValueError('At least one observation received multiple OOF predictions.')
    if set(oof_df['oof_row_id']) != set(combined_train_df['oof_row_id']):
        raise ValueError('OOF predictions do not cover every eligible observation exactly once.')
    probability_columns = [
        'aou_probability', 'weighted_probability', 'original_probability'
    ]
    if oof_df[probability_columns].isna().any().any():
        raise ValueError('Missing values were found in the OOF probabilities.')

    performance_rows = []
    for hpo, hpo_df in oof_df.groupby('src_hpo_id'):
        y_test = hpo_df['visit_label'].to_numpy()
        y_aou_probs = hpo_df['aou_probability'].to_numpy()
        weighted_y_probs = hpo_df['weighted_probability'].to_numpy()
        ori_y_probs = hpo_df['original_probability'].to_numpy()

        aou_metrics = predict_performance(y_test, y_aou_probs)
        weighted_metrics = predict_performance(y_test, weighted_y_probs)
        ori_metrics = predict_performance(y_test, ori_y_probs)

        ori_aou_delong = safe_delong(y_test, ori_y_probs, y_aou_probs)
        ori_weighted_delong = safe_delong(
            y_test, ori_y_probs, weighted_y_probs
        )
        aou_weighted_delong = safe_delong(
            y_test, y_aou_probs, weighted_y_probs
        )

        performance_rows.append({
            'hpo': hpo,
            'patient_count': hpo_count_dict[hpo],
            'hpo_positive_cases': hpo_positive_count_dict[hpo],
            'hpo_cci_mean': hpo_cci_dict[hpo],
            'lookback_year': lookback_year,
            'aou_roc_auc': aou_metrics[0],
            'aou_pr_auc': aou_metrics[3],
            'aou_brier_score': aou_metrics[5],
            'aou_ece': aou_metrics[4],
            'weighted_roc_auc': weighted_metrics[0],
            'weighted_pr_auc': weighted_metrics[3],
            'weighted_brier_score': weighted_metrics[5],
            'weighted_ece': weighted_metrics[4],
            'ori_roc_auc': ori_metrics[0],
            'ori_pr_auc': ori_metrics[3],
            'ori_brier_score': ori_metrics[5],
            'ori_ece': ori_metrics[4],
            'delong_z_score_ori_aou': ori_aou_delong[0],
            'delong_p_value_ori_aou': ori_aou_delong[1],
            'delong_z_score_ori_weighted': ori_weighted_delong[0],
            'delong_p_value_ori_weighted': ori_weighted_delong[1],
            'delong_z_score_aou_weighted': aou_weighted_delong[0],
            'delong_p_value_aou_weighted': aou_weighted_delong[1],
        })

    performance_df = pd.DataFrame(performance_rows)

    # Fit final AoU model on the entire training data
    print('Fitting final AoU model on the entire training data')
    combined_X_train = combined_train_df[feature_list]
    combined_y_train = combined_train_df['visit_label']
    combined_w_train = combined_train_df['sample_weight']

    combined_aou_model = aou_finetune(combined_X_train, combined_y_train, None)
    combined_weighted_aou_model = aou_finetune(
        combined_X_train, combined_y_train, combined_w_train
    )

    return (
        performance_df,
        oof_df,
        combined_aou_model.coef_,
        combined_weighted_aou_model.coef_,
    )


client = bigquery.Client()

performance_result_all_lookback_years = pd.DataFrame()
oof_result_all_lookback_years = pd.DataFrame()
coeff_all_lookback_years = pd.DataFrame()
inp1_opt1_visit_counts = []

for lookback_year in range(1, 8):
    loyalty_score_query = f"""
    SELECT ms.src_hpo_id, ls.*, cci.score as cci_score
    FROM `{OUTPUT_NAMESPACE}.{COHORT_TABLE}` AS ls
    LEFT JOIN `{ID_CROSSWALK_TABLE}` AS rid_pid
    ON ls.patient_num_rid = rid_pid.research_id
    LEFT JOIN `{MAPPING_NAMESPACE}.site_maskings` sm
    ON ls.src_id = sm.src_id
    LEFT JOIN `{OUTPUT_NAMESPACE}.mask_site_id` as ms
    ON sm.hpo_id = ms.src_hpo_id
    LEFT JOIN `{OUTPUT_NAMESPACE}.charlson_comorbidity_score_per_person` cci
    ON ls.patient_num_pid = cci.person_id
    AND cci.lookback_year = '{lookback_year}years'
    WHERE ls.cohort_name = '{COHORT_LABEL_PREFIX}_{ANALYSIS_END_DATE}_{lookback_year}years'
    """

    ls_df = client.query(loyalty_score_query).to_dataframe()

    # A participant can have records from more than one site. Count each
    # participant once and mark the feature as present when it is present in
    # any of their site-specific rows.
    patient_inp1_opt1_visit = (
        ls_df.groupby('patient_num_rid', dropna=False)['inp1_opt1_visit']
        .max()
        .fillna(0)
    )
    total_patients = patient_inp1_opt1_visit.size
    patients_with_inp1_opt1_visit = int(
        patient_inp1_opt1_visit.eq(1).sum()
    )
    inp1_opt1_visit_counts.append({
        'lookback_year': lookback_year,
        'total_patients': total_patients,
        'patients_with_inp1_opt1_visit': patients_with_inp1_opt1_visit,
        'percent_with_inp1_opt1_visit': (
            100 * patients_with_inp1_opt1_visit / total_patients
        ),
    })

    data_to_split, hpo_count, hpo_positive_count, hpo_cci = preprocess_data(ls_df)

    train_test_dict, combined_train_df = hpo_split(data_to_split)

    performance_result, oof_result, aou_coeff, weighted_aou_coeff = finetune(
        train_test_dict,
        combined_train_df,
        features,
        hpo_count,
        hpo_positive_count,
        hpo_cci,
        lookback_year=lookback_year,
    )

    coeff_df = pd.DataFrame(
        columns=['lookback_year', 'old_coeff', 'aou_coeff', 'weighted_aou_coeff', 'original_odds', 'aou_odds', 'weighted_aou_odds'])

    OLD_COEFFICIENT = np.array(OLD_COEFFICIENT).reshape(1, -1)
    coeff_df.loc[len(coeff_df)] = [lookback_year, OLD_COEFFICIENT, aou_coeff, weighted_aou_coeff, np.exp(OLD_COEFFICIENT),
                               np.exp(aou_coeff), np.exp(weighted_aou_coeff)]

    all_named_hpos = ls_df[['src_hpo_id']].dropna().drop_duplicates()
    performance_result = pd.merge(
        all_named_hpos,
        performance_result,
        how='left',
        left_on='src_hpo_id',
        right_on='hpo',
    )
    # Preserve denominators and exclusion information for HPOs that were not
    # eligible for five-fold stratification. Their performance metrics remain
    # missing, but they retain a site identifier, lookback year, and counts.
    performance_result['hpo'] = performance_result['hpo'].fillna(
        performance_result['src_hpo_id']
    )
    performance_result['lookback_year'] = performance_result['lookback_year'].fillna(
        lookback_year
    )
    performance_result['patient_count'] = performance_result['patient_count'].fillna(
        performance_result['src_hpo_id'].map(hpo_count)
    )
    performance_result['hpo_positive_cases'] = performance_result[
        'hpo_positive_cases'
    ].fillna(performance_result['src_hpo_id'].map(hpo_positive_count))
    performance_result['hpo_cci_mean'] = performance_result['hpo_cci_mean'].fillna(
        performance_result['src_hpo_id'].map(hpo_cci)
    )

    performance_result_all_lookback_years = pd.concat([performance_result_all_lookback_years, performance_result], ignore_index=True)
    oof_result_all_lookback_years = pd.concat(
        [oof_result_all_lookback_years, oof_result],
        ignore_index=True,
    )
    coeff_all_lookback_years = pd.concat([coeff_all_lookback_years, coeff_df], ignore_index=True)

performance_result_all_lookback_years.to_csv(
    'finetune_per_hpo_all_lookback_years_5fold_oof.csv',
    index=False,
    header=True,
)
oof_result_all_lookback_years.to_csv(
    'patient_level_out_of_fold_predictions.csv',
    index=False,
    header=True,
)
coeff_all_lookback_years.to_csv('coeff_all_lookback_years.csv', index=False)
pd.DataFrame(inp1_opt1_visit_counts).to_csv(
    'inp1_opt1_visit_patient_counts_by_lookback_year.csv',
    index=False,
)
