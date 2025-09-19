# src/formix/core/node.py
import asyncio
import random
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aiohttp import web
from loguru import logger

from ..db.database import NetworkDatabase, NodeDatabase
from ..protocols.aggregation import SecureAggregation
from ..protocols.messaging import Message, MessageProtocol
from ..protocols.secret_sharing import SecretSharing, ShareDistribution
from ..utils.config import setup_node_logging


class NodeStatus(Enum):
    ACTIVE = "active"
    STOPPING = "stopping"
    STOPPED = "stopped"


class BaseNode(ABC):
    """Abstract base class for all nodes."""

    def __init__(self, uid: str, port: int):
        self.uid = uid
        self.port = port
        self.status = NodeStatus.ACTIVE

        setup_node_logging(uid)

        self.db = NodeDatabase(uid)
        self.network_db = NetworkDatabase()
        self.shutdown_event = asyncio.Event()
        self.runner = None
        self.site = None

        # Setup HTTP app
        self.app = web.Application()
        self.app.router.add_post('/message', self.handle_message)
        self.app.router.add_get('/health', self.handle_health)
        self.app.router.add_post('/shutdown', self.handle_shutdown)

    async def handle_health(self, request):
        """Health check endpoint."""
        return web.json_response({
            'status': 'ok',
            'node_id': self.uid,
            'node_status': self.status.value
        })

    async def handle_shutdown(self, request):
        """Shutdown endpoint."""
        logger.info(f"Node {self.uid} received shutdown request")
        self.shutdown_event.set()
        return web.json_response({'status': 'shutting_down', 'node_id': self.uid})

    async def handle_message(self, request):
        """Handle incoming messages."""
        try:
            data = await request.json()
            message = Message(**data)

            if message.type == "computation":
                await self.handle_computation(message.payload)
                return web.json_response({'status': 'ok'})
            elif message.type == "share":
                await self.handle_share(message.payload)
                return web.json_response({'status': 'ok'})
            elif message.type == "reveal_request":
                response = await self.handle_reveal_request(message.payload)
                return web.json_response(response or {'status': 'ok'})
            elif message.type == "reveal_response":
                await self.handle_reveal_response(message.payload)
                return web.json_response({'status': 'ok'})
            elif message.type == "heavy_init_confirm":
                await self.handle_heavy_init_confirm(message.payload)
                return web.json_response({'status': 'ok'})
            elif message.type == "shutdown":
                self.shutdown_event.set()
                return web.json_response({'status': 'shutting_down'})

            return web.json_response({'status': 'ok', 'message': 'Unknown message type'})

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

    async def handle_reveal_request(self, request_data: dict[str, Any]):
        """Handle reveal request (only for heavy nodes)."""
        pass

    async def handle_reveal_response(self, response_data: dict[str, Any]):
        """Handle reveal response (only for heavy nodes)."""
        pass

    async def handle_heavy_init_confirm(self, data: dict[str, Any]):
        """Handle heavy node initialization confirmation (only for heavy nodes)."""
        pass

    async def start(self):
        """Start the node server."""
        # Register node in network database (if not already registered)
        node_type = "heavy" if isinstance(self, HeavyNode) else "light"
        existing_node = await self.network_db.get_node(self.uid)
        if not existing_node:
            await self.network_db.add_node(self.uid, node_type, self.port)
            logger.info(f"Registered {node_type} node {self.uid} on port {self.port}")

        # Start HTTP server
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, 'localhost', self.port)
        await self.site.start()
        logger.info(f"Node {self.uid} started on port {self.port}")

        # Wait for shutdown signal
        await self.shutdown_event.wait()
        await self.cleanup()

    async def cleanup(self):
        """Comprehensive cleanup of all node resources."""
        logger.info(f"Cleaning up node {self.uid}")
        self.status = NodeStatus.STOPPING

        # 1. Stop HTTP server
        if self.site:
            try:
                await asyncio.wait_for(self.site.stop(), timeout=3.0)
            except Exception as e:
                logger.warning(f"Error stopping site: {e}")

        if self.runner:
            try:
                await asyncio.wait_for(self.runner.cleanup(), timeout=3.0)
            except Exception as e:
                logger.warning(f"Error cleaning runner: {e}")

        # 2. Remove from network database
        try:
            await self.network_db.remove_node(self.uid)
            logger.info(f"Removed node {self.uid} from network database")
        except Exception as e:
            logger.error(f"Error removing from network DB: {e}")

        # 3. Clean up node folder and database
        try:
            self.db.cleanup()
            logger.info(f"Cleaned up node directory for {self.uid}")
        except Exception as e:
            logger.error(f"Error cleaning node directory: {e}")

        self.status = NodeStatus.STOPPED


