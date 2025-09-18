# src/formix/core/node.py
import asyncio
import random
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import Enum
from multiprocessing import Process
from typing import Any

from aiohttp import web
from loguru import logger

from ..db.database import NetworkDatabase, NodeDatabase
from ..protocols.aggregation import SecureAggregation
from ..protocols.messaging import Message, MessageProtocol
from ..protocols.secret_sharing import ShareDistribution
from ..utils.config import setup_node_logging


class NodeType(Enum):
    HEAVY = "heavy"
    LIGHT = "light"


class NodeStatus(Enum):
    STARTING = "starting"
    ACTIVE = "active"
    PROCESSING = "processing"
    STOPPING = "stopping"
    STOPPED = "stopped"


class BaseNode(ABC):
    """Abstract base class for all nodes."""

    def __init__(self, uid: str, port: int):
        self.uid = uid
        self.port = port
        self.status = NodeStatus.STARTING

        # Setup per-node logging
        setup_node_logging(uid)

        self.db = NodeDatabase(uid)
        self.network_db = NetworkDatabase()
        self.server = None
        self.app = web.Application()
        self.setup_routes()

    def setup_routes(self):
        """Setup HTTP routes for the node."""
        self.app.router.add_post('/message', self.handle_message)
        self.app.router.add_get('/health', self.handle_health)

    async def handle_health(self, request):
        """Health check endpoint."""
        return web.json_response({
            'status': 'ok',
            'node_id': self.uid,
            'node_status': self.status.value
        })

    async def handle_message(self, request):
        """Handle incoming messages."""
        try:
            data = await request.json()
            message = Message(**data)

            logger.debug(f"Node {self.uid} received message type: {message.type}")

            if message.type == "computation":
                await self.handle_computation(message.payload)
            elif message.type == "share":
                await self.handle_share(message.payload)
            elif message.type == "aggregate_request":
                await self.handle_aggregate_request(message.payload)
            else:
                logger.warning(f"Unknown message type: {message.type}")

            return web.json_response({'status': 'ok'})

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return web.json_response({'status': 'error', 'message': str(e)}, status=500)

    @abstractmethod
    async def handle_computation(self, computation: dict[str, Any]):
        """Handle computation request."""
        pass

    async def handle_share(self, share_data: dict[str, Any]):
        """Handle share message (only for heavy nodes)."""
        pass

    async def handle_aggregate_request(self, request_data: dict[str, Any]):
        """Handle aggregation request (only for heavy nodes)."""
        pass

    async def start(self):
        """Start the node server."""
        self.status = NodeStatus.ACTIVE
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', self.port)
        await site.start()
        logger.info(f"Node {self.uid} started on port {self.port}")

        # Keep the server running
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            logger.info(f"Node {self.uid} shutting down...")
            await runner.cleanup()
            self.status = NodeStatus.STOPPED


