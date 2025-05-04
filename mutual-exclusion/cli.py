#!/usr/bin/env python3
import socket
import json
import time
import sys

# Configuration
NODE_COUNT = 5
BASE_PORT = 5000

def send_command(node_id, command_type, payload=None):
    """Send a command to a specific node"""
    host = f"node{node_id}"
    port = BASE_PORT + node_id
    
    message = {
        "type": command_type,
        "payload": payload or {},
        "sender_id": -1  # CLI has special sender ID
    }
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        s.send(json.dumps(message).encode('utf-8'))
        
        # Wait for acknowledgment
        data = s.recv(1024)
        s.close()
        
        return True
    except Exception as e:
        print(f"Error sending command to Node {node_id}: {e}")
        return False

def main():
    print("Mutual Exclusion CLI")
    print("====================")
    
    # Wait for nodes to start
    print("Waiting for nodes to start...")
    time.sleep(5)
    
    while True:
        try:
            command = input("\nEnter command: ").strip()
            
            if not command:
                continue
                
            parts = command.split()
            cmd = parts[0].lower()
            
            if cmd == "help":
                print("\nAvailable commands:")
                print("  algorithm <centralized|token_ring>  - Set mutual exclusion algorithm")
                print("  request <node_id>                   - Node requests critical section")
                print("  release <node_id>                   - Node releases critical section")
                print("  state                               - Show current state")
                print("  help                                - Show this help")
                print("  exit                                - Exit the program")
                
            elif cmd == "algorithm":
                if len(parts) < 2:
                    print("Usage: algorithm <centralized|token_ring>")
                    continue
                    
                algorithm = parts[1].lower()
                if algorithm not in ["centralized", "token_ring"]:
                    print("Unknown algorithm. Use 'centralized' or 'token_ring'")
                    continue
                
                print(f"Setting algorithm to {algorithm}...")
                # Send to node 0, which will broadcast to all nodes
                success = send_command(0, "set_algorithm", {"algorithm": algorithm})
                if success:
                    print(f"Algorithm set to {algorithm}")
                
            elif cmd == "request":
                if len(parts) < 2:
                    print("Usage: request <node_id>")
                    continue
                    
                try:
                    # Handle both "request 1" and "request node1" formats
                    node_part = parts[1]
                    if node_part.startswith("node"):
                        node_part = node_part[4:]
                        
                    node_id = int(node_part)
                    if node_id < 0 or node_id >= NODE_COUNT:
                        print(f"Invalid node ID. Must be between 0 and {NODE_COUNT-1}")
                        continue
                        
                    print(f"Requesting CS access for Node {node_id}...")
                    success = send_command(node_id, "request_command")
                    if success:
                        print(f"Request sent to Node {node_id}")
                        
                except ValueError:
                    print("Node ID must be a number")
                    
            elif cmd == "release":
                if len(parts) < 2:
                    print("Usage: release <node_id>")
                    continue
                    
                try:
                    # Handle both "release 1" and "release node1" formats
                    node_part = parts[1]
                    if node_part.startswith("node"):
                        node_part = node_part[4:]
                        
                    node_id = int(node_part)
                    if node_id < 0 or node_id >= NODE_COUNT:
                        print(f"Invalid node ID. Must be between 0 and {NODE_COUNT-1}")
                        continue
                        
                    print(f"Releasing CS for Node {node_id}...")
                    success = send_command(node_id, "release_command")
                    if success:
                        print(f"Release command sent to Node {node_id}")
                        
                except ValueError:
                    print("Node ID must be a number")
                    
            elif cmd == "state":
                print("Requesting system state...")
                success = send_command(0, "get_state")
                if success:
                    print("State request sent, check node0 logs")
                    
            elif cmd == "exit":
                print("Exiting...")
                sys.exit(0)
                
            else:
                print(f"Unknown command: {cmd}")
                print("Type 'help' for available commands")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()