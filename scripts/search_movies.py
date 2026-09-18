import os
import psycopg2
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

print("Chargement du modèle d'embedding...")
model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

def search_similar_movies(query_text, top_k=5):
    """
    Recherche les films les plus proches sémantiquement de la requête.
    """
    # 1. Vectorisation de la requête utilisateur
    query_vector = model.encode(query_text).tolist()

    # 2. Requête SQL utilisant l'opérateur de distance cosinus (<=>) de pgvector
    search_query = """
        SELECT title, overview, release_date, vote_average, 
               1 - (embedding <=> %s::vector) AS similarity
        FROM movies
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector ASC
        LIMIT %s;
    """

    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute(search_query, (query_vector, query_vector, top_k))
        results = cur.fetchall()
    conn.close()

    return results

if __name__ == "__main__":
    # Test avec une recherche en langage naturel
    user_query = "un film qui parle de bipolarité"
    print(f"\nRecherche : '{user_query}'\n" + "-" * 50)

    matches = search_similar_movies(user_query, top_k=3)

    for i, (title, overview, release_date, vote_average, similarity) in enumerate(matches, 1):
        print(f"{i}. {title} (Score de similarité : {similarity:.2%})")
        print(f"   Note : {vote_average}/10 | Date : {release_date}")
        print(f"   Synopsis : {overview[:150]}...\n")