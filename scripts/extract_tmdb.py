import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"

def fetch_movies(pages=2, sort_by="popularity.desc", with_genres=None):
    """
    Récupère des films depuis TMDB selon des critères paramétrables.
    """
    if not TMDB_API_KEY or TMDB_API_KEY == "ta_cle_read_access_token_tmdb_ici":
        raise ValueError("Veuillez configurer TMDB_API_KEY dans votre fichier .env")

    movies = []
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {TMDB_API_KEY}"
    }

    print(f"Extraction des films ({pages} pages, tri: {sort_by})...")

    for page in range(1, pages + 1):
        url = f"{BASE_URL}/discover/movie?language=fr-FR&page={page}&sort_by={sort_by}"
        if with_genres:
            url += f"&with_genres={with_genres}"
            
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
                        "popularity": movie.get("popularity"),
                        "poster_path": movie.get("poster_path")
                    })
        else:
            print(f"Erreur HTTP {response.status_code} à la page {page}")

    df = pd.DataFrame(movies)
    # Suppression des doublons potentiels et des films sans résumé
    df = df.drop_duplicates(subset=["tmdb_id"]).dropna(subset=["overview"])
    print(f"Extraction réussie : {len(df)} films exploitables.")
    return df

if __name__ == "__main__":
    try:
        # Exemple : 3 pages (60 films) d'un mix populaire
        df_movies = fetch_movies(pages=3, sort_by="popularity.desc")
        
        os.makedirs("data", exist_ok=True)
        df_movies.to_csv("data/sample_movies.csv", index=False)
        print("Données sauvegardées dans 'data/sample_movies.csv'")
    except Exception as e:
        print(f"Erreur : {e}")