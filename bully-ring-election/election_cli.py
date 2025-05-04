#!/usr/bin/env python3
import os
import sys
import time
import json
import socket
import random
import subprocess
import threading
from datetime import datetime
import argparse

# Global configuration
NODE_COUNT = 7
BASE_PORT = 5000

def setup_environment():
    """Create directories and ensure the environment is ready"""
    # Create app directory if it doesn't exist with proper permissions
    os.makedirs("app", exist_ok=True)
    
    # Make sure app directory has proper permissions
    try:
        os.chmod("app", 0o777)  # Everyone can read/write
    except Exception as e:
        print(f"Warning: Could not set app directory permissions: {e}")
    
    # Copy node script to app directory
    with open("app/node.py", "w") as f:
        with open("election_algorithm_code.py", "r") as src:
            f.write(src.read())
    
    # Make the script executable
    os.chmod("app/node.py", 0o755)
    
    print("Environment setup complete.")

def start_containers():
    """Start all Docker containers"""
    print("Starting Docker containers...")
    subprocess.run(["docker-compose", "up", "-d"], check=True)
    print("Waiting for containers to be ready...")
    time.sleep(3)  # Give containers time to start
    
    # Verify containers are running
    result = subprocess.run(["docker-compose", "ps"], capture_output=True, text=True)
    print(result.stdout)

def stop_containers():
    """Stop all Docker containers"""
    print("Stopping Docker containers...")
    subprocess.run(["docker-compose", "down"], check=True)

