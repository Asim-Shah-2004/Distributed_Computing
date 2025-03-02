#!/bin/bash

echo "====================================================="
echo "     REYANSH COLLEGE - PROCESS CLEANUP UTILITY"
echo "====================================================="
echo ""

PORTS="8000 8001 8080 8081"

echo "This utility will help clean up any stuck processes from previous runs."
echo ""

for PORT in $PORTS; do
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
        PIDS=$(lsof -ti:$PORT)
        echo "Found processes using port $PORT: $PIDS"
        echo "Killing processes..."
        kill -9 $PIDS 2>/dev/null
        echo "Port $PORT freed."
    else
        echo "Port $PORT is not in use."
    fi
done

# Kill any Gunicorn processes
if pgrep -u $(whoami) -f "gunicorn" > /dev/null; then
    PIDS=$(pgrep -u $(whoami) -f "gunicorn")
    echo "Found Gunicorn processes: $PIDS"
    echo "Killing Gunicorn processes..."
    pkill -u $(whoami) -f "gunicorn"
    sleep 1
    if pgrep -u $(whoami) -f "gunicorn" > /dev/null; then
        echo "Some processes didn't terminate. Forcing termination..."
        pkill -9 -u $(whoami) -f "gunicorn"
    fi
    echo "Gunicorn processes terminated."
else
    echo "No Gunicorn processes found."
fi

echo ""
echo "Cleanup complete. You can now run your benchmark or monitoring scripts."
echo ""