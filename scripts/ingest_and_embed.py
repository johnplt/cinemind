# ingest_and_embed.py
import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

def get_db_connection():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL manquante dans les variables d'environnement.")
    return psycopg2.connect(DATABASE_URL)

def init_db(conn):
    """
    Initialise l'extension pgvector, la table et s'assure que toutes les colonnes existent.
    """
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # 1. Création de la table de base si elle n'existe pas
        cur.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                tmdb_id INT UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                original_title VARCHAR(255),
                overview TEXT,
                release_date DATE,
                vote_average FLOAT,
                popularity FLOAT,
                poster_path VARCHAR(255),
                embedding vector(384),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 2. Sécurité : Ajoute les colonnes de suivi si la table existait déjà sous une ancienne version
        cur.execute("ALTER TABLE movies ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
        cur.execute("ALTER TABLE movies ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
        
        conn.commit()
    print("Base de données initialisée et schéma vérifié.")

def upsert_movies_metadata(conn, df):
    """
    Insère ou met à jour les métadonnées sans écraser les embeddings existants.
    """
    insert_query = """
        INSERT INTO movies (tmdb_id, title, original_title, overview, release_date, vote_average, popularity, poster_path)
        VALUES %s
        ON CONFLICT (tmdb_id) DO UPDATE SET
            title = EXCLUDED.title,
            overview = EXCLUDED.overview,
            vote_average = EXCLUDED.vote_average,
            popularity = EXCLUDED.popularity,
            poster_path = EXCLUDED.poster_path,
            updated_at = CURRENT_TIMESTAMP;
    """
    
    records = []
    for _, row in df.iterrows():
        release_date = row['release_date'] if pd.notna(row['release_date']) and row['release_date'] != '' else None
        records.append((
            int(row['tmdb_id']),
            row['title'],
            row['original_title'],
            row['overview'],
            release_date,
            float(row['vote_average']) if pd.notna(row['vote_average']) else None,
            float(row['popularity']) if pd.notna(row['popularity']) else None,
            row['poster_path']
        ))

    with conn.cursor() as cur:
        execute_values(cur, insert_query, records)
        conn.commit()
    print(f"{len(records)} métadonnées de films traitées dans PostgreSQL.")

def generate_missing_embeddings(conn):
    """
    Calcule les vector embeddings uniquement pour les films qui n'en ont pas (embedding IS NULL).
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT tmdb_id, title, overview 
            FROM movies 
            WHERE embedding IS NULL AND overview IS NOT NULL AND TRIM(overview) != '';
        """)
        pending_movies = cur.fetchall()

    if not pending_movies:
        print("Tous les films ont déjà leurs embeddings calculés !")
        return

    print(f"Génération des vector embeddings pour {len(pending_movies)} films...")
    
    print(f"Chargement du modèle '{MODEL_NAME}'...")
    model = SentenceTransformer(MODEL_NAME)
    
    tmdb_ids = [m[0] for m in pending_movies]
    texts_to_embed = [f"Titre: {m[1]}. Synopsis: {m[2]}" for m in pending_movies]
    
    # Encoder en batch
    embeddings = model.encode(texts_to_embed, show_progress_bar=True, batch_size=32)

    # Ordre des arguments aligné avec (m_id, emb) : ID d'abord (int), embedding en texte ensuite
    update_records = [
        (int(tmdb_id), str(embedding.tolist())) 
        for tmdb_id, embedding in zip(tmdb_ids, embeddings)
    ]

    # Cast explicite des colonnes virtuelles : m_id en integer, emb en vector
    update_query = """
        UPDATE movies AS m
        SET embedding = v.emb::vector,
            updated_at = CURRENT_TIMESTAMP
        FROM (VALUES %s) AS v(m_id, emb)
        WHERE m.tmdb_id = v.m_id::integer;
    """

    with conn.cursor() as cur:
        # Template spécifiant qu'il s'agit d'un int et d'une chaîne texte
        execute_values(cur, update_query, update_records, template="(%s::integer, %s::text)", page_size=100)
        conn.commit()

    print(f"Embeddings sauvegardés avec succès pour {len(pending_movies)} films.")

def run_pipeline(csv_path):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Fichier '{csv_path}' introuvable. Lance d'abord extract_tmdb.py.")

    df_movies = pd.read_csv(csv_path)
    
    conn = get_db_connection()
    try:
        init_db(conn)
        upsert_movies_metadata(conn, df_movies)
        generate_missing_embeddings(conn)
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "incremental"
    target_csv = f"data/extracted_movies_{mode}.csv"
    
    print(f"Lancement du pipeline d'ingestion/embedding pour le mode '{mode}'...")
    try:
        run_pipeline(target_csv)
        print("Pipeline exécuté avec succès !")
    except Exception as e:
        print(f"Erreur lors de l'exécution du pipeline : {e}")