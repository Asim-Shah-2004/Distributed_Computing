from flask import Flask, jsonify
import time
import numpy as np

app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

def compute_intensive_task():
    result = 0
    for i in range(1000): 
        result += i * i
    return result

@app.route('/')
def home():
    return "ok"

@app.route('/analyze')
def analyze():
    result = compute_intensive_task()
    return jsonify({"result": result})

if __name__ == '__main__':
    app.run(debug=False, port=8000, threaded=True)