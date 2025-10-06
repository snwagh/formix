#!/usr/bin/env python3
"""
Formix Network Performance Experiments
Measure and visualize various performance metrics
"""

import asyncio
import time
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import matplotlib.pyplot as plt
import numpy as np
from loguru import logger
from src.formix import FormixNetwork


class FormixExperiments:
    """Run performance experiments on Formix network"""

    def __init__(self):
        self.results = []
        self.results_dir = Path("experiment_results")
        self.results_dir.mkdir(exist_ok=True)

    async def measure_computation_latency(self, network: FormixNetwork,
                                         num_computations: int = 10) -> List[float]:
        """Measure end-to-end computation latency"""
        latencies = []

        for i in range(num_computations):
            start_time = time.time()

            comp_id = await network.propose_computation(
                f"Test computation {i}: Pick a number",
                deadline_seconds=30
            )

            result = await network.wait_for_computation(comp_id)

            latency = time.time() - start_time
            latencies.append(latency)

            print(f"Computation {i+1}/{num_computations}: {latency:.3f}s")

            # Small delay between computations
            await asyncio.sleep(1)

        return latencies

    async def measure_uniform_deadline_latency(self, network: FormixNetwork,
                                               num_computations: int = 30,
                                               deadline: int = 10) -> List[float]:
        """Measure latency for computations with uniform deadline"""
        latencies = []

        # Suppress logger output for accurate timing
        logger.disable("src.formix")

        # # Warm-up: Run a test computation to ensure all nodes are ready
        # print("\nWarming up network with test computation...")
        # try:
        #     warmup_id = await network.propose_computation(
        #         "Warm-up computation",
        #         deadline_seconds=30,
        #         min_participants=1
        #     )
        #     await network.wait_for_computation(warmup_id, timeout=35)
        #     print("✅ Network warmed up and ready")
        # except Exception as e:
        #     print(f"⚠️ Warm-up computation failed (continuing anyway): {e}")

        # # Give network a moment to stabilize after warm-up
        # await asyncio.sleep(2)

        print(f"\nRunning {num_computations} computations with {deadline}s deadline...")

        for i in range(num_computations):
            start_time = time.time()

            comp_id = await network.propose_computation(
                f"Test computation {i}: Pick a number",
                deadline_seconds=deadline,
                min_participants=1
            )

            try:
                result = await network.wait_for_computation(comp_id, timeout=deadline+5)
                latency = time.time() - start_time
                latencies.append(latency)
                print(f"  Computation {i+1}/{num_computations}: {latency:.3f}s")
            except Exception as e:
                print(f"    Warning: Computation {i+1} failed: {e}")
                # Skip failed computations rather than using fake data
                continue

            # Small delay between computations
            await asyncio.sleep(0.5)

        # Re-enable logger after measurements
        logger.enable("src.formix")

        return latencies

    async def measure_scaling_performance(self, max_light_nodes: int = 20) -> Dict[str, List]:
        """Measure how performance scales with number of nodes"""
        scaling_results = {
            'node_counts': [],
            'avg_latencies': [],
            'throughputs': []
        }

        for light_count in range(2, max_light_nodes + 1, 2):
            print(f"\n--- Testing with {light_count} light nodes ---")

            network = FormixNetwork()
            await network.start_network(heavy_count=3, light_count=light_count)

            # Run multiple computations
            latencies = await self.measure_computation_latency(network, num_computations=5)

            avg_latency = statistics.mean(latencies)
            throughput = 1.0 / avg_latency  # computations per second

            scaling_results['node_counts'].append(light_count)
            scaling_results['avg_latencies'].append(avg_latency)
            scaling_results['throughputs'].append(throughput)

            await network.shutdown()
            await asyncio.sleep(2)  # Clean break between tests

        return scaling_results

    async def measure_share_aggregation_time(self, network: FormixNetwork) -> Dict[str, List]:
        """Measure time for different phases of computation"""
        phases = {
            'initialization': [],
            'broadcast': [],
            'share_generation': [],
            'aggregation': [],
            'reveal': [],
            'total': []
        }

        # This would require instrumenting the code with timestamps
        # For now, we'll measure what we can from outside

        for i in range(5):
            start = time.time()

            # Propose computation
            comp_id = await network.propose_computation(
                f"Phase timing test {i}",
                deadline_seconds=30
            )

            # Poll for status changes
            prev_status = None
            status_times = {}

            while True:
                status = await network.get_computation_status(comp_id)
                current_status = status['status']

                if current_status != prev_status:
                    status_times[current_status] = time.time() - start
                    prev_status = current_status

                if current_status in ['completed', 'failed']:
                    break

                await asyncio.sleep(0.1)

            phases['total'].append(status_times.get('completed', 0))

        return phases

    async def measure_concurrent_computations(self, network: FormixNetwork,
                                             concurrent_count: int = 5) -> Dict[str, Any]:
        """Measure performance with concurrent computations"""

        async def run_computation(index: int) -> float:
            start = time.time()
            comp_id = await network.propose_computation(
                f"Concurrent test {index}",
                deadline_seconds=60
            )
            await network.wait_for_computation(comp_id)
            return time.time() - start

        # Run computations concurrently
        start_time = time.time()
        tasks = [run_computation(i) for i in range(concurrent_count)]
        latencies = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        return {
            'individual_latencies': latencies,
            'total_time': total_time,
            'avg_latency': statistics.mean(latencies),
            'throughput': concurrent_count / total_time
        }

    async def measure_network_overhead(self, network: FormixNetwork) -> Dict[str, float]:
        """Measure network communication overhead"""
        overhead_results = {}

        # Measure simple computation (minimal processing)
        simple_latencies = []
        for i in range(5):
            start = time.time()
            comp_id = await network.propose_computation("Return 1", deadline_seconds=10)
            await network.wait_for_computation(comp_id)
            simple_latencies.append(time.time() - start)

        # Measure complex computation (more processing)
        complex_latencies = []
        for i in range(5):
            start = time.time()
            comp_id = await network.propose_computation(
                "Calculate sum of squares from 1 to 1000",
                deadline_seconds=10
            )
            await network.wait_for_computation(comp_id)
            complex_latencies.append(time.time() - start)

        overhead_results['simple_avg'] = statistics.mean(simple_latencies)
        overhead_results['complex_avg'] = statistics.mean(complex_latencies)
        overhead_results['processing_overhead'] = (
            overhead_results['complex_avg'] - overhead_results['simple_avg']
        )

        return overhead_results

    def plot_latency_distribution(self, latencies: List[float], title: str = "Computation Latency Distribution"):
        """Plot histogram of latency distribution"""
        plt.figure(figsize=(10, 6))

        plt.subplot(1, 2, 1)
        plt.hist(latencies, bins=20, edgecolor='black', alpha=0.7)
        plt.xlabel('Latency (seconds)')
        plt.ylabel('Frequency')
        plt.title(title)
        plt.grid(True, alpha=0.3)

        # Add statistics
        plt.axvline(statistics.mean(latencies), color='red',
                   linestyle='--', label=f'Mean: {statistics.mean(latencies):.3f}s')
        plt.axvline(statistics.median(latencies), color='green',
                   linestyle='--', label=f'Median: {statistics.median(latencies):.3f}s')
        plt.legend()

        # Box plot
        plt.subplot(1, 2, 2)
        plt.boxplot(latencies, vert=True)
        plt.ylabel('Latency (seconds)')
        plt.title('Latency Box Plot')
        plt.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.results_dir / 'latency_distribution.png')
        plt.close()  # Close instead of show to continue execution

    def plot_uniform_latency_histogram(self, latencies: List[float]):
        """Plot histogram of latencies with 4:1 aspect ratio matching reference image"""
        plt.figure(figsize=(16, 4))  # 4:1 aspect ratio

        # For tightly clustered data, create bins based on the data range
        min_lat, max_lat = min(latencies), max(latencies)

        # If data is very tightly clustered, use more granular bins
        data_range = max_lat - min_lat
        if data_range < 1:  # Less than 1 second range
            # Use 20 bins for fine-grained view
            bins_to_use = np.linspace(min_lat - 0.01, max_lat + 0.01, 20)
        else:
            # Use at least 15 bins across the range
            bins_to_use = 15

        # Create histogram
        n, bins, patches = plt.hist(latencies, bins=bins_to_use,
                                   edgecolor='black', color='steelblue', alpha=0.7)

        # Calculate statistics
        mean_val = statistics.mean(latencies)
        median_val = statistics.median(latencies)

        # Add vertical lines for mean and median
        plt.axvline(mean_val, color='red', linestyle='--', linewidth=1.5,
                   label=f'Mean: {mean_val:.3f}s')
        plt.axvline(median_val, color='green', linestyle='--', linewidth=1.5,
                   label=f'Median: {median_val:.3f}s')

        # Labels and title
        plt.xlabel('Latency (seconds)', fontsize=12)
        plt.ylabel('Frequency', fontsize=12)
        plt.title('Computation Latency Distribution', fontsize=14)

        # Grid
        plt.grid(True, alpha=0.3)

        # Legend
        plt.legend(loc='upper right', fontsize=11)

        # Tight layout to prevent label cutoff
        plt.tight_layout()

        # Save figure
        plt.savefig(self.results_dir / 'latency_distribution.png', dpi=100)
        plt.close()

    def plot_scaling_results(self, scaling_results: Dict[str, List]):
        """Plot how performance scales with node count"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # Latency vs Node Count
        ax1.plot(scaling_results['node_counts'],
                scaling_results['avg_latencies'],
                marker='o', linewidth=2, markersize=8)
        ax1.set_xlabel('Number of Light Nodes')
        ax1.set_ylabel('Average Latency (seconds)')
        ax1.set_title('Latency vs Network Size')
        ax1.grid(True, alpha=0.3)

        # Throughput vs Node Count
        ax2.plot(scaling_results['node_counts'],
                scaling_results['throughputs'],
                marker='s', linewidth=2, markersize=8, color='green')
        ax2.set_xlabel('Number of Light Nodes')
        ax2.set_ylabel('Throughput (computations/second)')
        ax2.set_title('Throughput vs Network Size')
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.results_dir / 'scaling_performance.png')
        plt.close()  # Close instead of show

    def plot_concurrent_performance(self, concurrent_results: List[Dict]):
        """Plot performance with different levels of concurrency"""
        concurrency_levels = [r['concurrent_count'] for r in concurrent_results]
        throughputs = [r['throughput'] for r in concurrent_results]
        avg_latencies = [r['avg_latency'] for r in concurrent_results]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # Throughput vs Concurrency
        ax1.bar(concurrency_levels, throughputs, color='blue', alpha=0.7)
        ax1.set_xlabel('Concurrent Computations')
        ax1.set_ylabel('Throughput (comp/sec)')
        ax1.set_title('Throughput vs Concurrency')
        ax1.grid(True, alpha=0.3, axis='y')

        # Average Latency vs Concurrency
        ax2.plot(concurrency_levels, avg_latencies,
                marker='o', linewidth=2, color='red')
        ax2.set_xlabel('Concurrent Computations')
        ax2.set_ylabel('Average Latency (seconds)')
        ax2.set_title('Latency vs Concurrency')
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.results_dir / 'concurrent_performance.png')
        plt.close()  # Close instead of show

    def plot_phase_breakdown(self, phase_times: Dict[str, List]):
        """Plot breakdown of computation phases"""
        phases = list(phase_times.keys())
        avg_times = [statistics.mean(times) if times else 0
                    for times in phase_times.values()]

        plt.figure(figsize=(10, 6))
        colors = plt.cm.Set3(np.linspace(0, 1, len(phases)))

        plt.pie(avg_times, labels=phases, colors=colors, autopct='%1.1f%%',
                startangle=90)
        plt.title('Computation Phase Time Breakdown')
        plt.axis('equal')

        plt.savefig(self.results_dir / 'phase_breakdown.png')
        plt.close()  # Close instead of show

    def save_results(self, experiment_name: str, results: Any):
        """Save experiment results to JSON"""
        timestamp = datetime.now().isoformat()
        filename = self.results_dir / f"{experiment_name}_{timestamp}.json"

        with open(filename, 'w') as f:
            json.dump({
                'experiment': experiment_name,
                'timestamp': timestamp,
                'results': results
            }, f, indent=2, default=str)

        print(f"Results saved to {filename}")


async def run_all_experiments():
    """Run comprehensive experiment suite"""
    exp = FormixExperiments()

    print("=" * 60)
    print("FORMIX NETWORK PERFORMANCE EXPERIMENTS")
    print("=" * 60)

    # Experiment 1: Uniform Deadline Latency (30 computations, 10s deadline)
    print("\n[1/5] Measuring computation latency (30 computations, 10s deadline)...")
    network = FormixNetwork()
    await network.start_network(heavy_count=3, light_count=5)

    # Allow network to fully initialize
    print("Network started. Allowing 3 seconds for initialization...")
    await asyncio.sleep(3)

    latencies = await exp.measure_uniform_deadline_latency(network, num_computations=30, deadline=10)

    if latencies:
        exp.plot_uniform_latency_histogram(latencies)
        exp.save_results("uniform_deadline_latency", {
            'latencies': latencies,
            'stats': {
                'count': len(latencies),
                'mean': statistics.mean(latencies),
                'median': statistics.median(latencies),
                'stdev': statistics.stdev(latencies) if len(latencies) > 1 else 0,
                'min': min(latencies),
                'max': max(latencies)
            }
        })

    await network.shutdown()
    await asyncio.sleep(2)

    # Experiment 2: Scaling Performance
    print("\n[2/5] Measuring scaling performance...")
    scaling_results = await exp.measure_scaling_performance(max_light_nodes=20)
    exp.plot_scaling_results(scaling_results)
    exp.save_results("scaling_performance", scaling_results)

    # Experiment 3: Concurrent Computations
    print("\n[3/5] Measuring concurrent computation performance...")
    network = FormixNetwork()
    await network.start_network(heavy_count=3, light_count=10)

    # Allow network to fully initialize
    print("Network started. Allowing 3 seconds for initialization...")
    await asyncio.sleep(3)

    concurrent_results = []
    for concurrent_count in [1, 2, 5, 10]:
        print(f"Testing {concurrent_count} concurrent computations...")
        result = await exp.measure_concurrent_computations(network, concurrent_count)
        result['concurrent_count'] = concurrent_count
        concurrent_results.append(result)

    exp.plot_concurrent_performance(concurrent_results)
    exp.save_results("concurrent_performance", concurrent_results)

    await network.shutdown()
    await asyncio.sleep(2)

    # Experiment 4: Network Overhead
    print("\n[4/5] Measuring network overhead...")
    network = FormixNetwork()
    await network.start_network(heavy_count=3, light_count=5)

    # Allow network to fully initialize
    print("Network started. Allowing 3 seconds for initialization...")
    await asyncio.sleep(3)

    overhead = await exp.measure_network_overhead(network)
    print(f"Simple computation avg: {overhead['simple_avg']:.3f}s")
    print(f"Complex computation avg: {overhead['complex_avg']:.3f}s")
    print(f"Processing overhead: {overhead['processing_overhead']:.3f}s")
    exp.save_results("network_overhead", overhead)

    await network.shutdown()

    # Experiment 5: Phase Timing (if instrumented)
    print("\n[5/5] Measuring computation phases...")
    network = FormixNetwork()
    await network.start_network(heavy_count=3, light_count=5)

    # Allow network to fully initialize
    print("Network started. Allowing 3 seconds for initialization...")
    await asyncio.sleep(3)

    phase_times = await exp.measure_share_aggregation_time(network)
    if any(phase_times.values()):
        exp.plot_phase_breakdown(phase_times)
        exp.save_results("phase_timing", phase_times)

    await network.shutdown()

    print("\n" + "=" * 60)
    print("EXPERIMENTS COMPLETE")
    print(f"Results saved in: {exp.results_dir}")
    print("=" * 60)


async def quick_latency_test():
    """Quick test to measure latency with uniform 10s deadline"""
    exp = FormixExperiments()

    print("Quick Latency Test - 30 Computations with 10s Deadline")
    print("-" * 55)

    network = FormixNetwork()
    await network.start_network(heavy_count=50, light_count=950)

    # Allow network to fully initialize
    print("\nNetwork started. Allowing 3 seconds for initialization...")
    await asyncio.sleep(3)

    # Run the uniform deadline experiment (30 computations, 10s deadline each)
    latencies = await exp.measure_uniform_deadline_latency(network,
                                                          num_computations=30,
                                                          deadline=10)

    # Plot the histogram
    if latencies:
        exp.plot_uniform_latency_histogram(latencies)

        # Print summary statistics
        print("\nResults Summary:")
        print(f"  Total successful computations: {len(latencies)}/30")
        print(f"  Mean latency: {statistics.mean(latencies):.3f}s")
        print(f"  Median latency: {statistics.median(latencies):.3f}s")
        print(f"  Min latency: {min(latencies):.3f}s")
        print(f"  Max latency: {max(latencies):.3f}s")
        if len(latencies) > 1:
            print(f"  Std deviation: {statistics.stdev(latencies):.3f}s")
    else:
        print("\n❌ No successful computations completed")

    await network.shutdown()


if __name__ == "__main__":
    # Install matplotlib if not present
    try:
        import matplotlib
    except ImportError:
        print("Installing matplotlib...")
        import subprocess
        subprocess.check_call(["pip", "install", "matplotlib"])

    # Run experiments
    choice = input("Run [A]ll experiments, [Q]uick test, or [C]ustom? ").lower()

    if choice == 'a':
        asyncio.run(run_all_experiments())
    elif choice == 'q':
        asyncio.run(quick_latency_test())
    else:
        print("Custom experiment - implement your own!")