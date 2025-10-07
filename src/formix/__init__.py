# src/formix/__init__.py
"""
Formix - Private Map Secure Reduce

A privacy-preserving distributed computation network.
"""

__version__ = "0.1.0"
__author__ = "Your Name"

from .core.node import HeavyNode, LightNode
from .core.network import FormixNetwork, quick_network, quick_computation
from .db.database import NetworkDatabase, NodeDatabase
from .protocols.secret_sharing import SecretSharing

__all__ = [
    # Core components
    "HeavyNode",
    "LightNode",
    "NetworkDatabase",
    "NodeDatabase",
    "SecretSharing",
    # Main network interface
    "FormixNetwork",
    "quick_network",
    "quick_computation",
]


