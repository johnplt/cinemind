FROM python:3.13-slim

# Installer les outils de compilation nécessaires (build-essential pour pyarrow / httptools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copier le binaire uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copier les fichiers de dépendances
COPY pyproject.toml uv.lock ./

# Synchroniser les dépendances (la version de Python système correspondra à >=3.13)
RUN uv sync --frozen --no-cache

# Copier le reste du code
COPY . .

# Lancer Streamlit
CMD [".venv/bin/streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]