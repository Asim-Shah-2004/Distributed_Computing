#!/bin/bash

# Create logs directory if it doesn't exist
mkdir -p logs

# Clean up old logs
rm -f logs/*.log
rm -f logs/*.txt

# Run with specified algorithm or default to bully
ALGORITHM=${1:-bully}

if [ "$ALGORITHM" != "bully" ] && [ "$ALGORITHM" != "ring" ]; then
  echo "Error: Algorithm must be either 'bully' or 'ring'"
  echo "Usage: ./run_election.sh [bully|ring]"
  exit 1
fi

echo "Running election with $ALGORITHM algorithm..."

# Run the Docker Compose setup with the specified algorithm
ALGORITHM=$ALGORITHM docker-compose up --build

# Display the results
echo ""
echo "Election complete! Results:"
cat logs/report_${ALGORITHM}.txt