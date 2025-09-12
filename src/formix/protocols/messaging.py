# src/formix/protocols/messaging.py
import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC
from typing import Any

import aiohttp
from loguru import logger

from ..utils.async_helpers import gather_with_concurrency


@dataclass
class Message:
    """Message structure for inter-node communication."""
    type: str  # computation, share, aggregate_request, etc.
    payload: dict[str, Any]
    sender_uid: str | None = None
    timestamp: str | None = None

    def __post_init__(self):
        if not self.timestamp:
            from datetime import datetime
            self.timestamp = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Message':
        """Create message from dictionary."""
        return cls(**data)


class MessageProtocol:
    """Handles message sending and receiving between nodes."""

    # Connection settings
    TIMEOUT = aiohttp.ClientTimeout(total=30)
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0

    @staticmethod
    async def send_message(
        target_port: int,
        message: Message,
        timeout: float | None = None
    ) -> dict[str, Any]:
        """
        Send a message to a specific node.
        
        Args:
            target_port: Port of the target node
            message: Message to send
            timeout: Optional custom timeout
            
        Returns:
            Response from the target node
        """
        url = f"http://localhost:{target_port}/message"

        # Use custom timeout if provided
        client_timeout = aiohttp.ClientTimeout(total=timeout) if timeout else MessageProtocol.TIMEOUT

        # Retry logic
        for attempt in range(MessageProtocol.MAX_RETRIES):
            try:
                async with aiohttp.ClientSession(timeout=client_timeout) as session:
                    async with session.post(url, json=message.to_dict()) as response:
                        if response.status == 200:
                            result = await response.json()
                            logger.debug(f"Successfully sent message to port {target_port}")
                            return result
                        else:
                            error_text = await response.text()
                            logger.warning(f"Error response from {target_port}: {response.status} - {error_text}")

            except aiohttp.ClientConnectorError:
                logger.warning(f"Failed to connect to port {target_port} (attempt {attempt + 1})")
            except TimeoutError:
                logger.warning(f"Timeout sending message to port {target_port} (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"Unexpected error sending to port {target_port}: {e}")

            # Wait before retry
            if attempt < MessageProtocol.MAX_RETRIES - 1:
                await asyncio.sleep(MessageProtocol.RETRY_DELAY * (attempt + 1))

        # All retries failed
        raise ConnectionError(f"Failed to send message to port {target_port} after {MessageProtocol.MAX_RETRIES} attempts")

    @staticmethod
    async def broadcast(
        ports: list[int],
        message: Message,
        max_concurrent: int = 10
    ) -> list[dict[str, Any]]:
        """
        Broadcast a message to multiple nodes.
        
        Args:
            ports: List of target node ports
            message: Message to broadcast
            max_concurrent: Maximum concurrent connections
            
        Returns:
            List of responses (or exceptions) from target nodes
        """
        if not ports:
            logger.warning("No ports provided for broadcast")
            return []

        logger.info(f"Broadcasting message type '{message.type}' to {len(ports)} nodes")

        # Create tasks for sending to each port
        tasks = [
            MessageProtocol.send_message(port, message)
            for port in ports
        ]

        # Execute with limited concurrency
        results = await gather_with_concurrency(max_concurrent, tasks)

        # Count successes and failures
        successes = sum(1 for r in results if not isinstance(r, Exception))
        failures = len(results) - successes

        logger.info(f"Broadcast complete: {successes} successes, {failures} failures")

        return results

    @staticmethod
    async def request_response(
        target_port: int,
        request: Message,
        response_timeout: float = 10.0
    ) -> dict[str, Any] | None:
        """
        Send a request and wait for a specific response.
        
        Args:
            target_port: Port of the target node
            request: Request message
            response_timeout: Timeout for response
            
        Returns:
            Response data or None if timeout
        """
        try:
            response = await MessageProtocol.send_message(
                target_port,
                request,
                timeout=response_timeout
            )
            return response
        except Exception as e:
            logger.error(f"Request-response failed: {e}")
            return None


class MessageValidator:
    """Validates messages according to protocol rules."""

    # Required fields for each message type
    REQUIRED_FIELDS = {
        "computation": ["comp_id", "proposer_uid", "heavy_node_1", "heavy_node_2",
                       "heavy_node_3", "computation_prompt", "response_schema",
                       "deadline", "min_participants"],
        "share": ["comp_id", "sender_uid", "share_value"],
        "aggregate_request": ["comp_id", "sender_uid", "partial_sum", "participant_count"],
        "aggregate_response": ["comp_id", "sender_uid", "partial_sum", "status"]
    }

    @staticmethod
    def validate_message(message: Message) -> bool:
        """
        Validate a message structure.
        
        Args:
            message: Message to validate
            
        Returns:
            True if valid, raises ValueError if invalid
        """
        # Check message type
        if message.type not in MessageValidator.REQUIRED_FIELDS:
            raise ValueError(f"Unknown message type: {message.type}")

        # Check required fields
        required = MessageValidator.REQUIRED_FIELDS[message.type]
        missing = [field for field in required if field not in message.payload]

        if missing:
            raise ValueError(f"Missing required fields for {message.type}: {missing}")

        # Type-specific validation
        if message.type == "share":
            share_value = message.payload.get("share_value")
            if not isinstance(share_value, int) or share_value < 0:
                raise ValueError("Invalid share value")

        elif message.type == "computation":
            # Validate JSON schema
            schema = message.payload.get("response_schema")
            try:
                parsed_schema = json.loads(schema) if isinstance(schema, str) else schema
                if parsed_schema.get("type") != "number":
                    raise ValueError("Response schema must be for a number type")
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON in response schema")

        return True


class MessageQueue:
    """Simple message queue for async processing."""

    def __init__(self, max_size: int = 1000):
        self.queue = asyncio.Queue(maxsize=max_size)
        self.processors = {}
        self.running = False

    async def put(self, message: Message):
        """Add a message to the queue."""
        await self.queue.put(message)

    async def get(self) -> Message:
        """Get a message from the queue."""
        return await self.queue.get()

    def register_processor(self, message_type: str, processor):
        """Register a processor function for a message type."""
        self.processors[message_type] = processor

    async def start_processing(self):
        """Start processing messages from the queue."""
        self.running = True
        logger.info("Message queue processing started")

        while self.running:
            try:
                # Wait for message with timeout to allow checking running status
                message = await asyncio.wait_for(self.queue.get(), timeout=1.0)

                # Find processor for message type
                processor = self.processors.get(message.type)
                if processor:
                    try:
                        await processor(message)
                    except Exception as e:
                        logger.error(f"Error processing message type {message.type}: {e}")
                else:
                    logger.warning(f"No processor registered for message type: {message.type}")

            except TimeoutError:
                continue  # Continue the loop to check self.running
            except asyncio.CancelledError:
                logger.info("Message processing cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in message processing: {e}")
                if not self.running:
                    break

    def stop_processing(self):
        """Stop processing messages."""
        self.running = False
        logger.info("Message queue processing stopped")
