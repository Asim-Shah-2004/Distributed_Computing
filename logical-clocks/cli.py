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

class ClockSynchronizationExperiment:
    def __init__(self, algorithm: str, nodes: int):
        self.algorithm = algorithm.lower()
        self.nodes = nodes
        self.log_dir = os.path.join(os.getcwd(), "logs")
        
        # Ensure logs directory exists
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Docker compose services configuration
        self.compose_config = {
            "version": "3",
            "services": {},
            "volumes": {
                "logs": {"driver": "local"}
            }
        }
        
        # Add node services
        for i in range(nodes):
            self.compose_config["services"][f"node{i}"] = {
                "build": ".",
                "command": f"python node.py --id {i} --nodes {nodes} --algorithm {algorithm} --host-prefix node",
                "volumes": ["logs:/logs"],
                "networks": ["clock_network"]
            }
        
        # Add the analyzer service
        self.compose_config["services"]["analyzer"] = {
            "build": ".",
            "command": f"python analyze_logs.py --algorithm {algorithm} --nodes {nodes}",
            "volumes": ["logs:/logs"],
            "depends_on": [f"node{i}" for i in range(nodes)],
            "networks": ["clock_network"]
        }
        
        # Add network configuration
        self.compose_config["networks"] = {
            "clock_network": {"driver": "bridge"}
        }
    
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
        
        # Log analyzer script
        with open("analyze_logs.py", "w") as f:
            f.write("""#!/usr/bin/env python3
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
    print("\nEvent counts per node:")
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
    print(f"\\nAnalysis visualization saved to {analysis_file}")
    
    # Create a summary report
    report_file = f"{log_dir}/{algorithm}_report.txt"
    with open(report_file, 'w') as f:
        f.write(f"{algorithm.upper()} CLOCK SYNCHRONIZATION ANALYSIS\\n")
        f.write(f"{'='*50}\\n\\n")
        f.write(f"Number of nodes: {nodes}\\n")
        f.write(f"Total events: {len(df)}\\n\\n")
        
        f.write("Event counts per node:\\n")
        f.write(f"{event_counts}\\n\\n")
        
        f.write("Causality Analysis:\\n")
        if algorithm == 'lamport':
            # Check for events with out-of-order Lamport clocks
            f.write("Events are ordered by Lamport timestamps.\\n")
        else:  # Vector clock
            # Check for concurrent events
            f.write("Vector clocks can identify concurrent events.\\n")
    
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
            timeout = 300  # 5 minutes timeout
            
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
        """Analyze the experiment results"""
        # Check if log files exist
        log_files = [f"logs/node{i}_{self.algorithm}_log.json" for i in range(self.nodes)]
        missing_logs = [f for f in log_files if not os.path.exists(f)]
        
        if missing_logs:
            print(f"Warning: Some log files are missing: {missing_logs}")
        
        # Run log analyzer
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
        import pandas as pd
        df = pd.DataFrame(all_events)
        
        # Basic statistics
        event_counts = df.groupby(['node_id', 'event']).size().unstack(fill_value=0)
        print("\nEvent counts per node:")
        print(event_counts)
        
        # Create visualization of message patterns
        import matplotlib.pyplot as plt
        import networkx as nx
        
        msg_graph = nx.DiGraph()
        
        # Add nodes
        for i in range(self.nodes):
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
        plt.title(f"Message Pattern with {self.algorithm.capitalize()} Clock")
        
        # Plot event timeline
        plt.subplot(222)
        for i in range(self.nodes):
            node_events = df[df['node_id'] == i]
            plt.plot(range(len(node_events)), node_events.index, marker='o', label=f"Node {i}")
        
        plt.xlabel("Event Sequence")
        plt.ylabel("Global Time Index")
        plt.title("Event Timeline")
        plt.legend()
        
        # Save analysis results
        analysis_file = f"logs/{self.algorithm}_analysis.png"
        plt.tight_layout()
        plt.savefig(analysis_file)
        print(f"\nAnalysis visualization saved to {analysis_file}")
        
        # Create a summary report
        report_file = f"logs/{self.algorithm}_report.txt"
        with open(report_file, 'w') as f:
            f.write(f"{self.algorithm.upper()} CLOCK SYNCHRONIZATION ANALYSIS\n")
            f.write(f"{'='*50}\n\n")
            f.write(f"Number of nodes: {self.nodes}\n")
            f.write(f"Total events: {len(df)}\n\n")
            
            f.write("Event counts per node:\n")
            f.write(f"{event_counts}\n\n")
            
            f.write("Causality Analysis:\n")
            if self.algorithm == 'lamport':
                # Check for events with out-of-order Lamport clocks
                f.write("Events are ordered by Lamport timestamps.\n")
            else:  # Vector clock
                # Check for concurrent events
                f.write("Vector clocks can identify concurrent events.\n")
        
        print(f"Analysis report saved to {report_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run logical clock synchronization experiments')
    parser.add_argument('algorithm', type=str, choices=['lamport', 'vector'], 
                        help='Clock synchronization algorithm to use')
    parser.add_argument('--nodes', type=int, default=3, help='Number of nodes (default: 3)')
    
    args = parser.parse_args()
    
    experiment = ClockSynchronizationExperiment(args.algorithm, args.nodes)
    experiment.run_experiment()