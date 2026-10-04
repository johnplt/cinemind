# ingest_and_embed.py
import os
import sys
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
HF_TOKEN = os.getenv("HF_TOKEN")
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def get_db_connection():
    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL manquante dans les variables d'environnement."
        )

    # Sur Supabase, s'assurer que sslmode est géré correctement
    db_url = DATABASE_URL
    if "sslmode=" not in db_url:
        db_url += "?sslmode=require" if "?" not in db_url else "&sslmode=require"

    return psycopg2.connect(db_url)


def init_db(conn):
    """Initialise l'extension pgvector, la table, les index et la fonction RPC pour Supabase."""
    with conn.cursor() as cur:
        # 1. Activation de l'extension vector
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # 2. Création de la table movies si elle n'existe pas
        cur.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                tmdb_id INT PRIMARY KEY,
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

        # 3. Colonnes de suivi et index HNSW
        cur.execute(
            "ALTER TABLE movies ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP"
            " DEFAULT CURRENT_TIMESTAMP;"
        )
        cur.execute(
            "ALTER TABLE movies ADD COLUMN IF NOT EXISTS created_at TIMESTAMP"
            " DEFAULT CURRENT_TIMESTAMP;"
        )
        cur.execute("""
            CREATE INDEX IF NOT EXISTS movies_embedding_hnsw_idx 
            ON movies USING hnsw (embedding vector_cosine_ops);
        """)

        # 4. Fonction RPC pour les requêtes RAG
        cur.execute("""
            CREATE OR REPLACE FUNCTION match_movies (
              query_embedding vector(384),
              match_threshold float,
              match_count int
            )
            RETURNS TABLE (
              tmdb_id int,
              title varchar(255),
              original_title varchar(255),
              overview text,
              release_date date,
              vote_average float,
              popularity float,
              poster_path varchar(255),
              similarity float
            )
            LANGUAGE sql STABLE
            AS $$
              SELECT
                movies.tmdb_id,
                movies.title,
                movies.original_title,
                movies.overview,
                movies.release_date,
                movies.vote_average,
                movies.popularity,
                movies.poster_path,
                1 - (movies.embedding <=> query_embedding) AS similarity
              FROM movies
              WHERE 1 - (movies.embedding <=> query_embedding) > match_threshold
              ORDER BY movies.embedding <=> query_embedding
              LIMIT match_count;
            $$;
        """)

        conn.commit()
    print(
        "✅ Base de données initialisée (Schéma, Index HNSW et RPC"
        " match_movies vérifiés)."
    )


def upsert_movies_metadata(conn, df):
    """Insère ou met à jour les métadonnées sans écraser les embeddings existants."""
    insert_query = """
        INSERT INTO movies (tmdb_id, title, original_title, overview, release_date, vote_average, popularity, poster_path)
        VALUES %s
        ON CONFLICT (tmdb_id) DO UPDATE SET
            title = EXCLUDED.title,
            original_title = EXCLUDED.original_title,
            overview = EXCLUDED.overview,
            release_date = EXCLUDED.release_date,
            vote_average = EXCLUDED.vote_average,
            popularity = EXCLUDED.popularity,
            poster_path = EXCLUDED.poster_path,
            updated_at = CURRENT_TIMESTAMP;
    """

    records = []
    for _, row in df.iterrows():
        release_date = (
            row["release_date"]
            if pd.notna(row["release_date"]) and str(row["release_date"]).strip() != ""
            else None
        )
        records.append((
            int(row["tmdb_id"]),
            row["title"],
            row.get("original_title"),
            row.get("overview"),
            release_date,
            (
                float(row["vote_average"])
                if pd.notna(row.get("vote_average"))
                else None
            ),
            float(row["popularity"]) if pd.notna(row.get("popularity")) else None,
            row.get("poster_path"),
        ))

    with conn.cursor() as cur:
        execute_values(cur, insert_query, records)
        conn.commit()
    print(f"📦 {len(records)} métadonnées de films synchronisées dans PostgreSQL.")


def get_embeddings_via_api(client: InferenceClient, texts: list) -> np.ndarray:
    """Génère les embeddings via l'API Serverless de Hugging Face."""
    res = client.feature_extraction(text=texts, model=MODEL_NAME)
    arr = np.array(res)
    if arr.ndim == 3:
        arr = np.mean(arr, axis=1)
    return arr


def generate_missing_embeddings(conn):
    """Calcule les vector embeddings via l'API Hugging Face pour les films sans embedding."""
    if not HF_TOKEN:
        raise ValueError(
            "HF_TOKEN manquant dans les variables d'environnement."
        )

    client = InferenceClient(token=HF_TOKEN)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT tmdb_id, title, overview 
            FROM movies 
            WHERE embedding IS NULL AND overview IS NOT NULL AND TRIM(overview) != '';
        """)
        pending_movies = cur.fetchall()

    if not pending_movies:
        print("✨ Tous les films ont déjà leurs embeddings calculés !")
        return

    print(
        f"⚡ Génération API des embeddings pour {len(pending_movies)} films..."
    )

    batch_size = 32
    update_records = []

    for i in range(0, len(pending_movies), batch_size):
        batch = pending_movies[i : i + batch_size]
        tmdb_ids = [m[0] for m in batch]
        texts = [f"Titre: {m[1]}. Synopsis: {m[2]}" for m in batch]

        try:
            embeddings = get_embeddings_via_api(client, texts)
            for tmdb_id, emb in zip(tmdb_ids, embeddings):
                update_records.append((int(tmdb_id), str(emb.tolist())))
            print(
                f"  -> Batch {i // batch_size + 1}/{(len(pending_movies) - 1) // batch_size + 1} traité."
            )
        except Exception as e:
            print(f"❌ Erreur lors de l'encodage du batch : {e}")
            continue

    if not update_records:
        print("Aucun embedding n'a pu être généré.")
        return

    update_query = """
        UPDATE movies AS m
        SET embedding = v.emb::vector,
            updated_at = CURRENT_TIMESTAMP
        FROM (VALUES %s) AS v(m_id, emb)
        WHERE m.tmdb_id = v.m_id::integer;
    """

    with conn.cursor() as cur:
        execute_values(
            cur,
            update_query,
            update_records,
            template="(%s::integer, %s::text)",
            page_size=100,
        )
        conn.commit()

    print(
        f"✅ Embeddings sauvegardés avec succès pour {len(update_records)} films."
    )


def run_pipeline(csv_path):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Fichier '{csv_path}' introuvable. Lance d'abord extract_tmdb.py."
        )

    df_movies = pd.read_csv(csv_path)

    conn = get_db_connection()
    try:
        init_db(conn)
        upsert_movies_metadata(conn, df_movies)
        generate_missing_embeddings(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "incremental"
    target_csv = f"data/extracted_movies_{mode}.csv"

    print(
        f"🚀 Lancement du pipeline d'ingestion/embedding (mode '{mode}')..."
    )
    try:
        run_pipeline(target_csv)
        print("🎉 Pipeline exécuté avec succès !")
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution du pipeline : {e}")