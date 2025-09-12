# src/formix/db/database.py
from typing import Any
import asyncio
import fcntl
import random
from pathlib import Path

import aiosqlite
from loguru import logger

from ..utils.config import FORMIX_HOME, NETWORK_DB_PATH


class DatabaseConnectionPool:
    """Connection pool for SQLite database to handle concurrent access."""
    
    _instances = {}  # Singleton instances per database path
    _locks = {}      # File locks per database path for multi-process safety
    
    def __new__(cls, db_path: str, max_connections: int = 10):
        """Ensure singleton instance per database path."""
        if db_path not in cls._instances:
            # Ensure the directory exists before creating lock file
            lock_file_path = f"{db_path}.lock"
            lock_dir = Path(lock_file_path).parent
            lock_dir.mkdir(parents=True, exist_ok=True)
            
            cls._instances[db_path] = super().__new__(cls)
            cls._locks[db_path] = open(lock_file_path, 'w')
            cls._instances[db_path]._initialized = False
        return cls._instances[db_path]
    
    def __init__(self, db_path: str, max_connections: int = 10):
        if hasattr(self, '_initialized') and self._initialized:
            return  # Already initialized
            
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool: list[aiosqlite.Connection] = []
        self._available: list[aiosqlite.Connection] = []
        self._lock = asyncio.Lock()
        self._file_lock = self._locks[db_path]  # Reference to the file lock
        self._initialized = False
    
    async def initialize(self):
        """Initialize the connection pool."""
        if self._initialized:
            return
            
        async with self._lock:
            if self._initialized:
                return
                
            # Create initial connections
            for _ in range(self.max_connections):
                conn = await aiosqlite.connect(self.db_path)
                # Enable WAL mode for better concurrency
                await conn.execute("PRAGMA journal_mode = WAL")
                await conn.execute("PRAGMA synchronous = NORMAL")
                await conn.execute("PRAGMA cache_size = 1000000")  # 1GB cache
                await conn.execute("PRAGMA temp_store = memory")
                await conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
                await conn.execute("PRAGMA foreign_keys = ON")
                await conn.execute("PRAGMA busy_timeout = 60000")  # 60 second timeout
                await conn.execute("PRAGMA wal_autocheckpoint = 1000")  # More frequent checkpoints
                await conn.commit()
                
                self._pool.append(conn)
                self._available.append(conn)
            
            self._initialized = True
            logger.info(f"Database connection pool initialized with {self.max_connections} connections")
    
    async def acquire(self) -> aiosqlite.Connection:
        """Acquire a connection from the pool."""
        await self.initialize()
        
        while True:
            async with self._lock:
                if self._available:
                    conn = self._available.pop()
                    return conn
            
            # Wait a bit before retrying
            await asyncio.sleep(0.01)
    
    async def _acquire_with_file_lock(self) -> aiosqlite.Connection:
        """Acquire a connection with file locking for multi-process safety."""
        # Acquire file lock (blocking)
        fcntl.flock(self._file_lock.fileno(), fcntl.LOCK_EX)
        
        try:
            conn = await self.acquire()
            # Store the connection so we can release the file lock later
            conn._has_file_lock = True
            return conn
        except Exception:
            # Release file lock if connection acquisition fails
            fcntl.flock(self._file_lock.fileno(), fcntl.LOCK_UN)
            raise
    
    async def _release_with_file_lock(self, conn: aiosqlite.Connection):
        """Release a connection and file lock."""
        try:
            await self.release(conn)
        finally:
            if hasattr(conn, '_has_file_lock'):
                fcntl.flock(self._file_lock.fileno(), fcntl.LOCK_UN)
    
    async def release(self, conn: aiosqlite.Connection):
        """Release a connection back to the pool."""
        async with self._lock:
            if conn in self._pool:
                self._available.append(conn)
    
    async def close_all(self):
        """Close all connections in the pool."""
        async with self._lock:
            for conn in self._pool:
                await conn.close()
            self._pool.clear()
            self._available.clear()
            self._initialized = False


async def retry_db_operation(operation, max_retries=10, base_delay=0.05):
    """Retry a database operation with exponential backoff and file locking."""
    for attempt in range(max_retries):
        try:
            # For database operations, we need to use file locking
            if hasattr(operation, '__self__') and hasattr(operation.__self__, '_acquire_with_file_lock'):
                # This is a method of a DatabaseConnectionPool, use file locking
                pool = operation.__self__
                conn = await pool._acquire_with_file_lock()
                try:
                    result = await operation()
                    return result
                finally:
                    await pool._release_with_file_lock(conn)
            else:
                # Regular operation without file locking
                return await operation()
        except (aiosqlite.OperationalError, aiosqlite.DatabaseError) as e:
            if "database is locked" in str(e).lower() or "busy" in str(e).lower():
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.05)
                    logger.debug(f"Database operation failed (attempt {attempt + 1}), retrying in {delay:.2f}s: {e}")
                    await asyncio.sleep(delay)
                    continue
            # Re-raise if it's not a locking issue or we've exhausted retries
            raise e
    raise Exception(f"Database operation failed after {max_retries} retries")


