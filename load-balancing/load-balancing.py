#!/usr/bin/env python3
"""
Load Balancing Demo CLI - Demonstrates static LB with Nginx and dynamic LB with HAProxy
"""

import os
import sys
import time
import subprocess
import argparse
import random
import requests
import json
from pathlib import Path
import socket
import signal
import threading
import http.server
import socketserver
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Constants
BASE_PORT = 9000  # Backend server ports will start from this number
NUM_SERVERS = 3   # Number of backend servers to run
NGINX_PORT = 8090 # Main endpoint as requested
HAPROXY_PORT = 8091 # HAProxy endpoint

# Server management
server_processes = []
config_path = Path("./lb_configs")

class BackendServer(http.server.SimpleHTTPRequestHandler):
    """Simple HTTP server that identifies which server instance it is"""
    
    def __init__(self, *args, server_id=None, **kwargs):
        self.server_id = server_id
        self.request_count = 0
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests with server information"""
        self.request_count += 1
        
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Add some random delay to simulate varying server load
            delay = random.uniform(0.1, 0.5)
            time.sleep(delay)
            
            # Create response with server details
            response = {
                'server_id': self.server_id,
                'server_port': self.server.server_address[1],
                'request_count': self.request_count,
                'delay': delay,
                'time': datetime.now().strftime('%H:%M:%S.%f'),
                'headers': dict(self.headers)
            }
            
            try:
                self.wfile.write(json.dumps(response, indent=4).encode())
            except (BrokenPipeError, ConnectionResetError) as e:
                # This happens when the client disconnects before we can send the response
                # It's normal with load balancers doing health checks
                sys.stderr.write(f"Client disconnected: {e}\n")
        except Exception as e:
            sys.stderr.write(f"Error handling request: {e}\n")
        
    def log_message(self, format, *args):
        """Override log messages to include server ID"""
        try:
            sys.stderr.write(f"Backend {self.server_id} - {self.server.server_address[1]}: {format % args}\n")
        except Exception as e:
            sys.stderr.write(f"Error logging message: {e}\n")

def run_backend_server(port, server_id):
    """Run a backend server on the specified port"""
    handler = lambda *args, **kwargs: BackendServer(*args, server_id=server_id, **kwargs)
    
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Backend server {server_id} started at port {port}")
        httpd.serve_forever()

def generate_nginx_config():
    """Generate Nginx configuration file for static load balancing"""
    # Create the upstream servers block separately
    upstream_servers = ''
    for i in range(NUM_SERVERS):
        upstream_servers += f'server 127.0.0.1:{BASE_PORT + i};\n        '
    
    nginx_conf = f"""
http {{
    upstream backends {{
        # Static load balancing (round-robin by default)
        {upstream_servers}
    }}
    
    server {{
        listen {NGINX_PORT};
        
        location / {{
            proxy_pass http://backends;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            add_header X-Load-Balancer "Nginx Static LB";
            
            # Ensure proper content-type handling
            proxy_set_header Accept "application/json";
            proxy_http_version 1.1;
        }}
    }}
    
    # Disable default handling of HTML/CSS
    types {{
        application/json json;
        text/plain txt;
    }}
    default_type application/json;
}}

events {{
    worker_connections 1024;
}}
"""
    config_path.mkdir(exist_ok=True)
    with open(config_path / "nginx.conf", "w") as f:
        f.write(nginx_conf)
    
    return config_path / "nginx.conf"

def generate_haproxy_config():
    """Generate HAProxy configuration file for dynamic load balancing"""
    # Create the servers block separately
    server_configs = ''
    for i in range(NUM_SERVERS):
        server_configs += f'server server{i} 127.0.0.1:{BASE_PORT + i} maxconn 32 weight 10\n    '
    
    haproxy_conf = f"""
global
    daemon
    maxconn 256

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms

frontend http-in
    bind *:{HAPROXY_PORT}
    default_backend dynamic_backends

backend dynamic_backends
    # Dynamic load balancing with health checks
    balance leastconn  # Least connections algorithm
    option httpchk GET /
    default-server check inter 2s fall 3 rise 2
    
    {server_configs}
