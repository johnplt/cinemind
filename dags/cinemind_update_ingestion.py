from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email": ["johnplt@live.com"],  
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="CINEMIND_update_ingestion",
    default_args=default_args,
    description="Exécute le script cron_job.py de Cinemind chaque jeudi à 6h00",
    schedule="0 6 * * 1",  # Tous les jeudis à 06:00
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["CINEMIND", "PYTHON"],
) as dag:

    run_cron_job = BashOperator(
        task_id="run_cinemind_ingestion",
        bash_command="docker exec cinemind-app uv run scripts/cron_job.py",
    )