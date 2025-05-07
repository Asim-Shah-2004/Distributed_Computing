import subprocess
import os
from pathlib import Path
from lib.utils import setup_logging

class LoadBalancerConfig:
    def __init__(self, config_dir="lb_configs"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        # Setup logs directory
        self.logs_dir = self.config_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        
        # Setup logging
        self.logger = setup_logging(self.__class__.__name__)
        
    def _run_command(self, cmd, check=True):
        try:
            result = subprocess.run(
                cmd,
                check=check,
                capture_output=True,
                text=True
            )
            if result.stdout:
                self.logger.info(f"📝 {result.stdout}")
            if result.stderr:
                self.logger.warning(f"⚠️ {result.stderr}")
            return result
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ Command failed: {' '.join(cmd)}")
            self.logger.error(f"❌ Error: {e.stderr}")
            raise

    def _kill_process(self, process_name):
        try:
            # Try to find and kill the process
            self._run_command(["pkill", "-f", process_name], check=False)
            self.logger.info(f"✅ Successfully killed {process_name} process")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to kill {process_name}: {str(e)}")

class NginxManager(LoadBalancerConfig):
    def __init__(self, config_dir):
        super().__init__(config_dir)
        self.pid_file = str(self.logs_dir / "nginx.pid")
        self.error_log = str(self.logs_dir / "nginx_error.log")
        self.access_log = str(self.logs_dir / "nginx_access.log")

    def generate_config(self, backend_ports, listen_port):
        self.logger.info("🔄 Generating Nginx configuration...")
        # Create a basic Nginx configuration
        config = f"""
events {{
    worker_connections 1024;
}}

http {{
    access_log {self.access_log};
    error_log {self.error_log};

    upstream backend {{
        {chr(10).join(f'server 127.0.0.1:{port};' for port in backend_ports)}
    }}

    server {{
        listen {listen_port};
        
        location / {{
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }}
    }}
}}
"""
        # Write the configuration to a file
        config_path = self.config_dir / "nginx.conf"
        config_path.write_text(config)
        self.logger.info(f"✅ Nginx configuration generated at {config_path}")
        return str(config_path)

    def start(self, config_path):
        try:
            self.logger.info("🔄 Starting Nginx load balancer...")
            # Kill any existing Nginx processes
            self._kill_process("nginx")
            
            # Create necessary directories and files
            self.logs_dir.mkdir(exist_ok=True, parents=True)
            
            # Start Nginx with the configuration
            cmd = [
                "nginx",
                "-c", config_path,
                "-p", str(self.config_dir),
                "-g", f"pid {self.pid_file}; error_log {self.error_log};"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.logger.error(f"❌ Failed to start Nginx: {result.stderr}")
                return False
                
            self.logger.info("✅ Nginx started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error starting Nginx: {str(e)}")
            return False

    def stop(self):
        try:
            self.logger.info("🛑 Stopping Nginx...")
            self._kill_process("nginx")
            self.logger.info("✅ Nginx stopped successfully")
        except Exception as e:
            self.logger.error(f"❌ Error stopping Nginx: {str(e)}")

class HAProxyManager(LoadBalancerConfig):
    def generate_config(self, backend_ports, listen_port):
        self.logger.info("🔄 Generating HAProxy configuration...")
        servers = "\n".join(
            [f"server s{i} 127.0.0.1:{port} check" 
             for i, port in enumerate(backend_ports)]
        )
        
        config = f"""
global
    log {self.logs_dir}/haproxy.log local0
    maxconn 4096
    daemon
    pidfile {self.logs_dir}/haproxy.pid

defaults
    log     global
    mode    http
    option  httplog
    option  dontlognull
    timeout connect 5000
    timeout client  50000
    timeout server  50000

frontend http
    bind *:{listen_port}
    default_backend servers

backend servers
    balance leastconn
    {servers}
"""
        
        config_path = self.config_dir / "haproxy.cfg"
        config_path.write_text(config)
        self.logger.info(f"✅ HAProxy configuration generated at {config_path}")
        return config_path

    def start(self, config_path):
        try:
            self.logger.info("🔄 Starting HAProxy load balancer...")
            # Kill any existing HAProxy processes
            self._kill_process("haproxy")
            
            # Start HAProxy
            result = self._run_command([
                "haproxy", 
                "-f", str(config_path),
                "-D"
            ])
            self.logger.info("✅ HAProxy started successfully")
            return result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.logger.error(f"❌ Failed to start HAProxy: {str(e)}")
            return False