import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"

def fetch_movies_by_strategy(sort_by="popularity.desc", pages=5, vote_count_gte=100):
    """
    Récupère des films depuis TMDB selon une stratégie de tri spécifique.
    """
    if not TMDB_API_KEY:
        raise ValueError("Veuillez configurer TMDB_API_KEY dans votre fichier .env")

    movies = []
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {TMDB_API_KEY}"
    }

    for page in range(1, pages + 1):
        url = (
            f"{BASE_URL}/discover/movie"
            f"?language=fr-FR&page={page}&sort_by={sort_by}"
            f"&vote_count.gte={vote_count_gte}"
            f"&include_adult=false"
        )
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            for movie in data.get("results", []):
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
            print(f"Erreur HTTP {response.status_code} à la page {page} ({sort_by})")

    return movies

def build_full_dataset(target_pages_per_strategy=15):
    """
    Combine plusieurs stratégies de tri pour maximiser la diversité du catalogue :
    1. Les films les plus populaires
    2. Les films les mieux notés (minimum 500 votes)
    3. Les plus gros succès au box-office (revenue.desc)
    """
    strategies = [
        {"sort_by": "popularity.desc", "vote_count_gte": 50},
        {"sort_by": "vote_average.desc", "vote_count_gte": 500},
        {"sort_by": "revenue.desc", "vote_count_gte": 100},
    ]

    all_movies = []
    for strat in strategies:
        print(f"Extraction via stratégie : {strat['sort_by']} ({target_pages_per_strategy} pages)...")
        extracted = fetch_movies_by_strategy(
            sort_by=strat["sort_by"],
            pages=target_pages_per_strategy,
            vote_count_gte=strat["vote_count_gte"]
        )
        all_movies.extend(extracted)

    df = pd.DataFrame(all_movies)
    
    # Dédoublonnage sur l'ID TMDB et nettoyage des résumés vides
    initial_count = len(df)
    df = df.drop_duplicates(subset=["tmdb_id"]).dropna(subset=["overview"])
    print(f"\nTotal extrait : {initial_count} -> {len(df)} films uniques exploitables.")
    return df

if __name__ == "__main__":
    try:
        # 15 pages * 20 films * 3 stratégies = ~900 films potentiels (env. 700-800 uniques)
        df_movies = build_full_dataset(target_pages_per_strategy=15)
        
        os.makedirs("data", exist_ok=True)
        output_path = "data/sample_movies.csv"
        df_movies.to_csv(output_path, index=False)
        print(f"Données enregistrées avec succès dans '{output_path}' !")
    except Exception as e:
        print(f"Erreur lors de l'extraction : {e}")