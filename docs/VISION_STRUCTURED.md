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

#### Computation Flow
1. Proposal → 3 Heavy Nodes
2. Broadcast → All Light Nodes
3. Local Execution → Secret Shares
4. Aggregation → Result (if threshold met)

### Security & Privacy Requirements
- **Secret Sharing**: Modulo 2^64 arithmetic
- **Threshold Privacy**: Minimum participants before revealing
- **No Single Point of Trust**: 3-party computation
- **Time-bounded**: UTC deadlines for all computations

## Implementation Phases

### Phase 1: Foundation
- Project structure with UV
- CLI skeleton with Typer
- Database schema and migrations
- Logging infrastructure

### Phase 2: Node Management
- `formix new-node` implementation
- `formix stop-node` implementation
- `formix view` network visualization
- Node lifecycle management

### Phase 3: Computation Engine
- `formix comp` interactive prompt
- Computation proposal and validation
- Broadcasting mechanism
- Secret sharing implementation

### Phase 4: Execution & Aggregation
- Light node computation execution
- Heavy node aggregation logic
- Threshold checking
- Result finalization

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

## Future Considerations

### Potential Extensions
- Support for complex Pydantic schemas
- Differential privacy mechanisms
- Network communication protocols
- Authentication and authorization
- Computation marketplace
- Resource management and quotas

### Research Questions
- Optimal secret sharing schemes
- Incentive mechanisms for participation
- Computation verification methods
- Privacy-utility tradeoffs
- Scalability limits and optimizations