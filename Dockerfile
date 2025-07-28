# Dockerfile

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh

EXPOSE 5000

# --- REMOVED: ENTRYPOINT instruction ---
# The startup command will now be specified in docker-compose.yml for each service individually.
