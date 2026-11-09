from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator


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

    run_cron_job = DockerOperator(
        task_id="run_cinemind_ingestion",
        image="cinemind-app:latest",  # Le nom ou le tag de ton image locale/distante
        api_version="auto",
        auto_remove='force',  # Supprime le conteneur après exécution
        command="uv run scripts/cron_job.py",
        docker_url="unix://var/run/docker.sock",
        network_mode="app-network",  # Pour garder l'accès au réseau de tes autres services
        mount_tmp_dir=False,
        environment={
            "TMDB_API_KEY": "{{ var.value.TMDB_API_KEY }}",
            "HF_TOKEN": "{{ var.value.HF_TOKEN }}"
        }
    )