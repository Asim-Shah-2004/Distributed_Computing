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

echo "Starting Gunicorn with 4 processes (multi-processing)..."
gunicorn -w 4 --threads 1 reyansh_college:app --timeout 120 &
SERVER_PID=$!

sleep 3
echo "Server started with PID: $SERVER_PID"

echo ""
echo "Running Apache Bench test on multi-processing configuration..."
echo "ab -n $REQUESTS -c $CONCURRENCY $ENDPOINT"
ab -n $REQUESTS -c $CONCURRENCY $ENDPOINT | grep -E "Requests per second|Time per request|Complete requests|Failed requests"

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
echo "ab -n $REQUESTS -c $CONCURRENCY $ENDPOINT"
ab -n $REQUESTS -c $CONCURRENCY $ENDPOINT | grep -E "Requests per second|Time per request|Complete requests|Failed requests"


kill $SERVER_PID
echo "Server stopped."
echo ""

echo "====================================================="
echo "                BENCHMARK COMPLETE"
echo "====================================================="
echo ""
echo "Check the results above to compare:"
echo "1. Throughput (Requests per second)"
echo "2. Latency (Time per request)"
echo "3. Reliability (Failed requests)"
echo ""
