import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def init_db(conn):
    """
    Initialise l'extension pgvector et la table movies.
    """
    with conn.cursor() as cur:
        # Activation de l'extension pgvector
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # Création de la table movies
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
    print("Base de données initialisée (Table 'movies' et extension 'pgvector' prêtes).")

def insert_movies(conn, df):
    """
    Insère ou met à jour les films dans PostgreSQL.
    """
    insert_query = """
        INSERT INTO movies (tmdb_id, title, original_title, overview, release_date, vote_average, popularity, poster_path)
        VALUES %s
        ON CONFLICT (tmdb_id) DO UPDATE SET
            title = EXCLUDED.title,
            overview = EXCLUDED.overview,
            vote_average = EXCLUDED.vote_average,
            popularity = EXCLUDED.popularity;
    """
    
    # Nettoyage des valeurs pour l'injection SQL
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
    print(f"{len(records)} films insérés/mis à jour dans PostgreSQL.")

if __name__ == "__main__":
    if not os.path.exists("data/sample_movies.csv"):
        print("Erreur : Fichier 'data/sample_movies.csv' introuvable. Exécute d'abord extract_tmdb.py.")
        exit(1)

    df_movies = pd.read_csv("data/sample_movies.csv")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        init_db(conn)
        insert_movies(conn, df_movies)
        conn.close()
        print("Ingestion terminée avec succès !")
    except Exception as e:
        print(f"Erreur lors de l'ingestion : {e}")