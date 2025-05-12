# Distributed Computing Lab

Welcome to the **Distributed Computing Lab** repository! This repository contains various experiments related to distributed computing, covering fundamental concepts, algorithms, and implementations.

## Topics Covered
- Message Passing and RPC
- Message queues
- Multiprocessing vs parallel processing
- Network Time Protocol
- Logical Clocks
- Mutual Exclusion
- Load Balancing
- Leader Election Algorithms

## Experiments

### RPC (Remote Procedure Calls)
```mermaid
graph LR
    Client[Client] -->|Request| Server[Server]
    Server -->|Response| Client
    subgraph "RPC Implementations"
    gRPC[gRPC]
    XML[XML-RPC]
    Pyro[Pyro]
    end
```

### Message Queues
```mermaid
graph LR
    P1[Producer 1] -->|send| Queue[Message Queue]
    P2[Producer 2] -->|send| Queue
    Queue -->|receive| C1[Consumer 1]
    Queue -->|receive| C2[Consumer 2]
```

### Multiprocessing vs Multithreading
```mermaid
graph TB
    subgraph "Multiprocessing"
    Process1[Process 1] 
    Process2[Process 2]
    Process3[Process 3]
    end
    
    subgraph "Multithreading"
    Process[Process] --> Thread1[Thread 1]
    Process --> Thread2[Thread 2]
    Process --> Thread3[Thread 3]
    end
```

### Network Time Protocol
```mermaid
sequenceDiagram
    participant C as Client
    participant S as NTP Server
    C->>S: Request Time (t1)
    Note right of S: Server receives at t2
    S->>C: Response (t3)
    Note left of C: Client receives at t4
    Note left of C: Offset = ((t2-t1)+(t3-t4))/2
```

### Logical Clocks
```mermaid
sequenceDiagram
    participant A as Process A
    participant B as Process B
    participant C as Process C
    Note over A,C: Initial clock values: A=0, B=0, C=0
    A->>A: Local event (Clock: 1)
    A->>B: Message (Clock: 2)
    Note over B: Clock max(0, 2)+1 = 3
    B->>C: Message (Clock: 4)
    Note over C: Clock max(0, 4)+1 = 5
```

### Mutual Exclusion
```mermaid
stateDiagram-v2
    [*] --> Not_Requesting
    Not_Requesting --> Requesting: Request Critical Section
    Requesting --> In_CS: Acquire Permission
    In_CS --> Not_Requesting: Release Critical Section
```

### Load Balancing
```mermaid
graph LR
    Client1[Client 1] -->|Request| LB[Load Balancer]
    Client2[Client 2] -->|Request| LB
    Client3[Client 3] -->|Request| LB
    LB -->|Forward| S1[Server 1]
    LB -->|Forward| S2[Server 2]
    LB -->|Forward| S3[Server 3]
```

### Bully and Ring Election Algorithms
```mermaid
graph TD
    subgraph "Bully Algorithm"
    N1[Node 1] -->|Election| N2[Node 2]
    N1 -->|Election| N3[Node 3]
    N2 -->|OK| N1
    N3 -->|Coordinator| N1
    N3 -->|Coordinator| N2
    end
    
    subgraph "Ring Algorithm"
    P1[Process 1] -->|Token| P2[Process 2]
    P2 -->|Token| P3[Process 3] 
    P3 -->|Token| P4[Process 4]
    P4 -->|Token| P1
    end
```

## How to Use
1. Clone the repository:
   ```sh
   git clone https://github.com/Asim-Shah-2004/Distributed_Computing-lab.git
   ```
2. Navigate to the specific experiment directory.
3. Follow the instructions in the respective README files to run the experiments.

## Requirements
- Programming Languages: Python / Java / C++
- MPI Library (e.g., OpenMPI)
- Docker (if needed for containerized execution)

## Contributing
Contributions are welcome! Feel free to submit issues or pull requests to improve the experiments and documentation.
