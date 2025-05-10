# Distributed System Consistency Models Demonstration

This project demonstrates different consistency models in distributed systems using Docker containers. It provides a visual and interactive way to understand the CAP theorem, consistency models, and their trade-offs in real-world scenarios.

## Features

- **Multiple Consistency Models**:
  - Strong Consistency (CP)
  - Eventual Consistency (AP)
  - Causal Consistency
  - Read Your Writes Consistency

- **CAP Theorem Demonstrations**:
  - Real-time network state visualization
  - Live demonstrations of consistency, availability, and partition tolerance
  - Trade-off analysis with pros and cons
  - Real-world examples of different CAP choices

- **Advanced Visualization**:
  - Interactive network diagram
  - CAP triangle visualization
  - Detailed performance metrics and statistics
  - Operation history with status tracking
  - Step-by-step explanations with Markdown formatting

- **Chaos Testing**:
  - Network partitions
  - Node failures
  - Recovery scenarios
  - Performance monitoring during failures

## Prerequisites

- Docker and Docker Compose
- Python 3.11 or higher
- Git

## Quick Start

1. Clone the repository:
```bash
git clone <repository-url>
cd consistency-models
```

2. Build and start the containers:
```bash
docker-compose up --build
```

3. The system will automatically:
   - Start a Redis cache for coordination
   - Launch 4 nodes with different consistency models
   - Run the test client to demonstrate various scenarios
   - Display visualizations in the terminal

## System Architecture

The system consists of several components:

- **Redis Cache**: Central coordination and state management
- **Distributed Nodes**: 4 nodes implementing different consistency models
  - Node 1: Strong Consistency (Port 5001)
  - Node 2: Eventual Consistency (Port 5002)
  - Node 3: Causal Consistency (Port 5003)
  - Node 4: Read Your Writes Consistency (Port 5004)
- **Test Client**: Automated testing and demonstration
- **Visualizer**: Real-time system state visualization

## Testing and Demonstration

The test client automatically runs through several scenarios:

1. **Strong Consistency Test**:
   - Demonstrates immediate consistency across all nodes
   - Shows CP (Consistency over Availability) trade-offs

2. **Eventual Consistency Test**:
   - Shows how data eventually converges
   - Demonstrates AP (Availability over Consistency) benefits

3. **Causal Consistency Test**:
   - Demonstrates preservation of causal relationships
   - Shows how operations maintain their logical order

## Monitoring and Logs

- Logs are stored in the `logs/` directory
- Each node has its own log file
- Real-time visualization in the terminal
- Performance metrics and statistics

## Development

To modify or extend the system:

1. Update the consistency models in `distributed_node.py`
2. Modify test scenarios in `test_client.py`
3. Enhance visualizations in `visualizer.py`
4. Update Docker configuration in `docker-compose.yml`

## Tech Stack

### Backend
- **Python 3.11**: Core programming language
- **FastAPI**: High-performance web framework for building APIs
- **Redis**: In-memory data store for coordination and caching
- **Uvicorn**: ASGI server for running FastAPI applications

### Visualization & UI
- **Rich**: Terminal formatting and visualization library
- **Colorama**: Cross-platform colored terminal text
- **Markdown**: Documentation and text formatting
- **Pygments**: Syntax highlighting

### Containerization & Deployment
- **Docker**: Containerization platform
- **Docker Compose**: Multi-container orchestration
- **Python Slim**: Lightweight base image for containers

### Testing & Monitoring
- **Requests**: HTTP library for API testing
- **Logging**: Built-in Python logging with rotation
- **Custom Test Client**: Automated testing framework

## API Routes

Each distributed node exposes the following REST API endpoints:

### Node Status
- `GET /status`
  - Returns node information including ID, consistency model, and health status
  - Response includes vector clock and performance metrics

### Data Operations
- `POST /write`
  - Write data to the node
  - Request body: `{"key": string, "value": string}`
  - Returns success status and confirmation message

- `GET /read/{key}`
  - Read data from the node
  - Path parameter: key to read
  - Returns data item with metadata and version information

### Replication
- `POST /replicate`
  - Handle data replication from other nodes
  - Request body: `{"key": string, "data": object}`
  - Returns replication status

### Simulation Controls
- `POST /simulate_failure`
  - Simulate node failure
  - Returns confirmation of failure state

- `POST /simulate_recovery`
  - Simulate node recovery
  - Returns confirmation of recovery

- `POST /simulate_partition`
  - Simulate network partition
  - Request body: `{"nodes": string[]}`
  - Returns partition status

### Example Usage

```bash
# Check node status
curl http://localhost:5001/status

# Write data
curl -X POST http://localhost:5001/write \
  -H "Content-Type: application/json" \
  -d '{"key": "test", "value": "hello"}'

# Read data
curl http://localhost:5001/read/test

# Simulate failure
curl -X POST http://localhost:5001/simulate_failure
```
