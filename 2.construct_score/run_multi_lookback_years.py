from construct_cohort import create_cohort
from construct_query import run_query
from run_cohort import extract_cohort
import pandas as pd
import logging
from google.cloud import bigquery
from utils import read_config

config = read_config.load_config()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

OUTPUT_NAMESPACE = config['bigquery']['namespaces']['output']
COHORT_TABLE = config['analysis_configs']['COHORT_TABLE']


client = bigquery.Client()

combined_df = pd.DataFrame()
LOOK_BACK_YEARS = config['lookback_years']['LOOK_BACK_YEARS']
min_look_back_year = min(LOOK_BACK_YEARS)
max_look_back_year = max(LOOK_BACK_YEARS)

logging.info(f"The lookback years are {LOOK_BACK_YEARS}")

for lookback_year in LOOK_BACK_YEARS:
    logging.info(f"Lookback year: {lookback_year} years")
    logging.info("Update query for this lookback year")
    run_query(lookback_year)
    logging.info("Extracting feature cohorts into csv files")
    extract_cohort()
    logging.info("Combine csv files and merge into person dataframe")
    cohort = create_cohort(lookback_year)
    logging.info(f"Entire cohort size is {cohort.shape} for lookback year {lookback_year} years")
    logging.info("Combine all lookback years into a single dataframe")
    combined_df = pd.concat([combined_df, cohort])
    logging.info(f'Done with year {lookback_year}')
combined_df.to_csv('combined_data.csv', index=False)

client.load_table_from_dataframe(
    dataframe=combined_df,
    destination=f"{OUTPUT_NAMESPACE}.{COHORT_TABLE}",
    job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE"),
).result()
logging.info(
    'Combined data with lookback years %s-%s is saved in BigQuery table %s.%s',
    min_look_back_year,
    max_look_back_year,
    OUTPUT_NAMESPACE,
    COHORT_TABLE,
)
