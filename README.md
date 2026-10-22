# Loyalty Score for the All of Us Research Program

This repository contains the cohort-construction, model-training, and analysis
code used to calculate an electronic health record (EHR) loyalty score for
participants in the NIH All of Us Research Program. The score is based on a
published [I2B2 loyalty-score study](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10654861/)
and is adapted here to OMOP CDM data.

The workflow:

1. maps the original loyalty-score concepts to OMOP concepts;
2. constructs one- through seven-year lookback cohorts;
3. calculates Charlson Comorbidity Index (CCI) scores;
4. retrains and evaluates logistic-regression models;
5. runs five-fold and leave-one-HPO-out validation; and
6. supports statistical, data-quality, and phecode analyses.

## Data privacy

This repository contains code and reference mappings only. It does not contain
participant-level All of Us data. Generated CSV, spreadsheet, figure, query,
and analysis-output files are excluded by `.gitignore`.

Several scripts produce files containing participant identifiers or
participant-level predictions. Keep those files in an approved environment and
do not add them to Git, including with `git add -f`.

## Prerequisites

- Python 3.9 or newer
- Git LFS, for the reference CSV files
- Access to the required Google Cloud and BigQuery projects
- Application Default Credentials or an approved service-account credential
- Source data represented in OMOP CDM, including required local extensions
- Permission to create the configured analysis outputs

The workflow also requires institution-specific identifier linkage, site
mapping, and model-coefficient resources. These resources are not distributed
with the repository. Configure them locally using the provided template and
adapt the queries to the access controls and schemas in your environment.

## Installation

