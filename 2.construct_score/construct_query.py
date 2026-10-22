from google.cloud import bigquery
from jinja2 import Environment, FileSystemLoader
import os
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from utils import read_config
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

config = read_config.load_config()
namespaces = config['bigquery']['namespaces']
OUTPUT_NAMESPACE = namespaces['output']
OMOP_NAMESPACE = namespaces['omop']

OMOP_TABLE_PREFIX = config['omop_table_configs']['OMOP_TABLE_PREFIX']

ANALYSIS_END_DATE = config['omop_table_configs']['ANALYSIS_END_DATE']
QUERY_OUTPUT_FOLDER = config['folders']['QUERY_OUTPUT_FOLDER']

omop_table_spec = json.load(open('omop_table_column_mapping.json'))


def render_query(entire_omop_table, provider_required, domain_id, feature_name, analysis_start_date):
    if entire_omop_table:
        file_loader = FileSystemLoader('query_templates/dx_or_rx_events/')
    else:
        if provider_required:
            file_loader = FileSystemLoader('query_templates/provider_events')
        else:
            file_loader = FileSystemLoader('query_templates/feature_events')
    env = Environment(loader=file_loader)
    omop_table = (OMOP_TABLE_PREFIX + omop_table_spec[domain_id.lower()]['table_name'])
    omop_visit_table = (OMOP_TABLE_PREFIX + omop_table_spec['visit']['table_name'])
    date_column = omop_table_spec[domain_id.lower()]['date_column']
    concept_column_name = omop_table_spec[domain_id.lower()]['concept_column_name']
    source_concept_column_name = omop_table_spec[domain_id.lower()]['source_concept_column_name']
    omop_table_id = omop_table_spec[domain_id.lower()]['omop_table_id']

    query_template = env.get_template('standard_query_template.sql')
    if (domain_id == 'Observation') and (feature_name in ['MAMMOGRAPHY', 'COLONOSCOPY', 'PAP_TEST', 'PSA_TEST']):
        query_template = env.get_template('standard_query_observation_template.sql')
    query = query_template.render({'omop_table': omop_table,
                                   'omop_visit_table': omop_visit_table,
                                   'date_column': date_column,
                                   'concept_column_name': concept_column_name,
                                   'source_concept_column_name': source_concept_column_name,
                                   'output_namespace': OUTPUT_NAMESPACE,
                                   'omop_namespace': OMOP_NAMESPACE,
                                   'start_date': analysis_start_date,
                                   'end_date': ANALYSIS_END_DATE,
                                   'omop_table_id': omop_table_id,
                                   'feature_name': feature_name,
                                   'domain_id': domain_id})
    return query


def fill_in_query(entire_omop_table, domain_union, provider_required, instance_required, feature_name, is_routine_care, analysis_start_date):
    final_query = ' '
    query_sequence = 0
    for domain in domain_union:
        standard_query = render_query(entire_omop_table, provider_required, domain, feature_name, analysis_start_date)
        if query_sequence == 0:
            final_query += standard_query
        else:
            final_query += "\nUNION DISTINCT\n" + standard_query
        query_sequence += 1
    if provider_required != 1 and is_routine_care != 1:
        final_query = (f"SELECT DISTINCT person_id, src_id, 1 AS {feature_name} FROM (" + final_query +
                       f") GROUP BY person_id, src_id HAVING COUNT(omop_table_id) >= {instance_required}")

#loose up the provider, count if they have the same visit types (visit_concept_id) 2-3 times
    elif provider_required == 1:
        final_query = (f"SELECT DISTINCT person_id, src_id, 1 AS {feature_name} FROM (" + final_query +
                       f") GROUP BY person_id, src_id, visit_concept_id HAVING COUNT(event_date) >= {instance_required}")
    return final_query


