#!/bin/bash

# Check if algorithm is provided
ALGORITHM=${1:-lamport}  # Default to lamport if not provided

# Validate algorithm
if [[ "$ALGORITHM" != "lamport" && "$ALGORITHM" != "vector" ]]; then
    echo "Invalid algorithm. Choose 'lamport' or 'vector'"
    exit 1
fi

echo "Running experiment with $ALGORITHM clock algorithm..."

# Create logs directory if it doesn't exist
mkdir -p logs

# Clean any previous logs
rm -f logs/*.json logs/*.txt logs/*.png

# Export algorithm as environment variable for docker-compose
export ALGORITHM

# Build and run the containers
docker-compose build
docker-compose up -d

echo "Experiment is running... (waiting for completion)"

# Wait for logs to be generated (up to 60 seconds)
MAX_WAIT=60
for ((i=1; i<=MAX_WAIT; i++)); do
    # Check if all log files exist (for all 3 nodes)
    if [ -f "logs/node0_${ALGORITHM}_log.json" ] && \
       [ -f "logs/node1_${ALGORITHM}_log.json" ] && \
       [ -f "logs/node2_${ALGORITHM}_log.json" ]; then
        echo "All log files generated. Stopping containers..."
        break
    fi
    
    # If we've waited the maximum time, exit loop
    if [ $i -eq $MAX_WAIT ]; then
        echo "Timeout waiting for log files."
    fi
    
    # Wait 1 second before checking again
    sleep 1
    echo -n "."
done

# Stop containers
docker-compose down

# Run the analysis
echo "Analyzing results..."
python3 event_analyzer.py --algorithm $ALGORITHM --nodes 3

echo "Experiment complete!"
echo "Results are in the 'logs' directory:"
echo "  - event_order.txt: Order of events with causality analysis"
echo "  - event_graph.png: Visualization of event relationships"