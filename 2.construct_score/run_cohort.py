from google.cloud import bigquery
import os
import glob
from utils import read_config
import logging

config = read_config.load_config()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

QUERY_OUTPUT_FOLDER = config['folders']['QUERY_OUTPUT_FOLDER']
CSV_OUTPUT_FOLDER = config['folders']['CSV_OUTPUT_FOLDER']

client = bigquery.Client()


def extract_cohort():
    sql_files = glob.glob(QUERY_OUTPUT_FOLDER + '/*.sql')
    for sql_file in sql_files:
        file_name = sql_file.split('/')[-1].split('.')[0]
        logging.info(f"Cohort csv file extraction: Start extracting {file_name} feature cohort")
        with open(os.path.join(sql_file), 'r') as f:
            sql = f.read()
            data = client.query(sql).to_dataframe()
            data.to_csv(os.path.join(CSV_OUTPUT_FOLDER, file_name + '.csv'), index=False)
            logging.info(f"Saved {file_name}.csv to {os.path.join(CSV_OUTPUT_FOLDER)}")
