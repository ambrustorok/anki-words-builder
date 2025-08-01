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

# Verify the installation of libsndfile
RUN ls -la /usr/lib/x86_64-linux-gnu | grep libsndfile

# Install dependencies
COPY pyproject.toml .
COPY uv.lock .
RUN pip install --user -e .

# Copy the source directory
COPY src/ src/
COPY languages.yml languages.yml

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu

# Command to run the application
CMD ["uv", "run", "src/app.py"]
