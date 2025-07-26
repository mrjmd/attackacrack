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

# --- THIS IS A FIX ---
# Make the entrypoint script executable
RUN chmod +x /app/entrypoint.sh
# --- END FIX ---

EXPOSE 5000

# --- THIS IS A FIX ---
# Set the entrypoint script as the command to run when the container starts.
ENTRYPOINT ["/app/entrypoint.sh"]
# --- END FIX ---