class NetworkDatabase:
    """Manages the central network database."""

    def __init__(self):
        self.db_path = NETWORK_DB_PATH
        self._pool = DatabaseConnectionPool(str(self.db_path))
        self._ensure_db_dir()

    def _ensure_db_dir(self):
        """Ensure the database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Initialize the network database with required tables."""
        await self._pool.initialize()
        
        async def _init_tables():
            conn = await self._pool.acquire()
            try:
                # Enable WAL mode for better concurrency
                await conn.execute("PRAGMA journal_mode = WAL")
                await conn.execute("PRAGMA synchronous = NORMAL")
                await conn.execute("PRAGMA cache_size = 1000000")  # 1GB cache
                await conn.execute("PRAGMA temp_store = memory")
                await conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
                await conn.execute("PRAGMA busy_timeout = 60000")  # 60 second timeout
                await conn.execute("PRAGMA wal_autocheckpoint = 1000")  # More frequent checkpoints
                await conn.execute("PRAGMA foreign_keys = ON")

                # Create users table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        uid TEXT PRIMARY KEY,
                        node_type TEXT CHECK(node_type IN ('heavy', 'light')),
                        port INTEGER UNIQUE,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create computations table
                await conn.execute("""
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

                await conn.commit()
                logger.info("Network database initialized with concurrency optimizations")
            finally:
                await self._pool.release(conn)
        
        await retry_db_operation(_init_tables)

    async def add_node(self, uid: str, node_type: str, port: int) -> bool:
        """Add a new node to the network."""
        async def _add_node():
            conn = await self._pool.acquire()
            try:
                await conn.execute(
                    "INSERT INTO users (uid, node_type, port) VALUES (?, ?, ?)",
                    (uid, node_type, port)
                )
                await conn.commit()
                logger.info(f"Added {node_type} node {uid} on port {port}")
                return True
            except aiosqlite.IntegrityError:
                logger.error(f"Node {uid} already exists or port {port} is taken")
                return False
            finally:
                await self._pool.release(conn)
        
        return await retry_db_operation(_add_node)

    async def remove_node(self, uid: str) -> bool:
        """Remove a node from the network."""
        async def _remove_node():
            conn = await self._pool.acquire()
            try:
                cursor = await conn.execute(
                    "DELETE FROM users WHERE uid = ?", (uid,)
                )
                await conn.commit()
                return cursor.rowcount > 0
            finally:
                await self._pool.release(conn)
        
        return await retry_db_operation(_remove_node)

    async def get_node(self, uid: str) -> dict[str, Any] | None:
        """Get node information by UID."""
        async def _get_node():
            conn = await self._pool.acquire()
            try:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE uid = ?", (uid,)
                )
                row = await cursor.fetchone()
                result = dict(row) if row else None
                logger.debug(f"Database lookup for node {uid}: {'found' if result else 'not found'}")
                return result
            finally:
                await self._pool.release(conn)
        
        return await retry_db_operation(_get_node)

    async def get_all_nodes(self) -> list[dict[str, Any]]:
        """Get all nodes in the network."""
        async def _get_all_nodes():
            conn = await self._pool.acquire()
            try:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT * FROM users ORDER BY created_at"
                )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
            finally:
                await self._pool.release(conn)
        
        return await retry_db_operation(_get_all_nodes)

    async def get_nodes_by_type(self, node_type: str) -> list[dict[str, Any]]:
        """Get all nodes of a specific type."""
        async def _get_nodes_by_type():
            conn = await self._pool.acquire()
            try:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT * FROM users WHERE node_type = ? AND status = 'active'",
                    (node_type,)
                )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
            finally:
                await self._pool.release(conn)
        
        return await retry_db_operation(_get_nodes_by_type)

    async def get_next_available_port(self) -> int:
        """Get the next available port for a new node."""
        async def _get_next_port():
            conn = await self._pool.acquire()
            try:
                cursor = await conn.execute(
                    "SELECT MAX(port) as max_port FROM users"
                )
                row = await cursor.fetchone()
                max_port = row[0] if row[0] else 7999
                return max_port + 1
            finally:
                await self._pool.release(conn)
        
        return await retry_db_operation(_get_next_port)

    async def add_computation(self, computation: dict[str, Any]) -> bool:
        """Add a new computation to the network."""
        async def _add_computation():
            conn = await self._pool.acquire()
            try:
                await conn.execute("""
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
                await conn.commit()
                logger.info(f"Added computation {computation['comp_id']}")
                return True
            except Exception as e:
                logger.error(f"Failed to add computation: {e}")
                return False
            finally:
                await self._pool.release(conn)
        
        return await retry_db_operation(_add_computation)

    async def update_computation_result(
        self, comp_id: str, result: float, participants_count: int
    ):
        """Update computation with final result."""
        async def _update_result():
            conn = await self._pool.acquire()
            try:
                await conn.execute("""
                    UPDATE computations 
                    SET status = 'completed', result = ?, participants_count = ?,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE comp_id = ?
                """, (result, participants_count, comp_id))
                await conn.commit()
            finally:
                await self._pool.release(conn)
        
        await retry_db_operation(_update_result)

    async def get_computation_result(self, comp_id: str) -> dict[str, Any] | None:
        """Get computation result by ID."""
        async def _get_result():
            conn = await self._pool.acquire()
            try:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute(
                    "SELECT * FROM computations WHERE comp_id = ?",
                    (comp_id,)
                )
                row = await cursor.fetchone()
                return dict(row) if row else None
            finally:
                await self._pool.release(conn)
        
        return await retry_db_operation(_get_result)


class NodeDatabase:
    """Manages individual node databases."""

    def __init__(self, uid: str):
        self.uid = uid
        self.db_path = FORMIX_HOME / "Nodes" / uid / "node.db"
        self._pool = DatabaseConnectionPool(str(self.db_path), max_connections=3)  # Fewer connections for node DBs
        self._ensure_db_dir()

    def _ensure_db_dir(self):
        """Ensure the node database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize_heavy_node(self):
        """Initialize database for a heavy node."""
        await self._pool.initialize()
        
        async def _init_tables():
            conn = await self._pool.acquire()
            try:
                # Table for received shares
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS received_shares (
                        comp_id TEXT,
                        sender_uid TEXT,
                        share_value INTEGER,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (comp_id, sender_uid)
                    )
                """)

                # Common computation log
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS computation_log (
                        comp_id TEXT,
                        action TEXT,
                        details JSON,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                await conn.commit()
                logger.info(f"Initialized heavy node database for {self.uid}")
            finally:
                await self._pool.release(conn)
        
        await retry_db_operation(_init_tables)

    async def initialize_light_node(self):
        """Initialize database for a light node."""
        await self._pool.initialize()
        
        async def _init_tables():
            conn = await self._pool.acquire()
            try:
                # Table for computation responses
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS computation_responses (
                        comp_id TEXT PRIMARY KEY,
                        response_value INTEGER,
                        responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Common computation log
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS computation_log (
                        comp_id TEXT,
                        action TEXT,
                        details JSON,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                await conn.commit()
                logger.info(f"Initialized light node database for {self.uid}")
            finally:
                await self._pool.release(conn)
        
        await retry_db_operation(_init_tables)

    async def add_share(self, comp_id: str, sender_uid: str, share_value: int):
        """Add a received share (for heavy nodes)."""
        async def _add_share():
            conn = await self._pool.acquire()
            try:
                await conn.execute("""
                    INSERT OR REPLACE INTO received_shares 
                    (comp_id, sender_uid, share_value) VALUES (?, ?, ?)
                """, (comp_id, sender_uid, share_value))
                await conn.commit()
            finally:
                await self._pool.release(conn)
        
        await retry_db_operation(_add_share)

    async def get_shares_for_computation(self, comp_id: str) -> list[dict[str, Any]]:
        """Get all shares for a computation."""
        async def _get_shares():
            conn = await self._pool.acquire()
            try:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute("""
                    SELECT * FROM received_shares 
                    WHERE comp_id = ? 
                    ORDER BY timestamp
                """, (comp_id,))
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
            finally:
                await self._pool.release(conn)
        
        return await retry_db_operation(_get_shares)

    async def add_response(self, comp_id: str, response_value: int):
        """Add a computation response (for light nodes)."""
        async def _add_response():
            conn = await self._pool.acquire()
            try:
                try:
                    await conn.execute("""
                        INSERT INTO computation_responses 
                        (comp_id, response_value) VALUES (?, ?)
                    """, (comp_id, response_value))
                    await conn.commit()
                except aiosqlite.IntegrityError:
                    # Response already exists, update it
                    await conn.execute("""
                        UPDATE computation_responses 
                        SET response_value = ?, responded_at = CURRENT_TIMESTAMP
                        WHERE comp_id = ?
                    """, (response_value, comp_id))
                    await conn.commit()
                    logger.debug(f"Updated existing response for computation {comp_id}")
            finally:
                await self._pool.release(conn)
        
        await retry_db_operation(_add_response)

    async def log_action(self, comp_id: str, action: str, details: dict[str, Any]):
        """Log a computation-related action."""
        import json
        
        async def _log_action():
            conn = await self._pool.acquire()
            try:
                await conn.execute("""
                    INSERT INTO computation_log 
                    (comp_id, action, details) VALUES (?, ?, ?)
                """, (comp_id, action, json.dumps(details)))
                await conn.commit()
            finally:
                await self._pool.release(conn)
        
        await retry_db_operation(_log_action)

    def cleanup(self):
        """Remove the node's database directory."""
        import shutil
        if self.db_path.parent.exists():
            shutil.rmtree(self.db_path.parent)
            logger.info(f"Cleaned up database for node {self.uid}")
