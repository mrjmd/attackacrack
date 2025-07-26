# Dockerfile

# Start with an official Python base image.
# Using a specific version ensures a consistent environment.
FROM python:3.11-slim

# Set the working directory inside the container.
# All subsequent commands will run from this directory.
WORKDIR /app

# Set environment variables to prevent Python from writing .pyc files
# and to ensure output is sent straight to the terminal without buffering.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies that might be needed by Python packages.
# Added 'git' for handling any potential git-based dependencies.
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy the dependency files into the container.
COPY requirements.txt pyproject.toml ./

# Install the Python dependencies.
# We install from requirements.txt to ensure the versions are locked.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application code into the container.
# This will be done after installing dependencies to leverage Docker's caching.
COPY . .

# Expose the port that the application will run on.
# We'll configure Gunicorn to run on this port.
EXPOSE 5000

# The command to run when the container starts.
# This will be overridden later by our Gunicorn command, but it's good practice
# to have a default command for running the development server.
CMD ["flask", "run", "--host=0.0.0.0"]