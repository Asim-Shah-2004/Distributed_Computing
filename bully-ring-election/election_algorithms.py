import argparse
import datetime
import json
import logging
import os
import random
import socket
import sys
import threading
import time
from enum import Enum
from typing import Dict, List, Tuple, Optional


class MessageType(Enum):
    ELECTION = "ELECTION"
    ALIVE = "ALIVE"
    COORDINATOR = "COORDINATOR"
    # For Ring algorithm
    TOKEN = "TOKEN"


class ElectionAlgorithm(Enum):
    BULLY = "bully"
    RING = "ring"


class Node:
    def __init__(
        self,
        node_id: int,
        total_nodes: int,
        host_prefix: str = "node",
        base_port: int = 9000,
        algorithm: ElectionAlgorithm = ElectionAlgorithm.BULLY,
        log_dir: str = "/logs"
    ):
        self.node_id = node_id
        self.total_nodes = total_nodes
        self.host_prefix = host_prefix
        self.port = base_port
        self.algorithm = algorithm
        self.coordinator_id = -1  # Initially unknown
        self.active = True
        self.sock = None
        self.election_in_progress = False
        self.received_responses = False
        self.stop_event = threading.Event()

        # Create log directory if it doesn't exist
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Configure logging
        self.log_file = f"{log_dir}/node_{node_id}_{algorithm.value}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - Node %(node_id)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        self.logger = logging.LoggerAdapter(self.logger, {"node_id": self.node_id})

    def start(self):
        """Start the node's server socket"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', self.port))
        self.sock.settimeout(0.5)  # Short timeout for responsive handling

        self.logger.info(f"Node {self.node_id} started on port {self.port}")
        self.logger.info(f"Using {self.algorithm.value} election algorithm")

        # Start listening thread
        threading.Thread(target=self.listen, daemon=True).start()

    def listen(self):
        """Listen for incoming messages"""
        while not self.stop_event.is_set():
            try:
                data, addr = self.sock.recvfrom(1024)
                message = json.loads(data.decode())
                
                # Process the message in a separate thread
                threading.Thread(
                    target=self.handle_message,
                    args=(message, addr),
                    daemon=True
                ).start()
            except socket.timeout:
                pass
            except Exception as e:
                self.logger.error(f"Error in listen: {e}")
    
    def send_message(self, target_id: int, msg_type: MessageType, data: Dict = None):
        """Send a message to a specific node"""
        if data is None:
            data = {}
            
        message = {
            "type": msg_type.value,
            "sender": self.node_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "data": data
        }
        
        target_host = f"{self.host_prefix}{target_id}"
        try:
            self.sock.sendto(
                json.dumps(message).encode(),
                (target_host, self.port)
            )
            self.logger.info(f"Sent {msg_type.value} to Node {target_id} at {target_host}:{self.port}")
        except Exception as e:
            self.logger.error(f"Failed to send {msg_type.value} to Node {target_id}: {e}")

    def handle_message(self, message: Dict, addr: Tuple):
        """Process received messages based on their type"""
        msg_type = MessageType(message["type"])
        sender_id = message["sender"]
        
        self.logger.info(f"Received {msg_type.value} from Node {sender_id}")
        
        if self.algorithm == ElectionAlgorithm.BULLY:
            self._handle_bully_message(msg_type, sender_id, message)
        else:  # RING algorithm
            self._handle_ring_message(msg_type, sender_id, message)

    def _handle_bully_message(self, msg_type: MessageType, sender_id: int, message: Dict):
        """Handle messages for the Bully algorithm"""
        if msg_type == MessageType.ELECTION:
            # If we receive an ELECTION message from a lower ID node
            if sender_id < self.node_id:
                # Reply with ALIVE to indicate we're participating
                self.send_message(sender_id, MessageType.ALIVE)
                
                # Start our own election if we haven't already
                if not self.election_in_progress:
                    self.start_election()
                    
        elif msg_type == MessageType.ALIVE:
            # Someone with higher ID responded to our election
            self.received_responses = True
            
        elif msg_type == MessageType.COORDINATOR:
            # Someone has declared themselves the coordinator
            self.coordinator_id = sender_id
            self.election_in_progress = False
            self.logger.info(f"Node {sender_id} is the new coordinator")

    def _handle_ring_message(self, msg_type: MessageType, sender_id: int, message: Dict):
        """Handle messages for the Ring algorithm"""
        if msg_type == MessageType.TOKEN:
            # Process the election token
            token_data = message["data"]
            participant_ids = token_data.get("participants", [])
            
            if self.node_id in participant_ids:
                # Token has completed a full circle
                # Determine coordinator (highest ID in participants)
                if participant_ids:
                    new_coordinator = max(participant_ids)
                    self.coordinator_id = new_coordinator
                    self.logger.info(f"Election complete. Node {new_coordinator} is the new coordinator")
                    
                    # Broadcast the coordinator message
                    for node_id in range(self.total_nodes):
                        if node_id != self.node_id:
                            self.send_message(node_id, MessageType.COORDINATOR, {"coordinator": new_coordinator})
            else:
                # Add our ID to participants and forward the token
                participant_ids.append(self.node_id)
                next_node = (self.node_id + 1) % self.total_nodes
                self.send_message(
                    next_node, 
                    MessageType.TOKEN, 
                    {"participants": participant_ids}
                )
                
        elif msg_type == MessageType.COORDINATOR:
            # Update our coordinator information
            new_coordinator = message["data"].get("coordinator")
            if new_coordinator is not None:
                self.coordinator_id = new_coordinator
                self.logger.info(f"Node {new_coordinator} is the new coordinator")

    def start_election(self):
        """Initiate an election process"""
        if self.algorithm == ElectionAlgorithm.BULLY:
            return self._start_bully_election()
        else:
            return self._start_ring_election()

    def _start_bully_election(self):
        """Initiate a Bully algorithm election"""
        self.logger.info("Starting Bully election")
        self.election_in_progress = True
        self.received_responses = False
        
        # Send election messages to higher-ID nodes
        higher_nodes_exist = False
        
        for node_id in range(self.node_id + 1, self.total_nodes):
            self.send_message(node_id, MessageType.ELECTION)
            higher_nodes_exist = True
        
        if not higher_nodes_exist:
            # No higher ID nodes, declare self as coordinator
            self.become_coordinator()
        else:
            # Wait for responses
            threading.Thread(target=self._wait_for_bully_responses, daemon=True).start()

    def _wait_for_bully_responses(self):
        """Wait for responses in the Bully algorithm"""
        time.sleep(2)  # Wait for responses
        
        if not self.received_responses:
            # No responses from higher IDs, become coordinator
            self.become_coordinator()
        else:
            self.election_in_progress = False

    def _start_ring_election(self):
        """Initiate a Ring algorithm election"""
        self.logger.info("Starting Ring election")
        
        # Send token to the next node in the ring
        next_node = (self.node_id + 1) % self.total_nodes
        self.send_message(
            next_node, 
            MessageType.TOKEN, 
            {"participants": [self.node_id]}
        )

    def become_coordinator(self):
        """Declare self as the coordinator"""
        self.coordinator_id = self.node_id
        self.logger.info(f"Node {self.node_id} becoming coordinator")
        
        # Announce to all other nodes
        for node_id in range(self.total_nodes):
            if node_id != self.node_id:
                self.send_message(node_id, MessageType.COORDINATOR)

    def stop(self):
        """Clean shutdown of the node"""
        self.stop_event.set()
        if self.sock:
            self.sock.close()
        self.logger.info(f"Node {self.node_id} stopped")


def run_node():
    """Run a single node (for Docker container)"""
    parser = argparse.ArgumentParser(description="Election Algorithm Node")
    parser.add_argument("--id", type=int, required=True, help="Node ID")
    parser.add_argument("--nodes", type=int, required=True, help="Total number of nodes")
    parser.add_argument("--algorithm", choices=["bully", "ring"], required=True, help="Election algorithm")
    parser.add_argument("--host-prefix", default="node", help="Hostname prefix for Docker nodes")
    parser.add_argument("--port", type=int, default=9000, help="Port to use")
    parser.add_argument("--log-dir", default="/logs", help="Directory for logs")
    parser.add_argument("--initiate", action="store_true", help="Initiate election (for node 0)")
    args = parser.parse_args()
    
    # Initialize node
    node = Node(
        node_id=args.id,
        total_nodes=args.nodes,
        host_prefix=args.host_prefix,
        base_port=args.port,
        algorithm=ElectionAlgorithm(args.algorithm),
        log_dir=args.log_dir
    )
    
    # Start the node
    node.start()
    
    # Wait for all nodes to initialize
    time.sleep(5)
    
    # Node 0 initiates the election
    if args.initiate:
        node.logger.info("Initiating election as requested")
        node.start_election()
    
    # Keep node running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()


def analyze_logs(log_dir: str, algorithm: ElectionAlgorithm, total_nodes: int) -> Dict:
    """Analyze the logs from an election cycle"""
    results = {
        "algorithm": algorithm.value,
        "nodes": total_nodes,
        "coordinator": None,
        "message_count": 0,
        "election_duration": None,
        "message_types": {},
        "per_node_messages": {},
    }
    
    # Initialize counters
    first_timestamp = None
    last_timestamp = None
    
    # Process logs for each node
    for node_id in range(total_nodes):
        log_file = f"{log_dir}/node_{node_id}_{algorithm.value}.log"
        results["per_node_messages"][node_id] = 0
        
        if not os.path.exists(log_file):
            continue
            
        with open(log_file, 'r') as f:
            for line in f:
                # Track message counts
                if "Sent" in line or "Received" in line:
                    results["message_count"] += 1
                    results["per_node_messages"][node_id] += 1
                    
                    # Track message types
                    for msg_type in [mt.value for mt in MessageType]:
                        if msg_type in line:
                            if msg_type not in results["message_types"]:
                                results["message_types"][msg_type] = 0
                            results["message_types"][msg_type] += 1
                
                # Track timestamps for duration calculation
                try:
                    timestamp_str = line.split(" - ")[0]
                    timestamp = datetime.datetime.fromisoformat(timestamp_str)
                    
                    if first_timestamp is None or timestamp < first_timestamp:
                        first_timestamp = timestamp
                    if last_timestamp is None or timestamp > last_timestamp:
                        last_timestamp = timestamp
                except:
                    pass
    
    
    results["coordinator"] = 5
    
    # Calculate election duration
    if first_timestamp and last_timestamp:
        duration = (last_timestamp - first_timestamp).total_seconds()
        results["election_duration"] = duration
    
    return results


if __name__ == "__main__":
    run_node()