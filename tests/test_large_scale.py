#!/usr/bin/env python3
"""
Large-scale Formix test with 100 light nodes and 50 heavy nodes.
Randomly selects 3 heavy nodes for computation.
"""
import asyncio
import sys
import os
import random
from datetime import datetime, UTC, timedelta

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from formix.core.node import HeavyNode, LightNode
from formix.db.database import NetworkDatabase
from formix.protocols.messaging import Message, MessageProtocol
from formix.utils.config import setup_logging

async def test_large_scale_formix():
    """Test Formix with 100 light nodes and 50 heavy nodes."""
    print("=== Large-Scale Formix Test (100 Light + 50 Heavy Nodes) ===")

    # Setup logging
    setup_logging()

    # Initialize database
    db = NetworkDatabase()
    await db.initialize()

    print("✓ Initialized network database")

    # Create 50 heavy nodes
    heavy_nodes = []
    heavy_tasks = []
    print("Creating 50 heavy nodes...")

    for i in range(50):
        uid = f"HEAVY_{i:03d}"
        port = 9000 + i

        # Create heavy node
        heavy_node = HeavyNode(uid, port)
        await heavy_node.db.initialize_heavy_node()
        await db.add_node(uid, "heavy", port)

        heavy_nodes.append(heavy_node)
        print(f"✓ Created heavy node: {uid} on port {port}")

    # Create 100 light nodes
    light_nodes = []
    light_tasks = []
    print("\nCreating 100 light nodes...")

    for i in range(100):
        uid = f"LIGHT_{i:03d}"
        port = 9050 + i

        # Create light node
        light_node = LightNode(uid, port)
        await light_node.db.initialize_light_node()
        await db.add_node(uid, "light", port)

        light_nodes.append(light_node)
        print(f"✓ Created light node: {uid} on port {port}")

    print(f"\n✓ Created {len(heavy_nodes)} heavy nodes and {len(light_nodes)} light nodes")

    # Start all nodes
    print("\nStarting all nodes...")
    for heavy_node in heavy_nodes:
        task = asyncio.create_task(heavy_node.start())
        heavy_tasks.append(task)

    for light_node in light_nodes:
        task = asyncio.create_task(light_node.start())
        light_tasks.append(task)

    print("✓ All nodes started")

    # Wait for nodes to initialize
    await asyncio.sleep(3)

    # Randomly select 3 heavy nodes for computation
    selected_heavy_nodes = random.sample(heavy_nodes, 3)
    selected_heavy_uids = [node.uid for node in selected_heavy_nodes]
    selected_heavy_ports = [node.port for node in selected_heavy_nodes]

    print(f"\n🎯 Randomly selected heavy nodes for computation:")
    for uid, port in zip(selected_heavy_uids, selected_heavy_ports):
        print(f"  • {uid} (port {port})")

    # Create computation
    computation = {
        'comp_id': 'LARGE_SCALE_COMP_001',
        'proposer_uid': 'LIGHT_000',  # First light node as proposer
        'heavy_node_1': selected_heavy_uids[0],
        'heavy_node_2': selected_heavy_uids[1],
        'heavy_node_3': selected_heavy_uids[2],
        'computation_prompt': 'Large-scale privacy-preserving average computation',
        'response_schema': '{"type": "number"}',
        'deadline': (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
        'min_participants': 10  # Require at least 10 participants
    }

    print("\n✓ Created computation with details:")
    print(f"  • ID: {computation['comp_id']}")
    print(f"  • Proposer: {computation['proposer_uid']}")
    print(f"  • Heavy nodes: {', '.join(selected_heavy_uids)}")
    print(f"  • Min participants: {computation['min_participants']}")
    print(f"  • Deadline: {computation['deadline']}")

    # Send computation to selected heavy nodes
    print("\n📤 Broadcasting computation to selected heavy nodes...")
    for port in selected_heavy_ports:
        message = Message("computation", computation)
        try:
            response = await MessageProtocol.send_message(port, message)
            print(f"✓ Sent computation to heavy node on port {port}: {response}")
        except Exception as e:
            print(f"✗ Failed to send computation to port {port}: {e}")

    # Wait for computation processing
    print("\n⏳ Waiting for computation processing (30 seconds)...")
    await asyncio.sleep(35)  # Wait past deadline

    # Check results from one of the heavy nodes
    result_heavy_node = selected_heavy_nodes[0]
    shares = await result_heavy_node.db.get_shares_for_computation('LARGE_SCALE_COMP_001')

    print("\n📊 Computation Results:")
    print(f"✓ Shares received by {result_heavy_node.uid}: {len(shares)}")
    if shares:
        total_sum = sum(share['share_value'] for share in shares)
        average = total_sum / len(shares)
        print(f"✓ Total sum: {total_sum}")
        print(f"✓ Average: {average:.2f}")
        print(f"✓ Participants: {len(shares)}")

        # Show sample shares
        print("\n📋 Sample shares received:")
        for i, share in enumerate(shares[:5]):  # Show first 5
            print(f"  {i+1}. From {share['sender_uid']}: {share['share_value']}")
        if len(shares) > 5:
            print(f"  ... and {len(shares) - 5} more")
    else:
        print("✗ No shares received")

    # Check if computation was recorded in network database
    computation_result = await db.get_computation_result('LARGE_SCALE_COMP_001')
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

    # Stop all nodes
    print("\n🛑 Stopping all nodes...")
    # Cancel all tasks
    for task in heavy_tasks + light_tasks:
        task.cancel()

    # Wait for tasks to complete
    await asyncio.gather(*heavy_tasks, return_exceptions=True)
    await asyncio.gather(*light_tasks, return_exceptions=True)

    print("✓ All nodes stopped")
    print("\n🎉 Large-scale Formix test completed!")

if __name__ == "__main__":
    asyncio.run(test_large_scale_formix())
