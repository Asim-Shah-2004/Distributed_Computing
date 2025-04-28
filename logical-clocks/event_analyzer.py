#!/usr/bin/env python3
import os
import json
import matplotlib.pyplot as plt
import pandas as pd
import networkx as nx
from pathlib import Path

def analyze_events(algorithm, nodes):
    """Analyze event logs and create event ordering documentation"""
    log_dir = "./logs"
    
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
                        # Add event_type key to each event dictionary
                        event['event_type'] = event['event'].split()[0]
                        all_events.append(event)
            except Exception as e:
                print(f"Error reading log file {log_file}: {e}")
    
    if not all_events:
        print("No events found in logs. Cannot perform analysis.")
        return
    
    # Sort by event number to get the global order
    all_events.sort(key=lambda x: x.get('event_number', float('inf')))
    
    # Create a DataFrame for analysis
    df = pd.DataFrame(all_events)
    
    # Create readable timestamp
    df['time'] = pd.to_datetime(df['timestamp'], unit='s')
    
    # Generate event order text file
    with open(f"{log_dir}/event_order.txt", "w") as f:
        f.write(f"{algorithm.upper()} CLOCK EVENT ORDER\n")
        f.write("========================\n\n")
        
        for i, event in enumerate(all_events):
            node_id = event['node_id']
            event_type = event['event']
            clock_value = event['clock']
            
            if algorithm == 'lamport':
                clock_str = f"Lamport Clock: {clock_value}"
            else:  # vector
                clock_str = f"Vector Clock: {clock_value}"
                
            f.write(f"Event {i+1}: Node {node_id} - {event_type}\n")
            f.write(f"  {clock_str}\n")
            f.write(f"  Description: {event['description']}\n\n")
        
        # Add causal relationship analysis
        f.write("\nCAUSAL RELATIONSHIPS:\n")
        f.write("====================\n\n")
        
        if algorithm == 'lamport':
            # For Lamport clocks, we can identify some "happened before" relationships
            for i, event1 in enumerate(all_events):
                for j, event2 in enumerate(all_events):
                    if i < j and event1['clock'] < event2['clock']:
                        # If it's a send-receive pair, the relationship is clearer
                        if "SEND to Node" in event1['event'] and "RECEIVE from Node" in event2['event']:
                            node_sent_to = int(event1['event'].split()[-1])
                            node_received_from = int(event2['event'].split()[-1])
                            
                            if event1['node_id'] == node_received_from and event2['node_id'] == node_sent_to:
                                f.write(f"Event {i+1} (Node {event1['node_id']} - {event1['event']}) directly caused ")
                                f.write(f"Event {j+1} (Node {event2['node_id']} - {event2['event']})\n")
        else:  # Vector clock
            # For Vector clocks, we can identify clear happens-before relationships
            for i, event1 in enumerate(all_events):
                for j, event2 in enumerate(all_events):
                    if i < j:
                        v1 = event1['clock']
                        v2 = event2['clock']
                        
                        # Check if all elements of v1 are <= corresponding elements in v2
                        # and at least one element is strictly less than
                        if all(v1[k] <= v2[k] for k in range(len(v1))) and any(v1[k] < v2[k] for k in range(len(v1))):
                            f.write(f"Event {i+1} (Node {event1['node_id']} - {event1['event']}) happened before ")
                            f.write(f"Event {j+1} (Node {event2['node_id']} - {event2['event']})\n")
                        
                        # Check for concurrent events
                        elif any(v1[k] > v2[k] for k in range(len(v1))) and any(v1[k] < v2[k] for k in range(len(v1))):
                            f.write(f"Event {i+1} (Node {event1['node_id']} - {event1['event']}) is concurrent with ")
                            f.write(f"Event {j+1} (Node {event2['node_id']} - {event2['event']})\n")
    
    print(f"Event order saved to {log_dir}/event_order.txt")
    
    # Create event graph visualization
    plt.figure(figsize=(14, 10))
    
    # Set up colors for nodes
    node_colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    event_type_colors = {
        'SEND': 'green',
        'RECEIVE': 'blue',
        'INTERNAL': 'red'
    }
    
    # Create a directed graph
    G = nx.DiGraph()
    
    # Add nodes to the graph
    for i, event in enumerate(all_events):
        node_id = event['node_id']
        event_type = event['event_type']
        event_desc = event['event']
        
        node_label = f"E{i+1}: N{node_id}\n{event_type}"
        
        # Add node with attributes
        G.add_node(i+1, 
                  label=node_label,
                  node_id=node_id, 
                  event_type=event_type,
                  event_desc=event_desc)
    
    # Add edges based on causal relationships
    if algorithm == 'lamport':
        # For Lamport, connect send events to their corresponding receives
        send_events = [(i+1, event) for i, event in enumerate(all_events) if 'SEND to Node' in event['event']]
        recv_events = [(i+1, event) for i, event in enumerate(all_events) if 'RECEIVE from Node' in event['event']]
        
        for send_idx, send_event in send_events:
            send_node = send_event['node_id']
            target_node = int(send_event['event'].split()[-1])
            
            # Find matching receive events
            for recv_idx, recv_event in recv_events:
                recv_node = recv_event['node_id']
                source_node = int(recv_event['event'].split()[-1])
                
                if target_node == recv_node and source_node == send_node:
                    G.add_edge(send_idx, recv_idx, weight=2)
    else:  # Vector clock
        # For Vector clocks, we can add edges based on happens-before relationship
        for i, event1 in enumerate(all_events):
            for j, event2 in enumerate(all_events):
                if i < j:
                    v1 = event1['clock']
                    v2 = event2['clock']
                    
                    # Check if v1 happens before v2
                    if all(v1[k] <= v2[k] for k in range(len(v1))) and any(v1[k] < v2[k] for k in range(len(v1))):
                        # Skip if there's an intermediate event that would create a path
                        intermediate_exists = False
                        for k, event3 in enumerate(all_events):
                            if i < k < j:
                                v3 = event3['clock']
                                if (all(v1[m] <= v3[m] for m in range(len(v1))) and 
                                    any(v1[m] < v3[m] for m in range(len(v1)))) and \
                                   (all(v3[m] <= v2[m] for m in range(len(v1))) and 
                                    any(v3[m] < v2[m] for m in range(len(v1)))):
                                    intermediate_exists = True
                                    break
                        
                        if not intermediate_exists:
                            G.add_edge(i+1, j+1, weight=1)
    
    # Add edges for events in the same process (node) to show local progression
    for i in range(nodes):
        node_events = [idx+1 for idx, event in enumerate(all_events) if event['node_id'] == i]
        for j in range(len(node_events) - 1):
            G.add_edge(node_events[j], node_events[j+1], style='dashed', weight=0.5)
    
    # Set node colors based on node ID
    node_colors_map = [node_colors[G.nodes[n]['node_id'] % len(node_colors)] for n in G.nodes()]
    
    # Position nodes using built-in NetworkX layouts instead of graphviz
    # First try a layered hierarchical layout
    pos = {}
    
    # Create a position layout that organizes nodes by their process/node_id
    # This creates a timeline-like visualization
    for node in G.nodes():
        node_id = G.nodes[node]['node_id']
        # Find the position of this node in its process sequence
        process_events = [n for n in G.nodes() if G.nodes[n]['node_id'] == node_id]
        position = process_events.index(node)
        pos[node] = (position, -node_id)  # x = event position, y = process ID (negative to go top-down)
    
    # Draw the graph
    nx.draw_networkx_nodes(G, pos, node_color=node_colors_map, node_size=1500, alpha=0.8)
    
    # Draw edges with different styles
    solid_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('style', 'solid') == 'solid']
    dashed_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get('style', 'solid') == 'dashed']
    
    nx.draw_networkx_edges(G, pos, edgelist=solid_edges, width=2, arrows=True)
    nx.draw_networkx_edges(G, pos, edgelist=dashed_edges, width=1, style='dashed', arrows=True)
    
    # Draw labels
    labels = {n: G.nodes[n]['label'] for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=10, font_weight='bold')
    
    # Set plot title and save
    plt.title(f"Event Graph with {algorithm.capitalize()} Clock", fontsize=16)
    plt.tight_layout()
    plt.axis('off')
    
    plt.savefig(f"{log_dir}/event_graph.png", dpi=300, bbox_inches='tight')
    print(f"Event graph saved to {log_dir}/event_graph.png")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze event logs and create event ordering')
    parser.add_argument('--algorithm', type=str, choices=['lamport', 'vector'], default='lamport',
                        help='Clock synchronization algorithm')
    parser.add_argument('--nodes', type=int, default=3, help='Number of nodes')
    
    args = parser.parse_args()
    analyze_events(args.algorithm, args.nodes)