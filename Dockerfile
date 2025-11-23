# Use Python base image
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set working directory
WORKDIR /app

# Install system dependencies using apt
RUN apt-get update && apt-get install -y \
    libffi-dev \
    libpq-dev \
    build-essential \
    ffmpeg \
    libsndfile1 \
    libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY pyproject.toml .
COPY uv.lock .
RUN uv pip install --system -e .

# Copy the source directory
COPY src/ src/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Command to run the application
CMD ["uv", "run", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8100"]
