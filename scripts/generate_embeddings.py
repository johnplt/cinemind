import os
import psycopg2
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Charger un modèle d'embedding multilingue très léger (~120 Mo en RAM)
print("Chargement du modèle d'embedding...")
model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

def add_vector_column(conn):
    """
    Ajoute la colonne 'embedding' de dimension 384 dans la table movies.
    """
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute("""
            ALTER TABLE movies 
            ADD COLUMN IF NOT EXISTS embedding vector(384);
        """)
        conn.commit()
    print("Colonne 'embedding' configurée (dimension 384).")

def process_and_store_embeddings(conn):
    """
    Récupère les films sans vector embedding, calcule le vecteur et le sauvegarde.
    """
    with conn.cursor() as cur:
        # Récupérer les films qui n'ont pas encore d'embedding
        cur.execute("SELECT tmdb_id, title, overview FROM movies WHERE embedding IS NULL AND overview IS NOT NULL;")
        movies = cur.fetchall()

        if not movies:
            print("Tous les films ont déjà leurs vector embeddings calculés !")
            return

        print(f"Génération des vector embeddings pour {len(movies)} films...")

        for tmdb_id, title, overview in movies:
            # Texte à vectoriser : combinaison du titre et du synopsis
            text_to_embed = f"Titre: {title}. Synopsis: {overview}"
            
            # Génération du vecteur (liste de 384 float)
            embedding = model.encode(text_to_embed).tolist()

            # Stockage dans PostgreSQL
            cur.execute(
                "UPDATE movies SET embedding = %s WHERE tmdb_id = %s;",
                (embedding, tmdb_id)
            )

        conn.commit()
        print(f"Vector embeddings générés et stockés pour {len(movies)} films !")

if __name__ == "__main__":
    try:
        conn = psycopg2.connect(DATABASE_URL)
        add_vector_column(conn)
        process_and_store_embeddings(conn)
        conn.close()
    except Exception as e:
        print(f"Erreur : {e}")