FROM python:3.12-slim

# Copy uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copie des fichiers de dépendances
COPY pyproject.toml uv.lock ./

# Installation des dépendances dans l'environnement virtuel (.venv)
RUN uv sync --frozen --no-cache

# Copie du reste du code
COPY . .

# Définition de l'entrée : on pointe directement sur l'exécutable streamlit de l'environnement virtuel
CMD [".venv/bin/streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]