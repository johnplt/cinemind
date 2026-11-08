from datetime import datetime
from airflow import DAG
from airflow.operators.empty import EmptyOperator

with DAG(
    dag_id="test_git_sync",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["test", "git-sync"],
) as dag:
    
    start = EmptyOperator(task_id="start")