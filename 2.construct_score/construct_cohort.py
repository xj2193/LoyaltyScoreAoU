import pandas as pd
from google.cloud import bigquery
import glob
from jinja2 import Environment, FileSystemLoader
from utils import read_config
import logging

config = read_config.load_config()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

namespaces = config['bigquery']['namespaces']
OUTPUT_NAMESPACE = namespaces['output']
OMOP_NAMESPACE = namespaces['omop']
PARTICIPANT_NAMESPACE = namespaces['participant']
MAPPING_NAMESPACE = namespaces['mappings']
ID_CROSSWALK_TABLE = config['bigquery']['tables']['id_crosswalk']

ANALYSIS_END_DATE = config['omop_table_configs']['ANALYSIS_END_DATE']
CSV_OUTPUT_FOLDER = config['folders']['CSV_OUTPUT_FOLDER']
INTERCEPT = config['analysis_configs']['INTERCEPT']
NORMALIZATION_SCALE = config['analysis_configs']['NORMALIZATION_SCALE']
COHORT_LABEL_PREFIX = config['analysis_configs']['COHORT_LABEL_PREFIX']


def create_cohort(look_back_year):

    csv_files = glob.glob(CSV_OUTPUT_FOLDER + '/*.csv')

    # extract person list with demographic data and EHR exist data
    client = bigquery.Client()

    file_loader = FileSystemLoader('query_templates/person_query')
    env = Environment(loader=file_loader)
    query_template = env.get_template('person_query.sql')

    person_query = query_template.render({
        'ANALYSIS_END_DATE': ANALYSIS_END_DATE,
        'OMOP_NAMESPACE': OMOP_NAMESPACE,
        'PARTICIPANT_NAMESPACE': PARTICIPANT_NAMESPACE,
        'MAPPING_NAMESPACE': MAPPING_NAMESPACE,
        'ID_CROSSWALK_TABLE': ID_CROSSWALK_TABLE,
    })

    person_df = client.query(person_query).to_dataframe()
    logging.info('Person data is extracted')

    for csv_file in csv_files:
        feature_df = pd.read_csv(csv_file)
        person_df = pd.merge(person_df, feature_df,
                             how='left',
                             left_on=['patient_num_rid', 'src_id'],
                             right_on=['person_id', 'src_id'])
        person_df.drop(columns=['person_id'], inplace=True)
    person_df.rename(columns={'MED_USE2': 'MEDUSE2',
                              'MED_USE1': 'MEDUSE1',
                              'PSA_TEST': 'PSATEST',
                              'PNEUMOCOCCAL_VACCINE': 'PNEUMOCOCCALVACCINE',
                              'PAP_TEST': 'PAPTEST',
                              'FECAL_OCCULT_TEST': 'FECALOCCULTTEST',
                              'FLU_SHOT': 'FLUSHOT',
                              'MEDICAL_EXAM': 'MEDICALEXAM'}, inplace=True)
    person_df.drop(columns=['MD_VISIT'], inplace=True)
    person_for_score = person_df.drop(columns=['patient_num_pid', 'race', 'ethnicity', 'gender', 'sex_at_birth', 'self_reported_race_ethnicity', 'age', 'INDEX_DT', 'LAST_VISIT', 'EHR_EXIST'])
    logging.info('Feature csv files are combined together')

    logging.info('Calculating loyalty score')
    coeff_df = client.query(
        f"SELECT * FROM "
        f"`{OUTPUT_NAMESPACE}.loyalty_code_pscoeff`"
    ).to_dataframe()
    coeff_df.set_index('fieldname', inplace=True)
    coeff_df.index = coeff_df.index.str.lower()
    coeff_df_sorted = coeff_df.reindex(person_for_score.columns.str.lower())
    coeff_df_sorted.dropna(inplace=True)

    person_df.columns = person_df.columns.str.lower()
    person_for_score.columns = person_for_score.columns.str.lower()

    person_for_score.set_index(['patient_num_rid', 'src_id'], inplace=True)
    coeff_array = coeff_df_sorted.astype(float).T.to_numpy()

    person_for_score.fillna(0, inplace=True)
    person_for_score['score'] = (person_for_score * coeff_array).sum(axis=1)
    person_for_score.reset_index(inplace=True)

    person_df_temp = pd.merge(person_df[['patient_num_rid', 'patient_num_pid', 'src_id', 'race', 'ethnicity', 'gender', 'sex_at_birth', 'self_reported_race_ethnicity', 'age', 'index_dt', 'last_visit', 'ehr_exist']],
                              person_for_score, how='inner', on=['patient_num_rid', 'src_id'])

    person_df_temp['score'] = (person_df_temp['score'] + INTERCEPT) / NORMALIZATION_SCALE
    person_df_temp['cohort_name'] = (
        f'{COHORT_LABEL_PREFIX}_{ANALYSIS_END_DATE}_{look_back_year}years'
    )
    logging.info(f'Look back year: {look_back_year} data has been extracted')
    return person_df_temp
