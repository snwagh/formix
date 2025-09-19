#!/usr/bin/env python3
"""
Example usage of FormixNetwork - Pure Python interface

This script demonstrates how to use the FormixNetwork class
to create and run computations without any CLI complexity.
"""

import asyncio
from src.formix import FormixNetwork, quick_network, quick_computation


async def basic_example():
    """Basic example showing network creation and computation."""
    print("🚀 Starting Formix Network...")

    # Create and start network
    network = FormixNetwork()
    nodes = await network.start_network(heavy_count=3, light_count=5)

    print(f"✅ Network started with:")
    print(f"   Heavy nodes: {nodes['heavy']}")
    print(f"   Light nodes: {nodes['light']}")

    # Propose a computation
    print("\n📊 Proposing computation...")
    comp_id = await network.propose_computation(
        "What's your favorite number between 0 and 100?"
    )

    print(f"✅ Computation proposed: {comp_id}")

    # Wait for result
    print("⏳ Waiting for computation to complete...")
    try:
        result = await network.wait_for_computation(comp_id, timeout=70)
        print(f"🎉 Computation completed!")
        print(f"   Result: {result['result']}")
        print(f"   Participants: {result['participants_count']}")
    except Exception as e:
        print(f"❌ Computation failed: {e}")

    # Show network status
    status = await network.get_network_status()
    print(f"\n📈 Network Status:")
    print(f"   Running: {status['running']}")
    print(f"   Total nodes: {status['total_nodes']}")
    print(f"   Active nodes: {status['running_nodes']}")

    # Shutdown
    print("\n🛑 Shutting down network...")
    await network.shutdown()
    print("✅ Network shutdown complete")


async def quick_example():
    """Quick example using convenience functions."""
    print("🚀 Quick Formix Network Demo...")

    # Quick network creation
    network = await quick_network(heavy_count=3, light_count=3)
    print("✅ Quick network started")

    # Quick computation
    result = await quick_computation(
        network,
        "Pick a random number from 1 to 50",
        wait=True
    )

    print(f"🎉 Quick computation result: {result['result']}")

    # Cleanup
    await network.shutdown()


async def context_manager_example():
    """Example using async context manager."""
    print("🚀 Context Manager Example...")

    async with FormixNetwork() as network:
        await network.start_network(heavy_count=3, light_count=2)

        # Multiple computations
        comp1_id = await network.propose_computation("What's 5 + 5?")
        comp2_id = await network.propose_computation("Pick your lucky number")

        print(f"✅ Proposed computations: {comp1_id}, {comp2_id}")

        # Wait for both
        try:
            result1 = await network.wait_for_computation(comp1_id)
            result2 = await network.wait_for_computation(comp2_id)

            print(f"🎉 Results:")
            print(f"   Computation 1: {result1['result']}")
            print(f"   Computation 2: {result2['result']}")
        except Exception as e:
            print(f"❌ Error: {e}")

    print("✅ Context manager automatically cleaned up")


async def monitoring_example():
    """Example showing monitoring capabilities."""
    print("🚀 Monitoring Example...")

    network = FormixNetwork()
    await network.start_network(heavy_count=3, light_count=4)

    # Start a computation
    comp_id = await network.propose_computation(
        "Rate this network from 1-100",
        deadline_seconds=30
    )

    # Monitor progress
    for i in range(35):
        status = await network.get_computation_status(comp_id)
        print(f"⏰ T+{i}s: Status = {status['status']}")

        if status['status'] == 'completed':
            print(f"🎉 Final result: {status['result']} (from {status['participants_count']} participants)")
            break
        elif status['status'].startswith('failed'):
            print(f"❌ Computation failed: {status['status']}")
            break

        await asyncio.sleep(1)

    await network.shutdown()


async def main():
    """Run all examples."""
    examples = [
        ("Basic Example", basic_example),
        ("Quick Example", quick_example),
        ("Context Manager Example", context_manager_example),
        ("Monitoring Example", monitoring_example),
    ]

    for name, example_func in examples:
        print(f"\n" + "=" * 60)
        print(f"Running: {name}")
        print("=" * 60)

        try:
            await example_func()
        except Exception as e:
            print(f"❌ Example failed: {e}")
            import traceback
            traceback.print_exc()

        print(f"\n✅ {name} completed")
        await asyncio.sleep(1)  # Brief pause between examples


if __name__ == "__main__":
    # Run examples
    asyncio.run(main())