#!/bin/bash

echo "====================================================="
echo "     REYANSH COLLEGE OF HOTEL MANAGEMENT"
echo "     THREADING VS PROCESSING BENCHMARK SUITE"
echo "====================================================="
echo ""

chmod +x benchmark.sh monitor.sh

mkdir -p results

check_requirements() {
    echo "Checking requirements..."
    
    if ! command -v ab &> /dev/null; then
        echo "Apache Bench (ab) not found. Installing apache2-utils..."
        sudo apt-get update && sudo apt-get install -y apache2-utils
    fi
    
    if ! command -v htop &> /dev/null; then
        echo "htop not found. Installing htop..."
        sudo apt-get update && sudo apt-get install -y htop
    fi
    
    pip install -q flask gunicorn numpy psutil
    
    echo "All requirements satisfied."
}

run_monitoring() {
    if command -v gnome-terminal &> /dev/null; then
        gnome-terminal -- ./monitor.sh
    elif command -v xterm &> /dev/null; then
        xterm -e "./monitor.sh" &
    elif command -v konsole &> /dev/null; then
        konsole -e "./monitor.sh" &
    elif command -v terminal &> /dev/null; then
        terminal -e "./monitor.sh" &
    else
        echo "Could not find a terminal emulator to run the monitoring script."
        echo "Please run ./monitor.sh in a separate terminal."
        read -p "Press Enter when you've started monitoring in another terminal..." dummy
    fi
}

# Main execution
check_requirements

echo ""
echo "This script will start both the benchmark and monitoring tools."
echo "The benchmark will test the performance differences between:"
echo "  - Multiprocessing: 4 workers with 1 thread each"
echo "  - Multithreading: 1 worker with 4 threads"
echo ""
echo "Options:"
echo "1) Run benchmark with simultaneous monitoring (recommended)"
echo "2) Run benchmark only"
echo "3) Run monitoring only"
echo "4) Exit"
echo ""

read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo "Starting monitoring in a new terminal..."
        run_monitoring
        sleep 2
        echo "Starting benchmark..."
        ./benchmark.sh
        ;;
    2)
        echo "Starting benchmark only..."
        ./benchmark.sh
        ;;
    3)
        echo "Starting monitoring only..."
        ./monitor.sh
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

echo ""
echo "====================================================="
echo "                   ALL DONE"
echo "====================================================="
echo ""
echo "Check the results directory for benchmark data."
echo "You can generate a comparison report by running:"
echo "./analyze_results.sh"
echo ""

# Create a simple analyze_results.sh script for convenience
cat > analyze_results.sh << 'EOF'
#!/bin/bash
echo "Generating comparison report from benchmark results..."
if [ -f results/multiproc.txt ] && [ -f results/multithread.txt ]; then
    echo "============ MULTIPROCESSING (4 Workers) ============" > results/comparison.txt
    cat results/multiproc.txt | grep -E "Requests per second|Time per request|Complete requests|Failed requests" >> results/comparison.txt
    echo "" >> results/comparison.txt
    echo "============ MULTITHREADING (1 Worker, 4 Threads) ============" >> results/comparison.txt
    cat results/multithread.txt | grep -E "Requests per second|Time per request|Complete requests|Failed requests" >> results/comparison.txt
    echo "Report generated at results/comparison.txt"
    cat results/comparison.txt
else
    echo "Benchmark results not found. Run the benchmark first."
fi
EOF

chmod +x analyze_results.sh