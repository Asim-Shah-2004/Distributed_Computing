#!/bin/bash

pip install flask gunicorn numpy psutil

MP_PORT=8080
MT_PORT=8081

ENDPOINT_MP="http://127.0.0.1:$MP_PORT/analyze"
ENDPOINT_MT="http://127.0.0.1:$MT_PORT/analyze"
REQUESTS=1000
CONCURRENCY=100

echo "====================================================="
echo "     REYANSH COLLEGE OF HOTEL MANAGEMENT"
echo "     THREADING VS PROCESSING BENCHMARK"
echo "====================================================="
echo ""

if pgrep -f "gunicorn" > /dev/null; then
    pkill -f "gunicorn"
    sleep 2
fi

mkdir -p results
rm -f results/multiproc.txt results/multithread.txt

gunicorn -w 4 --threads 1 reyansh_college:app --timeout 120 -b 127.0.0.1:$MP_PORT &
SERVER_PID=$!

for i in {1..10}; do
    sleep 1
    if curl -s http://127.0.0.1:$MP_PORT/ > /dev/null; then
        break
    fi
    if [ $i -eq 10 ]; then
        kill $SERVER_PID 2>/dev/null
        exit 1
    fi
done

ab -n $REQUESTS -c $CONCURRENCY -e results/mp_distribution.csv $ENDPOINT_MP > results/multiproc.txt
kill $SERVER_PID 2>/dev/null
sleep 3

gunicorn -w 1 --threads 4 reyansh_college:app --timeout 120 -b 127.0.0.1:$MT_PORT &
SERVER_PID=$!

for i in {1..10}; do
    sleep 1
    if curl -s http://127.0.0.1:$MT_PORT/ > /dev/null; then
        break
    fi
    if [ $i -eq 10 ]; then
        kill $SERVER_PID 2>/dev/null
        exit 1
    fi
done

ab -n $REQUESTS -c $CONCURRENCY -e results/mt_distribution.csv $ENDPOINT_MT > results/multithread.txt
kill $SERVER_PID 2>/dev/null
sleep 3

extract_metric() {
    grep "$2" $1 | awk -F'[: ]+' '{print $NF}'
}

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

echo "====================================================="
echo "                BENCHMARK RESULTS"
echo "====================================================="
echo ""
printf "%-30s | %-25s | %-25s\n" "Metric" "Multithreading (1, 4)" "Multiprocessing (4, 1)"
printf "%-30s | %-25s | %-25s\n" "-" "-" "-"
printf "%-30s | %-25s | %-25s\n" "Total Requests" "$REQUESTS" "$REQUESTS"
printf "%-30s | %-25s | %-25s\n" "Concurrency Level" "$CONCURRENCY" "$CONCURRENCY"
printf "%-30s | %-25s | %-25s\n" "Total Time (seconds)" "$MT_TOTAL_TIME" "$MP_TOTAL_TIME"
printf "%-30s | %-25s | %-25s\n" "Requests/second" "$MT_RPS" "$MP_RPS"
printf "%-30s | %-25s | %-25s\n" "Mean Time/Request (ms)" "$MT_MEAN_TIME" "$MP_MEAN_TIME"
printf "%-30s | %-25s | %-25s\n" "Failed Requests" "$MT_FAILED" "$MP_FAILED"
printf "%-30s | %-25s | %-25s\n" "Transferred (bytes)" "$MT_TRANSFERRED" "$MP_TRANSFERRED"
printf "%-30s | %-25s | %-25s\n" "Transfer Rate (KB/sec)" "$MT_TRANSFER_RATE" "$MP_TRANSFER_RATE"
printf "%-30s | %-25s | %-25s\n" "Median Time (ms)" "$MT_MEDIAN" "$MP_MEDIAN"
printf "%-30s | %-25s | %-25s\n" "90th Percentile (ms)" "$MT_90TH" "$MP_90TH"
printf "%-30s | %-25s | %-25s\n" "Max Time (ms)" "$MT_LONGEST" "$MP_LONGEST"
echo ""

pkill -f "gunicorn" 2>/dev/null