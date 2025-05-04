#!/bin/bash
# Setup script for bully-ring election demonstration

echo "Setting up the distributed election algorithm demonstration..."

# Create app directory
mkdir -p app

# Copy node implementation to app directory
cp election_algorithm_code.py app/node.py
chmod +x app/node.py

# Build and start containers
echo "Building and starting Docker containers..."
docker-compose down
docker-compose build
docker-compose up -d

# Check if containers are running
echo "Checking container status:"
docker-compose ps

echo "Setup complete! Now run ./election_cli.py to start the demonstration."