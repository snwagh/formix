# Formix Setup and Usage Guide

## Overview

This guide documents the complete setup and usage of the Formix privacy-preserving distributed computation network. Formix implements secure multi-party computation (MPC) using additive secret sharing to enable privacy-preserving data aggregation.

## Prerequisites

- Python 3.11+
- `pip` or `uv` package manager
- Basic understanding of terminal commands

## Installation

### Step 1: Install the Project

```bash
# Navigate to the project directory
cd /Users/Aayush/Documents/GitHub/formix

# Install the project in editable mode
pip install -e .
```

**Note**: If you encounter dependency conflicts, they are usually safe to ignore for basic functionality.

### Step 2: Verify Installation

```bash
# Check that the formix command is available
formix --help
```

You should see the CLI help menu with available commands.

## Network Setup

### Step 3: Create Heavy Nodes (Coordinators)

Formix requires at least 3 heavy nodes for secure computation. Create them one by one:

```bash
# Create first heavy node
formix --new-node --type heavy --foreground

# Create second heavy node (in new terminal)
formix --new-node --type heavy --foreground

# Create third heavy node (in new terminal)
formix --new-node --type heavy --foreground
```

**Important**: Each node runs in its own terminal. Keep all terminals open for the network to function.

### Step 4: Create Light Nodes (Data Providers)

Create light nodes that will provide private data for computations:

```bash
# Create first light node (in new terminal)
formix --new-node --type light --foreground

# Create second light node (in new terminal)
formix --new-node --type light --foreground
```

### Step 5: Verify Network Status

Check that all nodes are running:

```bash
formix --view
```

Expected output:

```
Formix Network Status
┏━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ UID      ┃ Node Type ┃ Port ┃ Status ┃ Created At          ┃
┡━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ [UID1]   │ heavy     │ 8000 │ active │ [timestamp]         │
│ [UID2]   │ heavy     │ 8001 │ active │ [timestamp]         │
│ [UID3]   │ heavy     │ 8002 │ active │ [timestamp]         │
│ [UID4]   │ light     │ 8003 │ active │ [timestamp]         │
│ [UID5]   │ light     │ 8004 │ active │ [timestamp]         │
└──────────┴───────────┴───────┴────────┴─────────────────────┘

Total nodes: 5 (Heavy: 3, Light: 2)
```

## Running Computations

### Step 6: Create a Computation

Create a privacy-preserving computation:

```bash
# Interactive mode
formix --comp

# Or with predefined inputs (use with echo for automation)
echo -e "[LIGHT_NODE_UID]\n[HEAVY_NODE_1]\n[HEAVY_NODE_2]\n[HEAVY_NODE_3]\n[COMPUTATION_PROMPT]\n{\"type\": \"number\"}\n[DEADLINE_SECONDS]\n[MIN_PARTICIPANTS]" | formix --comp
```

**Example computation:**

```bash
echo -e "Y2X1Z3VU\nBQX9DIJF\n4C7U5L8R\nY6B07RS6\nCalculate average user rating from 1-10\n{\"type\": \"number\"}\n20\n1" | formix --comp
```

**Parameters:**

- **Proposing node**: A light node UID (data provider)
- **Heavy nodes**: 3 coordinator node UIDs
- **Computation prompt**: Description of what to compute
- **Schema**: Must be `{"type": "number"}` for single numeric results
- **Deadline**: Seconds from now for computation completion
- **Min participants**: Minimum light nodes needed (1-2 recommended)

### Step 7: Monitor Computation Progress

```bash
# Check all computations
formix --status ""

# Check specific computation
formix --status COMP-[ID]
```

### Step 8: View Results

Once completed, the computation will show:

- **Status**: completed
- **Result**: The aggregated value (e.g., 54.0)
- **Participants**: Number of light nodes that contributed

## How It Works

### Privacy-Preserving Computation Flow

1. **Computation Creation**: A light node proposes a computation with 3 heavy node coordinators
2. **Broadcast**: Heavy nodes broadcast the computation to all light nodes
3. **Private Computation**: Each light node:
   - Computes on its private data (generates random value 1-100 in PoC)
   - Creates 3 secret shares using additive secret sharing (mod 2^64)
   - Sends one share to each heavy node
4. **Aggregation**: At deadline, heavy nodes combine received shares
5. **Result Reconstruction**: Heavy nodes reconstruct the final aggregated result

### Key Security Properties

- **Individual Privacy**: No single node sees another node's private data
- **Secure Aggregation**: Results computed without exposing raw data
- **Distributed Trust**: No single point of failure
- **Verifiable**: Cryptographic guarantees through secret sharing

## Troubleshooting

### Common Issues

1. **"formix: command not found"**

   - Ensure you ran `pip install -e .`
   - Try `python -m formix.cli.main` instead

2. **Computation stuck on "pending"**

   - Check that light nodes are running and connected
   - Ensure minimum participants is ≤ number of active light nodes
   - Verify heavy nodes can communicate with light nodes

3. **Connection failures in logs**

   - Some connectivity issues are normal in the PoC
   - The system is designed to work with partial failures

4. **No participants in computation**
   - Light nodes may not be receiving broadcasts
   - Check network connectivity between heavy and light nodes

### Log Files

Check logs for debugging:

```bash
# Main application logs
tail -f ~/.formix/formix.log

# Individual node logs
tail -f ~/.formix/[NODE_UID]/logs.log
```

## Example Session

Here's a complete working example:

```bash
# 1. Install
pip install -e .

# 2. Create 3 heavy nodes (each in separate terminals)
formix --new-node --type heavy --foreground  # Terminal 1
formix --new-node --type heavy --foreground  # Terminal 2
formix --new-node --type heavy --foreground  # Terminal 3

# 3. Create 2 light nodes (each in separate terminals)
formix --new-node --type light --foreground  # Terminal 4
formix --new-node --type light --foreground  # Terminal 5

# 4. Check network
formix --view

# 5. Create computation
echo -e "LIGHT_NODE_UID\nHEAVY1\nHEAVY2\nHEAVY3\nCalculate average rating\n{\"type\": \"number\"}\n30\n1" | formix --comp

# 6. Monitor and check results
formix --status ""
```

## Architecture Notes

- **Heavy Nodes**: Coordinate computations, perform secure aggregation
- **Light Nodes**: Provide private data, participate in secret sharing
- **Secret Sharing**: Additive sharing mod 2^64 for privacy
- **Communication**: HTTP-based messaging between nodes
- **Storage**: SQLite databases for each node and network state

## Next Steps

- Experiment with different computation prompts
- Add more nodes to increase network robustness
- Monitor logs to understand the secret sharing process
- Try computations with different minimum participant requirements

## Support

This is a proof-of-concept implementation. For issues or questions:

1. Check the logs in `~/.formix/`
2. Verify all nodes are running
3. Ensure network connectivity between nodes
4. Review the main README.md for additional context