def run_query(lookback_year):

    analysis_start_date = (
                datetime.strptime(ANALYSIS_END_DATE, '%Y-%m-%d') - relativedelta(years=lookback_year)).strftime(
        '%Y-%m-%d')

    client = bigquery.Client()

    loyalty_score_query = f"""SELECT DISTINCT FEATURE_NAME, DOMAIN_ID, ROUTINE_CARE_2 FROM `{OUTPUT_NAMESPACE}.mv_loyalty_score_concepts_with_standard_concepts`"""

    loyalty_concepts = client.query(loyalty_score_query).to_dataframe()
    loyalty_concepts = loyalty_concepts[~loyalty_concepts['DOMAIN_ID'].isin(['Metadata', 'Condition/Device'])]
    logging.info('Loyalty score standard OMOP concepts table is loaded from Google BigQuery.')

    distinct_features = loyalty_concepts.FEATURE_NAME.unique()

    for feature in distinct_features:
        logging.info(f'Query construction: feature: {feature}')
        instance_required = 1
        provider_required = 0
        entire_omop_table = 0

        if 'pname' in feature.lower():
            provider_required = 1
            if 'pname2' in feature.lower():
                instance_required = 2
            elif 'pname3' in feature.lower():
                instance_required = 3
        else:
            if 'use2' in feature.lower() or 'dx2' in feature.lower() or 'opt2' in feature.lower():
                instance_required = 2
            else:
                instance_required = 1
        domain_union = set(loyalty_concepts[loyalty_concepts.FEATURE_NAME == feature]['DOMAIN_ID'].unique())

#med use and dx should count all records in drug and diagnosis tables
        if 'med_use' in feature.lower():
            entire_omop_table = 1
            domain_union = set(['drug'])
        elif 'num_dx' in feature.lower():
            entire_omop_table = 1
            domain_union = set(['condition'])

        # print(f"feature name: {feature} \n "
        #       f"instance required: {instance_required} \n "
        #       f"provider required: {provider_required} \n "
        #       f"entire omop table: {entire_omop_table}")

        final_feature_query = fill_in_query(entire_omop_table, domain_union, provider_required, instance_required, feature,
                                            is_routine_care=0, analysis_start_date=analysis_start_date)
        with open(os.path.join(QUERY_OUTPUT_FOLDER, f'{feature.lower()}.sql'), 'w') as sql_file:
            sql_file.write(final_feature_query)
            logging.info(f'Query construction: feature: {feature.lower()}.sql is saved to {os.path.join(QUERY_OUTPUT_FOLDER)} ')

    # load json file
    logging.info(f'Query construction: Run routine care feature')
    routine_care_features = set(loyalty_concepts[loyalty_concepts.ROUTINE_CARE_2 == 1]['FEATURE_NAME'].unique())

    routine_care_query = ' '
    routine_query_sequence = 0
    for rf in routine_care_features:
        routine_care_domain_union = set(loyalty_concepts[(loyalty_concepts.ROUTINE_CARE_2 == 1) &
                                                         (loyalty_concepts.FEATURE_NAME == rf)]['DOMAIN_ID'].unique())
        if routine_query_sequence == 0:
            routine_care_query += fill_in_query(0, routine_care_domain_union, 0, 1, rf,
                                                is_routine_care = 1, analysis_start_date=analysis_start_date)
            routine_query_sequence += 1
        else:
            routine_care_query += "\nUNION DISTINCT\n"
            routine_care_query += fill_in_query(0, routine_care_domain_union, 0, 1, rf,
                                                is_routine_care = 1, analysis_start_date=analysis_start_date)
    routine_care_query = "SELECT DISTINCT person_id, src_id, 1 AS ROUTINE_CARE_2 FROM (" + routine_care_query + ")"
    with open(os.path.join(QUERY_OUTPUT_FOLDER, 'routine_care.sql'), 'w') as sql_file:
        sql_file.write(routine_care_query)
    logging.info(f'Query construction: routine_care.sql is saved in os.path.join(QUERY_OUTPUT_FOLDER')
