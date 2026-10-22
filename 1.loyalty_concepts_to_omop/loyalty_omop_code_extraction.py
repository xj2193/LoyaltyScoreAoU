import pandas as pd
import json
from google.cloud import bigquery
from utils import read_config
import logging
from jinja2 import Template

config = read_config.load_config()
namespaces = config['bigquery']['namespaces']
OUTPUT_NAMESPACE = namespaces['output']
UNIONED_EHR_NAMESPACE = namespaces['unioned_ehr']

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_code(loyalty_code_df, loyalty_omop_concepts_df):
    mapped_df = pd.DataFrame(columns=['FEATURE_NAME', 'CONCEPT_CD'])
    for _, row in loyalty_code_df.iterrows():
        co_eff = row['FEATURE_NAME']
        act_path = row['ACT_PATH']
        loyalty_omop_concepts_df['exist'] = loyalty_omop_concepts_df['CONCEPT_PATH'].apply(lambda x: act_path in x)
        matched_omop_concepts = loyalty_omop_concepts_df[loyalty_omop_concepts_df['exist']]['CONCEPT_CD'].astype(
            int).to_frame()
        matched_omop_concepts['FEATURE_NAME'] = co_eff
        mapped_df = pd.concat([mapped_df, matched_omop_concepts], axis=0)
    mapped_df.drop_duplicates(inplace=True)
    mapped_df.reset_index(inplace=True)
    mapped_df.drop('index', axis=1, inplace=True)
    return mapped_df


loyalty_code_df = pd.read_csv('xref_LoyaltyCode_paths.csv')
loyalty_omop_concepts_df = pd.read_csv('LoyaltyConceptDimensionOMOPUnique_commasep.csv')

logging.info('Loyalty score concepts files are loaded')

loyalty_omop_concepts_df = loyalty_omop_concepts_df[
    loyalty_omop_concepts_df.CONCEPT_CD != ' ']  # exclude empty CONCEPT_IDs
loyalty_omop_concepts_df = loyalty_omop_concepts_df.astype(dtype={'CONCEPT_CD': int})
loyalty_omop_concepts_df['CONCEPT_PATH'] = loyalty_omop_concepts_df['CONCEPT_PATH'].apply(lambda x: x.split('OMOP')[0])

map_result = extract_code(loyalty_code_df, loyalty_omop_concepts_df)
map_result.drop_duplicates(inplace=True)

logging.info('Expand concepts with manually curated concept list')
concept_expanded = json.load(open('concept_expansion.json'))
for i in concept_expanded:
    for j in concept_expanded[i]:
        map_result.loc[len(map_result)] = [i, j]

# add inpatient and outpatient concepts
for j in [9202, 32253, 8756, 32252, 8677, 32257, 581477]:
    map_result.loc[len(map_result)] = ['OPT2_VISIT', j]
for i in [9201, 8717, 262, 32037, 581379, 9202, 32253, 8756, 32252, 8677, 32257, 581477]:
    map_result.loc[len(map_result)] = ['INP1_OPT1_VISIT', i]
for e in [32583, 9203, 42627881, 8870, 8870, 262]:
    map_result.loc[len(map_result)] = ['ED_VISIT', e]

map_result['ROUTINE_CARE_2'] = map_result['FEATURE_NAME'].apply(lambda x: 1 if x in ['MAMMOGRAPHY', 'PAP_TEST',
                                                                                     'PSA_TEST', 'COLONOSCOPY',
                                                                                     'FECAL_OCCULT_TEST', 'FLU_SHOT',
                                                                                     'PNEUMOCOCCAL_VACCINE', 'BMI',
                                                                                     'A1C'] else 0)
map_result.drop_duplicates(inplace=True)
map_result.to_csv('loyalty_score_concepts.csv', index=False)
logging.info('Loyalty score concepts csv file is saved locally')

#Upload to BigQuery
client = bigquery.Client()
client.load_table_from_dataframe(dataframe=map_result,
                                 destination=f"{OUTPUT_NAMESPACE}.loyalty_score_concepts",
                                 job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE"))
logging.info('Loyalty score concepts csv file is updated in bigquery project')

# Generate loyalty_score_concepts_with_standard_concepts table using SQL file
logging.info('Creating loyalty_score_concepts_with_standard_concepts table')
with open('loyalty_score_concepts_with_standard_concepts.sql', 'r') as f:
    sql_template = Template(f.read())

# Render template with config values
sql_query = sql_template.render(
    output_namespace=OUTPUT_NAMESPACE,
    unioned_ehr_namespace=UNIONED_EHR_NAMESPACE,
)

# Execute the query to create the table
client.query(f"CREATE OR REPLACE TABLE `{OUTPUT_NAMESPACE}.loyalty_score_concepts_with_standard_concepts` AS {sql_query}").result()
logging.info('loyalty_score_concepts_with_standard_concepts table is created')

client.query(f"SELECT * FROM `{OUTPUT_NAMESPACE}.loyalty_score_concepts_with_standard_concepts`",
             job_config= bigquery.QueryJobConfig(
                 destination=f"{OUTPUT_NAMESPACE}.mv_loyalty_score_concepts_with_standard_concepts",
                 write_disposition="WRITE_TRUNCATE"
             ))
logging.info('mv_loyalty_score_concepts_with_standard_concepts table is updated')
