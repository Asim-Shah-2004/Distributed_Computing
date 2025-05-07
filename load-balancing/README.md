# Load Balancer Demo and Testing Framework

A comprehensive load balancing demonstration and testing framework that compares the performance of Nginx and HAProxy load balancers. This project provides a complete environment to test, analyze, and compare different load balancing solutions with detailed performance metrics and reports.

## Features

- 🚀 **Multiple Load Balancers Support**
  - Nginx load balancer implementation
  - HAProxy load balancer implementation
  - Easy to extend for other load balancers

- 📊 **Comprehensive Testing Framework**
  - Concurrent request testing
  - Detailed performance metrics
  - Response time analysis
  - Server distribution analysis
  - Error rate monitoring
  - Automatic report generation

- 🔧 **Easy Configuration**
  - Configurable number of backend servers
  - Customizable port ranges
  - Flexible request parameters
  - Automatic port management

- 📈 **Detailed Performance Reports**
  - Requests per second
  - Success/Error rates
  - Response time statistics (min, max, mean, median, p95, p99)
  - Server distribution analysis
  - Error analysis
  - Exportable reports in text and JSON formats

## Prerequisites

- Python 3.8+
- Nginx
- HAProxy
- Required Python packages (install via `pip install -r requirements.txt`):
  - requests
  - colorama
  - tabulate
  - pathlib

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd load-balancing
```

2. Install required Python packages:
```bash
pip install -r requirements.txt
```

3. Ensure Nginx and HAProxy are installed on your system:
```bash
# For Ubuntu/Debian
sudo apt-get update
sudo apt-get install nginx haproxy

## Usage

The project provides three main commands: `start`, `test`, and `stop`.

### Starting the Services

To start the load balancer demo with default settings:
```bash
python load-balancing.py start
```

### Running Tests

To run a load test comparing Nginx and HAProxy:
```bash
python load-balancing.py test
```

Additional test options:
```bash
python load-balancing.py test --requests 500 --backend-count 5 --base-port 9000
```

### Stopping Services

To stop all running services:
```bash
python load-balancing.py stop
```

## Command Line Options

- `--requests`: Number of requests to send during testing (default: 200)
- `--backend-count`: Number of backend servers to start (default: 3)
- `--base-port`: Starting port number for backend servers (default: 9000)

## Test Reports

The testing framework generates detailed reports including:
- Summary statistics
- Response time analysis
- Server distribution
- Error analysis
- Raw data in JSON format for further analysis

Reports are saved in the current directory with timestamps:
- `load_test_report_YYYYMMDD_HHMMSS.txt`
- `load_test_stats_YYYYMMDD_HHMMSS.json`

## Project Structure

```
load-balancing/
├── lib/
│   ├── backend.py         # Backend server implementation
│   ├── load_balancers.py  # Load balancer implementations
│   ├── port_manager.py    # Port management utilities
│   ├── tester.py         # Load testing framework
│   └── utils.py          # Utility functions
├── load-balancing.py     # Main script
└── README.md            # This file
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 