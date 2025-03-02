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