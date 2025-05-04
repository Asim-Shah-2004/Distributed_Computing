#!/bin/bash

echo "Checking and fixing permissions for successful report generation"

# Get current user and group
CURRENT_USER=$(id -u)
CURRENT_GROUP=$(id -g)

echo "Current user: $CURRENT_USER:$CURRENT_GROUP"
echo "Fixing app directory permissions..."

# Create app directory if it doesn't exist
mkdir -p app

# Set permissions on app directory
chmod 777 app
echo "Set app directory to 777 permissions"

# Check if we can create a test file
echo "Test content" > app/test_write.txt
if [ $? -eq 0 ]; then
  echo "Successfully wrote to app directory"
  cat app/test_write.txt
  rm app/test_write.txt
else
  echo "Failed to write to app directory!"
  echo "There might be SELinux or other permission issues"
fi

echo "Checking Docker configuration..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running!"
  exit 1
fi

# Update docker-compose.yml with current user ID
echo "Your user ID ($CURRENT_USER) will be used in docker-compose.yml"
sed -i "s/user: \"[0-9]*:[0-9]*\"/user: \"$CURRENT_USER:$CURRENT_GROUP\"/" docker-compose.yml
echo "Updated docker-compose.yml with your user ID"

echo "Permission setup complete. Run the following commands to restart:"
echo "docker-compose down"
echo "docker-compose up -d"
echo "Then run election_cli.py to test the system"
