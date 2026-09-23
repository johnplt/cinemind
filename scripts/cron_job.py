# scripts/cron_job.py
import os
import sys

# S'assure que le dossier scripts est dans le path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_tmdb import extract_incremental
from ingest_and_embed import run_pipeline

def main():
    print("=== DÉMARRAGE DU CRON JOB HEBDOMADAIRE CINEMIND ===")
    
    # 1. Extraction des nouveautés des 14 derniers jours
    df_new = extract_incremental(days_back=14, pages=10)
    
    if df_new.empty:
        print("Aucun nouveau film à traiter cette semaine.")
        return

    os.makedirs("data", exist_ok=True)
    temp_csv = "data/extracted_movies_incremental.csv"
    df_new.to_csv(temp_csv, index=False)
    
    # 2. Ingestion + Embedding vectoriel
    run_pipeline(temp_csv)
    print("=== CRON JOB TERMINÉ AVEC SUCCÈS ===")

if __name__ == "__main__":
    main()