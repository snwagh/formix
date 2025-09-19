# src/formix/utils/config.py
import os
import sys
from pathlib import Path

from loguru import logger

# Base directory for all formix data
FORMIX_HOME = Path.home() / ".formix"
NETWORK_DB_PATH = FORMIX_HOME / "network.db"

# Logging configuration
LOG_LEVEL = os.getenv("FORMIX_LOG_LEVEL", "INFO")
LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"

# Network configuration
DEFAULT_PORT_START = 9000
MAX_NODES = 100

# Computation defaults
DEFAULT_MIN_PARTICIPANTS = 1
DEFAULT_DEADLINE_SECONDS = 60

# Secret sharing parameters
MODULUS = 2**32
NUM_SHARES = 3


def setup_logging():
    """Configure loguru logging for CLI - file only."""
    logger.remove()  # Remove default handler

    # Only file logging for CLI
    FORMIX_HOME.mkdir(parents=True, exist_ok=True)
    log_file = FORMIX_HOME / "formix.log"
    logger.add(
        log_file,
        format=LOG_FORMAT,
        level="DEBUG",
        rotation="10 MB",
        retention="1 week",
        compression="zip"
    )


def setup_node_logging(node_uid: str):
    """Configure per-node logging - file AND console for debugging."""
    # Remove existing handlers to avoid duplicates
    logger.remove()

    # Console logging for debugging
    logger.add(
        sys.stderr,
        format=f"<green>{{time:HH:mm:ss}}</green> | <level>{{level: <8}}</level> | <cyan>[{node_uid[:8]}]</cyan> - <level>{{message}}</level>",
        level="INFO"
    )

    # Node-specific file logging
    node_log_file = FORMIX_HOME / "Nodes" / node_uid / "logs.log"
    node_log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        node_log_file,
        format=f"{{time:YYYY-MM-DD HH:mm:ss}} | {{level: <8}} | [{node_uid}] - {{message}}",
        level="DEBUG",
        rotation="5 MB",
        retention="1 week",
        compression="zip"
    )

