#!/bin/bash

echo "====================================================="
echo "     REYANSH COLLEGE RESOURCE MONITORING"
echo "====================================================="
echo ""

# Set a minimum monitoring duration (in seconds)
MIN_DURATION=30

monitor_processes() {
    # Start time
    start_time=$(date +%s)
    
    echo "Starting continuous monitoring. Press q to quit htop or Ctrl+C to exit."
    echo "Monitoring will run for at least $MIN_DURATION seconds, even if processes complete."
    
    # Get all gunicorn processes
    while true; do
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))
        
        # Find running Gunicorn processes
        pids=$(pgrep -f "gunicorn")
        
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

# Add a function to manually start processes for monitoring
start_and_monitor() {
    echo "Starting both multiprocessing and multithreading configurations..."
    
    # Start multiprocessing configuration
    echo "Starting Gunicorn with 4 processes (multi-processing)..."
    gunicorn -w 4 --threads 1 reyansh_college:app --timeout 120 -b 127.0.0.1:8000 &
    mp_pid=$!
    
    # Wait to ensure processes start
    sleep 3
    
    # Start multithreading configuration
    echo "Starting Gunicorn with 1 process and 4 threads (multi-threading)..."
    gunicorn -w 1 --threads 4 reyansh_college:app --timeout 120 -b 127.0.0.1:8001 &
    mt_pid=$!
    
    # Wait to ensure processes start
    sleep 3
    
    # Monitor all processes
    monitor_processes
    
    # Clean up when done
    echo "Cleaning up processes..."
    kill $mp_pid $mt_pid 2>/dev/null
    pkill -f "gunicorn" 2>/dev/null
}

# Main menu
echo "This script monitors CPU and memory usage of Gunicorn processes"
echo ""
echo "Options:"
echo "1) Monitor existing Gunicorn processes"
echo "2) Start and monitor both configurations"
echo "3) Exit"
echo ""

read -p "Enter your choice (1-3): " choice

case $choice in
    1)
        monitor_processes
        ;;
    2)
        start_and_monitor
        ;;
    3)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice. Exiting..."
        exit 1
        ;;
esac