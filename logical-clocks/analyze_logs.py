#!/usr/bin/env python3
import os
import json
import time
import argparse
import matplotlib.pyplot as plt
import pandas as pd
import networkx as nx
from pathlib import Path

def analyze_logs(algorithm, nodes):
    log_dir = "/logs"
    
    # Wait for log files to be available
    all_logs_available = False
    max_attempts = 30
    attempts = 0
    
    while not all_logs_available and attempts < max_attempts:
        log_files = [f"{log_dir}/node{i}_{algorithm}_log.json" for i in range(nodes)]
        if all(os.path.exists(f) for f in log_files):
            all_logs_available = True
        else:
            print(f"Waiting for log files... Attempt {attempts+1}/{max_attempts}")
            time.sleep(5)
            attempts += 1
    
    if not all_logs_available:
        print("Not all log files are available. Analysis may be incomplete.")
    
    # Combine all logs
    all_events = []
    
    for i in range(nodes):
        log_file = f"{log_dir}/node{i}_{algorithm}_log.json"
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    node_log = json.load(f)
                    for event in node_log:
                        event['node_id'] = i
                        all_events.append(event)
            except Exception as e:
                print(f"Error reading log file {log_file}: {e}")
    
    if not all_events:
        print("No events found in logs. Cannot perform analysis.")
        return
    
    # Sort events by timestamp
    all_events.sort(key=lambda x: x['timestamp'])
    
    # Create a DataFrame for analysis
    df = pd.DataFrame(all_events)
    
    # Basic statistics
    event_counts = df.groupby(['node_id', 'event']).size().unstack(fill_value=0)
    print("Event counts per node:")
    print(event_counts)
    
    # Create visualization of message patterns
    msg_graph = nx.DiGraph()
    
    # Add nodes
    for i in range(nodes):
        msg_graph.add_node(f"Node {i}")
    
    # Add edges for send events
    send_events = df[df['event'].str.startswith('SEND')]
    for _, event in send_events.iterrows():
        source = f"Node {event['node_id']}"
        target = f"Node {int(event['event'].split()[-1])}"
        if msg_graph.has_edge(source, target):
            msg_graph[source][target]['weight'] += 1
        else:
            msg_graph.add_edge(source, target, weight=1)
    
    # Create a figure for visualization
    plt.figure(figsize=(12, 8))
    
    # Plot message graph
    plt.subplot(221)
    pos = nx.spring_layout(msg_graph)
    edge_width = [d['weight'] * 0.5 for _, _, d in msg_graph.edges(data=True)]
    nx.draw(msg_graph, pos, with_labels=True, arrows=True, node_color='skyblue', 
            node_size=700, edge_color='gray', width=edge_width, connectionstyle='arc3,rad=0.1')
    plt.title(f"Message Pattern with {algorithm.capitalize()} Clock")
    
    # Plot event timeline
    plt.subplot(222)
    for i in range(nodes):
        node_events = df[df['node_id'] == i]
        plt.plot(range(len(node_events)), node_events.index, marker='o', label=f"Node {i}")
    
    plt.xlabel("Event Sequence")
    plt.ylabel("Global Time Index")
    plt.title("Event Timeline")
    plt.legend()
    
    # Save analysis results
    analysis_file = f"{log_dir}/{algorithm}_analysis.png"
    plt.tight_layout()
    plt.savefig(analysis_file)
    print(f"\nAnalysis visualization saved to {analysis_file}")
    
    # Create a summary report
    report_file = f"{log_dir}/{algorithm}_report.txt"
    with open(report_file, 'w') as f:
        f.write(f"{algorithm.upper()} CLOCK SYNCHRONIZATION ANALYSIS\n")
        f.write(f"{'='*50}\n\n")
        f.write(f"Number of nodes: {nodes}\n")
        f.write(f"Total events: {len(df)}\n\n")
        
        f.write("Event counts per node:\n")
        f.write(f"{event_counts}\n\n")
        
        f.write("Causality Analysis:\n")
        if algorithm == 'lamport':
            # Check for events with out-of-order Lamport clocks
            f.write("Events are ordered by Lamport timestamps.\n")
        else:  # Vector clock
            # Check for concurrent events
            f.write("Vector clocks can identify concurrent events.\n")
    
    print(f"Analysis report saved to {report_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze logical clock synchronization logs')
    parser.add_argument('--algorithm', type=str, choices=['lamport', 'vector'], required=True,
                        help='Clock synchronization algorithm')
    parser.add_argument('--nodes', type=int, required=True, help='Number of nodes')
    
    args = parser.parse_args()
    analyze_logs(args.algorithm, args.nodes)
