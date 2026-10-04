import os
import psycopg2
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer
from scripts.rag_recommend import generate_rag_response

# --- CONFIGURATION DE LA PAGE STREAMLIT ---
st.set_page_config(
    page_title="CineMind - IA & Analytics Cinéma",
    page_icon="🎬",
    layout="wide"
)

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- CHARGEMENT DU MODÈLE EN SINGLETON ---
@st.cache_resource
def load_embedding_model():
    return SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# --- FONCTIONS UTILITAIRES BASE DE DONNÉES ---
def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("La variable d'environnement DATABASE_URL est introuvable ou non définie.")
    return psycopg2.connect(database_url)

def search_movies(query_text, top_k=5, min_vote=0.0):
    """
    Recherche sémantique avec gestion sécurisée de la connexion BDD.
    """
    embed_model = load_embedding_model()
    query_vector = embed_model.encode(query_text).tolist()
    search_query = """
        SELECT title, overview, release_date, vote_average, popularity,
               1 - (embedding <=> %s::vector) AS similarity
        FROM movies
        WHERE embedding IS NOT NULL AND vote_average >= %s
        ORDER BY embedding <=> %s::vector ASC
        LIMIT %s;
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(search_query, (query_vector, min_vote, query_vector, top_k))
            results = cur.fetchall()
        return results
    finally:
        if conn:
            conn.close()

@st.cache_data(ttl=3600)
def get_all_movies_df():
    """
    Récupère l'ensemble des films avec mise en cache (1h).
    """
    conn = None
    try:
        conn = get_db_connection()
        query = "SELECT title, overview, release_date, vote_average, popularity FROM movies WHERE overview IS NOT NULL;"
        df = pd.read_sql(query, conn)
        if not df.empty and "release_date" in df.columns:
            df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
            df["year"] = df["release_date"].dt.year
        return df
    finally:
        if conn:
            conn.close()

@st.cache_data(ttl=1800)
def get_movie_count():
    """
    Récupère le nombre total de films avec mise en cache (30 min).
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM movies WHERE overview IS NOT NULL;")
            count = cur.fetchone()[0]
        return count
    except Exception:
        return 0
    finally:
        if conn:
            conn.close()

# --- INTERFACE STREAMLIT ---
def main():

    st.title("🎬 CineMind — Intelligence Cinématographique & RAG")

    st.sidebar.header("⚙️ Configuration")
    navigation = st.sidebar.radio("Navigation", ["🔍 Recommandation RAG", "📊 Agent & Analytics Thématiques"])

    min_rating = st.sidebar.slider("Note minimale du film", 0.0, 10.0, 5.0, 0.5)

    st.sidebar.divider()
    st.sidebar.subheader("📊 État du Catalogue")
    
    movie_count = get_movie_count()
    st.sidebar.info(f"Base actuelle : **{movie_count:,} films**".replace(",", " "))
    st.sidebar.caption("🔄 **Pipeline ETL :** Catalogue synchronisé et enrichi automatiquement chaque semaine via TMDB.")

    # --- ONGLET 1 : RECOMMANDATION RAG ---
    if navigation == "🔍 Recommandation RAG":
        st.subheader("Trouvez votre prochain film grâce au RAG Sémantique")
        user_query = st.text_input("Exemple : 'Une quête épique mais menée par un groupe de héros qui ne se supportent pas du tout'", key="rag_input")

        if st.button("Lancer la recherche", type="primary"):
            if user_query.strip():
                with st.spinner("Recherche vectorielle dans PostgreSQL & Analyse Groq..."):
                    results = search_movies(user_query, top_k=3, min_vote=min_rating)

                    if results:
                        col1, col2 = st.columns([1, 1])

                        with col1:
                            st.markdown("### 🤖 Recommandation CineMind")
                            ai_response = generate_rag_response(user_query, results)
                            st.info(ai_response)

                        with col2:
                            st.markdown("### 🎯 Films correspondants (PostgreSQL)")
                            for movie in results:
                                # Gestion flexible 5 ou 6 colonnes
                                if len(movie) == 6:
                                    title, overview, release_date, vote_average, popularity, similarity = movie
                                else:
                                    title, overview, release_date, vote_average, similarity = movie

                                with st.expander(f"{title} ({vote_average}/10) — Similarité : {similarity:.1%}"):
                                    st.write(f"**Date de sortie :** {release_date}")
                                    st.write(f"**Synopsis :** {overview}")
                    else:
                        st.warning("Aucun film ne correspond aux critères sélectionnés.")

    # --- ONGLET 2 : AGENT & ANALYTICS THÉMATIQUES ---
    elif navigation == "📊 Agent & Analytics Thématiques":
        st.subheader("Analyses Sémantiques et Tendances du Cinéma")

        df_movies = get_all_movies_df()

        if not df_movies.empty:
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Films en base", len(df_movies))
            col_m2.metric("Note moyenne globale", f"{df_movies['vote_average'].mean():.2f}/10")
            col_m3.metric("Année la plus représentée", int(df_movies['year'].mode()[0]) if not df_movies['year'].dropna().empty else "N/A")

            st.divider()

            theme_query = st.text_input(
                "Analyse de tendance par thème (ex: 'Cinéma Action', 'Thriller & Suspense', 'Aventure & Fantasy')",
                value="Aventure & Fantasy"
            )

            st.caption(f"ℹ️ *Analyse calculée dynamiquement sur l'échantillon actuel de {len(df_movies)} films.*")

            if theme_query:
                embed_model = load_embedding_model()
                theme_vector = embed_model.encode(theme_query).tolist()

                # Requête optimisée avec limitation SQL pour soulager le serveur
                query_all = """
                    SELECT tmdb_id, title, release_date, vote_average,
                           1 - (embedding <=> %s::vector) AS theme_similarity
                    FROM movies
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector ASC
                    LIMIT 1000;
                """
                conn = None
                try:
                    conn = get_db_connection()
                    df_theme = pd.read_sql(query_all, conn, params=(theme_vector, theme_vector))
                finally:
                    if conn:
                        conn.close()

                if not df_theme.empty:
                    df_theme["release_date"] = pd.to_datetime(df_theme["release_date"], errors="coerce")
                    df_theme["year"] = df_theme["release_date"].dt.year

                    df_filtered = df_theme[df_theme["theme_similarity"] >= 0.35]

                    st.markdown(f"### Évolution du thème *'{theme_query}'* dans le cinéma")

                    if not df_filtered.empty:
                        df_trend = df_filtered.groupby("year").agg(
                            nombre_de_films=('tmdb_id', 'count'),
                            note_moyenne=('vote_average', 'mean')
                        ).reset_index()

                        fig = px.line(
                            df_trend, 
                            x="year", 
                            y="nombre_de_films",
                            markers=True,
                            title=f"Nombre de films traitant de '{theme_query}' par année",
                            labels={"year": "Année", "nombre_de_films": "Nombre de films"},
                            template="plotly_white"
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        st.markdown("#### Films les plus représentatifs du thème :")
                        st.dataframe(
                            df_filtered.sort_values(by="theme_similarity", ascending=False)[["title", "year", "vote_average", "theme_similarity"]].head(10),
                            use_container_width=True
                        )
                    else:
                        st.info(f"Aucun film dans votre échantillon actuel ne dépasse le seuil de similarité pour le thème '{theme_query}'.")
        else:
            st.warning("Aucune donnée disponible dans la base de données.")

if __name__ == "__main__":
    main()