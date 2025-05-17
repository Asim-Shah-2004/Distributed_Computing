import os
import json
import time
import random
import threading
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests
import redis
from pydantic import BaseModel, Field, ConfigDict
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich import box
from rich.pretty import Pretty
from rich.style import Style
from rich.spinner import Spinner
from rich.live import Live
from logging.handlers import RotatingFileHandler
import sys
import uvicorn


# Configure logging
def setup_logging(node_id):
    """Set up coordinated logging for the node"""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
       
    # Create a custom formatter that includes node_id
    formatter = logging.Formatter(f'%(asctime)s [{node_id}] - %(levelname)s - %(message)s')
   
    # Set up file handler
    file_handler = RotatingFileHandler(
        f'logs/{node_id}.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
   
    # Set up console handler with node-specific formatting
    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setFormatter(formatter)
   
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
   
    # Remove any existing handlers and add our handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
   
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
   
    return logging.getLogger(node_id)


# Rich console for visualizations
console = Console()


class ConsistencyModel(Enum):
    STRONG = "Strong Consistency"
    EVENTUAL = "Eventual Consistency"
    CAUSAL = "Causal Consistency"
    READ_YOUR_WRITES = "Read Your Writes"


class DataItem(BaseModel):
    """Data item stored in the distributed system"""
    value: str
    timestamp: float
    version: int
    node_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
   
    model_config = ConfigDict(
        extra="ignore",
        json_encoders={
            # Custom encoders if needed
        }
    )


class WriteRequest(BaseModel):
    key: str
    value: str


class ReplicateRequest(BaseModel):
    key: str
    data: Dict[str, Any]


class PartitionRequest(BaseModel):
    nodes: List[str]


class Node:
    def __init__(self, node_id: str, consistency_model: ConsistencyModel, port: int):
        self.node_id = node_id
        self.consistency_model = consistency_model
        self.port = port
        self.data: Dict[str, DataItem] = {}
        self.vector_clock: Dict[str, int] = {node_id: 0}
        self.lock = threading.Lock()
        self.failed = False
        self.partitioned_nodes = set()
       
        # Set up node-specific logging
        self.logger = setup_logging(node_id)
       
        # Log coordination initialization
        self.log_coordination_key = f"log_coordination"
        self.next_log_timestamp = time.time()
        self.log_lock = threading.Lock()
       
        # Initialize Redis for shared state and node registry
        self.redis_client = redis.Redis(host='redis-cache', port=6379, db=0, decode_responses=True)
        self.register_node()
       
        # Initialize FastAPI app with CORS
        self.app = FastAPI(
            title=f"Distributed Node {node_id}",
            description=f"Node implementing {consistency_model.value}",
            version="1.0.0"
        )
       
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, replace with specific origins
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
       
        # Set up routes
        self._setup_routes()
       
        # Set up enhanced visualization
        self.setup_visualization()
       
        # Start stats collection thread
        self.stats = {"operations": 0, "reads": 0, "writes": 0, "replications": 0}
        stats_thread = threading.Thread(target=self._collect_stats, daemon=True)
        stats_thread.start()


    def _setup_routes(self):
        """Set up FastAPI routes with proper status code handling"""
        from fastapi import status  # Import status here to ensure proper scoping


        @self.app.post("/write", status_code=status.HTTP_200_OK)
        async def write(request: WriteRequest):
            if self.failed:
                self.coordinated_log(f"Write rejected - node is in failed state", level="warning")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Node is in failed state"
                )
           
            try:
                self.write(request.key, request.value)
                return {"status": "success", "message": f"Successfully wrote {request.key}={request.value}"}
            except Exception as e:
                self.coordinated_log(f"Write error: {str(e)}", level="error")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Write operation failed: {str(e)}"
                )


        @self.app.get("/read/{key}", status_code=status.HTTP_200_OK)
        async def read(key: str):
            if self.failed:
                self.coordinated_log(f"Read rejected - node is in failed state", level="warning")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Node is in failed state"
                )
           
            try:
                result = self.read(key)
                if result is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Key {key} not found"
                    )
                return result.model_dump()
            except HTTPException:
                raise
            except Exception as e:
                self.coordinated_log(f"Read error: {str(e)}", level="error")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Read operation failed: {str(e)}"
                )


        @self.app.post("/replicate", status_code=status.HTTP_200_OK)
        async def replicate(request: ReplicateRequest):
            if self.failed:
                self.coordinated_log(f"Replication rejected - node is in failed state", level="warning")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Node is in failed state"
                )
           
            try:
                self.replicate_data(request.dict())
                return {"status": "success", "message": "Data replicated successfully"}
            except Exception as e:
                self.coordinated_log(f"Replication error: {str(e)}", level="error")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Replication failed: {str(e)}"
                )


        @self.app.get("/status", status_code=status.HTTP_200_OK)
        async def node_status():
            return {
                "node_id": self.node_id,
                "consistency_model": self.consistency_model.value,
                "failed": self.failed,
                "partitioned_nodes": list(self.partitioned_nodes),
                "vector_clock": self.vector_clock,
                "stats": self.stats
            }


        @self.app.post("/simulate_failure", status_code=status.HTTP_200_OK)
        async def simulate_failure():
            self.failed = True
            self.coordinated_log(f"Node {self.node_id} simulating failure", level="warning")
            return {"status": "success", "message": "Node is now in failed state"}


        @self.app.post("/simulate_recovery", status_code=status.HTTP_200_OK)
        async def simulate_recovery():
            self.failed = False
            self.coordinated_log(f"Node {self.node_id} recovered from failure", level="info")
            return {"status": "success", "message": "Node has recovered"}


        @self.app.post("/simulate_partition", status_code=status.HTTP_200_OK)
        async def simulate_partition(request: PartitionRequest):
            self.partitioned_nodes.update(request.nodes)
            self.coordinated_log(f"Network partition simulated from nodes: {', '.join(request.nodes)}", level="warning")
            return {"status": "success", "message": f"Partitioned from nodes: {request.nodes}"}


    def coordinated_log(self, message, level="info", delay=0.05):
        """Coordinated logging with Redis to prevent interleaved messages"""
        with self.log_lock:
            try:
                # Get current cluster-wide log timestamp
                timestamp = float(self.redis_client.get(self.log_coordination_key) or time.time())
               
                # Ensure our timestamp is after the current one
                self.next_log_timestamp = max(timestamp + delay, self.next_log_timestamp + delay)
               
                # Set the new timestamp
                self.redis_client.set(self.log_coordination_key, str(self.next_log_timestamp))
               
                # Brief sleep to ensure ordering
                time.sleep(delay)
               
                # Log the message with the appropriate level
                if level == "info":
                    self.logger.info(message)
                elif level == "warning":
                    self.logger.warning(message)
                elif level == "error":
                    self.logger.error(message)
                elif level == "debug":
                    self.logger.debug(message)
               
            except Exception as e:
                # Fallback to uncoordinated logging if coordination fails
                self.logger.error(f"Log coordination failed: {e}")
                if level == "info":
                    self.logger.info(message)
                elif level == "warning":
                    self.logger.warning(message)
                elif level == "error":
                    self.logger.error(message)
                elif level == "debug":
                    self.logger.debug(message)


    def _collect_stats(self):
        """Collect system stats periodically"""
        while True:
            # Record current stats to Redis for system-wide monitoring
            try:
                self.redis_client.hset(
                    f"node_stats:{self.node_id}",
                    mapping={
                        "operations": self.stats["operations"],
                        "reads": self.stats["reads"],
                        "writes": self.stats["writes"],
                        "replications": self.stats["replications"],
                        "timestamp": time.time()
                    }
                )
            except Exception as e:
                self.coordinated_log(f"Stats collection error: {str(e)}", level="error")
            time.sleep(10)  # Update every 10 seconds


    def setup_visualization(self):
        """Set up enhanced visualization using Rich"""
        self.layout = Layout()
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main")
        )
        self.layout["main"].split_row(
            Layout(name="status"),
            Layout(name="operations")
        )


    def register_node(self):
        """Register this node in Redis for discovery by other nodes"""
        try:
            # Store node information in Redis
            node_info = {
                "node_id": self.node_id,
                "address": os.getenv('HOSTNAME', 'localhost'),
                "port": self.port,
                "consistency_model": self.consistency_model.value,
                "timestamp": time.time()
            }
           
            # Store node info in Redis
            self.redis_client.hset(
                "distributed_nodes",
                self.node_id,
                json.dumps(node_info)
            )
           
            # Set expiry to enable auto-cleanup of failed nodes
            self.redis_client.expire("distributed_nodes", 60)
           
            # Start a background thread to periodically renew registration
            registry_thread = threading.Thread(target=self._registry_heartbeat, daemon=True)
            registry_thread.start()
           
            # Use spinner for visual feedback during startup
            with console.status("[bold green]Registering node...", spinner="dots"):
                time.sleep(1)  # Simulate registration process
                self.coordinated_log(f"Node {self.node_id} registered successfully with {self.consistency_model.value} model")
                console.print(Panel.fit(
                    f"[bold green]Node {self.node_id} registered successfully[/bold green]",
                    title="Node Registration",
                    border_style="green"
                ))
        except redis.RedisError as e:
            error_msg = f"Failed to register with Redis: {str(e)}"
            self.coordinated_log(error_msg, level="error")
            console.print(Panel.fit(
                f"[bold red]{error_msg}[/bold red]",
                title="Registration Error",
                border_style="red"
            ))
   
    def _registry_heartbeat(self):
        """Periodically update registration to prevent expiry"""
        while True:
            try:
                node_info = {
                    "node_id": self.node_id,
                    "address": os.getenv('HOSTNAME', 'localhost'),
                    "port": self.port,
                    "consistency_model": self.consistency_model.value,
                    "timestamp": time.time()
                }
                self.redis_client.hset(
                    "distributed_nodes",
                    self.node_id,
                    json.dumps(node_info)
                )
                self.redis_client.expire("distributed_nodes", 60)
            except Exception as e:
                self.coordinated_log(f"Heartbeat error: {str(e)}", level="error")
            time.sleep(30)  # Update every 30 seconds


    def write(self, key: str, value: str) -> None:
        with self.lock:
            self.stats["operations"] += 1
            self.stats["writes"] += 1
            current_time = time.time()
            current_version = self.vector_clock[self.node_id]
            data_item = DataItem(
                value=value,
                timestamp=current_time,
                version=current_version,
                node_id=self.node_id,
                metadata={
                    'consistency_model': self.consistency_model.value,
                    'write_time': current_time
                }
            )
            self.data[key] = data_item
            self.vector_clock[self.node_id] += 1
           
            # Store in Redis for persistence
            try:
                self.redis_client.set(f"{self.node_id}:{key}", data_item.model_dump_json())
            except redis.RedisError as e:
                self.coordinated_log(f"Redis error during write: {str(e)}", level="error")
           
            # Log write operation
            self.coordinated_log(f"Write operation: {key}={value}")
           
            # Replicate to other nodes based on consistency model
            self.replicate_to_others(key, data_item)
           
            # Enhanced visualization
            table = Table(title="Write Operation Details", box=box.ROUNDED, highlight=True)
            table.add_column("Property", style="cyan", no_wrap=True)
            table.add_column("Value", style="green")
            table.add_row("Node", self.node_id)
            table.add_row("Key", key)
            table.add_row("Value", value)
            table.add_row("Timestamp", str(current_time))
            table.add_row("Vector Clock", Pretty(self.vector_clock, expand_all=True))
           
            # Use coordinated logging to prevent interleaved output
            with self.log_lock:
                console.print(Panel.fit(
                    table,
                    title=f"[bold green]Write Operation on {self.node_id}[/bold green]",
                    border_style="green"
                ))


    def read(self, key: str) -> Optional[DataItem]:
        with self.lock:
            self.stats["operations"] += 1
            self.stats["reads"] += 1
            if key in self.data:
                # Log read operation
                self.coordinated_log(f"Read operation: {key}={self.data[key].value}")
               
                # Enhanced visualization
                table = Table(title="Read Operation Details", box=box.ROUNDED, highlight=True)
                table.add_column("Property", style="cyan", no_wrap=True)
                table.add_column("Value", style="blue")
                table.add_row("Node", self.node_id)
                table.add_row("Key", key)
                table.add_row("Value", self.data[key].value)
                table.add_row("Timestamp", str(self.data[key].timestamp))
                table.add_row("Vector Clock", Pretty(self.vector_clock, expand_all=True))
               
                # Use coordinated logging to prevent interleaved output
                with self.log_lock:
                    console.print(Panel.fit(
                        table,
                        title=f"[bold blue]Read Operation on {self.node_id}[/bold blue]",
                        border_style="blue"
                    ))
                return self.data[key]
            else:
                self.coordinated_log(f"Read operation: Key {key} not found", level="warning")
                return None


    def replicate_to_others(self, key: str, data_item: DataItem):
        """Replicate data to other nodes based on consistency model"""
        # Get all other nodes from Redis-based registry
        nodes = self.discover_nodes()
       
        for node in nodes:
            node_id = node.get("node_id")
            if node_id in self.partitioned_nodes:
                self.coordinated_log(f"Skipping replication to partitioned node {node_id}", level="warning")
                with self.log_lock:
                    console.print(Panel.fit(
                        f"[yellow]Skipping replication to partitioned node {node_id}[/yellow]",
                        title="Partition Detection"
                    ))
                continue
           
            try:
                node_address = node.get("address")
                node_port = node.get("port")
               
                # Log replication attempt
                self.coordinated_log(f"Replicating {key}={data_item.value} to {node_id}")
               
                # Show replication in progress with spinner
                with console.status(f"[cyan]Replicating to {node_id}...", spinner="dots") as status:
                    response = requests.post(
                        f'http://{node_address}:{node_port}/replicate',
                        json={
                            'key': key,
                            'data': data_item.model_dump()
                        },
                        timeout=1  # Add timeout for better failure detection
                    )
                   
                    self.stats["replications"] += 1
                   
                    if response.status_code == 503:
                        error_msg = f"Target node {node_id} is in failed state"
                        self.coordinated_log(error_msg, level="error")
                        with self.log_lock:
                            console.print(Panel.fit(
                                f"[red]{error_msg}[/red]",
                                title="Replication Failure"
                            ))
                    else:
                        self.coordinated_log(f"Successfully replicated {key} to {node_id}")
            except requests.exceptions.RequestException as e:
                error_msg = f"Failed to replicate to node {node_id}: {str(e)}"
                self.coordinated_log(error_msg, level="error")
                with self.log_lock:
                    console.print(Panel.fit(
                        f"[red]{error_msg}[/red]",
                        title="Replication Error"
                    ))


    def replicate_data(self, data: dict):
        """Handle incoming replication requests"""
        with self.lock:
            self.stats["operations"] += 1
            self.stats["replications"] += 1
            key = data['key']
            data_item = DataItem(**data['data'])
           
            if self.consistency_model == ConsistencyModel.STRONG:
                # For strong consistency, always accept the latest version
                if key not in self.data or data_item.version > self.data[key].version:
                    self.data[key] = data_item
                    self.vector_clock[data_item.node_id] = data_item.version
                    msg = f"Strong consistency: Updated {key} to {data_item.value}"
                    self.coordinated_log(msg)
                    with self.log_lock:
                        console.print(Panel.fit(
                            f"[green]{msg}[/green]",
                            title="Replication"
                        ))
            else:
                # For eventual consistency, use last-write-wins
                if key not in self.data or data_item.timestamp > self.data[key].timestamp:
                    self.data[key] = data_item
                    self.vector_clock[data_item.node_id] = data_item.version
                    msg = f"Eventual consistency: Updated {key} to {data_item.value}"
                    self.coordinated_log(msg)
                    with self.log_lock:
                        console.print(Panel.fit(
                            f"[yellow]{msg}[/yellow]",
                            title="Replication"
                        ))


    def discover_nodes(self):
        """Discover other nodes from Redis registry"""
        try:
            # Get all nodes from Redis
            nodes_data = self.redis_client.hgetall("distributed_nodes")
            nodes = []
           
            if nodes_data:
                for node_id, node_info_str in nodes_data.items():
                    if node_id != self.node_id:  # Filter out self
                        try:
                            node_info = json.loads(node_info_str)
                            nodes.append(node_info)
                        except json.JSONDecodeError as e:
                            self.coordinated_log(f"Error parsing node info: {str(e)}", level="error")
           
            return nodes
        except redis.RedisError as e:
            error_msg = f"Redis error during node discovery: {str(e)}"
            self.coordinated_log(error_msg, level="error")
            console.print(Panel.fit(
                f"[red]{error_msg}[/red]",
                title="Discovery Error"
            ))
            return []


    def run(self):
        """Start the FastAPI server"""
        self.coordinated_log(f"Node {self.node_id} starting with {self.consistency_model.value} on port {self.port}")
        uvicorn.run(
            self.app,
            host='0.0.0.0',
            port=self.port,
            log_level="info",
            access_log=True
        )


def main():
    # Get node configuration from environment variables
    node_id = os.getenv('NODE_ID', 'node1')
   
    # Fix for enum conversion
    consistency_model_str = os.getenv('CONSISTENCY_MODEL', 'EVENTUAL')
    try:
        consistency_model = ConsistencyModel[consistency_model_str]
    except KeyError:
        print(f"Invalid consistency model: {consistency_model_str}. Using EVENTUAL consistency as fallback.")
        consistency_model = ConsistencyModel.EVENTUAL
       
    port = int(os.getenv('PORT', 5000))
   
    # Display startup information
    console.print(Panel.fit(
        f"[bold]Starting Distributed Node[/bold]\n"
        f"Node ID: [cyan]{node_id}[/cyan]\n"
        f"Consistency Model: [yellow]{consistency_model.value}[/yellow]\n"
        f"Port: [green]{port}[/green]",
        title="Node Configuration",
        border_style="blue"
    ))
   
    # Create and run node
    node = Node(node_id, consistency_model, port)
    node.run()


if __name__ == "__main__":
    main()