def run_algorithm(algorithm, node_to_kill=None):
    """Run the specified election algorithm on all nodes"""
    print(f"Starting {algorithm.upper()} election algorithm...")
    
    # Start the algorithm on all nodes except the one to kill
    processes = []
    for i in range(NODE_COUNT):
        if i == node_to_kill:
            print(f"Node {i} will not be started (simulating failure)")
            continue
            
        cmd = f"docker exec node-{i} python /app/node.py --id {i} --algorithm {algorithm}"
        print(f"Starting node {i}: {cmd}")
        
        # Start process and redirect output
        process = subprocess.Popen(
            cmd, 
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        processes.append((i, process))
    
    # Print output in real-time for 10 seconds or until we detect a leader has been elected
    print(f"\nMonitoring node outputs for election cycle:")
    print("=" * 50)
    
    # Function to read output from a process and detect when election completes
    election_complete = False
    leader_found = threading.Event()
    
    def read_output(process, node_id):
        nonlocal election_complete
        for line in process.stdout:
            line_text = line.strip()
            print(f"[Node {node_id}] {line_text}")
            # Check if line indicates election is complete
            if "elected" in line_text.lower() or "is now the coordinator" in line_text.lower():
                leader_found.set()
                break
    
    # Start threads to read output
    threads = []
    for node_id, process in processes:
        thread = threading.Thread(target=read_output, args=(process, node_id))
        thread.daemon = True
        thread.start()
        threads.append(thread)
    
    # Wait for leader to be found (max 10 seconds)
    leader_found.wait(10)
    
    # Wait one more second to capture any final messages
    time.sleep(1)
    
    # Terminate all processes
    print("\nElection cycle complete. Terminating node processes...")
    for _, process in processes:
        process.terminate()
    
    # Wait for processes to finish
    for _, process in processes:
        process.wait()
    
    print("\nAlgorithm execution completed.")

def generate_report():
    """Generate a comprehensive report from all node reports"""
    print("\nGenerating final report...")
    
    # First look for reports in the expected locations
    all_communications = []
    node_reports = {}
    reports_found = False
    
    # Try to find report files
    for i in range(NODE_COUNT):
        # Check for regular files
        paths_to_check = [
            f"app/report_{i}.json", 
            f"./app/report_{i}.json",
            f"report_{i}.json"
        ]
        
        for path in paths_to_check:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                        node_reports[i] = data
                        all_communications.extend(data.get("communications", []))
                        reports_found = True
                        print(f"Found report for Node {i} at {path}")
                        break
                except Exception as e:
                    print(f"Error reading {path}: {e}")
    
    # If no files found, try to extract data from the docker logs
    if not reports_found:
        print("\nNo report files found. Trying to extract report data from logs...")
        
        for i in range(NODE_COUNT):
            try:
                # Get logs from the container
                log_cmd = f"docker logs node-{i} 2>&1 | grep -A 100 -B 0 'NODE_REPORT_START:{i}' | grep -B 100 -A 0 'NODE_REPORT_END:{i}'"
                logs = subprocess.getoutput(log_cmd)
                
                if "NODE_REPORT_START" in logs and "NODE_REPORT_END" in logs:
                    print(f"Found report data in logs for Node {i}")
                    
                    # Parse report data from logs
                    report_data = {}
                    report_json_lines = []
                    parsing = False
                    
                    for line in logs.splitlines():
                        if f"NODE_REPORT_START:{i}" in line:
                            parsing = True
                            continue
                        elif f"NODE_REPORT_END:{i}" in line:
                            parsing = False
                        elif parsing and "REPORT_DATA:" in line:
                            # Extract the JSON content
                            json_line = line.split("REPORT_DATA:", 1)[1]
                            report_json_lines.append(json_line)
                    
                    if report_json_lines:
                        try:
                            # Combine all JSON lines and parse
                            combined_json = "\n".join(report_json_lines)
                            report_data = json.loads(combined_json)
                            node_reports[i] = report_data
                            all_communications.extend(report_data.get("communications", []))
                            reports_found = True
                            
                            # Write extracted data to file for future reference
                            with open(f"app/extracted_report_{i}.json", "w") as f:
                                f.write(combined_json)
                                print(f"Saved extracted report to app/extracted_report_{i}.json")
                        except json.JSONDecodeError as e:
                            print(f"Error parsing report JSON from logs for Node {i}: {e}")
                
                # Even if JSON parsing fails, try to get leader information from logs
                if not node_reports.get(i):
                    status_cmd = f"docker logs node-{i} 2>&1 | grep '### NODE_STATUS_INFO:'"
                    status_logs = subprocess.getoutput(status_cmd)
                    if "NODE_STATUS_INFO" in status_logs:
                        print(f"Found status info for Node {i}")
                        # Parse the status info
                        for line in status_logs.splitlines():
                            if "LEADER=True" in line:
                                print(f"Node {i} is the leader!")
                                # Create a minimal report
                                node_reports[i] = {
                                    "node_id": i,
                                    "is_leader": True,
                                    "communications": []
                                }
                                reports_found = True
                                break
                        
            except Exception as e:
                print(f"Failed to extract logs from container node-{i}: {e}")
    
    # If still no reports, create a minimal template
    if not reports_found:
        print("No report data could be found from files or logs.")
        # Create template report
        with open("report.txt", 'w') as f:
            f.write(f"# Distributed Election Algorithm Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"## Configuration\n")
            f.write(f"- Algorithm: UNKNOWN (Could not extract from nodes)\n")
            f.write(f"- Number of Nodes: {NODE_COUNT}\n")
            f.write(f"- Final Leader: Node None (Could not determine leader)\n\n")
            
            f.write(f"## Communication Summary\n")
            f.write(f"- Total Messages: 0\n")
            f.write(f"- Election Messages: 0\n")
            f.write(f"- Coordinator Messages: 0\n")
            f.write(f"- OK Messages: 0\n")
            f.write(f"- Heartbeat Messages: 0\n\n")
            
            f.write(f"## Detailed Communications\n\n")
            f.write(f"| Time | From | To | Type | Details |\n")
            f.write(f"|------|------|----|----|--------|\n")
            
            f.write(f"\n\n## Algorithm Description\n\n")
            
            f.write("""
The Bully Algorithm works as follows:
1. A node detects that the coordinator is not responding.
2. It sends an ELECTION message to all nodes with higher IDs.
3. If no response is received within a timeout, the node becomes the coordinator and sends COORDINATOR messages.
4. If a higher ID node receives an ELECTION message, it sends an OK response and starts its own election.
5. The highest ID node eventually becomes the coordinator.

The Ring Algorithm works as follows:
1. Nodes are arranged in a logical ring (Node 0 -> Node 1 -> ... -> Node N-1 -> Node 0).
2. When a node detects leader failure, it initiates an election by sending an ELECTION message with its ID to the next node.
3. Each node adds its ID to the list and forwards the message.
4. When the message completes the ring, the node with the highest ID becomes the coordinator.
5. The coordinator announcement is then propagated around the ring.
            """)
            
        print("\nCould not generate proper report. Created template instead.")
        print("\nPossible fixes to try:")
        print("1. Check Docker volume mount permissions")
        print("2. Make sure the directory './app' exists and is writable")
        print("3. Run 'chmod -R 777 ./app' to ensure proper permissions")
        print("4. Run the election algorithm again")
        
        return

    # Generate the final report
    # Sort all communications by timestamp 
    all_communications = sorted(all_communications, key=lambda x: x.get("time", ""))
    
    # Find the final leader
    final_leader = None
    for node_id, report in node_reports.items():
        if report.get("is_leader", False):
            final_leader = node_id
            break
    
    # If no leader was found in the reports but we have communications
    if final_leader is None and all_communications:
        # Try to infer leader from COORDINATOR messages
        coord_messages = [m for m in all_communications if m.get("type") == "COORDINATOR"]
        if coord_messages:
            # Get the last coordinator message
            last_coord = sorted(coord_messages, key=lambda x: x.get("time", ""))[-1]
            leader_data = last_coord.get("data", {}).get("leader")
            if leader_data is not None:
                final_leader = leader_data
                print(f"Inferred leader from communications: Node {final_leader}")
    
    # Get algorithm from reports
    algorithm = next(iter(node_reports.values())).get("algorithm", "unknown") if node_reports else "unknown"
    
    # Generate the report
    report = {
        "timestamp": datetime.now().isoformat(),
        "algorithm": algorithm.upper(),
        "node_count": NODE_COUNT,
        "final_leader": final_leader if final_leader is not None else "None",
        "communication_summary": {
            "total_messages": len(all_communications),
            "election_messages": sum(1 for msg in all_communications if msg.get("type") == "ELECTION"),
            "coordinator_messages": sum(1 for msg in all_communications if msg.get("type") == "COORDINATOR"),
            "ok_messages": sum(1 for msg in all_communications if msg.get("type") == "OK"),
            "heartbeat_messages": sum(1 for msg in all_communications if msg.get("type") == "HEARTBEAT"),
        },
        "detailed_communications": all_communications
    }
    
    # Write the report
    with open("report.txt", 'w') as f:
        f.write(f"# Distributed Election Algorithm Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Configuration\n")
        f.write(f"- Algorithm: {algorithm.upper()}\n")
        f.write(f"- Number of Nodes: {NODE_COUNT}\n")
        f.write(f"- Final Leader: Node {report['final_leader']}\n\n")
        
        f.write(f"## Communication Summary\n")
        f.write(f"- Total Messages: {report['communication_summary']['total_messages']}\n")
        f.write(f"- Election Messages: {report['communication_summary']['election_messages']}\n")
        f.write(f"- Coordinator Messages: {report['communication_summary']['coordinator_messages']}\n")
        f.write(f"- OK Messages: {report['communication_summary']['ok_messages']}\n")
        f.write(f"- Heartbeat Messages: {report['communication_summary']['heartbeat_messages']}\n\n")
        
        f.write(f"## Detailed Communications\n\n")
        f.write(f"| Time | From | To | Type | Details |\n")
        f.write(f"|------|------|----|----|--------|\n")
        
        for comm in all_communications:
            time_str = comm.get("time", "").split("T")[1].split(".")[0] if "T" in comm.get("time", "") else ""
            from_node = comm.get("from", "")
            to_node = comm.get("to", "")
            msg_type = comm.get("type", "")
            details = json.dumps(comm.get("data", {}))[:50] if comm.get("data") else ""
            f.write(f"| {time_str} | Node {from_node} | Node {to_node} | {msg_type} | {details} |\n")
        
        f.write(f"\n\n## Algorithm Description\n\n")
        
        if algorithm.lower() == "bully":
            f.write("""
The Bully Algorithm works as follows:
1. A node detects that the coordinator is not responding.
2. It sends an ELECTION message to all nodes with higher IDs.
3. If no response is received within a timeout, the node becomes the coordinator and sends COORDINATOR messages.
4. If a higher ID node receives an ELECTION message, it sends an OK response and starts its own election.
5. The highest ID node eventually becomes the coordinator.
            """)
        else:
            f.write("""
The Ring Algorithm works as follows:
1. Nodes are arranged in a logical ring (Node 0 -> Node 1 -> ... -> Node N-1 -> Node 0).
2. When a node detects leader failure, it initiates an election by sending an ELECTION message with its ID to the next node.
3. Each node adds its ID to the list and forwards the message.
4. When the message completes the ring, the node with the highest ID becomes the coordinator.
5. The coordinator announcement is then propagated around the ring.
            """)
    
    print(f"\nReport successfully generated: report.txt")
    
    # Print a preview of the report
    print("\nReport Preview:")
    print("=" * 50)
    with open("report.txt", 'r') as f:
        preview_lines = [next(f, None) for _ in range(20)]
        preview_lines = [line for line in preview_lines if line is not None]
        print("".join(preview_lines))
        print("..." if len(preview_lines) == 20 else "")
    print("=" * 50)

def main():
    """Main CLI function"""
    print("=" * 50)
    print("Distributed Election Algorithm Demonstration")
    print("=" * 50)
    
    # Setup
    try:
        setup_environment()
        start_containers()
        
        while True:
            print("\nMenu:")
            print("1. Run Bully Algorithm")
            print("2. Run Ring Algorithm")
            print("3. Exit")
            
            choice = input("\nEnter your choice (1-3): ")
            
            if choice == '1' or choice == '2':
                algorithm = "bully" if choice == '1' else "ring"
                
                kill_choice = input(f"\nDo you want to kill a node? (y/n): ")
                node_to_kill = None
                
                if kill_choice.lower() == 'y':
                    kill_time = input("Kill node before starting (b) or during execution (d)? ")
                    
                    if kill_time.lower() in ['b', 'd']:
                        node_id = input(f"Enter node ID to kill (0-{NODE_COUNT-1}): ")
                        try:
                            node_id = int(node_id)
                            if 0 <= node_id < NODE_COUNT:
                                node_to_kill = node_id
                                # If killing before, set it now
                                if kill_time.lower() == 'b':
                                    pass  # Will be handled in run_algorithm
                            else:
                                print(f"Invalid node ID. Must be between 0 and {NODE_COUNT-1}.")
                                continue
                        except ValueError:
                            print("Invalid input. Node ID must be a number.")
                            continue
                
                run_algorithm(algorithm, node_to_kill)
                generate_report()
                
            elif choice == '3':
                break
            else:
                print("Invalid choice. Please try again.")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            stop_containers()
        except Exception as e:
            print(f"Error stopping containers: {e}")

if __name__ == "__main__":
    main()