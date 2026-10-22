import pandas as pd
from utils import read_config
import logging
from google.cloud import bigquery
from jinja2 import Template
from datetime import datetime
from dateutil.relativedelta import relativedelta



def render_query(query, **kwargs):
    template = Template(query)
    rendered_query = template.render(**kwargs)
    return rendered_query


def execute_query(query, bq_client):
    df = bq_client.query(query).to_dataframe()
    return df


def run_cci_save_to_bq(client, query_path, context, bq_table_id, yr_gap):
    with open(query_path, 'r') as sql_file:
        sql_script = sql_file.read()
        sql_script = render_query(sql_script, **context)
        df = execute_query(sql_script, client)
        try:
            job_config = bigquery.LoadJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_APPEND
            )
            client.load_table_from_dataframe(
                df, bq_table_id, job_config=job_config
            ).result()
            print(f'{bq_table_id} table has been udpated with {yr_gap} years CCI data.')
        except Exception as e:
            print(f'Error {e}')

        
def main():
    config = read_config.load_config()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    print("Load config file...")

    namespaces = config['bigquery']['namespaces']
    OUTPUT_NAMESPACE = namespaces['output']
    UNIONED_EHR_NAMESPACE = namespaces['unioned_ehr']
    LOOK_BACK_YEARS = config['lookback_years']['LOOK_BACK_YEARS']
    min_look_back_year = min(LOOK_BACK_YEARS)
    max_look_back_year = max(LOOK_BACK_YEARS)

    cci_bq_table_id = f'{OUTPUT_NAMESPACE}.charlson_comorbidity_score_per_person'

    client = bigquery.Client()

    for yr in range(min_look_back_year, max_look_back_year+1):
        yr_gap = yr
        logging.info(f"The lookback year is {yr_gap}")

        analysis_end_date = datetime.strptime(config['omop_table_configs']['ANALYSIS_END_DATE'], '%Y-%m-%d')
        analysis_start_date = analysis_end_date + relativedelta(years=-yr_gap)

        context = {"year_gap": yr_gap,
            "start_date": analysis_start_date.strftime("%Y-%m-%d"),
            "end_date": analysis_end_date.strftime("%Y-%m-%d"),
            "UNIONED_EHR_NAMESPACE": UNIONED_EHR_NAMESPACE,
            "OUTPUT_NAMESPACE": OUTPUT_NAMESPACE,
            }
        
        run_cci_save_to_bq(client, 
                           './calculate_charlson_comorbidity_score.sql', 
                           context=context, 
                           bq_table_id=cci_bq_table_id,
                           yr_gap=yr_gap)
        logging.info(f"Processed lookback year {yr_gap}")

if __name__ == "__main__":
    main()
