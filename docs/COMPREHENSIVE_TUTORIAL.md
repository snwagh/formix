# Formix Tutorial: Privacy-Preserving Distributed Computation

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Creating Heavy Nodes](#creating-heavy-nodes)
4. [Creating Light Nodes](#creating-light-nodes)
5. [Network Verification](#network-verification)
6. [Creating Computations](#creating-computations)
7. [Monitoring Computations](#monitoring-computations)
8. [Understanding Results](#understanding-results)
9. [Technical Deep Dive](#technical-deep-dive)
10. [Troubleshooting](#troubleshooting)

## Introduction

Formix is a **privacy-preserving distributed computation network** that uses **secure multi-party computation (MPC)** and **additive secret sharing** to compute aggregate statistics across distributed private datasets without revealing individual data.

### What Makes Formix Special?

- **Zero-Knowledge Privacy**: Individual data never leaves its owner's node
- **Cryptographic Security**: Mathematical guarantees through secret sharing
- **Distributed Trust**: No single point of failure
- **Real-World MPC**: Practical implementation of advanced cryptographic techniques

### Architecture Overview

Formix uses a **two-tier network architecture**:

- **Heavy Nodes**: Coordinators that manage computations and perform secure aggregation
- **Light Nodes**: Data providers that compute on private data and send secret shares

---

## Installation

### Step 1: Install the Project

**Command:**

```bash
cd /Users/Aayush/Documents/GitHub/formix
pip install -e .
```

**What happens:**

- Installs Formix in "editable" mode (`-e`)
- Makes the `formix` CLI command available system-wide
- Installs all dependencies (aiohttp, typer, rich, etc.)

**Expected Output:**

```
Obtaining file:///Users/Aayush/Documents/GitHub/formix
Installing build dependencies ... done
Checking if build backend supports build_editable ... done
Getting requirements to build editable ... done
Installing backend dependencies ... done
Preparing editable metadata (pyproject.toml) ... done
Collecting aiohttp>=3.9.0 (from formix==0.1.0)
...
Successfully installed formix-0.1.0
```

**Process Explanation:**

- `pip install -e .` creates a symlink to your source code
- Changes to the code are immediately reflected (no reinstall needed)
- The `formix` command becomes available in your PATH

### Step 2: Verify Installation

**Command:**

```bash
formix --help
```

**Expected Output:**

```
Usage: formix [OPTIONS]

Formix - Private Map Secure Reduce Network
A privacy-preserving distributed computation network using secure multi-party computation.

╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --new-node    -nn            Create a new node                                                                                                      │
│ --type        -t       TEXT  Node type (heavy/light) [default: None]                                                                                │
│ --foreground  -f             Run node in foreground (blocks terminal)                                                                               │
│ --stop-node   -sn      TEXT  Stop a node by UID [default: None]                                                                                     │
│ --stop-all    -sa            Stop all nodes in the network                                                                                          │
│ --view        -v             View network status                                                                                                    │
│ --comp        -c             Create a computation                                                                                                   │
│ --status      -s       TEXT  Show computation status (optional: comp_id) [default: None]                                                            │
│ --help                       Show this message and exit.                                                                                            │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

**Process Explanation:**

- CLI built with **Typer** framework
- Rich formatting for beautiful terminal output
- Comprehensive help system with aliases

---

## Creating Heavy Nodes

### Step 3: Create First Heavy Node

**Command:**

```bash
formix --new-node --type heavy --foreground
```

**Expected Output:**

```
╭─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Create New Node                                                                                                                                     │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
2025-08-28 18:48:49 | INFO     | formix.db.database:initialize:63 - Network database initialized
2025-08-28 18:48:49 | INFO     | formix.db.database:add_node:74 - Added heavy node BQX9DIJF on port 8001
2025-08-28 18:48:49 | INFO     | formix.db.database:initialize_heavy_node:209 - Initialized heavy node database for BQX9DIJF
✓ Created heavy node: BQX9DIJF on port 8001
Node BQX9DIJF running on port 8001. Press Ctrl+C to stop.
2025-08-28 18:48:49 | INFO     | [BQX9DIJF] - Node BQX9DIJF started on port 8001
```

**Process Explanation:**

1. **Database Initialization:**

   - Creates/connects to SQLite database at `~/.formix/network.db`
   - Initializes network-wide state management

2. **Node Registration:**

   - Generates unique 8-character UID (e.g., "BQX9DIJF")
   - Assigns available port (starting from 8000)
   - Records node type as "heavy"

3. **Node-Specific Setup:**

   - Creates per-node database at `~/.formix/BQX9DIJF/node.db`
   - Sets up logging for this specific node

4. **Server Startup:**
   - Starts HTTP server on assigned port
   - Registers message handling routes (`/message`, `/health`)
   - Node enters active state and begins listening

**Important:** Each heavy node runs in its own terminal. Keep all terminals open!

### Step 4: Create Additional Heavy Nodes

**Repeat the command in new terminals:**

**Terminal 2:**

```bash
formix --new-node --type heavy --foreground
```

**Output:** Heavy node created on port 8002

**Terminal 3:**

```bash
formix --new-node --type heavy --foreground
```

**Output:** Heavy node created on port 8003

**Process Explanation:**

- Each node gets a unique UID and port
- Ports auto-increment (8000, 8001, 8002, etc.)
- All nodes share the same network database
- Each maintains its own node-specific database

---

## Creating Light Nodes

### Step 5: Create Light Nodes

**Terminal 4:**

```bash
formix --new-node --type light --foreground
```

**Expected Output:**

```
╭─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Create New Node                                                                                                                                     │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
2025-08-28 18:49:16 | INFO     | formix.db.database:initialize:63 - Network database initialized
2025-08-28 18:49:16 | INFO     | formix.db.database:add_node:74 - Added light node Y2X1Z3VU on port 8004
2025-08-28 18:49:16 | INFO     | formix.db.database:initialize_light_node:234 - Initialized light node database for Y2X1Z3VU
✓ Created light node: Y2X1Z3VU on port 8004
Node Y2X1Z3VU running on port 8004. Press Ctrl+C to stop.
2025-08-28 18:49:16 | INFO     | [Y2X1Z3VU] - Node Y2X1Z3VU started on port 8004
```

**Terminal 5:**

```bash
formix --new-node --type light --foreground
```

**Output:** Light node created on port 8005

**Process Explanation:**

**Light Node Responsibilities:**

- **Data Ownership**: Store and manage private datasets
- **Computation Participation**: Respond to computation requests
- **Secret Sharing**: Generate and distribute cryptographic shares
- **Local Processing**: All computation happens on local data

**Key Differences from Heavy Nodes:**

- No coordination responsibilities
- Simpler database schema (responses, actions)
- Automatic participation in computations
- No aggregation logic

---

## Network Verification

### Step 6: Check Network Status

**Command:**

```bash
formix --view
```

**Expected Output:**

```
                    Formix Network Status
┏━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ UID      ┃ Node Type ┃ Port ┃ Status ┃ Created At          ┃
┡━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ JWJT6TDJ │ heavy     │ 8000 │ active │ 2025-08-28 22:47:32 │
│ BQX9DIJF │ heavy     │ 8001 │ active │ 2025-08-28 22:48:49 │
│ 4C7U5L8R │ heavy     │ 8002 │ active │ 2025-08-28 22:48:58 │
│ Y6B07RS6 │ heavy     │ 8003 │ active │ 2025-08-28 22:49:06 │
│ Y2X1Z3VU │ light     │ 8004 │ active │ 2025-08-28 22:49:16 │
│ OLGGPAO7 │ light     │ 8005 │ active │ 2025-08-28 22:49:24 │
└──────────┴───────────┴────────┴────────┴─────────────────────┘

Total nodes: 6 (Heavy: 4, Light: 2)
```

**Process Explanation:**

**Database Query:**

- Connects to `~/.formix/network.db`
- Queries `nodes` table for all registered nodes
- Retrieves status, type, port, and creation timestamp

**Status Meanings:**

- **active**: Node is running and responding to health checks
- **starting**: Node is initializing
- **processing**: Node is handling a computation
- **stopping**: Node is shutting down

**Network Health Indicators:**

- **Heavy Nodes**: Should be ≥ 3 for fault tolerance
- **Light Nodes**: Data providers (more = better participation)
- **Total Nodes**: Complete network size

---

## Creating Computations

### Step 7: Create a Computation

**Command:**

```bash
formix --comp
```

**Interactive Prompts:**

```
Available Nodes:
  JWJT6TDJ (heavy)
  BQX9DIJF (heavy)
  4C7U5L8R (heavy)
  Y6B07RS6 (heavy)
  Y2X1Z3VU (light)
  OLGGPAO7 (light)

Proposing node UID: Y2X1Z3VU
Available Heavy Nodes:
  JWJT6TDJ
  BQX9DIJF
  4C7U5L8R
  Y6B07RS6
Heavy node 1 UID: JWJT6TDJ
Heavy node 2 UID: BQX9DIJF
Heavy node 3 UID: 4C7U5L8R
Computation prompt: Calculate average user rating from 1-10
Note: For this PoC, response schema must be a single number
Response schema (JSON) ({"type": "number"}): {"type": "number"}
Deadline (seconds from now) (60): 30
Minimum number of participants (1): 1
```

**Expected Output:**

```
✓ Computation COMP-FZ375MV7 created successfully!
```

**Process Explanation:**

### Computation Creation Flow:

1. **Node Selection:**

   - **Proposer**: Light node that initiates the computation
   - **Coordinators**: 3 heavy nodes for aggregation
   - **Participants**: All light nodes (automatic discovery)

2. **Computation Parameters:**

   - **Prompt**: Human-readable description
   - **Schema**: Data format specification (currently `{"type": "number"}`)
   - **Deadline**: Time limit for completion
   - **Min Participants**: Minimum responses needed

3. **Database Storage:**

   ```sql
   INSERT INTO computations (id, proposer_uid, status, prompt, deadline, min_participants)
   VALUES ('COMP-FZ375MV7', 'Y2X1Z3VU', 'pending', 'Calculate average...', '2025-08-28T23:00:00Z', 1)
   ```

4. **Broadcast Initiation:**
   - Computation sent to all 3 designated heavy nodes
   - Heavy nodes will broadcast to all light nodes
   - Asynchronous processing begins

---

## Monitoring Computations

### Step 8: Check Computation Status

**Command:**

```bash
formix --status ""
```

**Expected Output:**

```
                      Recent Computations
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ ID            ┃ Status    ┃ Proposer ┃ Result ┃ Participants ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━┩
│ COMP-FZ375MV7 │ completed │ Y2X1Z3VU │ 54.0   │ 1            │
└───────────────┴───────────┴──────────┴────────┴──────────────┘
```

**Process Explanation:**

**Status Values:**

- **pending**: Computation created, waiting for responses
- **processing**: Light nodes responding, heavy nodes aggregating
- **completed**: Final result available
- **failed**: Computation didn't meet requirements

**Database Query:**

```sql
SELECT id, status, proposer_uid, result, participants
FROM computations
ORDER BY created_at DESC
```

### Step 9: Detailed Computation View

**Command:**

```bash
formix --status COMP-FZ375MV7
```

**Expected Output:**

```
╭─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Computation COMP-FZ375MV7                                                                                                                           │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
Status: completed
Proposer: Y2X1Z3VU
Prompt: Calculate average user rating from 1-10
Deadline: 2025-08-28T22:53:50.183550+00:00
Min Participants: 1
Result: 54.0
Participants: 1
```

---

## Understanding Results

### Step 10: Analyze the Results

**Result Breakdown:**

- **Result: 54.0** - The final aggregated value
- **Participants: 1** - One light node contributed
- **Status: completed** - Computation finished successfully

### What Actually Happened:

1. **Light Node Response:**

   - Node `Y2X1Z3VU` received computation request
   - Generated private value (54.0) - simulated user rating
   - Created 3 secret shares using additive secret sharing

2. **Secret Sharing Process:**

   ```
   Secret = 54.0
   Share₁ = random_value_1
   Share₂ = random_value_2
   Share₃ = 54.0 - Share₁ - Share₂  (mod 2³²)
   ```

3. **Share Distribution:**

   - Share₁ sent to Heavy Node JWJT6TDJ
   - Share₂ sent to Heavy Node BQX9DIJF
   - Share₃ sent to Heavy Node 4C7U5L8R

4. **Aggregation:**
   - Each heavy node collects shares from all participating light nodes
   - At deadline, heavy nodes sum their respective shares
   - Result reconstruction: `54.0 = Share₁ + Share₂ + Share₃`

### Privacy Guarantee:

**No single node ever saw the value 54.0** - only meaningless shares!

---

## Technical Deep Dive

### Secret Sharing Mathematics

**Additive Secret Sharing Modulo 2³²:**

```python
MODULUS = 2**32  # 4,294,967,296

def create_shares(secret: int, num_shares: int = 3) -> list[int]:
    """Create additive shares that sum to secret mod MODULUS"""
    shares = []
    sum_shares = 0

    # Generate n-1 random shares
    for i in range(num_shares - 1):
        share = random.randint(0, MODULUS - 1)
        shares.append(share)
        sum_shares = (sum_shares + share) % MODULUS

    # Last share ensures sum = secret
    last_share = (secret - sum_shares) % MODULUS
    shares.append(last_share)

    return shares

def reconstruct_secret(shares: list[int]) -> int:
    """Sum all shares to reconstruct secret"""
    return sum(shares) % MODULUS
```

**Example:**

```
Secret = 42
Share₁ = 1,247,389,456
Share₂ = 2,893,456,789
Share₃ = (42 - 1,247,389,456 - 2,893,456,789) mod 2³²
       = (42 - 4,140,846,245) mod 4,294,967,296
       = 154,121,093

Verification: 1,247,389,456 + 2,893,456,789 + 154,121,093 = 4,294,967,296 + 42 = 42 mod 2³² ✅
```

### Network Communication Protocol

**Message Types:**

```python
@dataclass
class Message:
    type: str  # computation, share, aggregate_request
    payload: dict[str, Any]
    sender_uid: str
    timestamp: str
```

**HTTP Endpoints:**

- `POST /message` - Receive inter-node messages
- `GET /health` - Health check endpoint

**Communication Flow:**

1. CLI → Heavy Nodes (computation creation)
2. Heavy Nodes → Light Nodes (computation broadcast)
3. Light Nodes → Heavy Nodes (secret shares)
4. Heavy Nodes → Heavy Nodes (aggregation coordination)

### Database Schema

**Network Database (`~/.formix/network.db`):**

```sql
-- Global network state
CREATE TABLE nodes (
    uid TEXT PRIMARY KEY,
    node_type TEXT, -- 'heavy' or 'light'
    port INTEGER,
    status TEXT,
    created_at TIMESTAMP
);

CREATE TABLE computations (
    id TEXT PRIMARY KEY,
    proposer_uid TEXT,
    status TEXT,
    prompt TEXT,
    result REAL,
    participants INTEGER,
    deadline TIMESTAMP,
    created_at TIMESTAMP
);
```

**Node-Specific Database (`~/.formix/[UID]/node.db`):**

```sql
-- Heavy node aggregations
CREATE TABLE shares (
    comp_id TEXT,
    sender_uid TEXT,
    share_value INTEGER,
    received_at TIMESTAMP
);

-- Light node responses
CREATE TABLE responses (
    comp_id TEXT,
    value REAL,
    created_at TIMESTAMP
);

CREATE TABLE actions (
    comp_id TEXT,
    action_type TEXT,
    data TEXT,
    created_at TIMESTAMP
);
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. "formix: command not found"

**Problem:** CLI not installed or not in PATH
**Solution:**

```bash
# Reinstall
pip install -e .

# Or use full path
python -m formix.cli.main --help
```

#### 2. Computation Stuck on "pending"

**Problem:** Light nodes not participating
**Solutions:**

```bash
# Check node status
formix --view

# Check node logs
tail -f ~/.formix/[NODE_UID]/logs.log

# Verify network connectivity
curl http://localhost:[PORT]/health
```

#### 3. Connection Failures in Logs

**Problem:** Nodes can't communicate
**Solutions:**

- Ensure all node terminals are running
- Check firewall settings
- Verify ports are not in use: `lsof -i :8000`

#### 4. "Insufficient participants" Error

**Problem:** Not enough light nodes responded
**Solutions:**

- Reduce minimum participants requirement
- Add more light nodes to network
- Check light node logs for errors

#### 5. Database Errors

**Problem:** SQLite database issues
**Solutions:**

```bash
# Clean restart
rm -rf ~/.formix/
formix --new-node --type heavy --foreground
```

### Log Analysis

**Check Application Logs:**

```bash
tail -f ~/.formix/formix.log
```

**Check Node-Specific Logs:**

```bash
tail -f ~/.formix/[NODE_UID]/logs.log
```

**Common Log Messages:**

- `INFO`: Normal operations
- `WARNING`: Non-critical issues (retries, timeouts)
- `ERROR`: Critical failures requiring attention

### Performance Tuning

**For Production Use:**

- Increase `MODULUS` for larger value ranges
- Implement TLS/mTLS for secure communication
- Add node authentication and authorization
- Use distributed databases (PostgreSQL, etc.)
- Implement Byzantine fault tolerance

---

## Complete Workflow Summary

```bash
# 1. Setup
cd /Users/Aayush/Documents/GitHub/formix
pip install -e .

# 2. Create Network (in separate terminals)
formix --new-node --type heavy --foreground  # Terminal 1
formix --new-node --type heavy --foreground  # Terminal 2
formix --new-node --type heavy --foreground  # Terminal 3
formix --new-node --type light --foreground  # Terminal 4
formix --new-node --type light --foreground  # Terminal 5

# 3. Verify Network
formix --view

# 4. Create Computation
formix --comp
# Follow interactive prompts...

# 5. Monitor Progress
formix --status ""

# 6. View Results
formix --status COMP-[ID]

# 7. Cleanup (when done)
echo "y" | formix --stop-all
```

## Key Takeaways

1. **Privacy First**: Individual data never exposed
2. **Cryptographic Security**: Mathematical guarantees
3. **Distributed Architecture**: No single points of failure
4. **Real MPC Implementation**: Production-ready concepts
5. **Educational Value**: Learn advanced cryptography hands-on

Formix demonstrates how cutting-edge cryptographic techniques can be implemented in practical, real-world systems while maintaining strong privacy guarantees. 🚀🔒
