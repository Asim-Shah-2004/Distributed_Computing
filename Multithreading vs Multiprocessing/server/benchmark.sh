#!/bin/bash

echo "Installing dependencies..."
pip install flask gunicorn numpy psutil

ENDPOINT="http://127.0.0.1:8000/analyze"
REQUESTS=100
CONCURRENCY=10

echo "====================================================="
echo "     REYANSH COLLEGE OF HOTEL MANAGEMENT"
echo "     THREADING VS PROCESSING BENCHMARK"
echo "====================================================="
echo ""

# Create files to store benchmark results
mkdir -p results
rm -f results/multiproc.txt results/multithread.txt

echo "Starting Gunicorn with 4 processes (multi-processing)..."
gunicorn -w 4 --threads 1 reyansh_college:app --timeout 120 &
SERVER_PID=$!

sleep 3
echo "Server started with PID: $SERVER_PID"

echo ""
echo "Running Apache Bench test on multi-processing configuration..."
ab -n $REQUESTS -c $CONCURRENCY $ENDPOINT > results/multiproc.txt

kill $SERVER_PID
echo "Server stopped."
echo ""
sleep 3

echo "Starting Gunicorn with 1 process and 4 threads (multi-threading)..."
gunicorn -w 1 --threads 4 reyansh_college:app --timeout 120 &
SERVER_PID=$!

sleep 3
echo "Server started with PID: $SERVER_PID"

echo ""
echo "Running Apache Bench test on multi-threading configuration..."
ab -n $REQUESTS -c $CONCURRENCY $ENDPOINT > results/multithread.txt

kill $SERVER_PID
echo "Server stopped."
echo ""

# Extract metrics from the benchmark results
extract_metric() {
    local file=$1
    local pattern=$2
    grep "$pattern" $file | awk -F'[: ]+' '{print $NF}'
}

# Extract metrics from both benchmark results
MP_TOTAL_TIME=$(extract_metric "results/multiproc.txt" "Time taken for tests")
MP_RPS=$(extract_metric "results/multiproc.txt" "Requests per second")
MP_MEAN_TIME=$(extract_metric "results/multiproc.txt" "Time per request.*mean")
MP_FAILED=$(extract_metric "results/multiproc.txt" "Failed requests")
MP_TRANSFERRED=$(extract_metric "results/multiproc.txt" "Total transferred")
MP_TRANSFER_RATE=$(extract_metric "results/multiproc.txt" "Transfer rate")
MP_MEDIAN=$(extract_metric "results/multiproc.txt" "50%.*" | tr -d ' ')
MP_90TH=$(extract_metric "results/multiproc.txt" "90%.*" | tr -d ' ')
MP_LONGEST=$(extract_metric "results/multiproc.txt" "100%.*" | tr -d ' ')

MT_TOTAL_TIME=$(extract_metric "results/multithread.txt" "Time taken for tests")
MT_RPS=$(extract_metric "results/multithread.txt" "Requests per second")
MT_MEAN_TIME=$(extract_metric "results/multithread.txt" "Time per request.*mean")
MT_FAILED=$(extract_metric "results/multithread.txt" "Failed requests")
MT_TRANSFERRED=$(extract_metric "results/multithread.txt" "Total transferred")
MT_TRANSFER_RATE=$(extract_metric "results/multithread.txt" "Transfer rate")
MT_MEDIAN=$(extract_metric "results/multithread.txt" "50%.*" | tr -d ' ')
MT_90TH=$(extract_metric "results/multithread.txt" "90%.*" | tr -d ' ')
MT_LONGEST=$(extract_metric "results/multithread.txt" "100%.*" | tr -d ' ')

# Print results in a table format
echo "====================================================="
echo "                BENCHMARK RESULTS"
echo "====================================================="
echo ""
printf "%-30s | %-25s | %-25s\n" "Metric" "Multithreading (1 Worker, 4 Threads)" "Multiprocessing (4 Workers)"
printf "%-30s | %-25s | %-25s\n" "------------------------------" "-------------------------" "-------------------------"
printf "%-30s | %-25s | %-25s\n" "Total Requests" "$REQUESTS" "$REQUESTS"
printf "%-30s | %-25s | %-25s\n" "Concurrency Level" "$CONCURRENCY" "$CONCURRENCY"
printf "%-30s | %-25s | %-25s\n" "Total Time Taken (seconds)" "$MT_TOTAL_TIME" "$MP_TOTAL_TIME"
printf "%-30s | %-25s | %-25s\n" "Requests per Second (RPS)" "$MT_RPS" "$MP_RPS"
printf "%-30s | %-25s | %-25s\n" "Mean Time per Request (ms)" "$MT_MEAN_TIME" "$MP_MEAN_TIME"
printf "%-30s | %-25s | %-25s\n" "Failed Requests" "$MT_FAILED" "$MP_FAILED"
printf "%-30s | %-25s | %-25s\n" "Total Data Transferred (bytes)" "$MT_TRANSFERRED" "$MP_TRANSFERRED"
printf "%-30s | %-25s | %-25s\n" "Transfer Rate (Kbytes/sec)" "$MT_TRANSFER_RATE" "$MP_TRANSFER_RATE"
printf "%-30s | %-25s | %-25s\n" "Median Request Time (ms)" "$MT_MEDIAN" "$MP_MEDIAN"
printf "%-30s | %-25s | %-25s\n" "90th Percentile Request Time (ms)" "$MT_90TH" "$MP_90TH"
printf "%-30s | %-25s | %-25s\n" "Longest Request Time (ms)" "$MT_LONGEST" "$MP_LONGEST"
echo ""

echo "====================================================="
echo "              RESOURCE USAGE MONITORING"
echo "====================================================="
echo ""
echo "For CPU and memory monitoring, run the following in a separate terminal:"
echo "For multiprocessing test:"
echo "    watch -n 1 'ps -p \$(pgrep -f \"gunicorn -w 4\") -o pid,ppid,%cpu,%mem,cmd'"
echo ""
echo "For multithreading test:"
echo "    watch -n 1 'ps -p \$(pgrep -f \"gunicorn -w 1 --threads 4\") -o pid,ppid,%cpu,%mem,cmd'"
echo ""
echo "Or use htop by running:"
echo "    htop -p \$(pgrep -d',' -f gunicorn)"
echo ""
echo "====================================================="