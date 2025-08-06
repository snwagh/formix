# src/formix/db/database.py
from typing import Any

import aiosqlite
from loguru import logger

from ..utils.config import FORMIX_HOME, NETWORK_DB_PATH


class NetworkDatabase:
    """Manages the central network database."""

    def __init__(self):
        self.db_path = NETWORK_DB_PATH
        self._ensure_db_dir()

    def _ensure_db_dir(self):
        """Ensure the database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Initialize the network database with required tables."""
        async with aiosqlite.connect(self.db_path) as db:
            # Enable foreign keys
            await db.execute("PRAGMA foreign_keys = ON")

            # Create users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uid TEXT PRIMARY KEY,
                    node_type TEXT CHECK(node_type IN ('heavy', 'light')),
                    port INTEGER UNIQUE,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create computations table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS computations (
                    comp_id TEXT PRIMARY KEY,
                    proposer_uid TEXT,
                    heavy_node_1 TEXT,
                    heavy_node_2 TEXT,
                    heavy_node_3 TEXT,
                    computation_prompt TEXT,
                    response_schema JSON,
                    deadline TIMESTAMP,
                    min_participants INTEGER,
                    status TEXT DEFAULT 'pending',
                    result REAL,
                    participants_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (proposer_uid) REFERENCES users(uid),
                    FOREIGN KEY (heavy_node_1) REFERENCES users(uid),
                    FOREIGN KEY (heavy_node_2) REFERENCES users(uid),
                    FOREIGN KEY (heavy_node_3) REFERENCES users(uid)
                )
            """)

            await db.commit()
            logger.info("Network database initialized")

    async def add_node(self, uid: str, node_type: str, port: int) -> bool:
        """Add a new node to the network."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO users (uid, node_type, port) VALUES (?, ?, ?)",
                    (uid, node_type, port)
                )
                await db.commit()
                logger.info(f"Added {node_type} node {uid} on port {port}")
                return True
        except aiosqlite.IntegrityError:
            logger.error(f"Node {uid} already exists or port {port} is taken")
            return False

    async def remove_node(self, uid: str) -> bool:
        """Remove a node from the network."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM users WHERE uid = ?", (uid,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_node(self, uid: str) -> dict[str, Any] | None:
        """Get node information by UID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE uid = ?", (uid,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_all_nodes(self) -> list[dict[str, Any]]:
        """Get all nodes in the network."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users ORDER BY created_at"
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_nodes_by_type(self, node_type: str) -> list[dict[str, Any]]:
        """Get all nodes of a specific type."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE node_type = ? AND status = 'active'",
                (node_type,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_next_available_port(self) -> int:
        """Get the next available port for a new node."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT MAX(port) as max_port FROM users"
            )
            row = await cursor.fetchone()
            max_port = row[0] if row[0] else 7999
            return max_port + 1

    async def add_computation(self, computation: dict[str, Any]) -> bool:
        """Add a new computation to the network."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO computations (
                        comp_id, proposer_uid, heavy_node_1, heavy_node_2, 
                        heavy_node_3, computation_prompt, response_schema, 
                        deadline, min_participants
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    computation['comp_id'],
                    computation['proposer_uid'],
                    computation['heavy_node_1'],
                    computation['heavy_node_2'],
                    computation['heavy_node_3'],
                    computation['computation_prompt'],
                    computation['response_schema'],
                    computation['deadline'],
                    computation['min_participants']
                ))
                await db.commit()
                logger.info(f"Added computation {computation['comp_id']}")
                return True
        except Exception as e:
            logger.error(f"Failed to add computation: {e}")
            return False

    async def update_computation_result(
        self, comp_id: str, result: float, participants_count: int
    ):
        """Update computation with final result."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE computations 
                SET status = 'completed', result = ?, participants_count = ?,
                    completed_at = CURRENT_TIMESTAMP
                WHERE comp_id = ?
            """, (result, participants_count, comp_id))
            await db.commit()


class NodeDatabase:
    """Manages individual node databases."""

    def __init__(self, uid: str):
        self.uid = uid
        self.db_path = FORMIX_HOME / "Nodes" / uid / "node.db"
        self._ensure_db_dir()

    def _ensure_db_dir(self):
        """Ensure the node database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize_heavy_node(self):
        """Initialize database for a heavy node."""
        async with aiosqlite.connect(self.db_path) as db:
            # Table for received shares
            await db.execute("""
                CREATE TABLE IF NOT EXISTS received_shares (
                    comp_id TEXT,
                    sender_uid TEXT,
                    share_value INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (comp_id, sender_uid)
                )
            """)

            # Common computation log
            await db.execute("""
                CREATE TABLE IF NOT EXISTS computation_log (
                    comp_id TEXT,
                    action TEXT,
                    details JSON,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.commit()
            logger.info(f"Initialized heavy node database for {self.uid}")

    async def initialize_light_node(self):
        """Initialize database for a light node."""
        async with aiosqlite.connect(self.db_path) as db:
            # Table for computation responses
            await db.execute("""
                CREATE TABLE IF NOT EXISTS computation_responses (
                    comp_id TEXT PRIMARY KEY,
                    response_value INTEGER,
                    responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Common computation log
            await db.execute("""
                CREATE TABLE IF NOT EXISTS computation_log (
                    comp_id TEXT,
                    action TEXT,
                    details JSON,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.commit()
            logger.info(f"Initialized light node database for {self.uid}")

    async def add_share(self, comp_id: str, sender_uid: str, share_value: int):
        """Add a received share (for heavy nodes)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO received_shares 
                (comp_id, sender_uid, share_value) VALUES (?, ?, ?)
            """, (comp_id, sender_uid, share_value))
            await db.commit()

    async def get_shares_for_computation(self, comp_id: str) -> list[dict[str, Any]]:
        """Get all shares for a computation."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM received_shares 
                WHERE comp_id = ? 
                ORDER BY timestamp
            """, (comp_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def add_response(self, comp_id: str, response_value: int):
        """Add a computation response (for light nodes)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO computation_responses 
                (comp_id, response_value) VALUES (?, ?)
            """, (comp_id, response_value))
            await db.commit()

    async def log_action(self, comp_id: str, action: str, details: dict[str, Any]):
        """Log a computation-related action."""
        import json
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO computation_log 
                (comp_id, action, details) VALUES (?, ?, ?)
            """, (comp_id, action, json.dumps(details)))
            await db.commit()

    def cleanup(self):
        """Remove the node's database directory."""
        import shutil
        if self.db_path.parent.exists():
            shutil.rmtree(self.db_path.parent)
            logger.info(f"Cleaned up database for node {self.uid}")
