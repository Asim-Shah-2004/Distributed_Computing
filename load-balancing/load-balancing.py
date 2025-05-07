import argparse
import sys
import time
from pathlib import Path
from lib.backend import BackendCluster
from lib.load_balancers import NginxManager, HAProxyManager
from lib.port_manager import PortManager
from lib.tester import LoadBalancerTester
from lib.utils import cleanup, setup_logging
from tabulate import tabulate

def start_services(base_dir, backend_ports, nginx_port, haproxy_port, logger):
    # Start backend cluster
    logger.info(f"🚀 Initializing backend cluster with {len(backend_ports)} servers...")
    backend = BackendCluster(backend_ports[0], len(backend_ports))
    backend.start()
    logger.info(f"✅ Backend servers running on ports: {', '.join(map(str, backend_ports))}")

    # Start Nginx
    logger.info("🔄 Starting Nginx load balancer...")
    nginx = NginxManager(str(base_dir / "lb_configs"))
    nginx_cfg = nginx.generate_config(backend_ports, nginx_port)
    if not nginx.start(nginx_cfg):
        logger.error("❌ Failed to start Nginx load balancer")
        return False
    logger.info(f"✅ Nginx load balancer running on port {nginx_port}")

    # Start HAProxy
    logger.info("🔄 Starting HAProxy load balancer...")
    haproxy = HAProxyManager(str(base_dir / "lb_configs"))
    haproxy_cfg = haproxy.generate_config(backend_ports, haproxy_port)
    if not haproxy.start(haproxy_cfg):
        logger.error("❌ Failed to start HAProxy load balancer")
        return False
    logger.info(f"✅ HAProxy load balancer running on port {haproxy_port}")

    # Wait for services to be ready
    logger.info("⏳ Waiting for services to initialize...")
    time.sleep(2)
    logger.info("✨ All services are up and running!")
    return True

def main():
    logger = setup_logging()
    
    # Get the directory where lb_demo.py is located
    base_dir = Path(__file__).parent.absolute()
    
    parser = argparse.ArgumentParser(description="Load Balancer Demo")
    parser.add_argument("command", choices=["start", "test", "stop"])
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--backend-count", type=int, default=3)
    parser.add_argument("--base-port", type=int, default=9000)
    args = parser.parse_args()

    # Port configuration
    logger.info("🔍 Checking port availability...")
    port_manager = PortManager()
    backend_ports = [args.base_port + i for i in range(args.backend_count)]
    
    # Find available ports for load balancers
    nginx_port = port_manager.find_available_port(8080, 8100)
    if not nginx_port:
        logger.error("❌ Could not find available port for Nginx")
        sys.exit(1)
        
    haproxy_port = port_manager.find_available_port(nginx_port + 1, 8100)
    if not haproxy_port:
        logger.error("❌ Could not find available port for HAProxy")
        sys.exit(1)

    try:
        if args.command == "start":
            logger.info("🚀 Starting load balancer demo...")
            if not start_services(base_dir, backend_ports, nginx_port, haproxy_port, logger):
                sys.exit(1)
            
            logger.info("✨ All services running. Press Ctrl+C to stop.")
            try:
                while True: 
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("👋 Received shutdown signal")
                cleanup()

        elif args.command == "test":
            logger.info("🧪 Starting load balancer test...")
            
            if not start_services(base_dir, backend_ports, nginx_port, haproxy_port, logger):
                sys.exit(1)

            try:
                logger.info("\n📊 Testing Nginx Load Balancer:")
                nginx_tester = LoadBalancerTester(f"http://localhost:{nginx_port}", args.requests)
                nginx_tester.run()
                nginx_stats = nginx_tester.analyze()
                print("\n=== Nginx Load Balancer Report ===")
                print(nginx_tester._generate_report(nginx_stats))

                logger.info("\n📊 Testing HAProxy Load Balancer:")
                haproxy_tester = LoadBalancerTester(f"http://localhost:{haproxy_port}", args.requests)
                haproxy_tester.run()
                haproxy_stats = haproxy_tester.analyze()
                print("\n=== HAProxy Load Balancer Report ===")
                print(haproxy_tester._generate_report(haproxy_stats))

                # Compare the two load balancers
                logger.info("\n📊 Comparing Load Balancers:")
                comparison_data = [
                    ["Metric", "Nginx", "HAProxy"],
                    ["Requests per Second", 
                     f"{nginx_stats['metrics']['requests_per_second']:.2f}",
                     f"{haproxy_stats['metrics']['requests_per_second']:.2f}"],
                    ["Success Rate", 
                     f"{nginx_stats['metrics']['success_rate']:.2f}%",
                     f"{haproxy_stats['metrics']['success_rate']:.2f}%"],
                    ["Error Rate",
                     f"{nginx_stats['metrics']['error_rate']:.2f}%",
                     f"{haproxy_stats['metrics']['error_rate']:.2f}%"],
                    ["Avg Response Time",
                     f"{nginx_stats['response_time_stats']['mean']*1000:.2f}ms",
                     f"{haproxy_stats['response_time_stats']['mean']*1000:.2f}ms"],
                    ["P95 Response Time",
                     f"{nginx_stats['response_time_stats']['p95']*1000:.2f}ms",
                     f"{haproxy_stats['response_time_stats']['p95']*1000:.2f}ms"]
                ]
                print("\n=== Load Balancer Comparison ===")
                print(tabulate(comparison_data, headers="firstrow", tablefmt="grid"))
            finally:
                # Clean up after testing
                logger.info("🧹 Cleaning up after testing...")
                cleanup()

        elif args.command == "stop":
            logger.info("🛑 Stopping all services...")
            cleanup()
            logger.info("✅ All services stopped successfully")

    except Exception as e:
        logger.error(f"❌ An error occurred: {str(e)}")
        cleanup()
        sys.exit(1)

if __name__ == "__main__":
    main()