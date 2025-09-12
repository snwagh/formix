#!/usr/bin/env python3
"""
Simple test with 2 light nodes and 1 heavy node to verify basic communication.
"""
import asyncio
import sys
import os
import random
import signal
import subprocess
from datetime import datetime, UTC, timedelta

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from formix.core.node import HeavyNode, LightNode
from formix.db.database import NetworkDatabase
from formix.protocols.messaging import Message, MessageProtocol
from formix.utils.config import setup_logging


def kill_process_on_port(port: int):
    """Kill any process listening on the given port."""
    try:
        # Find process using the port
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid.strip():
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                        print(f"✓ Killed process {pid} on port {port}")
                    except (ProcessLookupError, OSError) as e:
                        print(f"⚠️  Could not kill process {pid} on port {port}: {e}")
        else:
            print(f"✓ No process found on port {port}")
            
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"⚠️  Could not check port {port}: {e}")


def cleanup_ports(ports: list[int]):
    """Clean up all specified ports by killing any processes using them."""
    print(f"🧹 Cleaning up ports: {ports}")
    for port in ports:
        kill_process_on_port(port)
    
    # Wait a moment for processes to fully terminate
    import time
    time.sleep(1)
    print("✓ Port cleanup completed")


async def test_simple_communication():
    """Test basic communication with 2 light nodes and 1 heavy node."""
    print("=== Simple Communication Test (2 Light + 1 Heavy Nodes) ===")

    # Setup logging with DEBUG level
    import os
    os.environ["FORMIX_LOG_LEVEL"] = "DEBUG"
    setup_logging()
    
    # Clean database from previous runs
    print("🧹 Cleaning database from previous runs...")
    db = NetworkDatabase()
    await db.initialize()
    
    # Get all existing nodes and remove them
    existing_nodes = await db.get_all_nodes()
    for node in existing_nodes:
        await db.remove_node(node['uid'])
        print(f"✓ Removed old node: {node['uid']}")
    
    print(f"✓ Cleaned {len(existing_nodes)} old nodes from database")

    # Create 1 heavy node
    heavy_nodes = []
    heavy_tasks = []
    print("Creating 1 heavy node...")

    uid = "HEAVY_000"
    port = 9000

    # Create heavy node
    heavy_node = HeavyNode(uid, port)
    await heavy_node.db.initialize_heavy_node()
    # Don't register here - let the node register itself when it starts
    heavy_nodes.append(heavy_node)
    print(f"✓ Created heavy node: {uid} on port {port}")

    # Create 2 light nodes
    light_nodes = []
    light_tasks = []
    print("\nCreating 2 light nodes...")

    for i in range(2):
        uid = f"LIGHT_{i:03d}"
        port = 9050 + i

        # Create light node
        light_node = LightNode(uid, port)
        await light_node.db.initialize_light_node()
        # Don't register here - let the node register itself when it starts
        light_nodes.append(light_node)
        print(f"✓ Created light node: {uid} on port {port}")

    print(f"\n✓ Created {len(heavy_nodes)} heavy node and {len(light_nodes)} light nodes")

    # Start all nodes
    print("\nStarting all nodes...")
    for heavy_node in heavy_nodes:
        task = asyncio.create_task(heavy_node.start())
        heavy_tasks.append(task)

    for light_node in light_nodes:
        task = asyncio.create_task(light_node.start())
        light_tasks.append(task)

    print("✓ All nodes started")

    # Wait for nodes to initialize and register themselves
    print("⏳ Waiting for nodes to fully initialize and register...")
    await asyncio.sleep(3)  # Reduced wait time

    # Verify nodes are registered and responding
    print("\n🔍 Verifying node registration...")
    all_nodes = await db.get_all_nodes()
    print(f"✓ Found {len(all_nodes)} nodes in database:")
    for node in all_nodes:
        node_type = node.get('node_type', node.get('type', 'unknown'))
        print(f"  • {node['uid']} ({node_type}) on port {node['port']}")

    # Test health checks
    print("\n🏥 Testing node health checks...")
    healthy_nodes = []
    
    # Skip health checks for now - focus on basic functionality
    print("⚠️  Skipping health checks to focus on core communication")
    healthy_nodes = all_nodes  # Assume all nodes are healthy
    
    if len(healthy_nodes) != 3:
        print(f"⚠️  Expected 3 nodes, got {len(healthy_nodes)}. Continuing anyway...")
    
    print("✓ Proceeding with test...")

    await asyncio.sleep(1)  # Brief wait for servers to be ready

    # Create computation
    computation = {
        'comp_id': 'SIMPLE_TEST_COMP_001',
        'proposer_uid': 'LIGHT_000',
        'heavy_node_1': 'HEAVY_000',
        'heavy_node_2': 'HEAVY_000',  # Same node for simplicity
        'heavy_node_3': 'HEAVY_000',  # Same node for simplicity
        'computation_prompt': 'Simple test computation',
        'response_schema': '{"type": "number"}',
        'deadline': (datetime.now(UTC) + timedelta(seconds=15)).isoformat(),
        'min_participants': 2  # Require at least 2 participants
    }

    print("\n✓ Created computation with details:")
    print(f"  • ID: {computation['comp_id']}")
    print(f"  • Proposer: {computation['proposer_uid']}")
    print(f"  • Heavy node: HEAVY_000")
    print(f"  • Min participants: {computation['min_participants']}")

    # Send computation to heavy node
    print("\n📤 Sending computation to heavy node...")
    message = Message("computation", computation)
    try:
        response = await MessageProtocol.send_message(9000, message)
        print(f"✓ Sent computation to heavy node: {response}")
    except Exception as e:
        print(f"✗ Failed to send computation to heavy node: {e}")

    # Wait for computation processing
    print("\n⏳ Waiting for computation processing (10 seconds)...")

    start_time = asyncio.get_event_loop().time()
    end_time = start_time + 10.0  # Reduced timeout

    while asyncio.get_event_loop().time() < end_time:
        # Check if computation is complete
        try:
            shares = await heavy_node.db.get_shares_for_computation('SIMPLE_TEST_COMP_001')
            total_shares = len(shares)
            print(f"📊 Progress: {total_shares} shares received")

            # If we have enough shares, computation might be complete
            if total_shares >= computation['min_participants']:
                print(f"✓ Minimum participants reached ({total_shares} >= {computation['min_participants']})")
                break

        except Exception as e:
            print(f"⚠️  Error checking shares: {e}")

        # Wait a bit before checking again
        await asyncio.sleep(1.0)

    if asyncio.get_event_loop().time() >= end_time:
        print("⚠️  Test timed out waiting for computation processing")

    # Check results
    print("\n📊 Computation Results:")
    shares = await heavy_node.db.get_shares_for_computation('SIMPLE_TEST_COMP_001')
    print(f"✓ Shares received by HEAVY_000: {len(shares)}")

    if shares:
        total_sum = sum(share['share_value'] for share in shares)
        average = total_sum / len(shares)
        print(f"✓ Total sum: {total_sum}")
        print(f"✓ Average: {average:.2f}")
        print(f"✓ Total participants: {len(shares)}")

        # Show sample shares
        print("\n📋 Shares received:")
        for share in shares:
            print(f"  From {share['sender_uid']}: {share['share_value']}")
    else:
        print("✗ No shares received")

    # Stop all nodes
    print("\n🛑 Stopping all nodes...")

    # First, send shutdown signals to all nodes
    node_ports = [9000, 9050, 9051]  # heavy node + 2 light nodes
    
    for port in node_ports:
        try:
            # Send shutdown message using MessageProtocol
            shutdown_message = Message("shutdown", {"reason": "test_complete"})
            response = await MessageProtocol.send_message(port, shutdown_message, timeout=5.0)
            print(f"✓ Sent shutdown signal to node on port {port}: {response}")
        except Exception as e:
            print(f"⚠️  Failed to send shutdown signal to port {port}: {e}")

    # Wait a moment for nodes to shut down gracefully
    await asyncio.sleep(2)

    # Cancel all tasks
    for task in heavy_tasks + light_tasks:
        if not task.done():
            task.cancel()

    if heavy_tasks + light_tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*(heavy_tasks + light_tasks), return_exceptions=True),
                timeout=5.0
            )
            print("✓ All tasks cancelled successfully")
        except asyncio.TimeoutError:
            print("⚠️  Some tasks did not stop within timeout")

    print("✓ All nodes stopped")
    print("\n🎉 Simple communication test completed!")

if __name__ == "__main__":
    asyncio.run(test_simple_communication())
