# Formix - Private Map Secure Reduce

A proof-of-concept implementation of a privacy-preserving distributed computation network using secure multi-party computation (MPC) principles.

## Overview

Formix implements a two-tier network architecture:
- **Heavy Nodes**: Coordinators that manage computations and perform secure aggregation
- **Light Nodes**: Data providers that compute on their private data and send secret-shared results

The system uses additive secret sharing (mod 2^64) to ensure that individual values remain private while allowing aggregate computation.

## Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd formix

# Install using UV (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

## Quick Start

### 1. Create Heavy Nodes (you need at least 3)

```bash
# Create first heavy node
$ formix nn
Node type (heavy/light): heavy
✓ Created heavy node: NODE-ABC123 on port 8000

# Create second heavy node
$ formix nn
Node type (heavy/light): heavy
✓ Created heavy node: NODE-DEF456 on port 8001

# Create third heavy node
$ formix nn
Node type (heavy/light): heavy
✓ Created heavy node: NODE-GHI789 on port 8002
```

### 2. Create Light Nodes

```bash
# Create some light nodes
$ formix nn
Node type (heavy/light): light
✓ Created light node: NODE-JKL012 on port 8003

$ formix nn
Node type (heavy/light): light
✓ Created light node: NODE-MNO345 on port 8004
```

### 3. View Network Status

```bash
$ formix view

Formix Network Status
┏━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ UID        ┃ Node Type ┃ Port  ┃ Status ┃ Created At          ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ NODE-ABC123│ heavy     │ 8000  │ active │ 2024-01-01 10:00:00 │
│ NODE-DEF456│ heavy     │ 8001  │ active │ 2024-01-01 10:01:00 │
│ NODE-GHI789│ heavy     │ 8002  │ active │ 2024-01-01 10:02:00 │
│ NODE-JKL012│ light     │ 8003  │ active │ 2024-01-01 10:03:00 │
│ NODE-MNO345│ light     │ 8004  │ active │ 2024-01-01 10:04:00 │
└────────────┴───────────┴───────┴────────┴─────────────────────┘

Total nodes: 5 (Heavy: 3, Light: 2)
```

### 4. Create a Computation

```bash
$ formix comp

Create New Computation

Available Nodes:
  NODE-ABC123 (heavy)
  NODE-DEF456 (heavy)
  NODE-GHI789 (heavy)
  NODE-JKL012 (light)
  NODE-MNO345 (light)

Proposing node UID: NODE-JKL012

Available Heavy Nodes:
  NODE-ABC123
  NODE-DEF456
  NODE-GHI789

Heavy node 1 UID: NODE-ABC123
Heavy node 2 UID: NODE-DEF456
Heavy node 3 UID: NODE-GHI789

Computation prompt: Calculate average user satisfaction score

Note: For this PoC, response schema must be a single number
Response schema (JSON) [{"type": "number"}]: 

Deadline (seconds from now) [60]: 30
Minimum number of participants [1]: 2

✓ Computation COMP-XYZ789 created successfully!
```

### 5. Stop a Node

```bash
$ formix sn NODE-JKL012
Are you sure you want to stop node NODE-JKL012? [y/N]: y
✓ Stopped node NODE-JKL012 and cleaned up resources
```

## CLI Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `formix new-node` | `formix nn` | Create a new node |
| `formix stop-node <uid>` | `formix sn <uid>` | Stop a node and clean up |
| `formix view` | `formix v` | View network status |
| `formix comp` | `formix c` | Create a new computation |
| `formix status [comp_id]` | - | View computation status |

## Architecture

### Data Flow

1. **Computation Creation**: A node proposes a computation with 3 designated heavy nodes
2. **Broadcasting**: Heavy nodes broadcast the computation to all light nodes
3. **Private Computation**: Light nodes compute on their private data (random 0-100 for PoC)
4. **Secret Sharing**: Light nodes create 3 shares of their value and send one to each heavy node
5. **Aggregation**: At deadline, heavy nodes aggregate received shares
6. **Result Reconstruction**: Heavy nodes combine their partial sums to get the final average

### File Structure

```
~/.formix/
├── network.db              # Central network database
├── formix.log             # Application logs
├── NODE-ABC123/           # Heavy node directory
│   └── node.db           # Node-specific database
└── NODE-JKL012/           # Light node directory
    └── node.db           # Node-specific database
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=formix

# Run specific test file
pytest tests/test_secret_sharing.py
```

### Logging

Logs are written to:
- Console (INFO level by default)
- `~/.formix/formix.log` (DEBUG level)

Set log level with environment variable:
```bash
export FORMIX_LOG_LEVEL=DEBUG
formix view
```

## Limitations (PoC)

This is a proof-of-concept with several limitations:

1. **Single Machine**: All nodes run on localhost
2. **Simple Secret Sharing**: Basic additive secret sharing mod 2^64
3. **No Authentication**: No node authentication or secure channels
4. **Limited Schema**: Only single number responses supported
5. **Simplified Aggregation**: Heavy nodes don't fully coordinate for final result
6. **No Byzantine Tolerance**: Assumes all nodes are honest

## Future Enhancements

- [ ] Distributed deployment across multiple machines
- [ ] TLS/mTLS for secure communication
- [ ] More sophisticated secret sharing schemes (Shamir's, etc.)
- [ ] Support for complex computation schemas
- [ ] Byzantine fault tolerance
- [ ] Privacy-preserving authentication
- [ ] Differential privacy mechanisms
- [ ] Computation verification and integrity checks

## Contributing

This is a proof-of-concept project. Feel free to experiment and extend!

## License

[Your chosen license]
