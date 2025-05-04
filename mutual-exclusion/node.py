#!/usr/bin/env python3
import socket
import time
import json
import threading
import sys
import os
import random
from collections import deque
import queue

# Configuration
NODE_COUNT = 5
BASE_PORT = 5000
HOST = '0.0.0.0'  # Listen on all interfaces
COORDINATOR_PORT = 6000

class Node:
    def __init__(self, node_id):
        self.node_id = node_id
        self.port = BASE_PORT + node_id
        self.algorithm = None  # 'centralized' or 'token_ring'
        self.is_coordinator = False
        self.has_token = False
        self.request_queue = deque()
        self.in_critical_section = False
        self.coordinator_id = None
        self.token_holder = None
        self.neighbors = {}  # {node_id: (host, port)}
        self.stop_flag = False
        self.message_queue = queue.Queue()
        self.waiting_for_token = False
        
        # For visualization
        self.queue_state = []
        
        # Initialize sockets
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((HOST, self.port))
        self.server_socket.listen(10)
        
        print(f"Node {self.node_id} started on port {self.port}")
        
        # Start server thread
        self.server_thread = threading.Thread(target=self.listen_for_connections)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Start message processor thread
        self.processor_thread = threading.Thread(target=self.process_messages)
        self.processor_thread.daemon = True
        self.processor_thread.start()
        
    def discover_nodes(self):
        """Initialize connections to other nodes"""
        # Connect to all other nodes
        for i in range(NODE_COUNT):
            if i != self.node_id:
                host = f"node{i}"  # Docker container name
                port = BASE_PORT + i
                self.neighbors[i] = (host, port)
        
        print(f"Node {self.node_id} discovered peers: {self.neighbors}")
        
    def listen_for_connections(self):
        """Listen for incoming connections from other nodes"""
        while not self.stop_flag:
            try:
                client_socket, address = self.server_socket.accept()
                client_handler = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_handler.daemon = True
                client_handler.start()
            except Exception as e:
                if not self.stop_flag:
                    print(f"Error accepting connection: {e}")
    
    def handle_client(self, client_socket):
        """Handle messages from a connected client"""
        try:
            data = client_socket.recv(4096)
            if data:
                message = json.loads(data.decode('utf-8'))
                self.message_queue.put(message)
                
                # Send acknowledgment for certain message types
                if message.get('type') in ['set_algorithm', 'request_cs', 'release_cs', 'get_state', 'request_command', 'release_command', 'get_algorithm']:
                    response = {}
                    
                    # For state requests, include the current state
                    if message.get('type') == 'get_state':
                        if self.algorithm == 'centralized':
                            if self.is_coordinator:
                                response = {
                                    'queue': list(self.request_queue),
                                    'in_cs': self.token_holder
                                }
                            else:
                                response = {
                                    'in_cs': self.in_critical_section
                                }
                        elif self.algorithm == 'token_ring':
                            response = {
                                'has_token': self.has_token,
                                'in_cs': self.in_critical_section,
                                'waiting': self.waiting_for_token
                            }
                    elif message.get('type') == 'get_algorithm':
                        response = {
                            'algorithm': self.algorithm
                        }
                    else:
                        response = {'status': 'ok'}
                        
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    
        except Exception as e:
            if not self.stop_flag:
                print(f"Error handling client: {e}")
        finally:
            client_socket.close()
            
    def process_messages(self):
        """Process messages from the queue"""
        while not self.stop_flag:
            try:
                if not self.message_queue.empty():
                    message = self.message_queue.get()
                    self.handle_message(message)
                time.sleep(0.1)
            except Exception as e:
                if not self.stop_flag:
                    print(f"Error processing message: {e}")
    
    def handle_message(self, message):
        """Handle different types of messages"""
        msg_type = message.get('type')
        
        if msg_type == 'election':
            self.handle_election_message(message)
        elif msg_type == 'coordinator_announcement':
            self.handle_coordinator_announcement(message)
        elif msg_type == 'request_cs':
            self.handle_request_cs(message)
        elif msg_type == 'release_cs':
            self.handle_release_cs(message)
        elif msg_type == 'grant_cs':
            self.handle_grant_cs(message)
        elif msg_type == 'token_passing':
            self.handle_token(message)
        elif msg_type == 'set_algorithm':
            algorithm = message.get('payload', {}).get('algorithm')
            if algorithm:
                self.set_algorithm(algorithm)
                # Broadcast to other nodes
                if self.node_id == 0:
                    for node_id in range(1, NODE_COUNT):
                        self.send_message(node_id, {
                            'type': 'set_algorithm',
                            'payload': {'algorithm': algorithm}
                        })
        elif msg_type == 'request_command':
            self.request_critical_section()
        elif msg_type == 'release_command':
            self.release_critical_section()
        elif msg_type == 'get_state':
            state = self.visualize_state()
            print("\nCurrent State:")
            print(state)
            
    def handle_election_message(self, message):
        """Handle election messages for centralized algorithm"""
        candidate_id = message.get('candidate_id')
        print(f"Node {self.node_id} received election message from Node {message.get('sender_id')} with candidate {candidate_id}")
        
        # If we have a higher ID, we become the candidate
        if self.node_id > candidate_id:
            # Broadcast our candidacy
            self.broadcast_message({
                'type': 'election',
                'sender_id': self.node_id,
                'candidate_id': self.node_id
            })
        
    def handle_coordinator_announcement(self, message):
        """Handle coordinator announcement messages"""
        coordinator_id = message.get('coordinator_id')
        print(f"Node {self.node_id} received coordinator announcement: Node {coordinator_id} is coordinator")
        self.coordinator_id = coordinator_id
        self.is_coordinator = (self.node_id == coordinator_id)
        
        if self.is_coordinator:
            print(f"Node {self.node_id} is now the coordinator!")
            # Initialize empty queue for CS requests
            self.request_queue = deque()
            
    def handle_request_cs(self, message):
        """Handle request for critical section"""
        if self.algorithm == 'centralized' and self.is_coordinator:
            requester_id = message.get('sender_id')
            print(f"Coordinator received CS request from Node {requester_id}")
            
            if not self.request_queue and not self.in_critical_section:
                # Grant access immediately
                self.send_message(requester_id, {
                    'type': 'grant_cs',
                    'sender_id': self.node_id
                })
                self.in_critical_section = True
                self.token_holder = requester_id
            else:
                # Add to queue
                self.request_queue.append(requester_id)
                print(f"Added Node {requester_id} to queue. Current queue: {list(self.request_queue)}")
            
            # Update queue state for visualization
            self.queue_state = list(self.request_queue)
            
    def handle_release_cs(self, message):
        """Handle release of critical section"""
        if self.algorithm == 'centralized' and self.is_coordinator:
            released_by = message.get('sender_id')
            print(f"Coordinator received CS release from Node {released_by}")
            
            if self.token_holder == released_by:
                self.in_critical_section = False
                self.token_holder = None
                
                # Grant access to next in queue if any
                if self.request_queue:
                    next_node = self.request_queue.popleft()
                    self.send_message(next_node, {
                        'type': 'grant_cs',
                        'sender_id': self.node_id
                    })
                    self.in_critical_section = True
                    self.token_holder = next_node
                    print(f"Granted CS to next node: {next_node}")
                
                # Update queue state for visualization
                self.queue_state = list(self.request_queue)
                
    def handle_grant_cs(self, message):
        """Handle grant of critical section"""
        print(f"Node {self.node_id} was granted access to critical section")
        self.in_critical_section = True
        
    def handle_token(self, message):
        """Handle token passing in token ring algorithm"""
        sender_id = message.get('sender_id')
        print(f"Node {self.node_id} received the token from Node {sender_id}")
        self.has_token = True
        
        # Update global token holder state - important for state requests
        self.token_holder = self.node_id
        
        # If we want to enter CS, use the token
        if self.in_critical_section or self.waiting_for_token:
            print(f"Node {self.node_id} is using the token to enter CS")
            self.in_critical_section = True
            self.waiting_for_token = False
            time.sleep(1)  # Simulate CS access
            
            # We're done with CS
            self.in_critical_section = False
            
        # Pass token to next node
        self.pass_token()
        
    def pass_token(self):
        """Pass token to the next node in the ring"""
        next_node = (self.node_id + 1) % NODE_COUNT
        print(f"Node {self.node_id} passing token to Node {next_node}")
        
        time.sleep(1)  # 1 second delay before passing token
        
        self.send_message(next_node, {
            'type': 'token_passing',
            'sender_id': self.node_id
        })
        
        self.has_token = False
        self.token_holder = next_node  # Update token holder reference before passing
        
    def send_message(self, target_node_id, message):
        """Send a message to a specific node"""
        if target_node_id not in self.neighbors and target_node_id != self.node_id:
            print(f"Unknown node ID: {target_node_id}")
            return
            
        try:
            if target_node_id == self.node_id:
                # Put message in our own queue
                self.message_queue.put(message)
                return
                
            target_host, target_port = self.neighbors[target_node_id]
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((target_host, target_port))
            client_socket.send(json.dumps(message).encode('utf-8'))
            client_socket.close()
        except Exception as e:
            print(f"Error sending message to Node {target_node_id}: {e}")
            
    def broadcast_message(self, message):
        """Send a message to all other nodes"""
        for node_id in self.neighbors:
            self.send_message(node_id, message)
            
    def start_election(self):
        """Start an election process (bully algorithm)"""
        print(f"Node {self.node_id} starting election")
        
        # First, broadcast our candidacy
        self.broadcast_message({
            'type': 'election',
            'sender_id': self.node_id,
            'candidate_id': self.node_id
        })
        
        # Wait for responses (in a real implementation, we'd wait for acknowledgments)
        time.sleep(2)
        
        # For simplicity, the highest ID always wins
        coordinator_id = max(range(NODE_COUNT))
        
        # Announce the coordinator
        self.broadcast_message({
            'type': 'coordinator_announcement',
            'sender_id': self.node_id,
            'coordinator_id': coordinator_id
        })
        
        # Also process the announcement ourselves
        self.handle_coordinator_announcement({
            'coordinator_id': coordinator_id
        })
        
    def request_critical_section(self):
        """Request access to the critical section"""
        if self.algorithm == 'centralized':
            if self.in_critical_section:
                print(f"Node {self.node_id} is already in critical section")
                return
                
            print(f"Node {self.node_id} requesting critical section from coordinator {self.coordinator_id}")
            self.send_message(self.coordinator_id, {
                'type': 'request_cs',
                'sender_id': self.node_id
            })
            
        elif self.algorithm == 'token_ring':
            # In token ring, we mark that we want to enter CS when we get the token
            print(f"Node {self.node_id} wants to enter critical section when token arrives")
            if self.has_token:
                self.in_critical_section = True
                print(f"Node {self.node_id} already has the token and enters CS")
                time.sleep(1)  # Simulate CS access
                self.in_critical_section = False
                self.pass_token()
            else:
                self.waiting_for_token = True
                self.in_critical_section = False
            
    def release_critical_section(self):
        """Release the critical section"""
        if not self.in_critical_section:
            print(f"Node {self.node_id} is not in critical section")
            return
            
        if self.algorithm == 'centralized':
            print(f"Node {self.node_id} releasing critical section")
            self.in_critical_section = False
            self.send_message(self.coordinator_id, {
                'type': 'release_cs',
                'sender_id': self.node_id
            })
            
        elif self.algorithm == 'token_ring':
            # In token ring, we just mark that we don't want to enter CS
            print(f"Node {self.node_id} no longer wants to enter critical section")
            self.in_critical_section = False
            self.waiting_for_token = False
            
    def start_token_ring(self):
        """Initialize token ring algorithm"""
        print(f"Starting token ring algorithm")
        
        # Reset all token-related state
        self.in_critical_section = False
        self.waiting_for_token = False
        
        if self.node_id == 0:  # Node 0 starts with the token
            self.has_token = True
            self.token_holder = 0
            print(f"Node {self.node_id} has the initial token")
            
            # Start token circulation
            self.pass_token()
        else:
            self.has_token = False
            self.token_holder = 0  # Initialize token holder to Node 0
            
    def set_algorithm(self, algorithm):
        """Set the mutual exclusion algorithm to use"""
        self.algorithm = algorithm
        print(f"Node {self.node_id} set algorithm to: {algorithm}")
        
        if algorithm == 'centralized':
            self.start_election()
        elif algorithm == 'token_ring':
            self.start_token_ring()
            
    def visualize_state(self):
        """Return a visualization of the current state"""
        if self.algorithm == 'centralized':
            output = []
            output.append(f"Coordinator: Node {self.coordinator_id}")
            
            if self.is_coordinator:
                if self.token_holder is not None:
                    output.append(f"Current CS holder: Node {self.token_holder}")
                else:
                    output.append("No node is in critical section")
                    
                output.append("Queue state:")
                if not self.queue_state:
                    output.append("  [Empty]")
                else:
                    queue_viz = " → ".join([f"Node {n}" for n in self.queue_state])
                    output.append(f"  {queue_viz}")
                    
            else:
                output.append(f"My state: {'In CS' if self.in_critical_section else 'Not in CS'}")
                
        elif self.algorithm == 'token_ring':
            output = []
            output.append(f"Token holder: Node {self.token_holder}")
            output.append(f"My state: {('In CS' if self.in_critical_section else ('Waiting for token' if self.waiting_for_token else 'Idle'))}")
            
            # Create ring visualization
            ring = ["┌"] + ["───"] * NODE_COUNT + ["┐"]
            nodes = ["|"]
            for i in range(NODE_COUNT):
                if i == self.token_holder:
                    nodes.append("(T)")
                else:
                    nodes.append(" o ")
            nodes.append("|")
            bottom = ["└"] + ["───"] * NODE_COUNT + ["┘"]
            
            labels = [" "]
            for i in range(NODE_COUNT):
                labels.append(f" {i} ")
            labels.append(" ")
            
            output.append("Token ring:")
            output.append("".join(ring))
            output.append("".join(nodes))
            output.append("".join(bottom))
            output.append("".join(labels))
            
        return "\n".join(output)
        
    def shutdown(self):
        """Gracefully shut down the node"""
        print(f"Node {self.node_id} shutting down")
        self.stop_flag = True
        self.server_socket.close()

def main():
    if len(sys.argv) < 2:
        print("Usage: python node.py <node_id>")
        sys.exit(1)
        
    node_id = int(sys.argv[1])
    node = Node(node_id)
    
    # Wait for all nodes to be up
    time.sleep(5)
    node.discover_nodes()
    
    # Wait for commands
    try:
        while True:
            time.sleep(0.1)
            
            # Handle messages from queue
            while not node.message_queue.empty():
                message = node.message_queue.get()
                node.handle_message(message)
                
    except KeyboardInterrupt:
        pass
    finally:
        node.shutdown()

if __name__ == "__main__":
    main()