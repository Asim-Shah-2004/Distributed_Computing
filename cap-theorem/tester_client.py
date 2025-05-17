#!/usr/bin/env python3
import os
import sys
import time
import requests
import logging
import threading
from typing import Dict, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress
from rich import box
from rich.markdown import Markdown
from logging.handlers import RotatingFileHandler
import redis
import json


# Configure logging
def setup_logging(node_id="test-client"):
    """Set up coordinated logging for the test client"""
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


# Set up logger
logger = setup_logging()
console = Console()


class ConsistencyTester:
    def __init__(self):
        # Auto-detect environment: Docker or local
        use_docker_networking = os.environ.get('DOCKER_MODE', 'false').lower() == 'true'
       
        # Set up log coordination with Redis
        self.log_coordination_key = "log_coordination"
        self.next_log_timestamp = time.time()
        self.log_lock = threading.Lock()
       
        # Initialize Redis for log coordination
        if use_docker_networking:
            redis_host = 'redis-cache'
        else:
            redis_host = 'localhost'
           
        try:
            self.redis_client = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
           
        if use_docker_networking:
            # Docker container networking (inside Docker)
            self.nodes = {
                'node1': 'http://node-strong:5001',
                'node2': 'http://node-eventual:5002',
                'node3': 'http://node-causal:5003',
                'node4': 'http://node-read-writes:5004'
            }
            self.coordinated_log("[yellow]Using Docker container networking[/yellow]")
        else:
            # Local development (outside Docker)
            self.nodes = {
                'node1': 'http://localhost:5001',
                'node2': 'http://localhost:5002',
                'node3': 'http://localhost:5003',
                'node4': 'http://localhost:5004'
            }
            self.coordinated_log("[yellow]Using localhost networking[/yellow]")
       
        # Print connection information
        node_info = f"[bold]Connecting to nodes:[/bold]\n" + "\n".join([f"{node}: {url}" for node, url in self.nodes.items()])
       
        with self.log_lock:
            console.print(Panel.fit(
                node_info,
                title="System Configuration"
            ))


    def coordinated_log(self, message, level="info", delay=0.05):
        """Coordinated logging with Redis to prevent interleaved messages"""
        with self.log_lock:
            try:
                if self.redis_client:
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
                    logger.info(message)
                elif level == "warning":
                    logger.warning(message)
                elif level == "error":
                    logger.error(message)
                elif level == "debug":
                    logger.debug(message)
                   
                # If it's a rich-formatted message, print it as well
                if message.startswith("[") and "]" in message:
                    console.print(message)
               
            except Exception as e:
                # Fallback to uncoordinated logging if coordination fails
                logger.error(f"Log coordination failed: {e}")
                if level == "info":
                    logger.info(message)
                elif level == "warning":
                    logger.warning(message)
                elif level == "error":
                    logger.error(message)
                elif level == "debug":
                    logger.debug(message)


    def check_node_availability(self, max_retries=3, retry_delay=5):
        """Check if nodes are available with retries"""
        with self.log_lock:
            console.print(Panel.fit(
                "[bold]Checking Node Availability[/bold]",
                title="System Status"
            ))
       
        available_nodes = {}
        retry_count = 0
       
        while retry_count < max_retries:
            unavailable_nodes = []
           
            for name, url in self.nodes.items():
                if name in available_nodes:
                    continue  # Skip nodes that are already available
                   
                try:
                    self.coordinated_log(f"Checking {name} at {url}/status...")
                    response = requests.get(f"{url}/status", timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        self.coordinated_log(f"{name} ({data['consistency_model']}): Available", "info")
                        available_nodes[name] = data
                    else:
                        self.coordinated_log(f"{name}: Returned status code {response.status_code}", "warning")
                        unavailable_nodes.append(name)
                except requests.exceptions.RequestException as e:
                    self.coordinated_log(f"{name}: Not available - {str(e)}", "error")
                    unavailable_nodes.append(name)
           
            # Check if we have found all nodes
            if len(available_nodes) == len(self.nodes):
                return True, available_nodes
           
            # If not all nodes are available, retry after delay
            if retry_count < max_retries - 1 and unavailable_nodes:
                retry_count += 1
                self.coordinated_log(f"Some nodes are not available. Retrying in {retry_delay} seconds (attempt {retry_count}/{max_retries})...", "warning")
               
                with Progress() as progress:
                    task = progress.add_task("[yellow]Waiting...", total=retry_delay)
                    for _ in range(retry_delay):
                        time.sleep(1)
                        progress.update(task, advance=1)
            else:
                break
       
        # At this point, we've either found all nodes or exhausted retries
        return len(available_nodes) > 0, available_nodes


    def write_to_node(self, node_name, key, value, retries=3):
        """Write data to a node with retries"""
        url = f"{self.nodes[node_name]}/write"
        for attempt in range(retries):
            try:
                self.coordinated_log(f"Writing {key}={value} to {node_name} (attempt {attempt+1}/{retries})")
                response = requests.post(
                    url,
                    json={'key': key, 'value': value},
                    timeout=5
                )
                if response.status_code == 200:
                    self.coordinated_log(f"Successfully wrote {key}={value} to {node_name}", "info")
                    return True
                else:
                    self.coordinated_log(f"Write failed with status code {response.status_code}", "warning")
                    if attempt < retries - 1:
                        self.coordinated_log(f"Retrying in 2 seconds...", "info")
                        time.sleep(2)
                    else:
                        return False
            except requests.exceptions.RequestException as e:
                self.coordinated_log(f"Write failed: {str(e)}", "error")
                if attempt < retries - 1:
                    self.coordinated_log(f"Retrying in 2 seconds...", "info")
                    time.sleep(2)
                else:
                    return False
        return False


    def read_from_node(self, node_name, key, retries=3):
        """Read data from a node with retries"""
        url = f"{self.nodes[node_name]}/read/{key}"
        for attempt in range(retries):
            try:
                self.coordinated_log(f"Reading {key} from {node_name} (attempt {attempt+1}/{retries})")
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        self.coordinated_log(f"Value from {node_name}: {data.get('value')}", "info")
                        return data
                    else:
                        self.coordinated_log(f"Key not found on {node_name}", "warning")
                        return None
                else:
                    self.coordinated_log(f"Read failed with status code {response.status_code}", "warning")
                    if attempt < retries - 1:
                        self.coordinated_log(f"Retrying in 2 seconds...", "info")
                        time.sleep(2)
                    else:
                        return None
            except requests.exceptions.RequestException as e:
                self.coordinated_log(f"Read failed: {str(e)}", "error")
                if attempt < retries - 1:
                    self.coordinated_log(f"Retrying in 2 seconds...", "info")
                    time.sleep(2)
                else:
                    return None
        return None
   
    def test_strong_consistency(self, available_nodes):
        """Test strong consistency"""
        with self.log_lock:
            console.print(Panel.fit(
                "[bold]Testing Strong Consistency (CP System)[/bold]",
                title="Test"
            ))
       
        # Find a strong consistency node
        strong_node = None
        for name, info in available_nodes.items():
            if "Strong" in info.get('consistency_model', ''):
                strong_node = name
                break
       
        if not strong_node:
            strong_node = list(available_nodes.keys())[0]  # Fallback to first available node
            self.coordinated_log(f"No Strong Consistency node found, using {strong_node} instead", "warning")
       
        # Write to strong consistency node
        test_key = "strong_test"
        test_value = f"Value-A"  # More readable value
       
        if self.write_to_node(strong_node, test_key, test_value):
            time.sleep(1)  # Allow for replication
           
            # Read from all available nodes
            table = Table(title="Strong Consistency Results", box=box.ROUNDED)
            table.add_column("Node", style="cyan")
            table.add_column("Consistency Model", style="magenta")
            table.add_column("Value", style="green")
           
            results = {}
            for name, info in available_nodes.items():
                result = self.read_from_node(name, test_key)
                value = result.get('value') if result else "Not Found"
                results[name] = value
                table.add_row(
                    name,
                    info.get('consistency_model', 'Unknown'),
                    value
                )
           
            with self.log_lock:
                console.print(table)
           
            # Check if all nodes have the same value
            all_consistent = len(set(results.values())) == 1
           
            # Add explanation
            explanation = f"""
            ### Strong Consistency Explanation
           
            **What we tested:**
            - Wrote value "{test_value}" to node "{strong_node}" (Strong Consistency)
            - Read the value from all available nodes immediately after
           
            **Results:**
            {"- All nodes returned the same value immediately ✓" if all_consistent else "- Not all nodes have the same value ✗"}
           
            **How this demonstrates Strong Consistency:**
            - Strong consistency guarantees that all nodes see the same value at the same time
            - Reads return the most recently written value, regardless of which node you read from
            - This is the "C" in CAP theorem (Consistency over Availability)
            - Trade-off: Strong consistency requires synchronous replication which can increase latency
            """
           
            with self.log_lock:
                console.print(Markdown(explanation))


    def test_eventual_consistency(self, available_nodes):
        """Test eventual consistency"""
        with self.log_lock:
            console.print(Panel.fit(
                "[bold]Testing Eventual Consistency (AP System)[/bold]",
                title="Test"
            ))
       
        # Find an eventual consistency node
        eventual_node = None
        for name, info in available_nodes.items():
            if "Eventual" in info.get('consistency_model', ''):
                eventual_node = name
                break
       
        if not eventual_node:
            # Find a node that's not strong consistency
            options = [n for n, i in available_nodes.items()
                       if "Strong" not in i.get('consistency_model', '')]
            eventual_node = options[0] if options else list(available_nodes.keys())[0]
            self.coordinated_log(f"No Eventual Consistency node found, using {eventual_node} instead", "warning")
       
        # Write to eventual consistency node
        test_key = "eventual_test"
        test_value = f"Value-B"  # More readable value
       
        if self.write_to_node(eventual_node, test_key, test_value):
            # Read immediately from all nodes
            self.coordinated_log("Reading immediately after write:", "info")
            table_before = Table(title="Immediate Results", box=box.ROUNDED)
            table_before.add_column("Node", style="cyan")
            table_before.add_column("Consistency Model", style="magenta")
            table_before.add_column("Value", style="green")
           
            before_results = {}
            for name, info in available_nodes.items():
                result = self.read_from_node(name, test_key)
                value = result.get('value') if result else "Not Found"
                before_results[name] = value
                table_before.add_row(
                    name,
                    info.get('consistency_model', 'Unknown'),
                    value
                )
           
            with self.log_lock:
                console.print(table_before)
           
            # Wait and read again
            self.coordinated_log("Waiting for eventual consistency to propagate...", "info")
            time.sleep(3)
           
            self.coordinated_log("Reading after delay:", "info")
            table_after = Table(title="After Delay Results", box=box.ROUNDED)
            table_after.add_column("Node", style="cyan")
            table_after.add_column("Consistency Model", style="magenta")
            table_after.add_column("Value", style="green")
           
            after_results = {}
            for name, info in available_nodes.items():
                result = self.read_from_node(name, test_key)
                value = result.get('value') if result else "Not Found"
                after_results[name] = value
                table_after.add_row(
                    name,
                    info.get('consistency_model', 'Unknown'),
                    value
                )
           
            with self.log_lock:
                console.print(table_after)
           
            # Check if all nodes have the same value after delay
            initially_consistent = len(set(before_results.values())) == 1
            eventually_consistent = len(set(after_results.values())) == 1
           
            # Add explanation
            explanation = f"""
            ### Eventual Consistency Explanation
           
            **What we tested:**
            - Wrote value "{test_value}" to node "{eventual_node}" (Eventual Consistency)
            - Read from all nodes immediately after write
            - Waited 3 seconds for replication
            - Read from all nodes again
           
            **Results:**
            - Immediate reads: {"All consistent ✓" if initially_consistent else "Different values across nodes ✓"}
            - After delay: {"All consistent ✓" if eventually_consistent else "Still inconsistent ✗"}
           
            **How this demonstrates Eventual Consistency:**
            - Eventual consistency guarantees that all nodes will eventually return the same value
            - Some nodes may initially return stale data after a write
            - After sufficient time for replication, all nodes eventually converge
            - This is the "A" in CAP theorem (Availability over Consistency)
            - Trade-off: Better availability but temporary inconsistency is possible
            """
           
            with self.log_lock:
                console.print(Markdown(explanation))


    def test_causal_consistency(self, available_nodes):
        """Test causal consistency"""
        # Find a causal consistency node
        causal_node = None
        for name, info in available_nodes.items():
            if "Causal" in info.get('consistency_model', ''):
                causal_node = name
                break
               
        if not causal_node:
            self.coordinated_log("No Causal Consistency node found, skipping test", "warning")
            return
           
        with self.log_lock:
            console.print(Panel.fit(
                "[bold]Testing Causal Consistency[/bold]",
                title="Test"
            ))
       
        # First write
        first_key = "causal_first"
        first_value = "First-Event"
       
        # Second write (causally dependent on the first)
        second_key = "causal_second"
        second_value = "Second-Event"
       
        # Write the first value
        if self.write_to_node(causal_node, first_key, first_value):
            time.sleep(0.5)
           
            # Write the second value
            if self.write_to_node(causal_node, second_key, second_value):
                time.sleep(1)  # Allow for replication
               
                # Read from all nodes
                results = {}
                for name in available_nodes:
                    node_result = {}
                    # Read first key
                    first_result = self.read_from_node(name, first_key)
                    first_value_read = first_result.get('value') if first_result else None
                   
                    # Read second key
                    second_result = self.read_from_node(name, second_key)
                    second_value_read = second_result.get('value') if second_result else None
                   
                    results[name] = {
                        'first': first_value_read,
                        'second': second_value_read
                    }
               
                # Display results in a table
                table = Table(title="Causal Consistency Results", box=box.ROUNDED)
                table.add_column("Node", style="cyan")
                table.add_column("First Event", style="green")
                table.add_column("Second Event", style="yellow")
                table.add_column("Causality Preserved", style="magenta")
               
                causal_violations = 0
                for name, result in results.items():
                    first = result['first']
                    second = result['second']
                   
                    # Check if causality is preserved
                    causality_preserved = "N/A"
                    if first is None and second is not None:
                        causality_preserved = "✗"  # Violation - saw effect without cause
                        causal_violations += 1
                    elif first is not None and second is not None:
                        causality_preserved = "✓"  # Correct - saw both cause and effect
                    elif first is not None and second is None:
                        causality_preserved = "?"  # Ambiguous - saw cause but not effect
                    else:
                        causality_preserved = "?"  # Ambiguous - saw neither
                       
                    table.add_row(
                        name,
                        str(first),
                        str(second),
                        causality_preserved
                    )
                   
                with self.log_lock:
                    console.print(table)
               
                # Add explanation
                explanation = f"""
                ### Causal Consistency Explanation
               
                **What we tested:**
                - Wrote two causally related values to node "{causal_node}"
                  1. First event: "{first_key}" = "{first_value}"
                  2. Second event: "{second_key}" = "{second_value}" (dependent on first)
                - Read both values from all nodes
               
                **Results:**
                - Causal violations: {causal_violations}
               
                **How this demonstrates Causal Consistency:**
                - Causal consistency guarantees that operations that are causally related are seen in the same order by all nodes
                - If a node can see the second event, it must also see the first event that caused it
                - Prevents "reading the effect before the cause" situations
                - More relaxed than strong consistency, but stronger than eventual consistency
                - Especially important for applications with dependencies between operations
                """
               
                with self.log_lock:
                    console.print(Markdown(explanation))


def main():
    with console.status("", spinner="dots") as status:
        console.print(Panel.fit(
            "[bold]Distributed System Consistency Models Test[/bold]",
            title="System Test"
        ))
   
    # Create tester instance
    tester = ConsistencyTester()
   
    # Wait for services to be ready
    tester.coordinated_log("Waiting for all services to be ready...", "info")
    time.sleep(3)
   
    # Check node availability
    success, available_nodes = tester.check_node_availability(max_retries=3, retry_delay=5)
   
    if success:
        tester.coordinated_log(f"Found {len(available_nodes)} available nodes!", "info")
       
        # Run consistency tests
        tester.test_strong_consistency(available_nodes)
        time.sleep(2)
       
        tester.test_eventual_consistency(available_nodes)
        time.sleep(2)
       
        tester.test_causal_consistency(available_nodes)
        time.sleep(2)
       
        tester.coordinated_log("Tests completed successfully!", "info")
    else:
        tester.coordinated_log("No nodes are available. Please check the system.", "error")
        return 1
   
    return 0


if __name__ == "__main__":
    sys.exit(main())
