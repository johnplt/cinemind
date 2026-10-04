# rag_recommend.py
import os
from dotenv import load_dotenv
from groq import Groq
from huggingface_hub import InferenceClient
import numpy as np
import psycopg2

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
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
    """Génère l'embedding de la requête utilisateur via l'API Hugging Face."""
    if not HF_TOKEN:
        raise ValueError(
            "HF_TOKEN manquant dans les variables d'environnement."
        )

    client = InferenceClient(token=HF_TOKEN)
    res = client.feature_extraction(text=query_text, model=MODEL_NAME)

    arr = np.array(res)
    if arr.ndim == 2:
        arr = np.mean(arr, axis=0)

    return arr.tolist()


def search_movies(query_text: str, top_k: int = 3):
    """Recherche sémantique des films dans PostgreSQL/Supabase via match_movies."""
    query_vector = get_query_embedding(query_text)

    search_query = """
        SELECT title, overview, release_date, vote_average, similarity
        FROM match_movies(%s::vector, 0.0, %s);
    """

    conn = get_db_connection()
    with conn.cursor() as cur:
        vector_str = str(query_vector)
        cur.execute(search_query, (vector_str, top_k))
        results = cur.fetchall()
    conn.close()

    return results


import os
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def generate_rag_response(user_query: str, retrieved_movies: list) -> str:
    """
    Génère une réponse structurée via l'API Groq avec gestion du fallback de modèles.
    """
    if not GROQ_API_KEY:
        return "Clé API Groq manquante dans l'environnement."

    client = Groq(api_key=GROQ_API_KEY)

    # Construction du contexte pour le LLM
    context = ""
    for i, item in enumerate(retrieved_movies, 1):
        # S'adapte automatiquement que tuple contienne 5 ou 6 éléments
        if len(item) == 6:
            title, overview, release_date, vote_average, popularity, similarity = item
        else:
            title, overview, release_date, vote_average, similarity = item

        context += (
            f"\n--- Film {i} ---\n"
            f"Titre: {title}\n"
            f"Date de sortie: {release_date}\n"
            f"Note: {vote_average}/10\n"
            f"Score de similarité: {similarity:.2f}\n"
            f"Synopsis: {overview}\n"
        )

    system_prompt = (
        "Tu es CineMind, un assistant cinématographique expert. "
        "Analyse les films du contexte et recommande le meilleur choix. "
        "Sois structuré, synthétique et captivant. "
        "Veille à toujours conclure clairement ta réponse."
    )
    user_prompt = f"Demande : '{user_query}'\n\nContexte :\n{context}"

    candidate_models = [
        "openai/gpt-oss-20b",
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768"
    ]

    for model_name in candidate_models:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1200  # <--- Augmenté de 600 à 1200 pour éviter toute coupure
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ Échec du modèle {model_name}: {e}")
            continue

    return "Désolé, le service d'analyse IA est temporairement indisponible."


if __name__ == "__main__":
    print("\n🎬 Welcome to CineMind RAG System!")
    print("-----------------------------------")

    user_query = input("\nQue cherchez-vous comme film aujourd'hui ? : ")

    if user_query.strip():
        try:
            print("\n[1/2] Recherche sémantique dans Supabase...")
            movies = search_movies(user_query, top_k=3)

            print("[2/2] Génération de la recommandation via Groq (Llama 3)...")
            recommendation = generate_rag_response(user_query, movies)

            print("\n🍿 Recommandation CineMind :\n")
            print(recommendation)
        except Exception as e:
            print(f"❌ Erreur lors de l'exécution du RAG : {e}")