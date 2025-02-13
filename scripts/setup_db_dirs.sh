#!/bin/bash

# Base directory for PostgreSQL
POSTGRES_DIR="/home/pi/docker/postgres"

# Create PostgreSQL directories
echo "Creating PostgreSQL directories..."
mkdir -p "${POSTGRES_DIR}/data"
mkdir -p "${POSTGRES_DIR}/files"

# Set appropriate permissions
echo "Setting permissions..."
chown -R pi:pi "${POSTGRES_DIR}"
chmod -R 755 "${POSTGRES_DIR}"

# Print summary
echo -e "\nSetup completed!"
echo "Directories created:"
echo "- ${POSTGRES_DIR}/data"
echo "- ${POSTGRES_DIR}/files"
echo -e "\nYou can now start your containers with docker-compose up -d"