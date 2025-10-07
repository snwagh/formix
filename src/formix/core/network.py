# src/formix/network.py
import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from loguru import logger

from .node import HeavyNode, LightNode, NodeManager
from ..db.database import NetworkDatabase, NodeDatabase
from ..utils.helpers import generate_uid


class FormixNetwork:
    """
    Pure Python interface for managing a Formix network.

    Eliminates CLI complexity and provides direct programmatic control.
    """

    def __init__(self):
        self.nodes = {}  # {uid: node_instance}
        self.node_tasks = {}  # {uid: asyncio.Task}
        self.heavy_nodes = []  # [uid, uid, uid] - ordered list
        self.light_nodes = []  # [uid, uid, ...] - ordered list
        self.running = False
        self.network_db = None

    async def initialize(self):
        """Initialize the network database."""
        self.network_db = NetworkDatabase()
        await self.network_db.initialize()

        # Clean up any stale nodes from previous runs
        await self._cleanup_stale_nodes()

        logger.info("FormixNetwork initialized")

    async def _cleanup_stale_nodes(self):
        """Remove any stale nodes from previous runs."""
        existing_nodes = await self.network_db.get_all_nodes()
        if existing_nodes:
            logger.info(f"Cleaning up {len(existing_nodes)} stale nodes from previous runs")
            for node in existing_nodes:
                await self.network_db.remove_node(node['uid'])
                # Also cleanup node directories
                try:
                    node_db = NodeDatabase(node['uid'])
                    node_db.cleanup()
                except Exception:
                    pass  # Directory might not exist

    async def start_network(self, heavy_count: int = 3, light_count: int = 5) -> dict[str, list[str]]:
        """
        Start a complete network with specified number of nodes.

        Args:
            heavy_count: Number of heavy nodes to create (default: 3)
            light_count: Number of light nodes to create (default: 5)

        Returns:
            Dict with 'heavy' and 'light' keys containing lists of node UIDs
        """
        if self.running:
            raise RuntimeError("Network is already running")

        await self.initialize()

        logger.info(f"Starting network with {heavy_count} heavy nodes and {light_count} light nodes")

        # Start with a clean port range
        import aiosqlite
        async with aiosqlite.connect(self.network_db.db_path) as db:
            await db.execute("DELETE FROM users")
            await db.commit()

        # Start heavy nodes
        for i in range(heavy_count):
            uid = await self._create_node("heavy")
            self.heavy_nodes.append(uid)

        # Start light nodes
        for i in range(light_count):
            uid = await self._create_node("light")
            self.light_nodes.append(uid)

        self.running = True

        logger.info(f"Network started successfully:")
        logger.info(f"  Heavy nodes: {self.heavy_nodes}")
        logger.info(f"  Light nodes: {self.light_nodes}")

        return {
            'heavy': self.heavy_nodes.copy(),
            'light': self.light_nodes.copy()
        }

    async def _create_node(self, node_type: str) -> str:
        """Create and start a single node."""
        uid = generate_uid()
        port = await self.network_db.get_next_available_port()

        # Add to database
        success = await self.network_db.add_node(uid, node_type, port)
        if not success:
            raise RuntimeError(f"Failed to add {node_type} node {uid} to database")

        # Initialize node database
        node_db = NodeDatabase(uid)
        if node_type == "heavy":
            await node_db.initialize_heavy_node()
            node = HeavyNode(uid, port)
        else:
            await node_db.initialize_light_node()
            node = LightNode(uid, port)

        # Start node in background task
        task = asyncio.create_task(node.start())

        # Store references to prevent garbage collection
        self.nodes[uid] = node
        self.node_tasks[uid] = task

        # Give node time to start
        await asyncio.sleep(0.2)

        logger.info(f"Created {node_type} node {uid} on port {port}")
        return uid

    async def add_node(self, node_type: str) -> str:
        """Add a single node to the running network."""
        if not self.running:
            raise RuntimeError("Network is not running")

        uid = await self._create_node(node_type)

        if node_type == "heavy":
            self.heavy_nodes.append(uid)
        else:
            self.light_nodes.append(uid)

        return uid

    async def propose_computation(
        self,
        prompt: str,
        proposer_uid: Optional[str] = None,
        heavy_node_uids: Optional[list[str]] = None,
        deadline_seconds: int = 60,
        min_participants: int = 1,
        response_schema: str = '{"type": "number"}'
    ) -> str:
        """
        Propose a computation with automatic defaults.

        Args:
            prompt: The computation question/prompt
            proposer_uid: Proposing node UID (default: first light node)
            heavy_node_uids: List of 3 heavy node UIDs (default: first 3 heavy nodes)
            deadline_seconds: Deadline in seconds from now
            min_participants: Minimum number of participants
            response_schema: JSON schema for responses

        Returns:
            Computation ID
        """
        if not self.running:
            raise RuntimeError("Network is not running")

        # Apply defaults
        if proposer_uid is None:
            if not self.light_nodes:
                raise RuntimeError("No light nodes available for proposer")
            proposer_uid = self.light_nodes[0]

        if heavy_node_uids is None:
            if len(self.heavy_nodes) < 3:
                raise RuntimeError(f"Need at least 3 heavy nodes, have {len(self.heavy_nodes)}")
            heavy_node_uids = self.heavy_nodes[:3]

        if len(heavy_node_uids) != 3:
            raise ValueError("Exactly 3 heavy nodes required")

        # Create computation
        deadline = datetime.now(UTC) + timedelta(seconds=deadline_seconds)
        comp_id = f"COMP-{generate_uid()}"

        computation = {
            'comp_id': comp_id,
            'proposer_uid': proposer_uid,
            'heavy_node_1': heavy_node_uids[0],
            'heavy_node_2': heavy_node_uids[1],
            'heavy_node_3': heavy_node_uids[2],
            'computation_prompt': prompt,
            'response_schema': response_schema,
            'deadline': deadline.isoformat(),
            'min_participants': min_participants
        }

        # Store in database
        success = await self.network_db.add_computation(computation)
        if not success:
            raise RuntimeError("Failed to store computation in database")

        # Broadcast to heavy nodes
        await NodeManager.broadcast_computation(computation)

        logger.info(f"Proposed computation {comp_id}: '{prompt}'")
        logger.info(f"  Proposer: {proposer_uid}")
        logger.info(f"  Heavy nodes: {heavy_node_uids}")
        logger.info(f"  Deadline: {deadline_seconds}s from now")
        logger.info(f"  Min participants: {min_participants}")

        return comp_id

    async def get_computation_status(self, comp_id: str) -> Optional[dict[str, Any]]:
        """Get the status and result of a computation."""
        if not self.network_db:
            await self.initialize()

        return await self.network_db.get_computation(comp_id)

    async def wait_for_computation(self, comp_id: str, timeout: int = 120) -> dict[str, Any]:
        """
        Wait for a computation to complete and return the result.

        Args:
            comp_id: Computation ID to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            Computation result dictionary
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            status = await self.get_computation_status(comp_id)
            if not status:
                raise RuntimeError(f"Computation {comp_id} not found")

            if status['status'] == 'completed':
                logger.info(f"Computation {comp_id} completed successfully!")
                return status
            elif status['status'].startswith('failed'):
                raise RuntimeError(f"Computation {comp_id} failed: {status['status']}")

            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"Computation {comp_id} did not complete within {timeout}s")

            # Wait before checking again
            await asyncio.sleep(1.0)

    async def list_computations(self) -> list[dict[str, Any]]:
        """List all computations in the network."""
        if not self.network_db:
            await self.initialize()

        import aiosqlite
        async with aiosqlite.connect(self.network_db.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM computations
                ORDER BY created_at DESC
                LIMIT 20
            """)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_network_status(self) -> dict[str, Any]:
        """Get current network status."""
        if not self.network_db:
            await self.initialize()

        all_nodes = await self.network_db.get_all_nodes()
        heavy_count = sum(1 for node in all_nodes if node['node_type'] == 'heavy')
        light_count = sum(1 for node in all_nodes if node['node_type'] == 'light')

        # Check which nodes are actually running
        running_nodes = []
        for uid, node in self.nodes.items():
            if not self.node_tasks[uid].done():
                running_nodes.append(uid)

        return {
            'running': self.running,
            'total_nodes': len(all_nodes),
            'heavy_nodes': heavy_count,
            'light_nodes': light_count,
            'running_nodes': len(running_nodes),
            'heavy_node_uids': self.heavy_nodes,
            'light_node_uids': self.light_nodes,
            'active_running_nodes': running_nodes
        }

    async def shutdown(self):
        """Gracefully shutdown the entire network."""
        if not self.running:
            logger.info("Network is not running")
            return

        logger.info("Shutting down FormixNetwork...")

        # Signal all nodes to shutdown
        for uid, node in self.nodes.items():
            try:
                node.shutdown_event.set()
            except Exception as e:
                logger.warning(f"Error signaling shutdown to {uid}: {e}")

        # Wait for all tasks to complete
        if self.node_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.node_tasks.values(), return_exceptions=True),
                    timeout=5.0
                )
            except TimeoutError:
                logger.warning("Some nodes did not shutdown gracefully within timeout")

        # Clean up database
        if self.network_db:
            # Clear all computations
            await self.network_db.clear_all_computations()

            # Remove all nodes and their directories
            existing_nodes = await self.network_db.get_all_nodes()
            for node in existing_nodes:
                await self.network_db.remove_node(node['uid'])
                # Also cleanup node directories
                try:
                    node_db = NodeDatabase(node['uid'])
                    node_db.cleanup()
                except Exception:
                    pass

        # Clean up in-memory state
        self.nodes.clear()
        self.node_tasks.clear()
        self.heavy_nodes.clear()
        self.light_nodes.clear()
        self.running = False

        logger.info("FormixNetwork shutdown complete")

    async def __aenter__(self):
        """Async context manager support."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager cleanup."""
        await self.shutdown()


# Convenience functions for quick testing
async def quick_network(heavy_count: int = 3, light_count: int = 5) -> FormixNetwork:
    """Quickly create and start a network."""
    network = FormixNetwork()
    await network.start_network(heavy_count, light_count)
    return network


async def quick_computation(network: FormixNetwork, prompt: str, wait: bool = True) -> dict[str, Any]:
    """Quickly propose a computation and optionally wait for result."""
    comp_id = await network.propose_computation(prompt)

    if wait:
        return await network.wait_for_computation(comp_id)
    else:
        return {'comp_id': comp_id}