class HeavyNode(BaseNode):
    """Heavy node implementation for coordination and aggregation."""

    def __init__(self, uid: str, port: int):
        super().__init__(uid, port)
        self.active_computations = {}  # comp_id -> SecureAggregation
        self.processed_computations = set()

    async def handle_computation(self, computation: dict[str, Any]):
        """Handle new computation - ALL heavy nodes initialize, only first broadcasts."""
        comp_id = computation['comp_id']

        if comp_id in self.processed_computations:
            return

        self.processed_computations.add(comp_id)

        # Check if this node is designated for this computation
        heavy_nodes = [computation['heavy_node_1'], computation['heavy_node_2'], computation['heavy_node_3']]
        if self.uid not in heavy_nodes:
            logger.debug(f"Heavy node {self.uid} not designated for computation {comp_id}")
            return

        logger.info(f"Heavy node {self.uid} initializing computation {comp_id}")

        # ALL designated heavy nodes must initialize aggregation
        self.active_computations[comp_id] = SecureAggregation(
            comp_id,
            computation['min_participants'],
            self.uid,
            heavy_nodes
        )

        # Send initialization confirmation to first heavy node
        first_heavy = heavy_nodes[0]
        if self.uid != first_heavy:
            await self._send_init_confirmation(first_heavy, comp_id)

        # Only the first heavy node coordinates with other heavy nodes
        if heavy_nodes[0] == self.uid:
            # Wait for other heavy nodes to confirm initialization
            await self._wait_for_heavy_node_confirmations(comp_id, heavy_nodes[1:])
            logger.info(f"All heavy nodes ready for computation {comp_id}")

        # Schedule aggregation
        deadline = datetime.fromisoformat(computation['deadline'])
        delay = (deadline - datetime.now(UTC)).total_seconds()
        if delay > 0:
            asyncio.create_task(self._process_at_deadline(comp_id, delay, computation))

    async def handle_share(self, share_data: dict[str, Any]):
        """Handle incoming share from light node."""
        comp_id = share_data['comp_id']
        sender_uid = share_data['sender_uid']
        share_value = share_data['share_value']

        logger.info(f"Heavy node {self.uid} received share from {sender_uid} for computation {comp_id}")

        if comp_id not in self.active_computations:
            logger.warning(f"Heavy node {self.uid} has no active computation {comp_id}")
            return

        await self.db.add_share(comp_id, sender_uid, share_value)
        self.active_computations[comp_id].add_share(sender_uid, share_value)

        # Log current state
        aggregator = self.active_computations[comp_id]
        logger.info(f"Heavy node {self.uid} now has {len(aggregator.received_shares)} shares for computation {comp_id}")

    async def _process_at_deadline(self, comp_id: str, delay: float, computation: dict[str, Any]):
        """Process computation at deadline."""
        await asyncio.sleep(delay)

        aggregator = self.active_computations.get(comp_id)
        if not aggregator:
            logger.warning(f"No aggregator found for computation {comp_id}")
            return

        # Check if we have enough participants
        if not aggregator.can_aggregate():
            logger.warning(f"Insufficient participants for computation {comp_id}: {len(aggregator.received_shares)} < {aggregator.min_participants}")
            # Mark computation as failed due to insufficient participants
            await self.network_db.update_computation_status(comp_id, "failed", "Insufficient participants")
            del self.active_computations[comp_id]
            return

        if aggregator.is_primary_heavy_node():
            # Primary heavy node initiates reveal process
            await self._initiate_reveal_process(comp_id, computation)
        else:
            # Secondary heavy nodes wait for reveal requests
            logger.info(f"Heavy node {self.uid} computed partial sum for computation {comp_id}, waiting for reveal request")

    async def _initiate_reveal_process(self, comp_id: str, computation: dict[str, Any]):
        """Initiate reveal process (primary heavy node only)."""
        try:
            aggregator = self.active_computations[comp_id]

            # Final check for anonymity threshold
            if not aggregator.meets_anonymity_threshold():
                logger.error(f"Cannot initiate reveal: anonymity threshold not met for computation {comp_id}")
                await self.network_db.update_computation_status(comp_id, "failed", "Anonymity threshold not met")
                del self.active_computations[comp_id]
                return

            # Get other heavy nodes
            heavy_nodes = [computation['heavy_node_1'], computation['heavy_node_2'], computation['heavy_node_3']]
            other_heavy_nodes = [uid for uid in heavy_nodes if uid != self.uid]

            logger.info(f"Primary heavy node {self.uid} initiating reveal process for computation {comp_id}")

            # Request partial sums from other heavy nodes
            successful_requests = 0
            failed_nodes = []

            for heavy_node_uid in other_heavy_nodes:
                try:
                    node = await self.network_db.get_node(heavy_node_uid)
                    if not node:
                        logger.error(f"Heavy node {heavy_node_uid} not found in database")
                        failed_nodes.append(heavy_node_uid)
                        continue

                    message = Message("reveal_request", {
                        "comp_id": comp_id,
                        "sender_uid": self.uid
                    })

                    response = await MessageProtocol.request_response(
                        node['port'], message, response_timeout=10.0
                    )

                    if response and response.get('status') == 'ok':
                        successful_requests += 1
                        logger.info(f"Successfully sent reveal request to {heavy_node_uid}")
                    else:
                        logger.error(f"Failed to get response from heavy node {heavy_node_uid}")
                        failed_nodes.append(heavy_node_uid)

                except Exception as e:
                    logger.error(f"Error requesting reveal from {heavy_node_uid}: {e}")
                    failed_nodes.append(heavy_node_uid)

            # Check if we have enough responses
            if successful_requests < len(other_heavy_nodes):
                logger.warning(f"Only {successful_requests}/{len(other_heavy_nodes)} heavy nodes responded to reveal request")
                if failed_nodes:
                    logger.warning(f"Failed nodes: {failed_nodes}")

            # Wait a bit for responses to arrive
            await asyncio.sleep(2.0)

            # Attempt final reconstruction
            await self._attempt_final_reconstruction(comp_id)

        except Exception as e:
            logger.error(f"Error in reveal process initiation for {comp_id}: {e}")
            await self.network_db.update_computation_status(comp_id, "failed", f"Reveal process error: {str(e)}")
            if comp_id in self.active_computations:
                del self.active_computations[comp_id]

    async def _send_init_confirmation(self, first_heavy_uid: str, comp_id: str):
        """Send initialization confirmation to the first heavy node."""
        try:
            first_heavy_node = await self.network_db.get_node(first_heavy_uid)
            if first_heavy_node:
                message = Message("heavy_init_confirm", {
                    "comp_id": comp_id,
                    "sender_uid": self.uid
                })
                await MessageProtocol.send_message(first_heavy_node['port'], message)
                logger.info(f"Heavy node {self.uid} sent init confirmation for {comp_id} to {first_heavy_uid}")
        except Exception as e:
            logger.error(f"Failed to send init confirmation: {e}")

    async def _wait_for_heavy_node_confirmations(self, comp_id: str, other_heavy_nodes: list[str]):
        """Wait for other heavy nodes to confirm initialization."""
        if not other_heavy_nodes:
            return

        # Initialize confirmation tracking
        if not hasattr(self, 'init_confirmations'):
            self.init_confirmations = {}
        self.init_confirmations[comp_id] = set()

        expected_confirmations = set(other_heavy_nodes)
        logger.info(f"Waiting for init confirmations from {expected_confirmations} for {comp_id}")

        # Wait up to 3 seconds for confirmations
        for attempt in range(30):  # 30 * 0.1s = 3s
            if expected_confirmations.issubset(self.init_confirmations[comp_id]):
                logger.info(f"All heavy nodes confirmed initialization for {comp_id}")
                return
            await asyncio.sleep(0.1)

        missing = expected_confirmations - self.init_confirmations[comp_id]
        logger.warning(f"Proceeding without confirmations from {missing} for {comp_id}")

    async def handle_heavy_init_confirm(self, data: dict[str, Any]):
        """Handle initialization confirmation from other heavy nodes."""
        comp_id = data['comp_id']
        sender_uid = data['sender_uid']

        if not hasattr(self, 'init_confirmations'):
            self.init_confirmations = {}
        if comp_id not in self.init_confirmations:
            self.init_confirmations[comp_id] = set()

        self.init_confirmations[comp_id].add(sender_uid)
        logger.info(f"Received init confirmation from {sender_uid} for {comp_id}")

    async def handle_reveal_request(self, request_data: dict[str, Any]):
        """Handle reveal request from primary heavy node."""
        comp_id = request_data['comp_id']
        requester_uid = request_data['sender_uid']

        aggregator = self.active_computations.get(comp_id)
        if not aggregator:
            logger.warning(f"No aggregator found for reveal request {comp_id}")
            return {'status': 'error', 'message': 'No aggregator found'}

        # Compute our partial sum
        partial_sum = aggregator.compute_partial_sum()
        participant_count = len(aggregator.received_shares)

        logger.info(f"Heavy node {self.uid} responding to reveal request for {comp_id} with partial sum {partial_sum}")

        # Send response to requester
        try:
            requester_node = await self.network_db.get_node(requester_uid)
            if requester_node:
                message = Message("reveal_response", {
                    "comp_id": comp_id,
                    "sender_uid": self.uid,
                    "partial_sum": partial_sum,
                    "participant_count": participant_count
                })

                await MessageProtocol.send_message(requester_node['port'], message)
                logger.info(f"Sent reveal response to {requester_uid}")
                return {'status': 'ok'}
            else:
                logger.error(f"Requester node {requester_uid} not found")
                return {'status': 'error', 'message': 'Requester not found'}
        except Exception as e:
            logger.error(f"Error sending reveal response: {e}")
            return {'status': 'error', 'message': str(e)}

    async def handle_reveal_response(self, response_data: dict[str, Any]):
        """Handle reveal response from other heavy nodes."""
        comp_id = response_data['comp_id']
        sender_uid = response_data['sender_uid']
        partial_sum = response_data['partial_sum']

        aggregator = self.active_computations.get(comp_id)
        if not aggregator:
            logger.warning(f"No aggregator found for reveal response {comp_id}")
            return

        # Add partial sum from other heavy node
        aggregator.add_partial_sum_from_heavy_node(sender_uid, partial_sum)
        logger.info(f"Received partial sum {partial_sum} from heavy node {sender_uid} for computation {comp_id}")

        # Check if we can perform final reconstruction
        if aggregator.can_perform_final_reconstruction():
            await self._attempt_final_reconstruction(comp_id)

    async def _attempt_final_reconstruction(self, comp_id: str):
        """Attempt to perform final reconstruction and store result."""
        aggregator = self.active_computations.get(comp_id)
        if not aggregator:
            logger.error(f"No aggregator found for computation {comp_id}")
            return

        if not aggregator.is_primary_heavy_node():
            logger.warning(f"Node {self.uid} is not the primary heavy node for computation {comp_id}")
            return

        try:
            # Check if we can perform reconstruction
            if not aggregator.can_perform_final_reconstruction():
                # Check how many partial sums we have
                received_count = len(aggregator.partial_sums_from_other_nodes)
                expected_count = len(aggregator.heavy_nodes) - 1  # Exclude ourselves

                if received_count == 0:
                    error_msg = "No partial sums received from other heavy nodes"
                else:
                    missing_nodes = [uid for uid in aggregator.heavy_nodes
                                   if uid != aggregator.heavy_node_uid and
                                   uid not in aggregator.partial_sums_from_other_nodes]
                    error_msg = f"Missing partial sums from heavy nodes: {missing_nodes}"

                logger.error(f"Cannot perform final reconstruction for {comp_id}: {error_msg}")
                await self.network_db.update_computation_status(comp_id, "failed", error_msg)
                del self.active_computations[comp_id]
                return

            # Perform final reconstruction
            final_result = aggregator.compute_final_result()
            total_participants = aggregator.get_total_participants()

            # Validate the result is reasonable
            if final_result < 0 or final_result >= SecretSharing.MODULUS:
                logger.warning(f"Unusual final result for {comp_id}: {final_result}")

            # Store result in database with completed status
            await self.network_db.update_computation_result(comp_id, final_result, total_participants)
            logger.info(f"🎉 Computation {comp_id} completed successfully!")
            logger.info(f"   Final result: {final_result}")
            logger.info(f"   Total participants: {total_participants}")
            logger.info(f"   Heavy nodes: {aggregator.heavy_nodes}")

            # Cleanup
            del self.active_computations[comp_id]

        except ValueError as e:
            # Handle validation errors (anonymity threshold, etc.)
            logger.error(f"Validation error in final reconstruction for {comp_id}: {e}")
            await self.network_db.update_computation_status(comp_id, "failed", str(e))
            if comp_id in self.active_computations:
                del self.active_computations[comp_id]

        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Unexpected error in final reconstruction for {comp_id}: {e}")
            await self.network_db.update_computation_status(comp_id, "failed", f"Reconstruction error: {str(e)}")
            if comp_id in self.active_computations:
                del self.active_computations[comp_id]


