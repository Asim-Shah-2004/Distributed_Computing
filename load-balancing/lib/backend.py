import http.server
import socketserver
import json
import threading
import time
import random
import math
import os
from datetime import datetime
from pathlib import Path
from lib.utils import setup_logging

class BackendHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, server_id=None, **kwargs):
        self.server_id = server_id
        self.logger = setup_logging(f"Backend-{server_id}")
        self.failure_chance = 0.1  # 10% chance of failure per request
        super().__init__(*args, **kwargs)

    def calculate_factorial(self, n):
        """Calculate factorial with additional CPU load"""
        result = 1
        # Add extra computational work
        temp_results = []
        
        for i in range(1, n + 1):
            result *= i
            # Every 5 numbers (was 10), do some extra calculations to increase intensity
            if i % 5 == 0:
                # Do some floating-point math to increase CPU load - more iterations
                for _ in range(5000):  # Increased from 1000
                    temp_results.append(math.sin(result % 360) * math.cos(result % 360) * math.tan(result % 89))
                # Keep only last 200 results to manage memory
                temp_results = temp_results[-200:]
                
        return result

    def perform_intensive_calculation(self):
        start_time = time.time()
        
        # Calculate multiple large factorials
        results = {}
        total_calculations = 0
        
        # Calculate factorials of different sizes - increased sizes
        factorial_numbers = [
            random.randint(100, 150),     # Was 50-100
            random.randint(150, 200),     # Was 100-150
            random.randint(200, 250),     # Was 150-200
            random.randint(250, 300)      # Adding a fourth, even larger calculation
        ]
        
        for n in factorial_numbers:
            try:
                result = self.calculate_factorial(n)
                results[f"factorial_{n}"] = str(result)  # Convert to string to handle large numbers
                total_calculations += 1
            except Exception as e:
                self.logger.error(f"Error calculating factorial of {n}: {str(e)}")
                results[f"factorial_{n}"] = f"Error: {str(e)}"
        
        # Add some random delay to simulate I/O operations - increased
        time.sleep(random.uniform(0.2, 0.5))  # Was 0.1-0.3
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        return processing_time, {
            "calculations_performed": total_calculations,
            "factorial_results": results,
            "processing_time_ms": round(processing_time * 1000, 2)
        }

    def do_GET(self):
        try:
            # Simulate server failure randomly
            if random.random() < self.failure_chance:
                self.logger.error(f"Simulated server failure on {self.server_id}")
                self.send_error(503, "Server temporarily unavailable")
                return
                
            # Add small initial delay to simulate network latency
            time.sleep(random.uniform(0.05, 0.2))  # Increased upper bound
            
            processing_time, calculation_results = self.perform_intensive_calculation()
            
            response = {
                "server_id": self.server_id,
                "message": "Factorial calculations complete",
                "timestamp": datetime.now().isoformat(),
                "processing_time": round(processing_time, 4),
                "results": calculation_results
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Connection', 'close')  # Important for load balancer testing
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            self.logger.error(f"Request processing error: {str(e)}")
            self.send_error(500, f"Internal server error: {str(e)}")

class BackendServer:
    def __init__(self, server_id, port):
        self.server_id = server_id
        self.port = port
        self._server = None
        self._thread = None
        self.failure_thread = None
        self.is_running = False

    def start(self):
        handler = lambda *args: BackendHandler(*args, server_id=self.server_id)
        self._server = socketserver.TCPServer(("", self.port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.daemon = True
        self._thread.start()
        self.is_running = True
        
        # Start the random failure simulation thread
        self.failure_thread = threading.Thread(target=self._simulate_random_failures)
        self.failure_thread.daemon = True
        self.failure_thread.start()

    def _simulate_random_failures(self):
        """Periodically simulate server crashes and recoveries"""
        logger = setup_logging(f"Failure-{self.server_id}")
        while self.is_running:
            # Sleep for a random time between 30 seconds and 3 minutes
            sleep_time = random.uniform(30, 180)
            time.sleep(sleep_time)
            
            # 20% chance of a server crash
            if random.random() < 0.2 and self.is_running:
                downtime = random.uniform(3, 15)  # Server down for 3-15 seconds
                logger.warning(f"🔥 Simulating server crash on {self.server_id}. Down for {downtime:.1f} seconds")
                
                # Stop the server
                if self._server:
                    self._server.shutdown()
                    self._server.server_close()
                
                time.sleep(downtime)
                
                # Restart the server if we're still supposed to be running
                if self.is_running:
                    logger.info(f"🔄 Restarting server {self.server_id} after simulated crash")
                    handler = lambda *args: BackendHandler(*args, server_id=self.server_id)
                    self._server = socketserver.TCPServer(("", self.port), handler)
                    self._thread = threading.Thread(target=self._server.serve_forever)
                    self._thread.daemon = True
                    self._thread.start()

    def stop(self):
        self.is_running = False
        if self._server:
            self._server.shutdown()
            self._server.server_close()

class BackendCluster:
    def __init__(self, base_port, num_servers):
        self.base_port = base_port
        self.num_servers = num_servers
        self.servers = []
        self.logger = setup_logging("BackendCluster")

    def start(self):
        self.logger.info(f"🚀 Initializing {self.num_servers} backend servers...")
        for i in range(self.num_servers):
            port = self.base_port + i
            
            try:
                server = BackendServer(f"backend-{i}", port)
                server.start()
                self.servers.append(server)
                self.logger.info(f"✅ Backend server {i} started successfully on port {port}")
            except Exception as e:
                self.logger.error(f"❌ Failed to start backend server {i} on port {port}: {str(e)}")
                self.stop()
                raise

    def stop(self):
        self.logger.info("🛑 Stopping all backend servers...")
        for server in self.servers:
            try:
                server.stop()
                self.logger.info(f"✅ Stopped backend server {server.server_id}")
            except Exception as e:
                self.logger.warning(f"⚠️ Error stopping backend server: {str(e)}")
        self.servers = []
        self.logger.info("✨ All backend servers stopped successfully")