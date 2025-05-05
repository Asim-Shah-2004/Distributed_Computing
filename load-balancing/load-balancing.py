#!/usr/bin/env python3
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
NGINX_PORT = 8080  # Default port for Nginx
HAPROXY_PORT = 8091  # HAProxy endpoint

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

def generate_nginx_config(nginx_port):
    """Generate Nginx configuration file for static load balancing with local logs"""
    # Create the upstream servers block separately
    upstream_servers = ''
    for i in range(NUM_SERVERS):
        upstream_servers += f'server 127.0.0.1:{BASE_PORT + i};\n        '
    
    # Create log directories
    logs_dir = config_path / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Get absolute paths for logs
    error_log = os.path.abspath(logs_dir / "error.log")
    access_log = os.path.abspath(logs_dir / "access.log")
    pid_file = os.path.abspath(logs_dir / "nginx.pid")
    
    nginx_conf = f"""
# Use local logs instead of system logs
error_log {error_log};
pid {pid_file};

events {{
    worker_connections 1024;
}}

http {{
    # Local access logs
    access_log {access_log};
    
    upstream backends {{
        # Static load balancing (round-robin by default)
        {upstream_servers}
    }}
    
    server {{
        listen {nginx_port};
        
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
    
    # Give them a moment to start up
    time.sleep(2)
    
    return threads

def check_nginx_installed():
    """Check if Nginx is installed on the system"""
    try:
        result = subprocess.run(["which", "nginx"], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE)
        return result.returncode == 0
    except:
        return False

def start_nginx(config_path, nginx_port):
    """Start Nginx with the generated configuration"""
    print("Starting Nginx for static load balancing...")
    
    if not check_nginx_installed():
        print("Error: Nginx not found. Please install Nginx first with:")
        print("sudo apt-get update && sudo apt-get install -y nginx")
        print("Then run this script again.")
        return None
    
    try:
        # First try to stop any running Nginx instance
        try:
            subprocess.run(["sudo", "nginx", "-s", "stop"], 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL)
            # Give it a moment to shut down
            time.sleep(2)
        except Exception as e:
            print(f"Warning when stopping Nginx: {e}")
            pass
        
        # Get absolute path for the configuration file
        abs_config_path = os.path.abspath(config_path)
        print(f"Using Nginx config at: {abs_config_path}")
        
        # Run nginx with sudo to avoid permission issues
        nginx_process = subprocess.Popen(
            ["sudo", "nginx", "-c", abs_config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Check if Nginx started successfully
        time.sleep(3)  # Give it more time to start
        
        # Validate Nginx is running by checking if we can connect to the port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex(('127.0.0.1', nginx_port))
            if result != 0:  # If connection fails
                out, err = nginx_process.communicate(timeout=1)
                print(f"Nginx failed to start. Error: {err.decode()}")
                # Check Nginx error logs
                error_log_path = config_path.parent / "logs" / "error.log"
                if os.path.exists(error_log_path):
                    with open(error_log_path, "r") as f:
                        print(f"Nginx error log: {f.read()}")
                        
                # Try to get more diagnostic information
                print("Checking nginx status:")
                subprocess.run(["sudo", "systemctl", "status", "nginx"], 
                              stdout=sys.stdout, 
                              stderr=sys.stderr)
                
                return None
            
        print(f"Nginx started with static load balancing on port {nginx_port}")
        return nginx_process
    except FileNotFoundError:
        print("Error: Nginx not found. Please install Nginx and try again.")
        return None
    except Exception as e:
        print(f"Error starting Nginx: {e}")
        return None

def start_haproxy(config_path):
    """Start HAProxy with the generated configuration"""
    print("Starting HAProxy for dynamic load balancing...")
    try:
        # Check if HAProxy is installed
        result = subprocess.run(["which", "haproxy"], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE)
        if result.returncode != 0:
            print("Error: HAProxy not found. Please install HAProxy first with:")
            print("sudo apt-get update && sudo apt-get install -y haproxy")
            print("Then run this script again.")
            return None
            
        # Stop any existing HAProxy instance
        try:
            subprocess.run(["sudo", "killall", "haproxy"], 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL)
            time.sleep(1)
        except:
            pass
            
        haproxy_process = subprocess.Popen(
            ["sudo", "haproxy", "-f", str(config_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Verify HAProxy started correctly
        time.sleep(2)
        if haproxy_process.poll() is not None:
            # Process has terminated
            out, err = haproxy_process.communicate()
            print(f"HAProxy failed to start. Error: {err.decode()}")
            return None
        
        # Verify we can connect to HAProxy
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex(('127.0.0.1', HAPROXY_PORT))
            if result != 0:  # If connection fails
                print("HAProxy seems to be running but the port is not accessible.")
                return None
        
        print(f"HAProxy started with dynamic load balancing on port {HAPROXY_PORT}")
        return haproxy_process
    except FileNotFoundError:
        print("Error: HAProxy not found. Please install HAProxy and try again.")
        return None
    except Exception as e:
        print(f"Error starting HAProxy: {e}")
        return None

def test_load_balancer(lb_type, lb_port, num_requests=10):
    """Test the load balancer by sending multiple requests"""
    lb_name = "Nginx (Static LB)" if lb_type == "nginx" else "HAProxy (Dynamic LB)"
    
    print(f"\nTesting {lb_name} with {num_requests} requests to port {lb_port}...")
    
    results = []
    for i in range(num_requests):
        try:
            # Add a cache-busting parameter to prevent browser/proxy caching
            cache_buster = f"?nocache={time.time()}"
            response = requests.get(f"http://localhost:{lb_port}/{cache_buster}", timeout=5)
            data = response.json()
            results.append(data)
            print(f"Request {i+1}: Server {data['server_id']} responded (Port {data['server_port']})")
            # Add a small delay between requests to see the round-robin effect better
            time.sleep(0.1)
        except Exception as e:
            print(f"Request {i+1}: Error - {e}")
            results.append(None)  # Add None for failed requests
    
    return results

def generate_report(nginx_results, haproxy_results, nginx_port, haproxy_port):
    """Generate a comparison report between Nginx and HAProxy results"""
    nginx_server_counts = {}
    haproxy_server_counts = {}
    
    for result in nginx_results:
        if isinstance(result, dict):  # Make sure result is valid
            server_id = result.get('server_id')
            nginx_server_counts[server_id] = nginx_server_counts.get(server_id, 0) + 1
    
    for result in haproxy_results:
        if isinstance(result, dict):  # Make sure result is valid
            server_id = result.get('server_id')
            haproxy_server_counts[server_id] = haproxy_server_counts.get(server_id, 0) + 1
    
    print("\n============= LOAD BALANCING REPORT =============")
    print("\nNginx (Static Load Balancing):")
    print("----------------------------------")
    print(f"Total successful requests: {len([r for r in nginx_results if isinstance(r, dict)])} of {len(nginx_results)}")
    
    if len(nginx_server_counts) > 0:
        for server_id, count in sorted(nginx_server_counts.items()):
            total = len([r for r in nginx_results if isinstance(r, dict)])
            if total > 0:
                print(f"Server {server_id}: {count} requests ({count/total*100:.1f}%)")
    else:
        print("No successful Nginx responses received.")
    
    print("\nHAProxy (Dynamic Load Balancing):")
    print("----------------------------------")
    print(f"Total successful requests: {len([r for r in haproxy_results if isinstance(r, dict)])} of {len(haproxy_results)}")
    
    if len(haproxy_server_counts) > 0:
        for server_id, count in sorted(haproxy_server_counts.items()):
            total = len([r for r in haproxy_results if isinstance(r, dict)])
            if total > 0:
                print(f"Server {server_id}: {count} requests ({count/total*100:.1f}%)")
    else:
        print("No successful HAProxy responses received.")
    
    print("\nComparison:")
    print("----------------------------------")
    print("Nginx uses static round-robin distribution by default.")
    print("HAProxy uses least connections algorithm for dynamic distribution.")
    
    if len(nginx_server_counts) > 0 and len(haproxy_server_counts) > 0:
        print("\nObservation: HAProxy distribution may vary based on server load,")
        print("while Nginx consistently follows its static allocation pattern.")
    elif len(nginx_server_counts) == 0:
        print(f"\nNginx failed to respond to requests on port {nginx_port}.")
        print("Possible issues:")
        print("1. Nginx may not be properly installed")
        print("2. The port may be blocked or in use")
        print("3. Configuration issues - check logs in lb_configs/logs/error.log")
    
    # Save report to file
    report_path = config_path / "lb_report.txt"
    with open(report_path, "w") as f:
        f.write("============= LOAD BALANCING REPORT =============\n")
        f.write("\nNginx (Static Load Balancing):\n")
        f.write("----------------------------------\n")
        f.write(f"Port used: {nginx_port}\n")
        f.write(f"Total successful requests: {len([r for r in nginx_results if isinstance(r, dict)])} of {len(nginx_results)}\n")
        
        if len(nginx_server_counts) > 0:
            for server_id, count in sorted(nginx_server_counts.items()):
                total = len([r for r in nginx_results if isinstance(r, dict)])
                if total > 0:
                    f.write(f"Server {server_id}: {count} requests ({count/total*100:.1f}%)\n")
        else:
            f.write("No successful Nginx responses received.\n")
        
        f.write("\nHAProxy (Dynamic Load Balancing):\n")
        f.write("----------------------------------\n")
        f.write(f"Port used: {haproxy_port}\n")
        f.write(f"Total successful requests: {len([r for r in haproxy_results if isinstance(r, dict)])} of {len(haproxy_results)}\n")
        
        if len(haproxy_server_counts) > 0:
            for server_id, count in sorted(haproxy_server_counts.items()):
                total = len([r for r in haproxy_results if isinstance(r, dict)])
                if total > 0:
                    f.write(f"Server {server_id}: {count} requests ({count/total*100:.1f}%)\n")
        else:
            f.write("No successful HAProxy responses received.\n")
        
        f.write("\nComparison:\n")
        f.write("----------------------------------\n")
        f.write("Nginx uses static round-robin distribution by default.\n")
        f.write("HAProxy uses least connections algorithm for dynamic distribution.\n")
        
        if len(nginx_server_counts) > 0 and len(haproxy_server_counts) > 0:
            f.write("\nObservation: HAProxy distribution may vary based on server load,\n")
            f.write("while Nginx consistently follows its static allocation pattern.\n")
        elif len(nginx_server_counts) == 0:
            f.write(f"\nNginx failed to respond to requests on port {nginx_port}.\n")
            f.write("Possible issues:\n")
            f.write("1. Nginx may not be properly installed\n")
            f.write("2. The port may be blocked or in use\n")
            f.write("3. Configuration issues - check logs in lb_configs/logs/error.log\n")
    
    print(f"\nReport saved to {report_path}")
    return report_path

def check_port_availability(port):
    """Check if a port is available"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex(('127.0.0.1', port))
        return result != 0  # True if port is available (connection failed)