class LightNode(BaseNode):
    """Light node implementation for private computation."""

    def __init__(self, uid: str, port: int):
        super().__init__(uid, port)
        self.processed_computations = set()

    async def handle_computation(self, computation: dict[str, Any]):
        """Handle computation request from heavy nodes."""
        comp_id = computation['comp_id']

        logger.info(f"Light node {self.uid} received computation {comp_id}")

        if comp_id in self.processed_computations:
            logger.debug(f"Light node {self.uid} already processed computation {comp_id}")
            return

        self.processed_computations.add(comp_id)

        # Small delay to ensure heavy nodes are ready
        await asyncio.sleep(0.5)

        # Generate response value (random for PoC)
        response_value = random.randint(0, 100)
        logger.info(f"Light node {self.uid} responding to computation {comp_id} with value {response_value}")

        # Store response
        await self.db.add_response(comp_id, response_value)

        # Get heavy node ports and create shares
        heavy_nodes = []
        for uid in [computation['heavy_node_1'], computation['heavy_node_2'], computation['heavy_node_3']]:
            node = await self.network_db.get_node(uid)
            if node:
                heavy_nodes.append((uid, node['port']))

        # Distribute shares
        distribution = ShareDistribution(heavy_nodes)
        shares_distribution = distribution.distribute(response_value)

        # Send shares to heavy nodes
        logger.info(f"Light node {self.uid} sending shares for computation {comp_id} to {len(shares_distribution)} heavy nodes")
        for node_uid, node_port, share_value in shares_distribution:
            message = Message("share", {
                'comp_id': comp_id,
                'sender_uid': self.uid,
                'share_value': share_value
            })

            try:
                await MessageProtocol.send_message(node_port, message)
                logger.debug(f"Light node {self.uid} sent share {share_value} to heavy node {node_uid} on port {node_port}")
            except Exception as e:
                logger.error(f"Failed to send share to {node_uid}: {e}")


