FROM python:3.12-slim

# Installer les outils de base si besoin
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copier le binaire uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copier les fichiers de dépendances
COPY pyproject.toml uv.lock ./

# Forcer uv à utiliser l'interpréteur python3.12 du système sans en télécharger un autre
RUN uv sync --frozen --no-cache --python python3.12

# Copier le reste du code
COPY . .

# Lancer streamlit
CMD [".venv/bin/streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]