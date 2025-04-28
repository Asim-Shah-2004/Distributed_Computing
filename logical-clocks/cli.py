#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import time
import json
import matplotlib.pyplot as plt
import pandas as pd
import networkx as nx
from pathlib import Path

class LogicalClockExperiment:
    def __init__(self, algorithm: str, nodes: int):
        self.algorithm = algorithm.lower()
        self.nodes = nodes
        self.log_dir = os.path.join(os.getcwd(), "logs")
        
        # Ensure logs directory exists
        os.makedirs(self.log_dir, exist_ok=True)
        
    def generate_files(self):
        """Generate necessary files for the experiment"""
        # Docker compose configuration
        with open("docker-compose.yml", "w") as f:
            yaml_content = "version: '3'\n\n"
            
            # Services section
            yaml_content += "services:\n"
            for i in range(self.nodes):
                yaml_content += f"  node{i}:\n"
                yaml_content += f"    build: .\n"
                yaml_content += f"    command: python node.py --id {i} --nodes {self.nodes} --algorithm {self.algorithm} --host-prefix node\n"
                yaml_content += f"    volumes:\n"
                yaml_content += f"      - ./logs:/logs\n"
                yaml_content += f"    networks:\n"
                yaml_content += f"      - clock_network\n\n"
            
            # Networks section
            yaml_content += "networks:\n"
            yaml_content += "  clock_network:\n"
            yaml_content += "    driver: bridge\n"
            
            f.write(yaml_content)
        
        # Dockerfile
        with open("Dockerfile", "w") as f:
            f.write("FROM python:3.9-slim\n\n")
            f.write("WORKDIR /app\n\n")
            f.write("COPY requirements.txt .\n")
            f.write("RUN pip install --no-cache-dir -r requirements.txt\n\n")
            f.write("COPY . .\n\n")
            f.write("CMD [\"python\", \"node.py\"]\n")
        
        # Requirements.txt
        with open("requirements.txt", "w") as f:
            f.write("matplotlib\n")
            f.write("pandas\n")
            f.write("networkx\n")
            f.write("pyyaml\n")
            f.write("seaborn\n")  # Added for better visualization
        
        # Modified node.py to limit events
        with open("node.py", "w") as f:
            # Getting original node code and modifying it
            with open("original_node.py", "r") as original:
                node_code = original.read()
            
            # Replace max_messages value
            node_code = node_code.replace("self.max_messages = 20", "self.max_messages = 10")
            
            f.write(node_code)
        
        # Log analyzer script with improved visualizations
        with open("analyze_logs.py", "w") as f:
            f.write("""#!/usr/bin/env python3
import os
import json
import time
import argparse
import matplotlib.pyplot as plt
import pandas as pd
import networkx as nx
import seaborn as sns
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
    
    # Add readable timestamp
    df['time'] = pd.to_datetime(df['timestamp'], unit='s')
    
    # Basic statistics
    event_counts = df.groupby(['node_id', 'event']).size().unstack(fill_value=0)
    print("\\nEvent counts per node:")
    print(event_counts)
    
    # Set the aesthetic style of plots
    sns.set_style("whitegrid")
    plt.rcParams.update({'font.size': 12})
    
    # Create a figure for visualizations
    fig = plt.figure(figsize=(16, 14))
    
    # 1. Message Graph - Clear visualization of communication pattern
    plt.subplot(221)
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
    
    pos = nx.circular_layout(msg_graph)  # Better layout for visualization
    edge_width = [d['weight'] * 2.0 for _, _, d in msg_graph.edges(data=True)]
    edge_labels = {(u, v): d['weight'] for u, v, d in msg_graph.edges(data=True)}
    
    nx.draw(msg_graph, pos, with_labels=True, arrows=True, 
            node_color='lightblue', node_size=1000, font_weight='bold',
            edge_color='darkblue', width=edge_width, connectionstyle='arc3,rad=0.2')
    nx.draw_networkx_edge_labels(msg_graph, pos, edge_labels=edge_labels, font_size=10)
    
    plt.title(f"Message Pattern with {algorithm.capitalize()} Clock", fontsize=16)
    
    # 2. Event Timeline with Logical Clocks
    plt.subplot(222)
    
    # Extract clock values based on algorithm
    if algorithm == 'lamport':
        # For Lamport clocks, just extract the scalar value
        df['clock_value'] = df['clock'].apply(lambda x: x if isinstance(x, (int, float)) else None)
    else:  # Vector clock
        # For Vector clocks, calculate the sum of the vector for visualization
        df['clock_value'] = df['clock'].apply(lambda x: sum(x) if isinstance(x, list) else None)
    
    # Create timeline plot
    for i in range(nodes):
        node_events = df[df['node_id'] == i]
        plt.plot(range(len(node_events)), node_events['clock_value'], 
                 marker='o', markersize=8, linewidth=2, label=f"Node {i}")
    
    plt.xlabel("Event Sequence", fontsize=14)
    plt.ylabel(f"{algorithm.capitalize()} Clock Value", fontsize=14)
    plt.title(f"{algorithm.capitalize()} Clock Progression", fontsize=16)
    plt.grid(True)
    plt.legend(fontsize=12)
    
    # 3. Message flow visualization
    plt.subplot(223)
    
    # Create a scatter plot of events over physical time
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    for i in range(nodes):
        node_df = df[df['node_id'] == i]
        plt.scatter(node_df['time'], [i] * len(node_df), 
                   s=100, c=colors[i % len(colors)], label=f"Node {i}", alpha=0.7)
        
        # Add event type labels
        for idx, row in node_df.iterrows():
            event_type = row['event'].split()[0]  # Just get SEND/RECEIVE/INTERNAL
            plt.annotate(event_type, 
                       (row['time'], i),
                       xytext=(0, 10), 
                       textcoords='offset points',
                       fontsize=8,
                       rotation=45)
    
    plt.yticks(range(nodes))
    plt.xlabel("Physical Time", fontsize=14)
    plt.ylabel("Node ID", fontsize=14)
    plt.title("Event Distribution Over Time", fontsize=16)
    plt.grid(True)
    plt.legend(fontsize=12)
    
    # 4. Event type distribution
    plt.subplot(224)
    
    # Prepare data for the bar chart
    event_types = []
    for event in df['event']:
        if event.startswith('SEND'):
            event_types.append('SEND')
        elif event.startswith('RECEIVE'):
            event_types.append('RECEIVE')
        else:
            event_types.append('INTERNAL')
    
    df['event_type'] = event_types
    event_type_counts = df.groupby(['node_id', 'event_type']).size().unstack(fill_value=0)
    
    event_type_counts.plot(kind='bar', stacked=False, colormap='viridis')
    plt.xlabel("Node ID", fontsize=14)
    plt.ylabel("Count", fontsize=14)
    plt.title("Event Type Distribution by Node", fontsize=16)
    plt.legend(title="Event Type", fontsize=12)
    plt.grid(axis='y')
    
    plt.tight_layout(pad=3.0)
    
    # Save analysis results
    analysis_file = f"{log_dir}/{algorithm}_analysis.png"
    plt.savefig(analysis_file, dpi=300)
    print(f"\\nAnalysis visualization saved to {analysis_file}")
    
    # Create a detailed summary report
    report_file = f"{log_dir}/{algorithm}_report.txt"
    with open(report_file, 'w') as f:
        f.write(f"{algorithm.upper()} CLOCK SYNCHRONIZATION ANALYSIS\\n")
        f.write(f"{'='*50}\\n\\n")
        f.write(f"Number of nodes: {nodes}\\n")
        f.write(f"Total events: {len(df)}\\n\\n")
        
        f.write("Event counts per node:\\n")
        f.write(f"{event_counts}\\n\\n")
        
        # Clock properties explanation
        if algorithm == 'lamport':
            f.write("LAMPORT CLOCK PROPERTIES:\\n")
            f.write("1. Lamport clocks provide a partial ordering of events\\n")
            f.write("2. If event A happened before event B, then clock(A) < clock(B)\\n")
            f.write("3. However, if clock(A) < clock(B), it doesn't necessarily mean A happened before B\\n")
            f.write("4. Lamport clocks don't capture concurrent events\\n\\n")
        else:  # Vector clock
            f.write("VECTOR CLOCK PROPERTIES:\\n")
            f.write("1. Vector clocks provide a partial ordering of events\\n")
            f.write("2. If event A happened before event B, then clock(A) < clock(B) (element-wise)\\n")
            f.write("3. If clock components are incomparable, the events are concurrent\\n")
            f.write("4. Vector clocks can identify concurrent events\\n\\n")
        
        # Message pattern analysis
        f.write("MESSAGE PATTERN ANALYSIS:\\n")
        for i in range(nodes):
            sent = df[(df['node_id'] == i) & (df['event_type'] == 'SEND')].shape[0]
            received = df[(df['node_id'] == i) & (df['event_type'] == 'RECEIVE')].shape[0]
            internal = df[(df['node_id'] == i) & (df['event_type'] == 'INTERNAL')].shape[0]
            f.write(f"Node {i}: Sent {sent}, Received {received}, Internal {internal}\\n")
    
    print(f"Analysis report saved to {report_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze logical clock synchronization logs')
    parser.add_argument('--algorithm', type=str, choices=['lamport', 'vector'], required=True,
                        help='Clock synchronization algorithm')
    parser.add_argument('--nodes', type=int, required=True, help='Number of nodes')
    
    args = parser.parse_args()
    analyze_logs(args.algorithm, args.nodes)
""")

    def run_experiment(self):
        """Run the distributed system experiment"""
        # Check if docker-compose is available
        try:
            subprocess.run(["docker", "--version"], check=True, stdout=subprocess.PIPE)
            subprocess.run(["docker-compose", "--version"], check=True, stdout=subprocess.PIPE)
        except (subprocess.SubprocessError, FileNotFoundError):
            print("Error: Docker or docker-compose not found. Please install Docker and docker-compose.")
            return False
        
        # First, save original node.py
        print("Backing up original node.py to original_node.py...")
        with open("original_node.py", "w") as f:
            with open("node.py", "r") as original:
                f.write(original.read())
        
        print(f"\nStarting {self.algorithm.capitalize()} Clock experiment with {self.nodes} nodes...")
        print("Generating necessary files...")
        self.generate_files()
        
        try:
            # Build and start the containers
            print("\nBuilding Docker containers...")
            subprocess.run(["docker-compose", "build"], check=True)
            
            print("\nStarting Docker containers...")
            subprocess.run(["docker-compose", "up", "-d"], check=True)
            
            print("\nExperiment is running. Press Ctrl+C to stop it early.")
            print("Waiting for experiment to complete (this may take a few minutes)...")
            
            # Wait for experiment to complete (monitor logs)
            start_time = time.time()
            timeout = 180  # 3 minutes timeout (reduced from 5)
            
            try:
                while time.time() - start_time < timeout:
                    time.sleep(5)
                    # Check if all nodes have finished by looking for their log files
                    log_files = [f"logs/node{i}_{self.algorithm}_log.json" for i in range(self.nodes)]
                    if all(os.path.exists(f) for f in log_files):
                        print("\nAll nodes have completed. Stopping containers...")
                        break
            except KeyboardInterrupt:
                print("\nExperiment stopped by user.")
            
            # Stop containers
            subprocess.run(["docker-compose", "down"], check=True)
            
            # Analyze results
            self.analyze_results()
            
            print("\nRestoring original node.py file...")
            os.rename("original_node.py", "node.py")
            
            return True
            
        except subprocess.SubprocessError as e:
            print(f"Error running experiment: {e}")
            # Try to clean up
            try:
                subprocess.run(["docker-compose", "down"], check=False)
            except:
                pass
            return False
    
    def analyze_results(self):
        """Analyze the experiment results locally"""
        print("\nAnalyzing results...")
        
        # Load and combine all logs
        all_events = []
        for i in range(self.nodes):
            log_file = f"logs/node{i}_{self.algorithm}_log.json"
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
        
        # Add readable timestamp
        df['time'] = pd.to_datetime(df['timestamp'], unit='s')
        
        # Extract event types
        event_types = []
        for event in df['event']:
            if event.startswith('SEND'):
                event_types.append('SEND')
            elif event.startswith('RECEIVE'):
                event_types.append('RECEIVE')
            else:
                event_types.append('INTERNAL')
        
        df['event_type'] = event_types
        
        # Basic statistics
        event_counts = df.groupby(['node_id', 'event_type']).size().unstack(fill_value=0)
        print("\nEvent counts per node:")
        print(event_counts)
        
        # Set up plots with better styling
        plt.style.use('seaborn-v0_8-whitegrid')
        plt.rcParams.update({'font.size': 12})
        
        # Create a figure for visualizations
        fig = plt.figure(figsize=(16, 14))
        
        # 1. Message Graph
        plt.subplot(221)
        msg_graph = nx.DiGraph()
        
        # Add nodes
        for i in range(self.nodes):
            msg_graph.add_node(f"Node {i}")
        
        # Add edges for send events
        send_events = df[df['event_type'] == 'SEND']
        for _, event in send_events.iterrows():
            source = f"Node {event['node_id']}"
            target = f"Node {int(event['event'].split()[-1])}"
            if msg_graph.has_edge(source, target):
                msg_graph[source][target]['weight'] += 1
            else:
                msg_graph.add_edge(source, target, weight=1)
        
        pos = nx.circular_layout(msg_graph)
        edge_width = [d['weight'] * 2.0 for _, _, d in msg_graph.edges(data=True)]
        edge_labels = {(u, v): d['weight'] for u, v, d in msg_graph.edges(data=True)}
        
        nx.draw(msg_graph, pos, with_labels=True, arrows=True, 
                node_color='lightblue', node_size=1000, font_weight='bold',
                edge_color='darkblue', width=edge_width, connectionstyle='arc3,rad=0.2')
        nx.draw_networkx_edge_labels(msg_graph, pos, edge_labels=edge_labels, font_size=10)
        
        plt.title(f"Message Pattern with {self.algorithm.capitalize()} Clock", fontsize=16)
        
        # 2. Clock values progression
        plt.subplot(222)
        
        # Extract clock values based on algorithm
        if self.algorithm == 'lamport':
            # For Lamport clocks, just extract the scalar value
            df['clock_value'] = df['clock'].apply(lambda x: x if isinstance(x, (int, float)) else None)
        else:  # Vector clock
            # Create a visualization that shows the sum of vector components
            df['clock_value'] = df['clock'].apply(lambda x: sum(x) if isinstance(x, list) else None)
        
        # Plot clock values over logical time
        for i in range(self.nodes):
            node_events = df[df['node_id'] == i]
            if not node_events.empty:
                plt.plot(range(len(node_events)), node_events['clock_value'], 
                        marker='o', markersize=8, linewidth=2, label=f"Node {i}")
        
        plt.xlabel("Event Sequence", fontsize=14)
        plt.ylabel(f"{self.algorithm.capitalize()} Clock Value", fontsize=14)
        plt.title(f"{self.algorithm.capitalize()} Clock Progression", fontsize=16)
        plt.grid(True)
        plt.legend(fontsize=12)
        
        # 3. Event distribution over physical time
        plt.subplot(223)
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        
        for i in range(self.nodes):
            node_df = df[df['node_id'] == i]
            plt.scatter(node_df['time'], [i] * len(node_df), 
                      s=100, c=colors[i % len(colors)], label=f"Node {i}", alpha=0.7)
            
            # Add event type labels
            for idx, row in node_df.iterrows():
                plt.annotate(row['event_type'], 
                          (row['time'], i),
                          xytext=(0, 10), 
                          textcoords='offset points',
                          fontsize=8,
                          rotation=45)
        
        plt.yticks(range(self.nodes))
        plt.xlabel("Physical Time", fontsize=14)
        plt.ylabel("Node ID", fontsize=14)
        plt.title("Event Distribution Over Time", fontsize=16)
        plt.grid(True)
        plt.legend(fontsize=12)
        
        # 4. Event type distribution
        plt.subplot(224)
        event_counts.plot(kind='bar', stacked=False, colormap='viridis')
        plt.xlabel("Node ID", fontsize=14)
        plt.ylabel("Count", fontsize=14)
        plt.title("Event Type Distribution by Node", fontsize=16)
        plt.legend(title="Event Type", fontsize=12)
        plt.grid(axis='y')
        
        plt.tight_layout(pad=3.0)
        
        # Save analysis results
        analysis_file = f"logs/{self.algorithm}_analysis.png"
        plt.savefig(analysis_file, dpi=300)
        print(f"\nAnalysis visualization saved to {analysis_file}")
        
        # Create a detailed summary report
        report_file = f"logs/{self.algorithm}_report.txt"
        with open(report_file, 'w') as f:
            f.write(f"{self.algorithm.upper()} CLOCK SYNCHRONIZATION ANALYSIS\n")
            f.write(f"{'='*50}\n\n")
            f.write(f"Number of nodes: {self.nodes}\n")
            f.write(f"Total events: {len(df)}\n\n")
            
            f.write("Event counts per node:\n")
            f.write(f"{event_counts}\n\n")
            
            # Clock properties explanation
            if self.algorithm == 'lamport':
                f.write("LAMPORT CLOCK PROPERTIES:\n")
                f.write("1. Lamport clocks provide a partial ordering of events\n")
                f.write("2. If event A happened before event B, then clock(A) < clock(B)\n")
                f.write("3. However, if clock(A) < clock(B), it doesn't necessarily mean A happened before B\n")
                f.write("4. Lamport clocks don't capture concurrent events\n\n")
            else:  # Vector clock
                f.write("VECTOR CLOCK PROPERTIES:\n")
                f.write("1. Vector clocks provide a partial ordering of events\n")
                f.write("2. If event A happened before event B, then clock(A) < clock(B) (element-wise)\n")
                f.write("3. If clock components are incomparable, the events are concurrent\n")
                f.write("4. Vector clocks can identify concurrent events\n\n")
            
            # Message pattern analysis
            f.write("MESSAGE PATTERN ANALYSIS:\n")
            for i in range(self.nodes):
                sent = df[(df['node_id'] == i) & (df['event_type'] == 'SEND')].shape[0]
                received = df[(df['node_id'] == i) & (df['event_type'] == 'RECEIVE')].shape[0]
                internal = df[(df['node_id'] == i) & (df['event_type'] == 'INTERNAL')].shape[0]
                f.write(f"Node {i}: Sent {sent}, Received {received}, Internal {internal}\n")
        
        print(f"Analysis report saved to {report_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run logical clock synchronization experiments')
    parser.add_argument('algorithm', type=str, choices=['lamport', 'vector'], 
                        help='Clock synchronization algorithm to use')
    parser.add_argument('--nodes', type=int, default=3, help='Number of nodes (default: 3)')
    
    args = parser.parse_args()
    
    experiment = LogicalClockExperiment(args.algorithm, args.nodes)
    experiment.run_experiment()