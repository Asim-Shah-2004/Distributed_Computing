

echo "====================================================="
echo "     REYANSH COLLEGE RESOURCE MONITORING"
echo "====================================================="
echo ""

# Define ports (must match those in benchmark.sh)
MP_PORT=8080
MT_PORT=8081

# Set a minimum monitoring duration (in seconds)
MIN_DURATION=30

# Check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Kill processes using specific ports
kill_port() {
    local port=$1
    local pids=$(lsof -ti:$port)
    if [ -n "$pids" ]; then
        echo "Killing processes using port $port: $pids"
        kill -9 $pids 2>/dev/null
    fi
}

# Function to clean up environment before starting
cleanup_environment() {
    echo "Cleaning up environment..."
    
    # Check and kill processes on monitoring ports
    if check_port $MP_PORT; then
        echo "Port $MP_PORT is in use. Attempting to free it..."
        kill_port $MP_PORT
        sleep 1
    fi
    
    if check_port $MT_PORT; then
        echo "Port $MT_PORT is in use. Attempting to free it..."
        kill_port $MT_PORT
        sleep 1
    fi
    
    # Kill any existing Gunicorn processes started by current user
    if pgrep -u $(whoami) -f "gunicorn" > /dev/null; then
        echo "Found existing Gunicorn processes. Terminating..."
        pkill -u $(whoami) -f "gunicorn"
        sleep 2
    fi
    
    echo "Environment cleaned up."
}

monitor_processes() {
    # Start time
    start_time=$(date +%s)
    
    echo "Starting continuous monitoring. Press q to quit htop or Ctrl+C to exit."
    echo "Monitoring will run for at least $MIN_DURATION seconds, even if processes complete."
    
    # Get all gunicorn processes for current user
    while true; do
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))
        
        # Find running Gunicorn processes
        pids=$(pgrep -u $(whoami) -f "gunicorn")
        
        if [ -n "$pids" ]; then
            pids_comma=$(echo $pids | tr ' ' ',')
            
            echo "Monitoring Gunicorn processes: $pids"
            echo "Elapsed time: $elapsed seconds"
            
            # Use htop if available, otherwise use ps/watch
            if command -v htop >/dev/null 2>&1; then
                htop -p $pids_comma
            else
                watch -n 1 "ps -p $pids -o pid,ppid,%cpu,%mem,cmd --sort=-%cpu"
            fi
        else
            # If no processes found but minimum duration not met, wait and look again
            if [ $elapsed -lt $MIN_DURATION ]; then
                echo "No Gunicorn processes found. Waiting and retrying... ($elapsed/$MIN_DURATION seconds)"
                sleep 2
            else
                echo "No Gunicorn processes found after minimum monitoring period. Exiting."
                break
            fi
        fi
        
        # Check if minimum duration has been met
        if [ $elapsed -ge $MIN_DURATION ]; then
            read -p "Minimum monitoring time reached. Continue monitoring? (y/n): " continue_mon
            if [ "$continue_mon" != "y" ]; then
                break
            fi
            # Reset timer if continuing
            start_time=$(date +%s)
        fi
    done
    
    echo "Monitoring complete."
}

# Function to manually start processes for monitoring
start_and_monitor() {
    # Clean up first
    cleanup_environment
    
    echo "Starting both multiprocessing and multithreading configurations..."
    
    # Start multiprocessing configuration
    echo "Starting Gunicorn with 4 processes (multi-processing) on port $MP_PORT..."
    gunicorn -w 4 --threads 1 reyansh_college:app --timeout 120 -b 127.0.0.1:$MP_PORT &
    mp_pid=$!
    
    # Wait to ensure processes start
    echo "Waiting for multiprocessing server to start..."
    for i in {1..10}; do
        sleep 1
        if curl -s http://127.0.0.1:$MP_PORT/ > /dev/null; then
            echo "Multiprocessing server started successfully with PID: $mp_pid"
            break
        fi
        if [ $i -eq 10 ]; then
            echo "Failed to start multiprocessing server after 10 seconds. Check for errors."
            kill $mp_pid 2>/dev/null
        fi
    done
    
    # Start multithreading configuration
    echo "Starting Gunicorn with 1 process and 4 threads (multi-threading) on port $MT_PORT..."
    gunicorn -w 1 --threads 4 reyansh_college:app --timeout 120 -b 127.0.0.1:$MT_PORT &
    mt_pid=$!
    
    # Wait to ensure processes start
    echo "Waiting for multithreading server to start..."
    for i in {1..10}; do
        sleep 1
        if curl -s http://127.0.0.1:$MT_PORT/ > /dev/null; then
            echo "Multithreading server started successfully with PID: $mt_pid"
            break
        fi
        if [ $i -eq 10 ]; then
            echo "Failed to start multithreading server after 10 seconds. Check for errors."
            kill $mt_pid 2>/dev/null
        fi
    done
    
    # Monitor all processes
    monitor_processes
    
    # Clean up when done
    echo "Cleaning up processes..."
    kill $mp_pid $mt_pid 2>/dev/null
    pkill -u $(whoami) -f "gunicorn" 2>/dev/null
}

# Main menu
echo "This script monitors CPU and memory usage of Gunicorn processes"
echo ""
echo "Options:"
echo "1) Monitor existing Gunicorn processes"
echo "2) Start and monitor both configurations"
echo "3) Clean up environment (kill existing processes)"
echo "4) Exit"
echo ""

read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        monitor_processes
        ;;
    2)
        start_and_monitor
        ;;
    3)
        cleanup_environment
        ;;
    4)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice. Exiting..."
        exit 1
        ;;
esac