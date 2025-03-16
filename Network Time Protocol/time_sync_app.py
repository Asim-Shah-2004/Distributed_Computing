import os
import time
import requests
import random
import json
import threading
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

NODE_NAME = os.environ.get('NODE_NAME', 'unknown')
NODE_TYPE = os.environ.get('NODE_TYPE', 'client')
PORT = 5000
NODES = {
    'monocarp': 'http://monocarp:5000',
    'polycarp': 'http://polycarp:5000',
    'pak_chenak': 'http://pak_chenak:5000'
}
MASTER_URL = 'http://master:5000' 

class SimulatedClock:
    def __init__(self, initial_offset=0, drift_rate=1.0):
        self.offset = initial_offset 
        self.drift_rate = drift_rate  
        self.last_update = time.time()
        
    def get_time(self):
        current_real_time = time.time()
        elapsed = current_real_time - self.last_update
        self.offset += elapsed * (self.drift_rate - 1.0)
        self.last_update = current_real_time
        return current_real_time + self.offset
        
    def set_time(self, new_time):
        self.offset = new_time - time.time()
        self.last_update = time.time()
        print(f"[{NODE_NAME}] Clock adjusted. New time: {format_time(self.get_time())}, Offset: {self.offset:.6f}s")

def format_time(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

if NODE_TYPE == 'client':
    initial_offset = random.uniform(-60, 60)
    drift_rate = random.uniform(0.9, 1.1)
    clock = SimulatedClock(initial_offset, drift_rate)
    print(f"[{NODE_NAME}] Started with offset: {initial_offset:.6f}s, drift rate: {drift_rate:.6f}")
else:
    clock = SimulatedClock(0, 1.0)
    print(f"[{NODE_NAME}] Started as master with precise time")

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "node": NODE_NAME}), 200

@app.route('/')
def index():
    return jsonify({
        "node": NODE_NAME,
        "type": NODE_TYPE,
        "time": format_time(clock.get_time())
    })

@app.route('/cli', methods=['POST'])
def cli_command():
    data = request.json
    command = data.get('command', '')
    
    if command == 'status':
        current_time = clock.get_time()
        return jsonify({
            "type": NODE_TYPE,
            "formatted_time": format_time(current_time),
            "timestamp": current_time,
            "offset": clock.offset,
            "drift_rate": clock.drift_rate
        })
        
    elif command == 'cristian' and NODE_TYPE == 'client':
        t0 = time.time()
        try:
            response = requests.post(f"{MASTER_URL}/cli", json={'command': 'get_time'})
            t1 = time.time()
            
            if response.status_code == 200:
                server_time = response.json().get('timestamp')
                
                rtt = t1 - t0
                adjusted_time = server_time + (rtt / 2)
                
                clock.set_time(adjusted_time)
                
                return jsonify({
                    "status": "synchronized",
                    "method": "cristian",
                    "rtt": rtt,
                    "server_time": server_time,
                    "new_time": adjusted_time,
                    "formatted_time": format_time(adjusted_time)
                })
            else:
                return jsonify({"error": "Failed to get time from master"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    elif command == 'get_time':
        return jsonify({"timestamp": clock.get_time()})
        
    elif command == 'berkeley' and NODE_TYPE == 'master':
        time_differences = {}
        master_time = clock.get_time()
        
        for node_name, node_url in NODES.items():
            try:
                response = requests.post(f"{node_url}/cli", json={'command': 'get_time'})
                if response.status_code == 200:
                    node_time = response.json().get('timestamp')
                    time_differences[node_name] = node_time - master_time
                    print(f"[{NODE_NAME}] Time difference with {node_name}: {time_differences[node_name]:.6f}s")
                else:
                    print(f"[{NODE_NAME}] Failed to get time from {node_name}")
            except Exception as e:
                print(f"[{NODE_NAME}] Error connecting to {node_name}: {str(e)}")
        
        time_differences['master'] = 0
        
        if time_differences:
            avg_diff = sum(time_differences.values()) / len(time_differences)
            print(f"[{NODE_NAME}] Average time difference: {avg_diff:.6f}s")
            
            new_master_time = master_time + avg_diff
            clock.set_time(new_master_time)
            
            for node_name, node_url in NODES.items():
                adjustment = avg_diff - time_differences[node_name]
                try:
                    requests.post(f"{node_url}/cli", json={
                        'command': 'adjust_time', 
                        'adjustment': adjustment
                    })
                    print(f"[{NODE_NAME}] Sent adjustment to {node_name}: {adjustment:.6f}s")
                except Exception as e:
                    print(f"[{NODE_NAME}] Error sending adjustment to {node_name}: {str(e)}")
            
            return jsonify({
                "status": "synchronized",
                "method": "berkeley",
                "average_difference": avg_diff,
                "time_differences": {k: f"{v:.6f}s" for k, v in time_differences.items()},
                "new_master_time": format_time(new_master_time)
            })
        else:
            return jsonify({"error": "No time differences collected"}), 500
            
    elif command == 'adjust_time':
        adjustment = data.get('adjustment', 0)
        current_time = clock.get_time()
        new_time = current_time + adjustment
        clock.set_time(new_time)
        return jsonify({
            "status": "time_adjusted",
            "adjustment": adjustment,
            "new_time": format_time(new_time)
        })
        
    elif command == 'drift':
        amount = data.get('amount', 0)
        clock.offset += amount
        print(f"[{NODE_NAME}] Added {amount:.6f}s drift. New offset: {clock.offset:.6f}s")
        return jsonify({
            "status": "drift_added",
            "amount": amount,
            "new_offset": clock.offset,
            "new_time": format_time(clock.get_time())
        })
    
    else:
        return jsonify({"error": "Unknown command"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)