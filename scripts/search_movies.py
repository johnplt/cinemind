# search_movies.py
import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
import numpy as np
import psycopg2

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
HF_TOKEN = os.getenv("HF_TOKEN")
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def get_db_connection():
    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL manquante dans les variables d'environnement."
        )

    db_url = DATABASE_URL
    if "sslmode=" not in db_url:
        db_url += "?sslmode=require" if "?" not in db_url else "&sslmode=require"

    return psycopg2.connect(db_url)


def get_query_embedding(query_text: str) -> list:
    """Génère l'embedding vectoriel de la requête via l'API Serverless Hugging Face."""
    if not HF_TOKEN:
        raise ValueError(
            "HF_TOKEN manquant dans les variables d'environnement."
        )

    client = InferenceClient(token=HF_TOKEN)
    res = client.feature_extraction(text=query_text, model=MODEL_NAME)

    arr = np.array(res)
    if arr.ndim == 3:
        arr = np.mean(arr, axis=1)

    # Récupération du vecteur 1D sous forme de liste standard
    return arr.squeeze().tolist()


def search_similar_movies(query_text: str, top_k: int = 5) -> list:
    """Recherche les films les plus proches sémantiquement de la requête."""
    # 1. Vectorisation de la requête utilisateur via API
    query_vector = get_query_embedding(query_text)

    # 2. Requête SQL utilisant la fonction RPC ou la distance cosinus pgvector (<=>)
    search_query = """
        SELECT title, overview, release_date, vote_average, 
               1 - (embedding <=> %s::vector) AS similarity
        FROM movies
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector ASC
        LIMIT %s;
    """

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                search_query, (str(query_vector), str(query_vector), top_k)
            )
            results = cur.fetchall()
    finally:
        conn.close()

    return results


if __name__ == "__main__":
    user_query = "un film qui parle de bipolarité"
    print(f"\nRecherche : '{user_query}'\n" + "-" * 50)

    matches = search_similar_movies(user_query, top_k=3)

    for i, (title, overview, release_date, vote_average, similarity) in enumerate(
        matches, 1
    ):
        print(f"{i}. {title} (Score de similarité : {similarity:.2%})")
        print(f"   Note : {vote_average}/10 | Date : {release_date}")
        overview_text = overview if overview else "Pas de synopsis disponible."
        print(f"   Synopsis : {overview_text[:150]}...\n")