"""
    config_path.mkdir(exist_ok=True)
    with open(config_path / "haproxy.cfg", "w") as f:
        f.write(haproxy_conf)
    
    return config_path / "haproxy.cfg"

def start_backends():
    """Start all backend server instances"""
    print("Starting backend servers...")
    threads = []
    
    for i in range(NUM_SERVERS):
        port = BASE_PORT + i
        server_id = i + 1
        thread = threading.Thread(
            target=run_backend_server, 
            args=(port, server_id),
            daemon=True
        )
        thread.start()
        threads.append(thread)
        print(f"Started backend server {server_id} on port {port}")
    
    return threads

def start_nginx(config_path):
    """Start Nginx with the generated configuration"""
    print("Starting Nginx for static load balancing...")
    try:
        # First try to stop any running Nginx instance
        try:
            subprocess.run(["nginx", "-s", "stop"], 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL)
            # Give it a moment to shut down
            time.sleep(1)
        except:
            pass
            
        nginx_process = subprocess.Popen(
            ["nginx", "-c", str(config_path), "-g", "daemon off;"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"Nginx started with static load balancing on port {NGINX_PORT}")
        return nginx_process
    except FileNotFoundError:
        print("Error: Nginx not found. Please install Nginx and try again.")
        return None

def start_haproxy(config_path):
    """Start HAProxy with the generated configuration"""
    print("Starting HAProxy for dynamic load balancing...")
    try:
        haproxy_process = subprocess.Popen(
            ["haproxy", "-f", str(config_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"HAProxy started with dynamic load balancing on port {HAPROXY_PORT}")
        return haproxy_process
    except FileNotFoundError:
        print("Error: HAProxy not found. Please install HAProxy and try again.")
        return None

def test_load_balancer(lb_type, num_requests=10):
    """Test the load balancer by sending multiple requests"""
    port = NGINX_PORT if lb_type == "nginx" else HAPROXY_PORT
    lb_name = "Nginx (Static LB)" if lb_type == "nginx" else "HAProxy (Dynamic LB)"
    
    print(f"\nTesting {lb_name} with {num_requests} requests...")
    
    results = []
    for i in range(num_requests):
        try:
            # Add a cache-busting parameter to prevent browser/proxy caching
            cache_buster = f"?nocache={time.time()}"
            response = requests.get(f"http://127.0.0.1:{port}/{cache_buster}", timeout=2)
            data = response.json()
            results.append(data)
            print(f"Request {i+1}: Server {data['server_id']} responded (Port {data['server_port']})")
            # Add a small delay between requests to see the round-robin effect better
            time.sleep(0.1)
        except Exception as e:
            print(f"Request {i+1}: Error - {e}")
    
    return results

def generate_report(nginx_results, haproxy_results):
    """Generate a comparison report between Nginx and HAProxy results"""
    nginx_server_counts = {}
    haproxy_server_counts = {}
    
    for result in nginx_results:
        server_id = result.get('server_id')
        nginx_server_counts[server_id] = nginx_server_counts.get(server_id, 0) + 1
    
    for result in haproxy_results:
        server_id = result.get('server_id')
        haproxy_server_counts[server_id] = haproxy_server_counts.get(server_id, 0) + 1
    
    print("\n============= LOAD BALANCING REPORT =============")
    print("\nNginx (Static Load Balancing):")
    print("----------------------------------")
    print(f"Total requests: {len(nginx_results)}")
    for server_id, count in sorted(nginx_server_counts.items()):
        print(f"Server {server_id}: {count} requests ({count/len(nginx_results)*100:.1f}%)")
    
    print("\nHAProxy (Dynamic Load Balancing):")
    print("----------------------------------")
    print(f"Total requests: {len(haproxy_results)}")
    for server_id, count in sorted(haproxy_server_counts.items()):
        print(f"Server {server_id}: {count} requests ({count/len(haproxy_results)*100:.1f}%)")
    
    print("\nComparison:")
    print("----------------------------------")
    print("Nginx uses static round-robin distribution by default.")
    print("HAProxy uses least connections algorithm for dynamic distribution.")
    print("\nObservation: HAProxy distribution may vary based on server load,")
    print("while Nginx consistently follows its static allocation pattern.")
    
    # Save report to file
    report_path = config_path / "lb_report.txt"
    with open(report_path, "w") as f:
        f.write("============= LOAD BALANCING REPORT =============\n")
        f.write("\nNginx (Static Load Balancing):\n")
        f.write("----------------------------------\n")
        f.write(f"Total requests: {len(nginx_results)}\n")
        for server_id, count in sorted(nginx_server_counts.items()):
            f.write(f"Server {server_id}: {count} requests ({count/len(nginx_results)*100:.1f}%)\n")
        
        f.write("\nHAProxy (Dynamic Load Balancing):\n")
        f.write("----------------------------------\n")
        f.write(f"Total requests: {len(haproxy_results)}\n")
        for server_id, count in sorted(haproxy_server_counts.items()):
            f.write(f"Server {server_id}: {count} requests ({count/len(haproxy_results)*100:.1f}%)\n")
        
        f.write("\nComparison:\n")
        f.write("----------------------------------\n")
        f.write("Nginx uses static round-robin distribution by default.\n")
        f.write("HAProxy uses least connections algorithm for dynamic distribution.\n")
        f.write("\nObservation: HAProxy distribution may vary based on server load,\n")
        f.write("while Nginx consistently follows its static allocation pattern.\n")
    
    print(f"\nReport saved to {report_path}")
    return report_path

def stop_all():
    """Stop all running processes"""
    print("Stopping all services...")
    
    # Stop Nginx if running
    try:
        subprocess.run(["nginx", "-s", "stop"], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL)
    except:
        pass
    
    # Stop HAProxy if running
    try:
        # Find HAProxy process and terminate it
        pids = subprocess.check_output(["pgrep", "haproxy"]).decode().strip().split()
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except:
                pass
    except:
        pass
    
    print("All services stopped.")

def main():
    """Main function to manage load balancer demo"""
    parser = argparse.ArgumentParser(description="Load Balancing Demo with Nginx and HAProxy")
    parser.add_argument("command", choices=["start", "test", "report", "stop"], 
                        help="Command to execute")
    parser.add_argument("--requests", type=int, default=20,
                        help="Number of test requests to send (default: 20)")
    
    args = parser.parse_args()
    
    # Create config directory if it doesn't exist
    config_path.mkdir(exist_ok=True)
    
    if args.command == "start":
        # Start backend servers
        backend_threads = start_backends()
        
        # Give backend servers time to start
        time.sleep(1)
        
        # Generate and start Nginx
        nginx_config = generate_nginx_config()
        nginx_process = start_nginx(nginx_config)
        
        # Generate and start HAProxy
        haproxy_config = generate_haproxy_config()
        haproxy_process = start_haproxy(haproxy_config)
        
        print("\nLoad balancers started successfully!")
        print(f"Nginx (Static LB): http://localhost:{NGINX_PORT}/")
        print(f"HAProxy (Dynamic LB): http://localhost:{HAPROXY_PORT}/")
        print("\nPress Ctrl+C to stop all services...")
        
        try:
            # Keep the script running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_all()
    
    elif args.command == "test":
        print("Testing both load balancers...")
        nginx_results = test_load_balancer("nginx", args.requests)
        time.sleep(1)  # Small pause between tests
        haproxy_results = test_load_balancer("haproxy", args.requests)
        
        # Save results for reporting
        with open(config_path / "nginx_results.json", "w") as f:
            json.dump(nginx_results, f, indent=2)
        with open(config_path / "haproxy_results.json", "w") as f:
            json.dump(haproxy_results, f, indent=2)
        
        print("\nTest completed. Results saved for reporting.")
    
    elif args.command == "report":
        # Load test results if available
        try:
            with open(config_path / "nginx_results.json", "r") as f:
                nginx_results = json.load(f)
            with open(config_path / "haproxy_results.json", "r") as f:
                haproxy_results = json.load(f)
            
            generate_report(nginx_results, haproxy_results)
        except FileNotFoundError:
            print("Error: Test results not found. Run the 'test' command first.")
    
    elif args.command == "stop":
        stop_all()

if __name__ == "__main__":
    main()