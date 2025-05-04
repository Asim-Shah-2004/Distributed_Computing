#!/usr/bin/env python3
import os
import sys
import time
import socket
import signal
import random
import json
import threading
import argparse
from datetime import datetime
import queue
import logging
from typing import List, Dict, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("node")

# Global configuration
NODE_COUNT = 7
BASE_PORT = 5000
MESSAGE_TIMEOUT = 2.0  # seconds
ELECTION_TIMEOUT = 5.0  # seconds
HEARTBEAT_INTERVAL = 3.0  # seconds

# Message types
MSG_ELECTION = "ELECTION"
MSG_COORDINATOR = "COORDINATOR"
MSG_OK = "OK"
MSG_HEARTBEAT = "HEARTBEAT"

class MessageQueue:
    def __init__(self):
        self.queue = queue.Queue()
        self.lock = threading.Lock()
        
    def put(self, message):
        with self.lock:
            self.queue.put(message)
    
    def get(self, block=True, timeout=None):
        with self.lock:
            try:
                return self.queue.get(block=block, timeout=timeout)
            except queue.Empty:
                return None

class Node:
    def __init__(self, node_id: int, algorithm: str):
        self.id = node_id
        self.algorithm = algorithm.lower()
        self.ip = "node-" + str(self.id)
        self.port = BASE_PORT + self.id
        self.leader_id = -1
        self.running = True
        self.is_leader = False
        self.socket = None
        self.message_queue = MessageQueue()
        self.last_heartbeat = time.time()
        self.election_in_progress = False
        self.report_data = []
        
        # For Ring algorithm
        self.next_node_id = (self.id + 1) % NODE_COUNT
        self.ring_election_sent = False
        
    def setup_socket(self):
        """Initialize socket for communication"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('0.0.0.0', self.port))
        self.socket.settimeout(0.1)  # Non-blocking with short timeout
        logger.info(f"Node {self.id} started on port {self.port}")
        
    def send_message(self, target_id: int, msg_type: str, data: dict = None):
        """Send message to another node"""
        if data is None:
            data = {}
            
        message = {
            "type": msg_type,
            "sender": self.id,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        dest_ip = "node-" + str(target_id)
        dest_port = BASE_PORT + target_id
        
        try:
            self.socket.sendto(json.dumps(message).encode(), (dest_ip, dest_port))
            self.report_data.append({
                "time": datetime.now().isoformat(),
                "from": self.id,
                "to": target_id,
                "type": msg_type,
                "data": data
            })
            logger.info(f"Node {self.id} sent {msg_type} to Node {target_id}")
        except Exception as e:
            logger.error(f"Failed to send message to Node {target_id}: {e}")

    def broadcast_message(self, msg_type: str, data: dict = None, exclude_self: bool = True):
        """Send message to all nodes"""
        for node_id in range(NODE_COUNT):
            if exclude_self and node_id == self.id:
                continue
            self.send_message(node_id, msg_type, data)
            
    def receive_messages(self):
        """Listen for incoming messages"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                message = json.loads(data.decode())
                self.message_queue.put(message)
                
                # Log the received message
                self.report_data.append({
                    "time": datetime.now().isoformat(),
                    "from": message["sender"],
                    "to": self.id,
                    "type": message["type"],
                    "data": message["data"]
                })
                
                logger.info(f"Node {self.id} received {message['type']} from Node {message['sender']}")
            except socket.timeout:
                pass
            except Exception as e:
                if self.running:  # Only log errors if we're still supposed to be running
                    logger.error(f"Error receiving message: {e}")
    
    def process_messages(self):
        """Process incoming messages"""
        while self.running:
            message = self.message_queue.get(block=False)
            if not message:
                time.sleep(0.1)
                continue
                
            msg_type = message["type"]
            sender = message["sender"]
            
            if msg_type == MSG_ELECTION:
                self.handle_election_message(sender, message["data"])
            elif msg_type == MSG_COORDINATOR:
                self.handle_coordinator_message(sender, message["data"])
            elif msg_type == MSG_OK:
                self.handle_ok_message(sender)
            elif msg_type == MSG_HEARTBEAT:
                self.handle_heartbeat(sender)
    
    def handle_election_message(self, sender: int, data: dict):
        """Handle election message based on algorithm"""
        if self.algorithm == "bully":
            # In Bully algorithm, respond with OK if our ID is higher
            if self.id > sender:
                self.send_message(sender, MSG_OK)
                # Start our own election if we haven't already
                if not self.election_in_progress:
                    self.start_election()
        
        elif self.algorithm == "ring":
            # In Ring algorithm, forward the election message with updated IDs list
            participants = data.get("participants", [])
            
            # Add ourselves to the list if not already there
            if self.id not in participants:
                participants.append(self.id)
                
            # If the message has gone full circle
            if sender == self.id or (participants and participants[0] == self.id):
                # Find the highest ID which will be the coordinator
                new_leader = max(participants)
                # Announce the new coordinator
                self.broadcast_message(MSG_COORDINATOR, {"leader": new_leader})
                self.leader_id = new_leader
                self.is_leader = (self.id == new_leader)
                self.election_in_progress = False
                logger.info(f"Node {self.id}: Election completed, Node {new_leader} is the new coordinator")
            else:
                # Forward to next node in the ring
                self.send_message(self.next_node_id, MSG_ELECTION, {"participants": participants})
    
    def handle_coordinator_message(self, sender: int, data: dict):
        """Handle coordinator announcement"""
        new_leader = data.get("leader", -1)
        if new_leader != -1:
            self.leader_id = new_leader
            self.is_leader = (self.id == new_leader)
            self.election_in_progress = False
            logger.info(f"Node {self.id}: Node {new_leader} is now the coordinator")
        
        # If we're the new leader, start sending heartbeats
        if self.is_leader:
            threading.Thread(target=self.send_heartbeats, daemon=True).start()
    
    def handle_ok_message(self, sender: int):
        """Handle OK message (Bully algorithm)"""
        # Someone with higher ID responded, we're not going to be the leader
        self.election_in_progress = False
        logger.info(f"Node {self.id}: Received OK from Node {sender}, stopping election")
    
    def handle_heartbeat(self, sender: int):
        """Handle heartbeat from leader"""
        if sender == self.leader_id:
            self.last_heartbeat = time.time()
            logger.debug(f"Node {self.id}: Received heartbeat from leader Node {sender}")
    
    def send_heartbeats(self):
        """Send periodic heartbeats if node is the leader"""
        while self.running and self.is_leader:
            self.broadcast_message(MSG_HEARTBEAT, exclude_self=True)
            time.sleep(HEARTBEAT_INTERVAL)
    
    def monitor_leader(self):
        """Monitor leader heartbeats and start election if needed"""
        while self.running:
            if (self.leader_id != -1 and not self.is_leader and 
                time.time() - self.last_heartbeat > HEARTBEAT_INTERVAL * 2 and
                not self.election_in_progress):
                logger.info(f"Node {self.id}: Leader Node {self.leader_id} seems down, starting election")
                self.start_election()
            time.sleep(1)
    
    def start_election(self):
        """Start election based on algorithm"""
        self.election_in_progress = True
        
        if self.algorithm == "bully":
            logger.info(f"Node {self.id}: Starting Bully election")
            # Send election message to all nodes with higher IDs
            higher_nodes_exist = False
            for node_id in range(self.id + 1, NODE_COUNT):
                self.send_message(node_id, MSG_ELECTION)
                higher_nodes_exist = True
            
            # If no higher nodes, declare self as leader
            if not higher_nodes_exist:
                # Wait briefly for any OK messages
                time.sleep(1.0)  
                if self.election_in_progress:  # If no OK received
                    self.leader_id = self.id
                    self.is_leader = True
                    self.broadcast_message(MSG_COORDINATOR, {"leader": self.id})
                    logger.info(f"Node {self.id}: Elected self as coordinator")
        
        elif self.algorithm == "ring":
            if not self.ring_election_sent:
                logger.info(f"Node {self.id}: Starting Ring election")
                self.ring_election_sent = True
                # Initiate ring algorithm by sending to next node
                self.send_message(self.next_node_id, MSG_ELECTION, {"participants": [self.id]})
                
                # Reset flag after timeout
                def reset_flag():
                    time.sleep(2.0)
                    self.ring_election_sent = False
                
                threading.Thread(target=reset_flag, daemon=True).start()
    
    def start(self):
        """Start the node's operation"""
        self.setup_socket()
        
        # Start threads for message handling
        receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        process_thread = threading.Thread(target=self.process_messages, daemon=True)
        
        receive_thread.start()
        process_thread.start()
        
        # Initial election
        if self.id == 0:  # Node 0 initiates first election
            time.sleep(1)  # Give other nodes time to start
            logger.info(f"Node {self.id}: Initiating first election")
            self.start_election()
            
        # Wait for threads to complete
        while self.running:
            try:
                time.sleep(0.1)
            except KeyboardInterrupt:
                self.stop()
                break
    
    def stop(self):
        """Stop the node's operation"""
        logger.info(f"Node {self.id}: Stopping")
        self.running = False
        time.sleep(1)
        if self.socket:
            self.socket.close()
    
    def generate_report(self):
        """Generate a report of all communications"""
        report = {
            "node_id": self.id,
            "algorithm": self.algorithm,
            "final_leader": self.leader_id,
            "is_leader": self.is_leader,
            "communications": sorted(self.report_data, key=lambda x: x["time"])
        }

        # Try to save report to file
        report_json = json.dumps(report, indent=2)
        
        # First, try to write to the shared volume
        try:
            # Make sure report file doesn't exist yet
            report_path = f"/app/report_{self.id}.json"
            with open(report_path, 'w') as f:
                f.write(report_json)
            logger.info(f"Node {self.id}: Report saved to {report_path}")
        except Exception as e:
            logger.error(f"Node {self.id}: Failed to write report to /app: {e}")
            
            # Try alternate locations
            try:
                # Try current directory
                alt_path = f"./report_{self.id}.json"
                with open(alt_path, 'w') as f:
                    f.write(report_json)
                logger.info(f"Node {self.id}: Report saved to {alt_path}")
            except Exception as e:
                logger.error(f"Node {self.id}: Failed to write to current directory: {e}")
        
        # Always print report data to log as backup
        logger.info(f"NODE_REPORT_START:{self.id}")
        for line in report_json.splitlines():
            logger.info(f"REPORT_DATA:{line}")
        logger.info(f"NODE_REPORT_END:{self.id}")
        
        # Always log the leader info explicitly for easier parsing
        logger.info(f"### NODE_STATUS_INFO: ID={self.id}, LEADER={self.is_leader}, LEADER_ID={self.leader_id} ###")
        
        return report


def main():
    parser = argparse.ArgumentParser(description='Distributed Election Algorithm Node')
    parser.add_argument('--id', type=int, required=True, help='Node ID')
    parser.add_argument('--algorithm', type=str, required=True, choices=['bully', 'ring'], 
                        help='Election algorithm to use')
    args = parser.parse_args()
    
    # Print debugging information
    logger.info(f"Starting Node {args.id} with {args.algorithm} algorithm")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Contents of /app directory:")
    try:
        files = os.listdir("/app")
        logger.info(", ".join(files))
    except Exception as e:
        logger.info(f"Could not list /app directory: {e}")
    
    node = Node(args.id, args.algorithm)
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print(f"Node {args.id}: Shutting down...")
        node.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start node
    try:
        node.start()
    except Exception as e:
        logger.error(f"Node {args.id} error: {e}")
        node.stop()
    finally:
        # Save report data to multiple locations for redundancy
        report = node.generate_report()
        logger.info(f"Node {args.id}: Final leader status: {node.is_leader}, Leader ID: {node.leader_id}")
        logger.info(f"Node {args.id}: Reports generated and saved")

if __name__ == "__main__":
    main()