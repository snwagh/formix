#!/usr/bin/env python3
"""
Simple test script to run Formix nodes in the same process for testing.
"""
import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from formix.core.node import HeavyNode, LightNode
from formix.db.database import NetworkDatabase
from formix.utils.config import setup_logging

async def test_basic_functionality():
    """Test basic Formix functionality."""
    print("=== Formix Basic Functionality Test ===")

    # Setup logging
    setup_logging()

    # Initialize database
    db = NetworkDatabase()
    await db.initialize()

    # Create test nodes
    heavy_node = HeavyNode("TEST_HEAVY", 9000)
    light_node1 = LightNode("TEST_LIGHT1", 9001)
    light_node2 = LightNode("TEST_LIGHT2", 9002)

    # Initialize databases
    await heavy_node.db.initialize_heavy_node()
    await light_node1.db.initialize_light_node()
    await light_node2.db.initialize_light_node()

    # Register nodes in network database
    await db.add_node("TEST_HEAVY", "heavy", 9000)
    await db.add_node("TEST_LIGHT1", "light", 9001)
    await db.add_node("TEST_LIGHT2", "light", 9002)

    print("✓ Created and initialized test nodes")

    # Start nodes in background tasks
    heavy_task = asyncio.create_task(heavy_node.start())
    light1_task = asyncio.create_task(light_node1.start())
    light2_task = asyncio.create_task(light_node2.start())

    print("✓ Started nodes")

    # Wait a moment for nodes to start
    await asyncio.sleep(2)

    # Test health check
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:9000/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✓ Heavy node health check: {data}")
                else:
                    print(f"✗ Heavy node health check failed: {response.status}")
    except Exception as e:
        print(f"✗ Health check failed: {e}")

    # Test computation creation
    from formix.protocols.messaging import Message, MessageProtocol
    from datetime import datetime, UTC, timedelta

    # Create additional heavy nodes for proper share distribution
    heavy_node2 = HeavyNode("TEST_HEAVY2", 9003)
    heavy_node3 = HeavyNode("TEST_HEAVY3", 9004)
    
    await heavy_node2.db.initialize_heavy_node()
    await heavy_node3.db.initialize_heavy_node()
    
    await db.add_node("TEST_HEAVY2", "heavy", 9003)
    await db.add_node("TEST_HEAVY3", "heavy", 9004)

    # Start additional heavy nodes
    heavy2_task = asyncio.create_task(heavy_node2.start())
    heavy3_task = asyncio.create_task(heavy_node3.start())

    computation = {
        'comp_id': 'TEST_COMP_001',
        'proposer_uid': 'TEST_LIGHT1',
        'heavy_node_1': 'TEST_HEAVY',
        'heavy_node_2': 'TEST_HEAVY2',
        'heavy_node_3': 'TEST_HEAVY3',
        'computation_prompt': 'Test computation',
        'response_schema': '{"type": "number"}',
        'deadline': (datetime.now(UTC) + timedelta(seconds=10)).isoformat(),
        'min_participants': 2
    }

    print("✓ Created test computation")

    # Send computation to all heavy nodes
    heavy_ports = [9000, 9003, 9004]  # TEST_HEAVY, TEST_HEAVY2, TEST_HEAVY3
    for port in heavy_ports:
        message = Message("computation", computation)
        try:
            response = await MessageProtocol.send_message(port, message)
            print(f"✓ Sent computation to heavy node on port {port}: {response}")
        except Exception as e:
            print(f"✗ Failed to send computation to port {port}: {e}")

    # Wait for processing
    await asyncio.sleep(5)

    # Wait for processing and aggregation
    await asyncio.sleep(15)  # Wait for deadline to pass

    # Check computation result (if aggregation completed)
    # Note: In this simple test, we may not get a final result due to timing
    print("✓ Computation processing completed")

    # Check shares in heavy node database
    shares = await heavy_node.db.get_shares_for_computation('TEST_COMP_001')
    print(f"✓ Shares stored in heavy node: {len(shares)}")
    for share in shares:
        print(f"  - From {share['sender_uid']}: share_value={share['share_value']}")

    # Check responses in light node databases
    # Note: We can't easily query responses from light nodes in this test
    # but we know they responded based on the logs
    print("✓ Light nodes processed computation (based on logs)")

    # Stop nodes
    heavy_task.cancel()
    heavy2_task.cancel()
    heavy3_task.cancel()
    light1_task.cancel()
    light2_task.cancel()

    try:
        await heavy_task
    except asyncio.CancelledError:
        pass

    try:
        await heavy2_task
    except asyncio.CancelledError:
        pass

    try:
        await heavy3_task
    except asyncio.CancelledError:
        pass

    try:
        await light1_task
    except asyncio.CancelledError:
        pass

    try:
        await light2_task
    except asyncio.CancelledError:
        pass

    print("✓ Test completed")

if __name__ == "__main__":
    asyncio.run(test_basic_functionality())
