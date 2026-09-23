import os
import time
from datetime import datetime, timedelta
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"

def fetch_movies_from_api(url_params, pages=5):
    """
    Fonction générique pour requêter TMDB avec gestion du rate-limit.
    """
    if not TMDB_API_KEY:
        raise ValueError("Veuillez configurer TMDB_API_KEY dans votre fichier .env")

    movies = []
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {TMDB_API_KEY}"
    }

    for page in range(1, pages + 1):
        # Ajout de la page aux paramètres
        url_params["page"] = page
        
        response = requests.get(f"{BASE_URL}/discover/movie", headers=headers, params=url_params)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                break # Plus de résultats disponibles
                
            for movie in results:
                overview = movie.get("overview")
                if overview and len(overview.strip()) > 20:
                    movies.append({
                        "tmdb_id": movie.get("id"),
                        "title": movie.get("title"),
                        "original_title": movie.get("original_title"),
                        "overview": movie.get("overview"),
                        "release_date": movie.get("release_date"),
                        "vote_average": movie.get("vote_average"),
                        "vote_count": movie.get("vote_count"),
                        "popularity": movie.get("popularity"),
                        "poster_path": movie.get("poster_path"),
                        "genre_ids": str(movie.get("genre_ids", []))
                    })
        elif response.status_code == 429:
            print("Limitation de taux atteinte, pause de 2 secondes...")
            time.sleep(2)
        else:
            print(f"Erreur HTTP {response.status_code} à la page {page}")

    return movies

def extract_backfill(pages_per_strategy=50):
    """
    Mode Backfill : Récupère un catalogue profond de plusieurs milliers de films.
    """
    print(f"--- DÉMARRAGE MODE BACKFILL ({pages_per_strategy} pages/stratégie) ---")
    strategies = [
        {"sort_by": "popularity.desc", "vote_count.gte": 30},
        {"sort_by": "vote_average.desc", "vote_count.gte": 300},
        {"sort_by": "revenue.desc", "vote_count.gte": 50},
        {"sort_by": "primary_release_date.desc", "vote_count.gte": 20}
    ]

    all_movies = []
    for strat in strategies:
        params = {
            "language": "fr-FR",
            "include_adult": "false",
            **strat
        }
        print(f"Extraction : {strat['sort_by']}...")
        extracted = fetch_movies_from_api(params, pages=pages_per_strategy)
        all_movies.extend(extracted)

    return process_and_clean_df(all_movies)

def extract_incremental(days_back=14, pages=10):
    """
    Mode Incrémental : Récupère les nouveautés des X derniers jours (ex: pour le Cron hebdo).
    """
    print(f"--- DÉMARRAGE MODE INCRÉMENTAL (derniers {days_back} jours) ---")
    
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    params = {
        "language": "fr-FR",
        "include_adult": "false",
        "sort_by": "popularity.desc",
        "primary_release_date.gte": start_date,
        "vote_count.gte": 5
    }

    extracted = fetch_movies_from_api(params, pages=pages)
    return process_and_clean_df(extracted)

def process_and_clean_df(movies_list):
    """Nettoie et dédoublonne les données."""
    if not movies_list:
        print("Aucun film récupéré.")
        return pd.DataFrame()

    df = pd.DataFrame(movies_list)
    initial_count = len(df)
    df = df.drop_duplicates(subset=["tmdb_id"]).dropna(subset=["overview"])
    print(f"Extrait : {initial_count} -> {len(df)} films uniques exploitables.\n")
    return df

if __name__ == "__main__":
    import sys
    
    # Choix du mode via argument de ligne de commande : python extract_tmdb.py [backfill|incremental]
    mode = sys.argv[1] if len(sys.argv) > 1 else "incremental"
    
    if mode == "backfill":
        df_movies = extract_backfill(pages_per_strategy=30) # ~2000-2500 films uniques
    else:
        df_movies = extract_incremental(days_back=14, pages=10) # Nouveautés récentes

    if not df_movies.empty:
        os.makedirs("data", exist_ok=True)
        output_path = f"data/extracted_movies_{mode}.csv"
        df_movies.to_csv(output_path, index=False)
        print(f"Succès ! Données enregistrées dans '{output_path}'.")