from flask import Flask, jsonify, request
import time
import numpy as np
import os
import psutil
import json

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

app = Flask(__name__)
app.json_encoder = NumpyEncoder

STUDENTS = [
    {"id": i, "name": f"Student {i}", "course": f"Hospitality Course {i % 5}", 
     "grades": [np.random.randint(60, 100) for _ in range(5)]} 
    for i in range(1, 1001)
]

def compute_intensive_task(iterations=500_000):
    """Simulate a CPU-intensive computation"""
    result = 0
    for i in range(iterations):
        result += i * np.sin(i) * np.cos(i)
    return float(result) 

@app.route('/')
def home():
    return jsonify({
        "status": "Reyansh College of Hotel Management API is running",
        "server_info": {
            "process_id": os.getpid(),
            "thread_id": psutil.Process().num_threads(),
            "time": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    })

@app.route('/students')
def get_students():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    start = (page - 1) * per_page
    end = start + per_page
    
    return jsonify({
        "students": STUDENTS[start:end],
        "page": page,
        "per_page": per_page,
        "total": len(STUDENTS)
    })

@app.route('/analyze')
def analyze_grades():
    start_time = time.time()
    
    compute_result = compute_intensive_task()
    
    all_grades = [grade for student in STUDENTS for grade in student["grades"]]
    stats = {
        "mean": float(np.mean(all_grades)),
        "median": float(np.median(all_grades)),
        "std_dev": float(np.std(all_grades)),
        "min": int(np.min(all_grades)),
        "max": int(np.max(all_grades)),
        "computation_result": compute_result,
        "processing_time": time.time() - start_time,
        "process_id": os.getpid()
    }
    
    return jsonify({
        "stats": stats,
        "server_info": {
            "pid": os.getpid(),
            "threads": psutil.Process().num_threads()
        }
    })

if __name__ == '__main__':
    app.run(debug=True,port=8000)