def find_available_port(start_port, end_port):
    """Find an available port in the given range"""
    for port in range(start_port, end_port + 1):
        if check_port_availability(port):
            return port
    return None

def stop_all():
    """Stop all running processes"""
    print("Stopping all services...")
    
    # Stop Nginx if running
    try:
        subprocess.run(["sudo", "nginx", "-s", "stop"], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL)
    except:
        pass
    
    # Stop HAProxy if running
    try:
        # Find HAProxy process and terminate it
        subprocess.run(["sudo", "killall", "haproxy"], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL)
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
    parser.add_argument("--nginx-port", type=int, default=0,
                        help="Specify Nginx port (default: auto-detect)")
    
    args = parser.parse_args()
    
    # Create config directory if it doesn't exist
    config_path.mkdir(exist_ok=True)
    
    # Create logs directory
    logs_dir = config_path / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Verify port availability for Nginx
    nginx_port = args.nginx_port if args.nginx_port > 0 else NGINX_PORT
    
    if not check_port_availability(nginx_port):
        print(f"Port {nginx_port} is already in use. Trying alternative port...")
        # Try to find an available port
        nginx_port = find_available_port(8080, 8099)
        if nginx_port:
            print(f"Using port {nginx_port} for Nginx")
        else:
            print("Could not find an available port for Nginx. Please close applications using ports 8080-8099.")
            if args.command != "stop":  # Only exit if not stopping
                return
    
    if args.command == "start":
        # Start backend servers
        backend_threads = start_backends()
        
        # Generate and start HAProxy
        haproxy_config = generate_haproxy_config()
        haproxy_process = start_haproxy(haproxy_config)
        
        # Generate and start Nginx
        nginx_config = generate_nginx_config(nginx_port)
        nginx_process = start_nginx(nginx_config, nginx_port)
        
        if nginx_process is None:
            print("\nWarning: Nginx failed to start. Only HAProxy is running.")
            print(f"HAProxy (Dynamic LB): http://localhost:{HAPROXY_PORT}/")
        else:
            print("\nLoad balancers started successfully!")
            print(f"Nginx (Static LB): http://localhost:{nginx_port}/")
            print(f"HAProxy (Dynamic LB): http://localhost:{HAPROXY_PORT}/")
        
        print("\nPress Ctrl+C to stop all services...")
        
        try:
            # Keep the script running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_all()
    
    elif args.command == "test":
        # First start backend servers since they're needed for testing
        backend_threads = start_backends()
        
        print("Testing both load balancers...")
        
        # Generate configs in case they don't exist
        haproxy_config = generate_haproxy_config()
        nginx_config = generate_nginx_config(nginx_port)
        
        # Test both load balancers
        nginx_results = test_load_balancer("nginx", nginx_port, args.requests)
        time.sleep(1)  # Small pause between tests
        haproxy_results = test_load_balancer("haproxy", HAPROXY_PORT, args.requests)
        
        # Save results for reporting
        with open(config_path / "nginx_results.json", "w") as f:
            json.dump(nginx_results, f, indent=2, default=str)
        with open(config_path / "haproxy_results.json", "w") as f:
            json.dump(haproxy_results, f, indent=2, default=str)
        
        print("\nTest completed. Results saved for reporting.")
        
        # Generate a report immediately after testing
        generate_report(nginx_results, haproxy_results, nginx_port, HAPROXY_PORT)
        
        # Ask if user wants to start load balancers
        try:
            start_lb = input("\nDo you want to start the load balancers? (y/n): ").strip().lower()
            if start_lb == 'y':
                # Generate and start HAProxy
                haproxy_process = start_haproxy(haproxy_config)
                
                # Generate and start Nginx
                nginx_process = start_nginx(nginx_config, nginx_port)
                
                if nginx_process is None:
                    print("\nWarning: Nginx failed to start. Only HAProxy is running.")
                    print(f"HAProxy (Dynamic LB): http://localhost:{HAPROXY_PORT}/")
                else:
                    print("\nLoad balancers started successfully!")
                    print(f"Nginx (Static LB): http://localhost:{nginx_port}/")
                    print(f"HAProxy (Dynamic LB): http://localhost:{HAPROXY_PORT}/")
                
                print("\nPress Ctrl+C to stop all services...")
                
                try:
                    # Keep the script running
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    stop_all()
        except KeyboardInterrupt:
            print("\nExiting...")
    
    elif args.command == "report":
        # Load test results if available
        try:
            with open(config_path / "nginx_results.json", "r") as f:
                nginx_results = json.load(f)
            with open(config_path / "haproxy_results.json", "r") as f:
                haproxy_results = json.load(f)
            
            generate_report(nginx_results, haproxy_results, nginx_port, HAPROXY_PORT)
        except FileNotFoundError:
            print("Error: Test results not found. Run the 'test' command first.")
    
    elif args.command == "stop":
        stop_all()

if __name__ == "__main__":
    main()