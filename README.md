# CineMind — Moteur de Recommandation de Films par Recherche Vectorielle (RAG)

![Texte alternatif](docs/images/cinemind_image.jpg)

CineMind est une application web interactive qui permet de recommander des films en fonction de requêtes en langage naturel (ex: *"un film de science-fiction sombre avec une fin inattendue"*). 

Le projet s'appuie sur une approche RAG (Retrieval-Augmented Generation) combinant **PostgreSQL + pgvector** pour la recherche de similarité vectorielle et **Streamlit** pour la présentation graphique.

---

## Architecture du Projet

L'application est déployée sur **Railway** au sein d'un projet consolidé pour garantir une communication réseau interne sécurisée via `.railway.internal`.

```text
               +-------------------------------------------+
               |              Railway Project              |
               |                                           |
               |  +------------------+  .railway.internal  |
User Request ->|  |   Streamlit Web  | ----------------->  |
               |  |  (cinemind-web)  |    Port: 5432       |
               |  +------------------+                     |
               |                               |           |
               |                               v           |
               |                    +--------------------+ |
               |                    | PostgreSQL + Vector| |
               |                    +--------------------+ |
               +-------------------------------------------+
```

## Structure du Dépôt

```text
├── app.py
├── data
│   └── sample_movies.csv
├── docker-compose.yaml
├── DockerFile
├── pyproject.toml
├── README.md
├── scripts
│   ├── extract_tmdb.py
│   ├── generate_embeddings.py
│   ├── ingest_to_db.py
│   ├── rag_recommend.py
│   ├── search_movies.py
│   └── test_groq.py
└── uv.lock
```

## Spécifications Techniques
- Base de données : PostgreSQL avec extension pgvector.

- Modèle d'embedding : Sentence-Transformers (all-MiniLM-L6-v2) — Vecteurs de 384 dimensions.

- Indexation : Indexation HNSW (vector_cosine_ops) pour optimiser la recherche par distance cosinus.

- Interface : Streamlit.

## Guide de Déploiement / Reproduire le Projet
Suivre ces étapes pour installer et exécuter CineMind sur son propre environnement.

1. Pré-requis
    - Python 3.10+

    - Un compte Railway (ou un serveur PostgreSQL local avec l'extension pgvector)

    - Git/Github

2. Installation locale (avec uv)

```bash
# Cloner le dépôt
git clone url
cd cinemind

# Créer l'environnement virtuel et installer les dépendances avec uv
uv sync
```


3. Configuration de la Base de Données sur Railway

    1. Créer un nouveau projet sur Railway.

    2. Ajouter un service PostgreSQL.

    3. Dans l'onglet Query du service PostgreSQL sur Railway, exécuter le script schema.sql suivant :

```sql
-- 1. Activation de l'extension vector
CREATE EXTENSION IF NOT EXISTS vector;
-- 2. Création de la table movies
CREATE TABLE IF NOT EXISTS movies (
    tmdb_id INTEGER PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    original_title VARCHAR(255),
    overview TEXT,
    release_date DATE,
    vote_average DOUBLE PRECISION,
    popularity DOUBLE PRECISION,
    poster_path VARCHAR(255),
    embedding vector(384),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
-- 3. Indexation HNSW
CREATE INDEX IF NOT EXISTS movies_embedding_hnsw_idx 
ON movies 
USING hnsw (embedding vector_cosine_ops);
```

4. Ingestion des Données

    Pour charger le dataset et générer les vectorisations depuis la  machine locale vers la base Railway :

    1. Dans le service PostgreSQL sur Railway, aller dans Settings > Networking > Public Networking et cliquer sur Add Public Access.

    2. Redéploiyer le service PostgreSQL si nécessaire pour afficher l'URL publique.

    3. Copier l'URL de connexion publique (DATABASE_PUBLIC_URL).

    4. Créer ou compléter le fichier .env à la racine du projet :

    ```text
    DATABASE_URL=postgresql://postgres:PASSWORD@REGION.proxyrlwy.   net:PORT/railway  
    ```

    5. Exécuter le script scripts/extract_tmdb.py pour l'extraction des données

    6. Exécuter le script scripts/ingest_to_db.py pour l'ingestion des données

5. Déploiement de l'Application Streamlit sur Railway

    Dans le même projet Railway, cliquer sur + New > GitHub Repo et sélectionner le dépôt.

    1. Dans les Variables du service Streamlit, connecter la base de données interne :

        - Variable : DATABASE_URL

        - Valeur : ${{Postgres.DATABASE_URL}} (ou ${{Postgres.DATABASE_PRIVATE_URL}})

    2. Ajustr la commande de démarrage (Start Command) dans Settings si nécessaire :

    ```bash
    streamlit run app.py --server.port $PORT --server.address 0.0.0.0
    ```

## Licence
Projet sous licence MIT. Libre réutilisation et modification.