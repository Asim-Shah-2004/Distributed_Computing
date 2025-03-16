#!/usr/bin/env python3
import requests
import sys
import json
import time

MASTER_URL = "http://master:5000"  
NODES = {
    'monocarp': 'http://monocarp:5000',
    'polycarp': 'http://polycarp:5000',
    'pak_chenak': 'http://pak_chenak:5000',
    'master': MASTER_URL
}

def print_heading(title):
    print("\n" + "=" * 50)
    print(f"{title}")
    print("=" * 50)

def print_status(node_name, status):
    print(f"Node: {node_name}")
    print(f"Type: {status.get('type', 'unknown')}")
    print(f"Time: {status.get('formatted_time', 'unknown')}")
    print(f"Offset: {status.get('offset', 0):.6f}s")
    print(f"Drift Rate: {status.get('drift_rate', 1.0):.6f}")
    print("-" * 30)

def get_all_status():
    print_heading("CURRENT STATUS OF ALL NODES")
    
    for node_name, node_url in NODES.items():
        try:
            response = requests.post(f"{node_url}/cli", json={'command': 'status'})
            if response.status_code == 200:
                status = response.json()
                print_status(node_name, status)
            else:
                print(f"Failed to get status from {node_name}: HTTP {response.status_code}")
        except Exception as e:
            print(f"Error connecting to {node_name}: {str(e)}")

def cristian_sync():
    print_heading("INITIATING CRISTIAN'S ALGORITHM")
    
    
    for node_name, node_url in NODES.items():
        try:
            response = requests.post(f"{node_url}/cli", json={'command': 'status'})
            if response.status_code == 200:
                status = response.json()
                print(f"{node_name} before sync: {status.get('formatted_time', 'unknown')}")
        except Exception as e:
            print(f"Error connecting to {node_name}: {str(e)}")
    
    
    for node_name, node_url in NODES.items():
        if node_name != 'master':
            try:
                print(f"\nInitiating sync on {node_name}...")
                response = requests.post(f"{node_url}/cli", json={'command': 'cristian'})
                if response.status_code == 200:
                    print(f"Sync response from {node_name}: {json.dumps(response.json(), indent=2)}")
                else:
                    print(f"Failed to sync {node_name}: HTTP {response.status_code}")
            except Exception as e:
                print(f"Error connecting to {node_name}: {str(e)}")
    
    
    print("\nAfter synchronization:")
    time.sleep(1) 
    for node_name, node_url in NODES.items():
        try:
            response = requests.post(f"{node_url}/cli", json={'command': 'status'})
            if response.status_code == 200:
                status = response.json()
                print(f"{node_name} after sync: {status.get('formatted_time', 'unknown')}")
        except Exception as e:
            print(f"Error connecting to {node_name}: {str(e)}")

def berkeley_sync():
    print_heading("INITIATING BERKELEY ALGORITHM")
    
    
    for node_name, node_url in NODES.items():
        try:
            response = requests.post(f"{node_url}/cli", json={'command': 'status'})
            if response.status_code == 200:
                status = response.json()
                print(f"{node_name} before sync: {status.get('formatted_time', 'unknown')}")
        except Exception as e:
            print(f"Error connecting to {node_name}: {str(e)}")
    
    
    try:
        print("\nInitiating Berkeley algorithm on master...")
        response = requests.post(f"{MASTER_URL}/cli", json={'command': 'berkeley'})
        if response.status_code == 200:
            print(f"Berkeley algorithm response: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"Failed to execute Berkeley algorithm: HTTP {response.status_code}")
    except Exception as e:
        print(f"Error connecting to master: {str(e)}")
    
    
    print("\nAfter synchronization:")
    time.sleep(1) 
    for node_name, node_url in NODES.items():
        try:
            response = requests.post(f"{node_url}/cli", json={'command': 'status'})
            if response.status_code == 200:
                status = response.json()
                print(f"{node_name} after sync: {status.get('formatted_time', 'unknown')}")
        except Exception as e:
            print(f"Error connecting to {node_name}: {str(e)}")

def add_drift(node_name, seconds):
    print_heading(f"ADDING {seconds} SECONDS DRIFT TO {node_name}")
    
    try:
        node_url = NODES.get(node_name)
        if not node_url:
            print(f"Unknown node: {node_name}")
            return
            
        response = requests.post(f"{node_url}/cli", json={'command': 'drift', 'amount': seconds})
        if response.status_code == 200:
            print(f"Drift response: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"Failed to add drift: HTTP {response.status_code}")
    except Exception as e:
        print(f"Error connecting to {node_name}: {str(e)}")

def display_help():
    print_heading("NETWORK TIME PROTOCOL SIMULATION HELP")
    print("Available commands:")
    print("  status             - Display current time status of all nodes")
    print("  cristian           - Synchronize using Cristian's algorithm")
    print("  berkeley           - Synchronize using Berkeley algorithm")
    print("  drift <node> <sec> - Add drift to a specific node")
    print("  help               - Display this help message")
    print("  exit               - Exit the program")

def main():
    print_heading("NETWORK TIME PROTOCOL SIMULATION")
    print("Welcome to the Network Time Protocol simulation!")
    print("Type 'help' for available commands.")
    
    while True:
        try:
            command = input("\nEnter command: ").strip().lower()
            
            if command == 'exit':
                print("Exiting simulation...")
                break
            elif command == 'status':
                get_all_status()
            elif command == 'cristian':
                cristian_sync()
            elif command == 'berkeley':
                berkeley_sync()
            elif command.startswith('drift'):
                parts = command.split()
                if len(parts) != 3:
                    print("Usage: drift <node> <seconds>")
                else:
                    try:
                        node = parts[1]
                        seconds = float(parts[2])
                        add_drift(node, seconds)
                    except ValueError:
                        print("Seconds must be a number")
            elif command == 'help':
                display_help()
            else:
                print("Unknown command. Type 'help' for available commands.")
        except KeyboardInterrupt:
            print("\nExiting simulation...")
            break
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()