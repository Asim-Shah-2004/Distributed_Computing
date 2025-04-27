import socket
import threading
import time
import json
import random
import os
import sys
from typing import Dict, List, Tuple

class Node:
    def __init__(self, node_id: int, total_nodes: int, algorithm: str, host_prefix: str = "node"):
        self.node_id = node_id
        self.total_nodes = total_nodes
        self.algorithm = algorithm.lower()  # "lamport" or "vector"
        self.port = 8000
        
        # Generate host addresses based on Docker service names
        self.hosts = [(f"{host_prefix}{i}", self.port) for i in range(total_nodes)]
        
        # Lamport's logical clock
        self.lamport_clock = 0
        
        # Vector clock (initialized with zeros)
        self.vector_clock = [0] * total_nodes
        
        # Event log for analysis
        self.event_log = []
        self.running = True
        self.message_count = 0
        self.max_messages = 20  # Limit the number of messages per node
        
        # Setup socket server
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", self.port))
        self.server_socket.listen(5)
        
        print(f"Node {self.node_id} initialized with algorithm: {self.algorithm}")
        print(f"  - Lamport clock: {self.lamport_clock}")
        print(f"  - Vector clock: {self.vector_clock}")
        
    def start(self):
        # Start server thread to listen for incoming messages
        server_thread = threading.Thread(target=self.listen_for_messages)
        server_thread.daemon = True
        server_thread.start()
        
        # Give time for all nodes to start
        time.sleep(5)
        
        # Start generating events
        event_thread = threading.Thread(target=self.generate_events)
        event_thread.daemon = True
        event_thread.start()
        
        # Wait for threads to complete
        try:
            while self.running and self.message_count < self.max_messages:
                time.sleep(1)
            
            # Allow time for final messages to be processed
            time.sleep(5)
            self.save_log()
            print(f"Node {self.node_id} completed experiment")
        except KeyboardInterrupt:
            print(f"Node {self.node_id} stopping...")
            self.running = False
            self.save_log()
    
    def listen_for_messages(self):
        print(f"Node {self.node_id} listening on port {self.port}")
        self.server_socket.settimeout(1)  # Set timeout to make it interruptible
        
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                client_handler = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_handler.daemon = True
                client_handler.start()
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Server error: {e}")
                if not self.running:
                    break
        
        self.server_socket.close()
    
    def handle_client(self, client_socket):
        try:
            data = client_socket.recv(4096)
            if data:
                message = json.loads(data.decode('utf-8'))
                self.process_message(message)
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client_socket.close()
    
    def process_message(self, message):
        sender_id = message['sender_id']
        event_type = message['event_type']
        
        if self.algorithm == "lamport":
            sender_clock = message['clock']
            # Update Lamport's clock
            self.lamport_clock = max(self.lamport_clock, sender_clock) + 1
            current_clock = self.lamport_clock
            
            clock_display = f"Lamport clock: {self.lamport_clock}"
        else:  # Vector clock
            sender_vector = message['clock']
            # Update Vector clock
            for i in range(self.total_nodes):
                if i != self.node_id:
                    self.vector_clock[i] = max(self.vector_clock[i], sender_vector[i])
            self.vector_clock[self.node_id] += 1
            current_clock = self.vector_clock.copy()
            
            clock_display = f"Vector clock: {self.vector_clock}"
        
        # Log the received message
        log_entry = {
            'timestamp': time.time(),
            'event': f"RECEIVE from Node {sender_id}",
            'description': f"Received: {event_type}",
            'clock': current_clock
        }
        self.event_log.append(log_entry)
        
        print(f"Node {self.node_id} received message from Node {sender_id}: {event_type}")
        print(f"  - Updated {clock_display}")
    
    def send_message(self, target_node: int, event_type: str):
        if not self.running or self.message_count >= self.max_messages:
            return
            
        try:
            # Update clocks before sending
            if self.algorithm == "lamport":
                self.lamport_clock += 1
                clock_value = self.lamport_clock
                clock_display = f"Lamport clock: {self.lamport_clock}"
            else:  # Vector clock
                self.vector_clock[self.node_id] += 1
                clock_value = self.vector_clock.copy()
                clock_display = f"Vector clock: {self.vector_clock}"
            
            # Create message
            message = {
                'sender_id': self.node_id,
                'event_type': event_type,
                'clock': clock_value
            }
            
            # Target host details
            target_host, target_port = self.hosts[target_node]
            
            # Log the send event
            log_entry = {
                'timestamp': time.time(),
                'event': f"SEND to Node {target_node}",
                'description': f"Sent: {event_type}",
                'clock': clock_value
            }
            self.event_log.append(log_entry)
            
            # Connect to target node
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2)
                    s.connect((target_host, target_port))
                    s.send(json.dumps(message).encode('utf-8'))
                    s.close()
                    
                    self.message_count += 1
                    print(f"Node {self.node_id} sent message to Node {target_node}: {event_type}")
                    print(f"  - Current {clock_display}")
                    break
                except (socket.error, socket.timeout) as e:
                    retry_count += 1
                    print(f"Connection failed to {target_host}:{target_port}, retry {retry_count}/{max_retries}")
                    time.sleep(1)
                    
            if retry_count == max_retries:
                print(f"Failed to send message to Node {target_node} after {max_retries} attempts")
                
        except Exception as e:
            print(f"Error sending message: {e}")
    
    def generate_events(self):
        """Generate random events (internal and message sends)"""
        event_types = ["DATABASE_UPDATE", "CACHE_REFRESH", "CONFIG_CHANGE", "TRANSACTION"]
        
        while self.running and self.message_count < self.max_messages:
            # Randomly choose between internal event or send message
            if random.random() < 0.3:  # 30% chance for internal event
                # Internal event
                event_type = random.choice(event_types)
                
                # Update clocks
                if self.algorithm == "lamport":
                    self.lamport_clock += 1
                    clock_value = self.lamport_clock
                    clock_display = f"Lamport clock: {self.lamport_clock}"
                else:  # Vector clock
                    self.vector_clock[self.node_id] += 1
                    clock_value = self.vector_clock.copy()
                    clock_display = f"Vector clock: {self.vector_clock}"
                
                # Log the internal event
                log_entry = {
                    'timestamp': time.time(),
                    'event': "INTERNAL",
                    'description': f"Internal event: {event_type}",
                    'clock': clock_value
                }
                self.event_log.append(log_entry)
                
                print(f"Node {self.node_id} internal event: {event_type}")
                print(f"  - Current {clock_display}")
            else:
                # Send message to random node
                target_node = random.choice([i for i in range(self.total_nodes) if i != self.node_id])
                event_type = random.choice(event_types)
                self.send_message(target_node, event_type)
            
            # Random delay between events
            time.sleep(random.uniform(1, 3))
    
    def save_log(self):
        """Save the event log to a file"""
        log_dir = "/logs"
        os.makedirs(log_dir, exist_ok=True)
        
        filename = f"{log_dir}/node{self.node_id}_{self.algorithm}_log.json"
        with open(filename, 'w') as f:
            json.dump(self.event_log, f, indent=2)
        
        print(f"Node {self.node_id} saved log to {filename}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Distributed System Node')
    parser.add_argument('--id', type=int, required=True, help='Node ID')
    parser.add_argument('--nodes', type=int, required=True, help='Total number of nodes')
    parser.add_argument('--algorithm', type=str, choices=['lamport', 'vector'], required=True,
                        help='Clock synchronization algorithm')
    parser.add_argument('--host-prefix', type=str, default="node", help='Host name prefix for Docker networking')
    
    args = parser.parse_args()
    
    node = Node(
        node_id=args.id,
        total_nodes=args.nodes,
        algorithm=args.algorithm,
        host_prefix=args.host_prefix
    )
    
    try:
        node.start()
    except KeyboardInterrupt:
        print(f"Node {args.id} stopping...")
        node.running = False
        node.save_log()