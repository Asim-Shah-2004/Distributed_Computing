import http.server
import socketserver
import json
import threading
import time
import random
from datetime import datetime
from pathlib import Path
from lib.utils import setup_logging

class BackendHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, server_id=None, **kwargs):
        self.server_id = server_id
        super().__init__(*args, **kwargs)

    def do_GET(self):
        response = {
            "server_id": self.server_id,
            "message": "Hello from backend server!"
        }
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

class BackendServer:
    def __init__(self, server_id, port):
        self.server_id = server_id
        self.port = port
        self._server = None
        self._thread = None

    def start(self):
        handler = lambda *args: BackendHandler(*args, server_id=self.server_id)
        self._server = socketserver.TCPServer(("", self.port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
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
            handler = lambda *args, **kwargs: BackendHandler(*args, server_id=f"backend-{i}", **kwargs)
            
            try:
                server = socketserver.TCPServer(("", port), handler)
                thread = threading.Thread(target=server.serve_forever)
                thread.daemon = True
                thread.start()
                self.servers.append((server, thread))
                self.logger.info(f"✅ Backend server {i} started successfully on port {port}")
            except Exception as e:
                self.logger.error(f"❌ Failed to start backend server {i} on port {port}: {str(e)}")
                self.stop()
                raise

    def stop(self):
        self.logger.info("🛑 Stopping all backend servers...")
        for server, thread in self.servers:
            try:
                server.shutdown()
                server.server_close()
                self.logger.info(f"✅ Stopped backend server on port {server.server_address[1]}")
            except Exception as e:
                self.logger.warning(f"⚠️ Error stopping backend server: {str(e)}")
        self.servers = []
        self.logger.info("✨ All backend servers stopped successfully")