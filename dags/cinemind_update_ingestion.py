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
        # On appelle directement Docker en ligne de commande avec injection des variables d'environnement Airflow
        bash_command="""
            docker run --rm \
              --network app-network \
              -e TMDB_API_KEY="{{ var.value.TMDB_API_KEY }}" \
              -e HF_TOKEN="{{ var.value.HF_TOKEN }}" \
              -e DATABASE_URL="postgresql://{{ var.value.CINEMIND_DB_USER }}:{{ var.value.CINEMIND_DB_PASSWORD }}@{{ var.value.CINEMIND_DB_HOST }}:5432/{{ var.value.CINEMIND_DB_NAME }}" \
              cinemind-app:latest \
              uv run scripts/cron_job.py
        """
    )