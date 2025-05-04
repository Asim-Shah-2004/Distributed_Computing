#!/bin/bash

# Function to make requests to specified host
test_endpoint() {
  local host=$1
  local method=$2
  local num_requests=${3:-10}
  
  echo "==================================================="
  echo "Testing $method load balancing at $host"
  echo "==================================================="
  
  for i in $(seq 1 $num_requests); do
    echo -n "Request $i: "
    curl -s -H "Host: $host" http://localhost | grep -o "Request served by: [^ ]*" | cut -d ":" -f2
    sleep 0.5
  done
  echo ""
}

# Test static round-robin load balancing
test_endpoint "static.example.com" "Static Round-Robin" 15

# Test static IP hash load balancing (should go to same server)
test_endpoint "static-iphash.example.com" "Static IP Hash" 5

# Test dynamic least connections
test_endpoint "dynamic.example.com" "Dynamic Least Connections" 15

# Test dynamic weighted load balancing
test_endpoint "dynamic-weighted.example.com" "Dynamic Weighted" 15

# Generate some load on app1 to demonstrate least connections
echo "Generating load on app1 to demonstrate least connections effect..."
docker exec -d load-balancing-demo_app1_1 sh -c "for i in {1..10}; do curl -s http://localhost:3000/ > /dev/null & done"

echo "Now testing least connections again (should favor app2 and app3)..."
test_endpoint "dynamic.example.com" "Dynamic Least Connections with Load" 10

echo "Testing complete!"