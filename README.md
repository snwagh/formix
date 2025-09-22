# Formix - Private Map Secure Reduce Network

A pure Python implementation of a privacy-preserving distributed computation network using secret sharing and secure multi-party computation.

## Overview

Formix implements the Private Map Secure Reduce (PMSR) paradigm, enabling secure distributed computation across private datasets without revealing individual data points. The network uses a two-tier architecture with heavy nodes (coordinators) and light nodes (data providers).

## Key Features

- **Secret Sharing**: Additive secret sharing scheme (mod 2^32) for privacy preservation
- **Two-tier Architecture**: Heavy nodes for coordination, light nodes for computation
- **3-Party Reveal Protocol**: Secure aggregation with threshold-based revelation
- **Heavy Node Coordination**: Synchronized initialization ensures reliable computation
- **Pure Python API**: Simple, clean interface without CLI complexity
- **Async/Await**: Modern Python async architecture for concurrent operations
- **Automatic Cleanup**: Proper resource management and database cleanup

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/formix.git
cd formix

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

## Quick Start

```python
import asyncio
from src.formix import FormixNetwork

async def run_computation():
    # Create and start a network
    network = FormixNetwork()
    await network.start_network(heavy_count=3, light_count=5)

    # Propose a computation
    comp_id = await network.propose_computation(
        "What's your favorite number between 0 and 100?"
    )

    # Wait for the result
    result = await network.wait_for_computation(comp_id)
    print(f"Result: {result['result']}")
    print(f"Participants: {result['participants_count']}")

    # Cleanup
    await network.shutdown()

# Run the computation
asyncio.run(run_computation())
```

## Architecture

### Network Components

- **Heavy Nodes**: Coordinate computations and perform secure aggregation
  - Exactly 3 heavy nodes required per computation
  - Receive secret shares from light nodes
  - Perform reveal protocol at deadline

- **Light Nodes**: Provide data and compute responses
  - Receive computation broadcasts
  - Generate responses and secret shares
  - Send shares to designated heavy nodes

### Computation Flow

1. **Proposal**: A computation is proposed with prompt, deadline, and minimum participants
2. **Heavy Node Initialization**: All 3 designated heavy nodes initialize computation aggregators
3. **Coordination**: Heavy nodes confirm readiness before proceeding
4. **Light Node Broadcast**: Computation details sent to all light nodes
5. **Response Generation**: Light nodes compute responses and create 3 secret shares each
6. **Share Distribution**: Each light node sends one share to each heavy node
7. **Share Aggregation**: Heavy nodes aggregate received shares independently
8. **3-Party Reveal**: At deadline, primary heavy node coordinates reveal with other 2 nodes
9. **Result Reconstruction**: Final result computed by combining all partial sums (mod 2^32)
10. **Database Storage**: Result and metadata stored for retrieval

## API Reference

### FormixNetwork Class

```python
class FormixNetwork:
    async def start_network(heavy_count: int = 3, light_count: int = 5)
        """Start a network with specified nodes"""

    async def propose_computation(
        prompt: str,
        deadline_seconds: int = 60,
        min_participants: int = 1
    ) -> str
        """Propose a computation and return computation ID"""

    async def wait_for_computation(comp_id: str, timeout: int = 120) -> dict
        """Wait for computation to complete and return result"""

    async def get_computation_status(comp_id: str) -> dict
        """Get current status of a computation"""

    async def get_network_status() -> dict
        """Get overall network status"""

    async def shutdown()
        """Gracefully shutdown the network"""
```

### Context Manager Support

```python
async with FormixNetwork() as network:
    await network.start_network(heavy_count=3, light_count=5)
    comp_id = await network.propose_computation("What is your average sleep score from last year", deadline_seconds=30)
    result = await network.wait_for_computation(comp_id)
    # Network automatically shuts down when context exits
```

### Convenience Functions

```python
from src.formix import quick_network, quick_computation

# Quick network creation
network = await quick_network(heavy_count=3, light_count=5)

# Quick computation with auto-wait
result = await quick_computation(network, "Your prompt", wait=True)
```

## Examples

### Basic Example

```bash
uv run python -m asyncio


from src.formix import FormixNetwork

network = FormixNetwork()
await network.start_network(heavy_count=3, light_count=5)

comp_id = await network.propose_computation("What was your average sleep score form the last year?", deadline_seconds=30, min_participants=2)

result = await network.wait_for_computation(comp_id)
print(f"Result: {result['result']}")
print(f"Participants: {result['participants_count']}")

await network.shutdown()
```


```python
import asyncio
from src.formix import FormixNetwork

async def basic_example():
    network = FormixNetwork()
    await network.start_network(heavy_count=3, light_count=5)

    comp_id = await network.propose_computation(
        "What's your favorite number?"
    )

    result = await network.wait_for_computation(comp_id)
    print(f"Result: {result['result']}")

    await network.shutdown()

asyncio.run(basic_example())
```

### Multiple Computations

```python
async def multiple_computations():
    async with FormixNetwork() as network:
        await network.start_network(heavy_count=3, light_count=10)

        # Launch multiple computations
        comp_ids = []
        for i in range(5):
            comp_id = await network.propose_computation(
                f"Computation {i}: Pick a random number",
                deadline_seconds=30
            )
            comp_ids.append(comp_id)

        # Wait for all results
        for comp_id in comp_ids:
            result = await network.wait_for_computation(comp_id)
            print(f"{comp_id}: {result['result']}")
```

