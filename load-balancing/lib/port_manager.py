import socket
from pathlib import Path
from lib.utils import setup_logging

class PortManager:
    def __init__(self):
        self.logger = setup_logging("PortManager")
        self.used_ports = set()

    def find_available_port(self, start, end):
        for port in range(start, end+1):
            if port not in self.used_ports and self.is_port_available(port):
                self.used_ports.add(port)
                self.logger.info(f"Found available port: {port}")
                return port
        self.logger.error(f"No available ports found in range {start}-{end}")
        return None

    def is_port_available(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return True
            except OSError:
                self.logger.warning(f"Port {port} is not available")
                return False

    def release_port(self, port):
        if port in self.used_ports:
            self.used_ports.remove(port)
            self.logger.info(f"Released port: {port}")