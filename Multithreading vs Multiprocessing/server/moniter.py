import psutil
import time
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

def monitor_resources(duration=60, interval=1, output_file="resource_usage.csv"):
    """Monitor CPU and memory usage for a specified duration."""
    print(f"Monitoring system resources for {duration} seconds...")
    
    timestamps = []
    cpu_percents = []
    memory_percents = []
    
    start_time = time.time()
    while time.time() - start_time < duration:
        current_time = datetime.now().strftime("%H:%M:%S")
        cpu_percent = psutil.cpu_percent(interval=None)
        memory_percent = psutil.virtual_memory().percent
        
        timestamps.append(current_time)
        cpu_percents.append(cpu_percent)
        memory_percents.append(memory_percent)
        
        print(f"Time: {current_time} | CPU: {cpu_percent:.1f}% | Memory: {memory_percent:.1f}%")
        time.sleep(interval)
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'cpu_percent': cpu_percents,
        'memory_percent': memory_percents
    })
    
    df.to_csv(output_file, index=False)
    print(f"Resource monitoring complete. Data saved to {output_file}")
    

    plt.figure(figsize=(12, 6))
    plt.plot(range(len(timestamps)), cpu_percents, label='CPU %')
    plt.plot(range(len(timestamps)), memory_percents, label='Memory %')
    plt.title('Resource Usage Over Time')
    plt.xlabel('Time Intervals')
    plt.ylabel('Usage Percentage')
    plt.legend()
    plt.grid(True)
    plt.savefig('resource_usage.png')
    plt.close()
    
    print("Resource usage plot saved to resource_usage.png")

if __name__ == "__main__":
    print("Resource Monitoring Tool for Reyansh College of Hotel Management")
    print("=============================================================")
    print("This tool monitors CPU and memory usage during benchmarking.")
    print("Run this script in a separate terminal while running benchmark.sh")
    print()
    
    try:
        duration = int(input("Enter monitoring duration in seconds (default: 60): ") or 60)
        interval = float(input("Enter sampling interval in seconds (default: 1): ") or 1)
        output_file = input("Enter output CSV file name (default: resource_usage.csv): ") or "resource_usage.csv"
        
        monitor_resources(duration, interval, output_file)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        print(f"Error: {e}")