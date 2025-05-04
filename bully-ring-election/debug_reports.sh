#!/bin/bash

echo "========== REPORT DEBUGGING TOOL =========="
echo "This script will help identify why reports aren't generating properly."
echo

# Check if Docker is running
echo "1. Checking Docker status:"
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is not running or not accessible!"
  exit 1
else
  echo "Docker is running."
fi

# Check container status
echo
echo "2. Checking container status:"
docker-compose ps

# Check app directory
echo
echo "3. Checking local app directory structure:"
mkdir -p app
ls -la ./app

# Check for report files inside containers
echo
echo "4. Checking for report files inside containers:"
for i in {0..6}; do
  echo "--- Node $i ---"
  docker exec -it node-$i ls -la /app/ 2>/dev/null | grep report || echo "No report files found"
done

# Check volume mount permissions
echo
echo "5. Checking volume mount permissions:"
for i in {0..6}; do
  echo "--- Node $i ---"
  docker exec -it node-$i stat -c "%A %U:%G" /app/ 2>/dev/null || echo "Could not check permissions"
done

# Generate test file in container
echo
echo "6. Testing file write from container to host volume:"
docker exec -it node-0 bash -c "echo 'test file content' > /app/test_write.txt" 2>/dev/null
if [ -f "./app/test_write.txt" ]; then
  echo "SUCCESS: Container can write to host volume."
  cat ./app/test_write.txt
else
  echo "ERROR: Container could not write to host volume!"
fi

# Manual report copy
echo
echo "7. Attempting manual copy of reports from containers:"
for i in {0..6}; do
  docker cp node-$i:/app/report_$i.json ./app/ 2>/dev/null
  if [ -f "./app/report_$i.json" ]; then
    echo "Successfully copied report_$i.json from container node-$i"
  else
    echo "Could not find or copy report_$i.json from container node-$i"
  fi
done

# Check copied reports
echo
echo "8. List all copied reports:"
ls -la ./app/report_*.json 2>/dev/null || echo "No reports found"

echo
echo "========== DEBUGGING COMPLETE =========="
echo "If no report files were found, run the election algorithm again."
echo "You can now run 'python election_cli.py' to try again."
echo "Make sure to check the 'app' directory for any report_*.json files afterward."
