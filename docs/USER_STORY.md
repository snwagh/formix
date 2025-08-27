# Formix Vision Document

## High-Level Vision

### Core Concept: Private Map Secure Reduce (PMSR)
A radical extension of the map-reduce paradigm that enables privacy-preserving distributed computation through a two-tier network architecture.

### Network Architecture
- **Two-tier participation model**: Heavy users and Light users
- **Privacy-first design**: Secure multi-party computation with secret sharing
- **Decentralized computation**: Network-wide distributed processing with privacy guarantees

### Key Innovation
Enable large-scale data science computations across private datasets without revealing individual data points, using secure aggregation and threshold-based anonymity.

## Proof of Concept Goals

### Primary Goals
1. **Demonstrate PMSR paradigm**: Show feasibility of private map-reduce operations
2. **Local network simulation**: Run entire network on single machine for testing
3. **End-to-end workflow**: Complete computation lifecycle from proposal to result
4. **Privacy mechanism**: Implement secret sharing and secure aggregation
5. **CLI-first experience**: Professional developer tooling comparable to gh, k3d, docker

### Non-Goals
1. **Production deployment**: Not targeting real network deployment in PoC
2. **Complex computations**: Limited to single numeric aggregations initially
3. **Advanced privacy**: No differential privacy or advanced cryptographic protocols
4. **Performance optimization**: Focus on correctness over performance
5. **Multi-machine setup**: All processes run locally
6. **Secret sharing**: This will be limited to creating random shares modulo 2^32

## Technical Requirements

### Core Technologies
- **Language**: Python (modern, async-first)
- **Package Management**: UV
- **CLI Framework**: Typer (rich terminal experience)
- **Database**: SQLite (lightweight, file-based)
- **Logging**: Loguru (structured, async-compatible)
- **Concurrency**: asyncio, concurrent.futures

### Architecture Components

#### Storage Layer
```
~/.formix/
├── network.db          # Global network state
│   ├── users table     # Node registry
│   └── computations    # Computation tracking
└── nodes/
    └── {UID}/
        └── node.db     # Node-specific data
```

#### Node Types
1. **Heavy Nodes**
   - Accept computation proposals
   - Broadcast to network
   - Perform secure aggregation
   - Manage computation lifecycle

2. **Light Nodes**
   - Receive computation broadcasts
   - Execute local computations
   - Send secret shares to heavy nodes
   - Manual/automatic approval flow

#### Main user story / flow
0. Entire flow is performed initially using the cli
1. A Node proposes a computation. 
2. 3 Heavy Nodes are chosen as the computation nodes (by default we should pick the first 3)
3. If a computation is valid, then the first heavy node will send the computation to all the light nodes in the network.
4. The light nodes upon receiving the computation will then generate with their response ( Note that in the proof of concept, the computation response will always be a simple dictionary with a single key and the light nodes will all respond with a random value between 0 and 100)
5. Their response is secret shared modular 2^32. So, essentially three random numbers, each between 0 and 2^32-1 are generated such that they add upto the response modulo 2^32.
6. Each of these numbers is sent to one of the heavy nodes of the computation respectively.
7. The heavy nodes at the end of the computation timeline will then (1) Check whether the anonymity threshold has been met so at least that many light nodes have responded and (2)if yes, then add up all their shares locally modulo 2^32. 
8. The other two heavy nodes will then send their total to the first heavy Node which who will then sum these 3 numbers modulo 2^32 and write the computation result to the network.db database as well as the stdout. 


## Success Criteria

### Functional Requirements
- [ ] Create and manage nodes via CLI
- [ ] Propose computations with Pydantic schemas
- [ ] Automatic computation execution on light nodes
- [ ] Secure aggregation with 3-party computation
- [ ] Threshold-based result revelation

### Quality Requirements
- [ ] Excellent CLI UX (comparable to gh, docker)
- [ ] Comprehensive logging with loguru
- [ ] Async/concurrent operations throughout
- [ ] Clean separation of concerns
- [ ] Extensible architecture for future enhancements
- [ ] Provide excellent concurrency support since everything is run on a single machine and the database is probably being accessed by multiple processes.