### Monitoring Example

```python
async def monitor_computation():
    network = FormixNetwork()
    await network.start_network(heavy_count=3, light_count=5)

    comp_id = await network.propose_computation("Test computation")

    # Monitor progress
    while True:
        status = await network.get_computation_status(comp_id)
        print(f"Status: {status['status']}")

        if status['status'] in ['completed', 'failed']:
            break

        await asyncio.sleep(1)

    await network.shutdown()
```

### Real Test Example

The included `test_network.py` demonstrates a complete working computation:

```python
# Example output from test_network.py
# Light nodes respond with values: 11, 20, 72
# Secret sharing splits each value into 3 shares
# Heavy nodes aggregate shares independently
# 3-party reveal reconstructs: 11 + 20 + 72 = 103
# Final result: 103 with 3 participants
```

**Key Validation Points:**
- ✅ All 6 nodes (3 heavy + 3 light) start successfully
- ✅ Heavy nodes coordinate initialization before processing
- ✅ Light nodes generate responses and create secret shares
- ✅ All shares properly distributed to all heavy nodes
- ✅ 3-party reveal protocol executes correctly
- ✅ Final result matches expected sum: `11 + 20 + 72 = 103`
- ✅ Database cleanup removes all nodes and data

```bash
# Run the working test
uv run test_network.py
```

## Development

### Project Structure

```
formix/
├── src/formix/
│   ├── core/           # Core node and network logic
│   │   ├── __init__.py
│   │   ├── node.py     # Heavy/Light node implementations with coordination
│   │   └── network.py  # FormixNetwork manager class
│   ├── db/             # Database layer
│   │   ├── __init__.py
│   │   └── database.py # Network and node databases
│   ├── protocols/      # Cryptographic protocols
│   │   ├── __init__.py
│   │   ├── aggregation.py    # 3-party secure aggregation
│   │   ├── messaging.py      # Network messaging with concurrency
│   │   └── secret_sharing.py # Additive secret sharing (mod 2^32)
│   ├── utils/          # Helper functions
│   │   ├── __init__.py
│   │   ├── async_helpers.py  # Concurrency utilities
│   │   ├── config.py         # Configuration and logging
│   │   └── helpers.py        # Utility functions
│   └── __init__.py     # Main package exports
├── test_network.py     # Complete workflow test
├── example_usage.py    # Usage examples
└── README.md          # This file
```

### Testing

```bash
# Run the main test (demonstrates complete workflow)
uv run test_network.py

# Run comprehensive examples (if available)
uv run python example_usage.py
```

### Logging

Logs are written to:
- `~/.formix/formix.log` - Main application log
- `~/.formix/Nodes/{UID}/logs.log` - Per-node logs

Set log level with environment variable:
```bash
export FORMIX_LOG_LEVEL=DEBUG
```

## Privacy & Security

### Secret Sharing Protocol
- All values are split into 3 shares modulo 2^32
- Each heavy node receives one share from each light node
- No single heavy node can reconstruct individual values
- Final result requires cooperation of all 3 heavy nodes

### Anonymity Threshold
- Minimum participant requirement before revealing results
- Configurable per computation (default: 1 for testing)
- Protects against deanonymization attacks

### Security Considerations
- **No Authentication**: Current implementation lacks node authentication
- **No Encryption**: Messages sent in plaintext (localhost only)
- **Trust Assumption**: Assumes honest-but-curious adversary model
- **Single Machine**: Designed for local testing, not distributed deployment

## Requirements

- Python 3.11+
- Dependencies:
  - `aiohttp>=3.9.0` - Async HTTP server/client
  - `aiosqlite>=0.19.0` - Async SQLite database
  - `loguru>=0.7.2` - Structured logging
  - `pydantic>=2.5.0` - Data validation

## Limitations (Proof of Concept)

This is a PoC implementation with several limitations:

1. **Local Execution**: All nodes run on localhost
2. **Simple Computations**: Only single numeric responses supported
3. **Basic Secret Sharing**: Additive secret sharing without advanced cryptography
4. **No Byzantine Tolerance**: Assumes all nodes follow protocol
5. **Limited Error Handling**: Basic error recovery mechanisms

## Current Status & Achievements

✅ **Completed Features:**
- Complete Private Map Secure Reduce (PMSR) workflow implementation
- Heavy node coordination with initialization synchronization
- 3-party reveal protocol with secure aggregation
- Additive secret sharing (mod 2^32) with proper reconstruction
- Automatic database and resource cleanup
- Pure Python API with async/await architecture
- Comprehensive logging and error handling

## Future Enhancements

- [ ] Distributed deployment across multiple machines
- [ ] TLS/mTLS for secure communication
- [ ] Advanced secret sharing schemes (Shamir's, etc.)
- [ ] Support for complex computation schemas
- [ ] Byzantine fault tolerance
- [ ] Differential privacy mechanisms
- [ ] Zero-knowledge proofs for result verification
- [ ] Persistent node processes with proper lifecycle management

## Contributing

Contributions are welcome! Please ensure:
1. Code follows existing patterns and style
2. Tests are included for new features
3. Documentation is updated

## License

MIT License - See LICENSE file for details

## Status

🎉 **Fully Functional PoC**: Complete implementation of Private Map Secure Reduce with working secret sharing, 3-party reveal protocol, and heavy node coordination. Suitable for research, demonstration, and local testing. Not suitable for production use without additional security hardening and distributed deployment capabilities.