class HeavyNode(BaseNode):
    """Heavy node implementation for coordination and aggregation."""

    def __init__(self, uid: str, port: int):
        super().__init__(uid, port)
        self.active_computations = {}  # comp_id -> SecureAggregation
        self.aggregation_tasks = {}  # comp_id -> asyncio.Task

    async def handle_computation(self, computation: dict[str, Any]):
        """Handle new computation - broadcast to light nodes."""
        comp_id = computation['comp_id']

        # Log the computation
        await self.db.log_action(comp_id, "received_computation", computation)

        # Only process if we're one of the designated heavy nodes
        heavy_nodes = [
            computation['heavy_node_1'],
            computation['heavy_node_2'],
            computation['heavy_node_3']
        ]

        if self.uid not in heavy_nodes:
            logger.warning(f"Node {self.uid} not designated for computation {comp_id}")
            return

        # Initialize aggregation tracker
        self.active_computations[comp_id] = SecureAggregation(
            comp_id, computation['min_participants']
        )

        # Broadcast to all light nodes
        light_nodes = await self.network_db.get_nodes_by_type("light")

        logger.info(f"Broadcasting computation {comp_id} to {len(light_nodes)} light nodes")

        message = Message("computation", computation)
        ports = [node['port'] for node in light_nodes]

        await MessageProtocol.broadcast(ports, message)

        # Schedule aggregation at deadline
        deadline = datetime.fromisoformat(computation['deadline'])
        delay = (deadline - datetime.now(UTC)).total_seconds()

        if delay > 0:
            task = asyncio.create_task(self._aggregate_at_deadline(comp_id, delay))
            self.aggregation_tasks[comp_id] = task

    async def handle_share(self, share_data: dict[str, Any]):
        """Handle incoming share from light node."""
        comp_id = share_data['comp_id']
        sender_uid = share_data['sender_uid']
        share_value = share_data['share_value']

        if comp_id not in self.active_computations:
            logger.warning(f"Received share for unknown computation {comp_id}")
            return

        # Store share in database
        await self.db.add_share(comp_id, sender_uid, share_value)

        # Add to aggregation tracker
        self.active_computations[comp_id].add_share(sender_uid, share_value)

        logger.debug(f"Received share from {sender_uid} for computation {comp_id}")

    async def _aggregate_at_deadline(self, comp_id: str, delay: float):
        """Aggregate shares at deadline."""
        await asyncio.sleep(delay)

        logger.info(f"Starting aggregation for computation {comp_id}")

        aggregator = self.active_computations.get(comp_id)
        if not aggregator:
            logger.error(f"No aggregator found for computation {comp_id}")
            return

        if not aggregator.can_aggregate():
            logger.warning(f"Insufficient participants for computation {comp_id}")
            await self.db.log_action(comp_id, "aggregation_failed", {
                "reason": "insufficient_participants",
                "received": len(aggregator.received_shares),
                "required": aggregator.min_participants
            })
            return

        # Compute partial sum
        partial_sum = aggregator.compute_partial_sum()

        # Exchange partial sums with other heavy nodes
        computation = await self._get_computation_details(comp_id)
        heavy_nodes = [
            computation['heavy_node_1'],
            computation['heavy_node_2'],
            computation['heavy_node_3']
        ]

        # Get other heavy nodes
        other_nodes = []
        for uid in heavy_nodes:
            if uid != self.uid:
                node = await self.network_db.get_node(uid)
                if node:
                    other_nodes.append((uid, node['port']))

        # Send our partial sum to other heavy nodes
        message = Message("aggregate_request", {
            'comp_id': comp_id,
            'sender_uid': self.uid,
            'partial_sum': partial_sum,
            'participant_count': len(aggregator.received_shares)
        })

        await MessageProtocol.broadcast([port for _, port in other_nodes], message)

        # Wait for responses and compute final result
        # (In a real implementation, we'd collect responses from other nodes)
        # For PoC, we'll simulate having all partial sums

        # Simulate reconstruction (in reality, we'd wait for other nodes)
        await asyncio.sleep(2)

        # For PoC, just use our partial sum as if it's the total
        # In reality, we'd add all partial sums from all heavy nodes
        total_sum = partial_sum
        num_participants = len(aggregator.received_shares)

        # Compute average
        result = SecureAggregation.compute_average(total_sum, num_participants)

        # Update database with result
        await self.network_db.update_computation_result(comp_id, result, num_participants)

        logger.info(f"Computation {comp_id} completed. Result: {result}, Participants: {num_participants}")

        # Clean up
        del self.active_computations[comp_id]
        del self.aggregation_tasks[comp_id]

    async def _get_computation_details(self, comp_id: str) -> dict[str, Any]:
        """Get computation details from database."""
        computation = await self.network_db.get_computation(comp_id)
        if not computation:
            raise ValueError(f"Computation {comp_id} not found in network database")
        return {
            'heavy_node_1': computation['heavy_node_1'],
            'heavy_node_2': computation['heavy_node_2'],
            'heavy_node_3': computation['heavy_node_3']
        }


