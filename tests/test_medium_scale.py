#!/usr/bin/env python3
"""
Medium-scale Formix test with 20 light nodes and 10 heavy nodes.
Randomly selects 3 heavy nodes for computation.
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


async def test_medium_scale_formix():
    """Test Formix with 20 light nodes and 10 heavy nodes."""
    print("=== Medium-Scale Formix Test (20 Light + 10 Heavy Nodes) ===")

    # Define ports we'll use
    heavy_ports = list(range(9000, 9010))  # 9000-9009
    light_ports = list(range(9050, 9070))  # 9050-9069
    test_ports = heavy_ports + light_ports
    
    # Clean up ports before starting
    cleanup_ports(test_ports)

async def test_medium_scale_formix():
    """Test Formix with 20 light nodes and 10 heavy nodes."""
    print("=== Medium-Scale Formix Test (20 Light + 10 Heavy Nodes) ===")

    # Setup logging
    setup_logging()

    # Initialize database
    db = NetworkDatabase()
    await db.initialize()

    print("✓ Initialized network database")

    # Create 10 heavy nodes
    heavy_nodes = []
    heavy_tasks = []
    print("Creating 10 heavy nodes...")

    for i in range(10):
        uid = f"HEAVY_{i:03d}"
        port = 9000 + i

        # Create heavy node
        heavy_node = HeavyNode(uid, port)
        await heavy_node.db.initialize_heavy_node()
        await db.add_node(uid, "heavy", port)

        heavy_nodes.append(heavy_node)
        print(f"✓ Created heavy node: {uid} on port {port}")

    # Create 20 light nodes
    light_nodes = []
    light_tasks = []
    print("\nCreating 20 light nodes...")

    for i in range(20):
        uid = f"LIGHT_{i:03d}"
        port = 9050 + i

        # Create light node
        light_node = LightNode(uid, port)
        await light_node.db.initialize_light_node()
        await db.add_node(uid, "light", port)

        light_nodes.append(light_node)
        print(f"✓ Created light node: {uid} on port {port}")

    print(f"\n✓ Created {len(heavy_nodes)} heavy nodes and {len(light_nodes)} light nodes")

    # Wait for database operations to settle
    print("\n⏳ Waiting for database operations to settle...")
    await asyncio.sleep(3)

    # Start all nodes
    print("\nStarting all nodes...")
    for heavy_node in heavy_nodes:
        task = asyncio.create_task(heavy_node.start())
        heavy_tasks.append(task)

    for light_node in light_nodes:
        task = asyncio.create_task(light_node.start())
        light_tasks.append(task)

    print("✓ All nodes started")

    # Wait for nodes to initialize and register
    print("\n⏳ Waiting for nodes to fully initialize and register...")
    await asyncio.sleep(5)  # Increased wait time
    
    # Verify all nodes are registered in the database
    print("\n🔍 Verifying node registration...")
    all_nodes = await db.get_all_nodes()
    heavy_count = len([n for n in all_nodes if n['node_type'] == 'heavy'])
    light_count = len([n for n in all_nodes if n['node_type'] == 'light'])
    
    print(f"✓ Found {heavy_count} heavy nodes and {light_count} light nodes registered")
    
    if heavy_count != 10 or light_count != 20:
        print(f"⚠️  Expected 10 heavy and 20 light nodes, but found {heavy_count} heavy and {light_count} light")
        # Continue anyway, some nodes might still be starting
    selected_heavy_nodes = random.sample(heavy_nodes, 3)
    selected_heavy_uids = [node.uid for node in selected_heavy_nodes]
    selected_heavy_ports = [node.port for node in selected_heavy_nodes]

    print(f"\n🎯 Randomly selected heavy nodes for computation:")
    for uid, port in zip(selected_heavy_uids, selected_heavy_ports):
        print(f"  • {uid} (port {port})")

    # Create computation
    computation = {
        'comp_id': 'MEDIUM_SCALE_COMP_001',
        'proposer_uid': 'LIGHT_000',  # First light node as proposer
        'heavy_node_1': selected_heavy_uids[0],
        'heavy_node_2': selected_heavy_uids[1],
        'heavy_node_3': selected_heavy_uids[2],
        'computation_prompt': 'Medium-scale privacy-preserving average computation',
        'response_schema': '{"type": "number"}',
        'deadline': (datetime.now(UTC) + timedelta(seconds=20)).isoformat(),
        'min_participants': 5  # Require at least 5 participants
    }

    print("\n✓ Created computation with details:")
    print(f"  • ID: {computation['comp_id']}")
    print(f"  • Proposer: {computation['proposer_uid']}")
    print(f"  • Heavy nodes: {', '.join(selected_heavy_uids)}")
    print(f"  • Min participants: {computation['min_participants']}")
    print(f"  • Deadline: {computation['deadline']}")

    # Send computation to selected heavy nodes with retry
    print("\n📤 Broadcasting computation to selected heavy nodes...")
    for port in selected_heavy_ports:
        success = False
        for attempt in range(3):  # Retry up to 3 times
            try:
                message = Message("computation", computation)
                response = await MessageProtocol.send_message(port, message)
                print(f"✓ Sent computation to heavy node on port {port}: {response}")
                success = True
                break
            except Exception as e:
                if attempt < 2:
                    print(f"⚠️  Failed to send to port {port} (attempt {attempt + 1}), retrying...")
                    await asyncio.sleep(2)  # Wait before retry
                else:
                    print(f"✗ Failed to send computation to port {port} after 3 attempts: {e}")
        
        if not success:
            print(f"⚠️  Could not reach heavy node on port {port}, computation may be incomplete")

    # Wait for computation processing with proper monitoring
    print("\n⏳ Waiting for computation processing (45 seconds)...")
    
    start_time = asyncio.get_event_loop().time()
    end_time = start_time + 45.0  # Increased timeout to 45 seconds
    
    while asyncio.get_event_loop().time() < end_time:
        # Check if computation is complete by looking at shares in all heavy nodes
        total_shares = 0
        for heavy_node in selected_heavy_nodes:
            try:
                shares = await heavy_node.db.get_shares_for_computation('MEDIUM_SCALE_COMP_001')
                total_shares += len(shares)
            except Exception as e:
                print(f"⚠️  Error checking shares for {heavy_node.uid}: {e}")
        
        print(f"📊 Progress: {total_shares} shares received across all heavy nodes")
        
        # If we have enough shares (at least min_participants), computation might be complete
        if total_shares >= computation['min_participants']:
            print(f"✓ Minimum participants reached ({total_shares} >= {computation['min_participants']})")
            break
            
        # Wait a bit before checking again
        await asyncio.sleep(2.0)
    
    if asyncio.get_event_loop().time() >= end_time:
        print("⚠️  Test timed out waiting for computation processing")
    
    # Check results from all heavy nodes
    print("\n📊 Computation Results:")
    all_shares = []
    for heavy_node in selected_heavy_nodes:
        shares = await heavy_node.db.get_shares_for_computation('MEDIUM_SCALE_COMP_001')
        print(f"✓ Shares received by {heavy_node.uid}: {len(shares)}")
        all_shares.extend(shares)
    
    if all_shares:
        total_sum = sum(share['share_value'] for share in all_shares)
        average = total_sum / len(all_shares)
        print(f"✓ Total sum: {total_sum}")
        print(f"✓ Average: {average:.2f}")
        print(f"✓ Total participants: {len(all_shares)}")

        # Show sample shares
        print("\n📋 Sample shares received:")
        for i, share in enumerate(all_shares[:10]):  # Show first 10
            print(f"  {i+1}. From {share['sender_uid']}: {share['share_value']}")
        if len(all_shares) > 10:
            print(f"  ... and {len(all_shares) - 10} more")
    else:
        print("✗ No shares received by any heavy node")

    # Check if computation was recorded in network database
    computation_result = await db.get_computation_result('MEDIUM_SCALE_COMP_001')
    if computation_result:
        print("\n🏆 Final network result:")
        print(f"✓ Status: {computation_result['status']}")
        if computation_result['status'] == 'completed':
            print(f"✓ Result: {computation_result['result']}")
            print(f"✓ Participants: {computation_result['participants_count']}")
        else:
            print(f"✗ Computation not completed: {computation_result['status']}")
    else:
        print("\n✗ Computation not found in network database")

    # Stop all nodes with timeout
    print("\n🛑 Stopping all nodes...")
    
    # First, send shutdown signals to all nodes
    heavy_ports = [9000 + i for i in range(10)]  # 10 heavy nodes
    light_ports = [9050 + i for i in range(20)]  # 20 light nodes
    node_ports = heavy_ports + light_ports
    
    for port in node_ports:
        try:
            # Send shutdown message using MessageProtocol
            shutdown_message = Message("shutdown", {"reason": "test_complete"})
            response = await MessageProtocol.send_message(port, shutdown_message, timeout=5.0)
            print(f"✓ Sent shutdown signal to node on port {port}: {response.get('node_id', 'unknown')}")
        except Exception as e:
            print(f"⚠️  Failed to send shutdown signal to port {port}: {e}")

    # Wait a moment for nodes to shut down gracefully
    await asyncio.sleep(3)

    # Cancel all tasks with timeout
    stop_tasks = []
    for task in heavy_tasks + light_tasks:
        if not task.done():
            task.cancel()
            stop_tasks.append(task)
    
    if stop_tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*stop_tasks, return_exceptions=True),
                timeout=10.0  # 10 second timeout for stopping
            )
            print("✓ All tasks cancelled successfully")
        except asyncio.TimeoutError:
            print("⚠️  Some tasks did not stop within timeout, forcing termination")
    
    print("✓ All nodes stopped")
    print("\n🎉 Medium-scale Formix test completed!")

if __name__ == "__main__":
    asyncio.run(test_medium_scale_formix())
