#!/usr/bin/env python3
"""
Test the pure Python FormixNetwork implementation
"""

import asyncio
from src.formix import FormixNetwork


async def test_network():
    """Test the basic FormixNetwork functionality."""
    print("🚀 Starting FormixNetwork test...")
    print("-" * 60)

    network = FormixNetwork()

    try:
        # Start network
        print("\n📝 Creating network with 3 heavy and 3 light nodes...")
        nodes = await network.start_network(heavy_count=3, light_count=3)

        print(f"✅ Network created successfully!")
        print(f"   Heavy nodes: {nodes['heavy']}")
        print(f"   Light nodes: {nodes['light']}")

        # Check network status
        status = await network.get_network_status()
        print(f"\n📊 Network Status:")
        print(f"   Running: {status['running']}")
        print(f"   Total nodes: {status['total_nodes']}")
        print(f"   Heavy nodes: {status['heavy_nodes']}")
        print(f"   Light nodes: {status['light_nodes']}")

        # Propose a computation
        print("\n💭 Proposing computation...")
        comp_id = await network.propose_computation(
            prompt="Pick a random number from 1 to 100",
            deadline_seconds=10,
            min_participants=2
        )
        print(f"✅ Computation {comp_id} proposed")
        print(f"⏳ Waiting for result (10 second deadline)...")

        # Wait for result
        try:
            result = await network.wait_for_computation(comp_id, timeout=20)
            print(f"\n🎉 SUCCESS! Computation completed!")
            print(f"   Final result: {result['result']}")
            print(f"   Participants: {result['participants_count']}")
            print(f"   Status: {result['status']}")
        except RuntimeError as e:
            print(f"\n❌ Computation failed: {e}")
        except TimeoutError:
            print(f"\n⏱️ Computation timed out")

        # List all computations
        print("\n📜 All computations:")
        computations = await network.list_computations()
        for comp in computations:
            print(f"   {comp['comp_id']}: {comp['status']} (result: {comp.get('result', 'N/A')})")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Shutdown
        print("\n🛑 Shutting down network...")
        await network.shutdown()
        print("✅ Network shutdown complete")

    print("-" * 60)
    print("✅ Test completed!")


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_network())