class LightNode(BaseNode):
    """Light node implementation for private computation."""

    def __init__(self, uid: str, port: int):
        super().__init__(uid, port)
        self.processed_computations = set()

    async def handle_computation(self, computation: dict[str, Any]):
        """Handle computation request from heavy nodes."""
        comp_id = computation['comp_id']

        # Check if already processed
        if comp_id in self.processed_computations:
            logger.warning(f"Already processed computation {comp_id}")
            return

        self.processed_computations.add(comp_id)

        # Log the computation
        await self.db.log_action(comp_id, "received_computation", computation)

        # For PoC, automatically approve and respond with random number
        response_value = random.randint(0, 100)

        logger.info(f"Node {self.uid} responding to computation {comp_id} with value {response_value}")

        # Store response locally
        await self.db.add_response(comp_id, response_value)

        # Create secret shares
        heavy_nodes = [
            (computation['heavy_node_1'], await self._get_node_port(computation['heavy_node_1'])),
            (computation['heavy_node_2'], await self._get_node_port(computation['heavy_node_2'])),
            (computation['heavy_node_3'], await self._get_node_port(computation['heavy_node_3']))
        ]

        distribution = ShareDistribution(heavy_nodes)
        shares_distribution = distribution.distribute(response_value)

        # Send shares to heavy nodes
        for node_uid, node_port, share_value in shares_distribution:
            message = Message("share", {
                'comp_id': comp_id,
                'sender_uid': self.uid,
                'share_value': share_value
            })

            try:
                await MessageProtocol.send_message(node_port, message)
                logger.debug(f"Sent share to heavy node {node_uid}")
            except Exception as e:
                logger.error(f"Failed to send share to {node_uid}: {e}")

        await self.db.log_action(comp_id, "sent_shares", {
            'response_value': response_value,
            'heavy_nodes': [uid for uid, _, _ in shares_distribution]
        })

    async def _get_node_port(self, uid: str) -> int:
        """Get port for a node by UID."""
        node = await self.network_db.get_node(uid)
        return node['port'] if node else 0


class NodeManager:
    """Manages node processes."""

    def __init__(self):
        self.processes = {}  # uid -> Process

    async def start_node(self, uid: str, node_type: str, port: int):
        """Start a node as a separate process."""
        if uid in self.processes:
            logger.warning(f"Node {uid} already running")
            return

        # Create and start process
        if node_type == "heavy":
            process = Process(target=self._run_heavy_node, args=(uid, port))
        else:
            process = Process(target=self._run_light_node, args=(uid, port))

        process.start()
        self.processes[uid] = process
        logger.info(f"Started {node_type} node {uid} as process {process.pid}")

    async def stop_node(self, uid: str):
        """Stop a node process."""
        process = self.processes.get(uid)
        if not process:
            logger.warning(f"No process found for node {uid}")
            return

        process.terminate()
        process.join(timeout=5)

        if process.is_alive():
            process.kill()
            process.join()

        del self.processes[uid]
        logger.info(f"Stopped node {uid}")

    async def stop_all_nodes(self):
        """Stop all managed node processes."""
        if not self.processes:
            logger.info("No running node processes to stop")
            return

        logger.info(f"Stopping {len(self.processes)} node processes...")
        stopped_uids = []
        failed_uids = []

        # Create a copy of the processes dict to avoid modification during iteration
        processes_to_stop = dict(self.processes)

        for uid, process in processes_to_stop.items():
            try:
                process.terminate()
                process.join(timeout=5)

                if process.is_alive():
                    logger.warning(f"Node {uid} did not terminate gracefully, killing...")
                    process.kill()
                    process.join()

                stopped_uids.append(uid)
                logger.info(f"Stopped node {uid}")

            except Exception as e:
                logger.error(f"Failed to stop node {uid}: {e}")
                failed_uids.append(uid)

        # Clear stopped processes from the dictionary
        for uid in stopped_uids:
            if uid in self.processes:
                del self.processes[uid]

        logger.info(f"Stopped {len(stopped_uids)} nodes successfully")
        if failed_uids:
            logger.warning(f"Failed to stop {len(failed_uids)} nodes: {failed_uids}")

        return len(stopped_uids), len(failed_uids)

    def _run_heavy_node(self, uid: str, port: int):
        """Run a heavy node in a separate process."""
        asyncio.run(self._run_node(HeavyNode(uid, port)))

    def _run_light_node(self, uid: str, port: int):
        """Run a light node in a separate process."""
        asyncio.run(self._run_node(LightNode(uid, port)))

    async def _run_node(self, node: BaseNode):
        """Run a node."""
        try:
            await node.start()
        except Exception as e:
            logger.error(f"Node {node.uid} crashed: {e}")

    async def broadcast_computation(self, computation: dict[str, Any]):
        """Broadcast computation to heavy nodes."""
        # Send computation to the designated heavy nodes
        heavy_node_uids = [
            computation['heavy_node_1'],
            computation['heavy_node_2'],
            computation['heavy_node_3']
        ]

        db = NetworkDatabase()
        message = Message("computation", computation)

        for uid in heavy_node_uids:
            node = await db.get_node(uid)
            if node:
                try:
                    await MessageProtocol.send_message(node['port'], message)
                    logger.info(f"Sent computation to heavy node {uid}")
                except Exception as e:
                    logger.error(f"Failed to send computation to {uid}: {e}")
