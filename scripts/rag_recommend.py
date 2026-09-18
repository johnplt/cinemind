import os
import psycopg2
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

print("Chargement du modèle d'embedding...")
embed_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

def search_movies(query_text, top_k=3):
    """
    Recherche sémantique des films dans PostgreSQL.
    """
    query_vector = embed_model.encode(query_text).tolist()
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

def generate_rag_response(user_query, retrieved_movies):
    """
    Génère une réponse structurée via l'API Groq (Llama 3).
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY est manquante dans le fichier .env")

    client = Groq(api_key=GROQ_API_KEY)

    # Construction du contexte pour le LLM
    context = ""
    for i, (title, overview, release_date, vote_average, similarity) in enumerate(retrieved_movies, 1):
        context += f"\n--- Film {i} ---\nTitre: {title}\nNote: {vote_average}/10\nSynopsis: {overview}\nSimilarity Score: {similarity:.2f}\n"

    system_prompt = (
        "Tu es CineMind, un assistant expert en recommandations de films. "
        "Ton rôle est d'analyser les films fournis en contexte et de recommander "
        "à l'utilisateur le ou les meilleurs choix selon sa recherche. "
        "Sois concis, enthousiaste et argumente en te basant sur les synopsis fournis. "
        "Si les films du contexte ne semblent pas correspondre à la demande, indique-le poliment."
    )

    user_prompt = f"Demande de l'utilisateur : '{user_query}'\n\nFilms trouvés en base :\n{context}"

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=500
    )

    return response.choices[0].message.content

if __name__ == "__main__":
    print("\n Welcome to CineMind RAG System!")
    print("-----------------------------------")
    
    # Prise en compte dynamique de la requête
    user_query = input("\nQue cherchez-vous comme film aujourd'hui ? : ")
    
    if user_query.strip():
        print("\n[1/2] Recherche sémantique dans PostgreSQL...")
        movies = search_movies(user_query, top_k=3)
        
        print("[2/2] Génération de la recommandation via Groq (Llama 3)...")
        recommendation = generate_rag_response(user_query, movies)
        
        print("\n Recommandation CineMind :\n")
        print(recommendation)