```bash
git lfs install
git clone https://github.com/xj2193/LoyaltyScoreAoU.git
cd LoyaltyScoreAoU
git lfs pull

python -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

The editable installation makes the repository-level `utils` package
available when scripts are run from their numbered subdirectories.

Authenticate with Google Cloud using the method approved for your environment.
For example, when local Application Default Credentials are permitted:

```bash
gcloud auth application-default login
```

Alternatively, set `GOOGLE_APPLICATION_CREDENTIALS` to an approved credential
file outside this repository. Never commit a credential file.

## Configuration

Create the local configuration file:

```bash
cp configs/bq_credentials_template.yaml configs/bq_credentials.yaml
```

Populate the neutral source, output, and private-resource placeholders in the
local file. The template intentionally separates public code from
institution-specific identifiers and storage layout. Do not replace the
placeholders in tracked source files.

Also review:

- `ANALYSIS_END_DATE`
- `OMOP_TABLE_PREFIX`
- `QUERY_OUTPUT_FOLDER` and `CSV_OUTPUT_FOLDER`
- `INTERCEPT` and `NORMALIZATION_SCALE`
- `LOOK_BACK_YEARS`

The private `configs/bq_credentials.yaml` file is ignored by Git.

## Required BigQuery setup

Before model training, confirm that the configured OMOP sources, vocabulary,
private linkage resources, model coefficients, and output locations are
accessible. The SQL templates under the numbered workflow directories must be
rendered with local configuration values before execution.

Create site pseudonyms once and reuse them consistently across analyses.

## End-to-end workflow

Run the following commands from the indicated directories after completing the
installation and BigQuery setup.

### 1. Convert loyalty-score concepts to OMOP

Reference inputs:

- [xref_LoyaltyCode_paths.csv](1.loyalty_concepts_to_omop/xref_LoyaltyCode_paths.csv)
- [LoyaltyConceptDimensionOMOPUnique_commasep.csv](1.loyalty_concepts_to_omop/LoyaltyConceptDimensionOMOPUnique_commasep.csv)
- [concept_expansion.json](1.loyalty_concepts_to_omop/concept_expansion.json)

```bash
cd 1.loyalty_concepts_to_omop
python loyalty_omop_code_extraction.py
cd ..
```

The script writes an ignored local mapping file and the corresponding objects
to the configured output location.

### 2. Construct lookback cohorts and calculate loyalty scores

Review [person_query.sql](2.construct_score/query_templates/person_query/person_query.sql)
before running this step. It contains All of Us-specific demographic joins and
defines the next-year visit outcome.

```bash
cd 2.construct_score
python run_multi_lookback_years.py
cd ..
```

For each configured lookback year, the pipeline:

1. renders feature queries into `output_query/`;
2. extracts feature cohorts into `feature_csv_output/`;
3. merges the features with participant and outcome data;
4. calculates the loyalty score using the configured coefficient resource; and
5. combines all lookback cohorts.

Outputs:

- local `combined_data.csv`
- a cohort object in the configured output location

The combined data contains participant and site identifiers, demographic
variables, model features, the loyalty score, cohort metadata, and the
next-year visit outcome. Treat it as restricted participant-level data.

### 3. Create and calculate Charlson Comorbidity Index scores

Render and execute
[create_charlson_comorbidity_index.sql](4.charlson_comorbidity_index/create_charlson_comorbidity_index.sql)
using the private local configuration. Then calculate per-participant scores:

```bash
cd 4.charlson_comorbidity_index
python run_charlson_comorbidity_score.py
cd ..
```

The current implementation appends results. Clear or replace the configured
target before rerunning a complete analysis to avoid duplicate records.

### 4. Run five-fold out-of-fold model evaluation

```bash
cd 3.retrain_regression
python finetune.py
python summarize_mean_fold_auc.py
cd ..
```

Primary outputs:

- `finetune_per_hpo_all_lookback_years_5fold_oof.csv`
- `patient_level_out_of_fold_predictions.csv`
- `coeff_all_lookback_years.csv`
- `inp1_opt1_visit_patient_counts_by_lookback_year.csv`
- `finetune_per_hpo_fold_auc.csv`
- `finetune_per_hpo_all_lookback_years_5fold_mean_auc.csv`

Run [performance_analysis.ipynb](3.retrain_regression/performance_analysis.ipynb)
after both Python scripts. It reads the OOF and mean-fold outputs and writes
tables and plots under `3.retrain_regression/analysis_outputs/`.

### 5. Plot odds-ratio comparisons

Set `LOOKBACK_YEAR` near the top of
[visualize_odds_error_bar.py](3.retrain_regression/visualize_odds_error_bar.py),
then run:

```bash
cd 3.retrain_regression
python visualize_odds_error_bar.py
cd ..
```

The script reads `coeff_all_lookback_years.csv` and creates pairwise
dumbbell plots plus a comparison CSV for the selected lookback year. These are
point estimates; the coefficient file does not contain confidence intervals.

### 6. Run leave-one-HPO-out validation

```bash
cd 3.retrain_regression
python finetune_leave_one_out.py
cd ..
```

Primary outputs:

- `finetune_per_hpo_all_lookback_years_leave_one_hpo_out.csv`
- `patient_level_leave_one_hpo_out_predictions.csv`
- `leave_one_hpo_out_eligibility.csv`
- `coeff_all_lookback_years_leave_one_hpo_out.csv`

Then run
[loho_performance_analysis.ipynb](3.retrain_regression/loho_performance_analysis.ipynb)
to create leave-one-HPO-out summary tables and figures.

### 7. Run exploratory analyses

Statistical analysis:

```bash
cd 5.exploratory_analysis/statistical_analysis
jupyter lab loyalty_score_analysis.ipynb
```

The notebook queries the loyalty-score and CCI tables and produces descriptive,
site-level, demographic, and CCI analyses.

Data Quality Dashboard analysis:

1. Place an OHDSI DQD result at
   `5.exploratory_analysis/dqd_analysis/dqd_results.json`.
2. Run:

```bash
cd 5.exploratory_analysis/dqd_analysis
jupyter lab dqd_analysis.ipynb
```

Both the DQD input and generated outputs are ignored by Git.

### 8. Run phecode analysis

Load [Phecode_mapX_filtered.csv](6.phecode/Phecode_mapX_filtered.csv) into the
configured private analysis environment and complete the required site-mapping
setup before running:

```bash
cd 6.phecode
jupyter lab phecode_analysis.ipynb
```

The notebook uses both `Phecode_mapX_filtered.csv` and
[phecodeX_info.csv](6.phecode/phecodeX_info.csv) for phecode-level and
category-level analyses.

## Current implementation assumptions

The training and analysis code currently assumes:

- the configured lookback-year range;
- the cohort table named by `COHORT_TABLE`; and
- cohort labels built from `COHORT_LABEL_PREFIX`, `ANALYSIS_END_DATE`, and the
  lookback year.

These values are shared by cohort construction, model training, and the
analysis notebooks through the private configuration file.

Generated filenames are stable and do not include run dates. Move or archive
earlier outputs before rerunning a workflow if they need to be preserved.

## Generated files and version control

Generated data, figures, archives, notebook checkpoints, and local credentials
are ignored. Four reference CSV files are intentionally retained through Git
LFS. Before committing, verify the staged file list:

```bash
git status --short
git diff --cached --stat
```

Do not force-add ignored data files.

## License

The source code and reference mappings in this repository are licensed under
the [Apache License 2.0](LICENSE).

## Citation

If you use this repository, cite the original loyalty-score study linked above
and any All of Us Research Program data-release documentation required by your
data-use agreement.

## Support

Use the GitHub repository's issue tracker for reproducible code and
documentation problems. Do not include participant data, credentials, project
identifiers, or restricted screenshots in an issue.