class NodeManager:
    """Simplified node manager with comprehensive cleanup orchestration."""

    @staticmethod
    async def run_node(uid: str, node_type: str, port: int):
        """Run a node with proper initialization and cleanup."""
        node = None
        try:
            # Initialize database
            node_db = NodeDatabase(uid)
            if node_type == "heavy":
                await node_db.initialize_heavy_node()
                node = HeavyNode(uid, port)
            else:
                await node_db.initialize_light_node()
                node = LightNode(uid, port)

            await node.start()

        except asyncio.CancelledError:
            logger.info(f"Node {uid} cancelled")
        except Exception as e:
            logger.error(f"Node {uid} crashed: {e}")
        finally:
            if node:
                await node.cleanup()

    @staticmethod
    async def shutdown_node(uid: str, port: int, fast_shutdown: bool = False):
        """Gracefully shutdown a node with comprehensive cleanup."""
        # Use shorter timeout for fast shutdown mode (used in stop-all)
        timeout = 1.0 if fast_shutdown else 3.0

        try:
            # Try graceful shutdown first
            message = Message("shutdown", {"uid": uid})
            await asyncio.wait_for(
                MessageProtocol.send_message(port, message, suppress_warnings=True, timeout=timeout),
                timeout=timeout
            )
            logger.info(f"Sent shutdown signal to node {uid}")
        except Exception as e:
            logger.info(f"Graceful shutdown failed for {uid} (node may already be stopped)")
            # Force cleanup processes
            await NodeManager._force_cleanup_port(port)

        # Always clean up database and files regardless of graceful shutdown success
        try:
            # Clean up database entry
            network_db = NetworkDatabase()
            removed = await network_db.remove_node(uid)
            if removed:
                logger.info(f"Removed node {uid} from network database")

            # Clean up node directory
            node_db = NodeDatabase(uid)
            node_db.cleanup()
            logger.info(f"Cleaned up node directory for {uid}")

        except Exception as cleanup_error:
            logger.error(f"Database/file cleanup failed for {uid}: {cleanup_error}")

    @staticmethod
    async def _force_cleanup_port(port: int):
        """Force cleanup processes on a specific port."""
        try:
            import subprocess
            # Find processes using the port
            result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    subprocess.run(['kill', '-9', pid], check=False)
                logger.info(f"Force killed processes on port {port}")
        except Exception as e:
            logger.error(f"Failed to force cleanup port {port}: {e}")

    @staticmethod
    async def _force_cleanup_ports_batch(ports: list[int]):
        """Force cleanup processes on multiple ports efficiently."""
        if not ports:
            return

        try:
            import subprocess
            # Single lsof call for all ports
            port_args = [f':{port}' for port in ports]
            result = subprocess.run(['lsof', '-ti'] + port_args, capture_output=True, text=True)

            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                if pids:
                    # Kill all PIDs in one command
                    subprocess.run(['kill', '-9'] + pids, check=False)
                    logger.info(f"Force killed processes on ports {ports}")
        except Exception as e:
            logger.error(f"Failed to batch cleanup ports {ports}: {e}")
            # Fallback to individual cleanup
            for port in ports:
                await NodeManager._force_cleanup_port(port)

    @staticmethod
    async def broadcast_computation(computation: dict[str, Any]):
        """Broadcast computation to designated heavy nodes, then to light nodes."""
        heavy_node_uids = [computation['heavy_node_1'], computation['heavy_node_2'], computation['heavy_node_3']]
        db = NetworkDatabase()
        message = Message("computation", computation)

        # Send to all heavy nodes first
        for uid in heavy_node_uids:
            node = await db.get_node(uid)
            if node:
                try:
                    await MessageProtocol.send_message(node['port'], message)
                    logger.info(f"Sent computation to heavy node {uid}")
                except Exception as e:
                    logger.error(f"Failed to send computation to {uid}: {e}")

        # Wait for heavy nodes to initialize and confirm readiness
        await asyncio.sleep(2.0)  # Give time for initialization and confirmation

        # Now broadcast to light nodes
        light_nodes = await db.get_nodes_by_type("light")
        if light_nodes:
            light_ports = [node['port'] for node in light_nodes]
            await MessageProtocol.broadcast(light_ports, message)
            logger.info(f"Broadcasted computation {computation['comp_id']} to {len(light_nodes)} light nodes")