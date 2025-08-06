# src/formix/__init__.py
"""
Formix - Private Map Secure Reduce

A privacy-preserving distributed computation network.
"""

__version__ = "0.1.0"
__author__ = "Your Name"

from .core.node import HeavyNode, LightNode, NodeType
from .db.database import NetworkDatabase, NodeDatabase
from .protocols.secret_sharing import SecretSharing

__all__ = [
    "HeavyNode",
    "LightNode",
    "NetworkDatabase",
    "NodeDatabase",
    "NodeType",
    "SecretSharing",
]


