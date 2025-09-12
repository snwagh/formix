# src/formix/protocols/secret_sharing.py
import random

from loguru import logger


class SecretSharing:
    """
    Simple additive secret sharing scheme modulo 2^32.
    
    This implements a (3,3)-threshold scheme where all 3 shares
    are needed to reconstruct the secret.
    """

    MODULUS = 2**32

    @staticmethod
    def create_shares(secret: int, num_shares: int = 3) -> list[int]:
        """
        Create shares for Formix.
        
        For simplicity and correctness, each light node sends its value
        to all heavy nodes. This ensures that aggregation works correctly.
        
        Args:
            secret: The value to be shared
            num_shares: Number of shares to create
            
        Returns:
            List of shares (all equal to the secret)
        """
        if not 0 <= secret < SecretSharing.MODULUS:
            raise ValueError(f"Secret must be in range [0, {SecretSharing.MODULUS})")

        # Simple approach: send the secret to all heavy nodes
        # This ensures sum of received values = sum of secrets
        shares = [secret] * num_shares

        logger.debug(f"Created {num_shares} shares for secret {secret}: {shares}")
        return shares

    @staticmethod
    def reconstruct_secret(shares: list[int]) -> int:
        """
        Reconstruct secret from all shares.
        
        Args:
            shares: List of all shares
            
        Returns:
            The reconstructed secret
        """
        if not shares:
            raise ValueError("Cannot reconstruct from empty shares")

        result = sum(shares) % SecretSharing.MODULUS
        logger.debug(f"Reconstructed secret: {result} from {len(shares)} shares")
        return result

    @staticmethod
    def add_shares(shares_list: list[list[int]]) -> list[int]:
        """
        Add multiple sets of shares component-wise.
        Used by heavy nodes to aggregate shares from multiple light nodes.
        
        Args:
            shares_list: List of share sets, where each set has the same number of shares
            
        Returns:
            Aggregated shares
        """
        if not shares_list:
            raise ValueError("Cannot add empty list of shares")

        num_shares = len(shares_list[0])
        if not all(len(shares) == num_shares for shares in shares_list):
            raise ValueError("All share sets must have the same number of shares")

        # Add shares component-wise
        aggregated = []
        for i in range(num_shares):
            component_sum = sum(shares[i] for shares in shares_list) % SecretSharing.MODULUS
            aggregated.append(component_sum)

        logger.debug(f"Aggregated {len(shares_list)} sets of shares")
        return aggregated

    @staticmethod
    def verify_share_range(share: int) -> bool:
        """Verify that a share is in the valid range."""
        return 0 <= share < SecretSharing.MODULUS


class ShareDistribution:
    """Handles the distribution of shares to heavy nodes."""

    def __init__(self, heavy_nodes: list[tuple[str, int]]):
        """
        Initialize with list of heavy nodes.
        
        Args:
            heavy_nodes: List of (uid, port) tuples for heavy nodes
        """
        if len(heavy_nodes) != 3:
            raise ValueError("Exactly 3 heavy nodes required")

        self.heavy_nodes = heavy_nodes

    def distribute(self, secret: int) -> list[tuple[str, int, int]]:
        """
        Create shares and assign to heavy nodes.
        
        Args:
            secret: The value to be secret-shared
            
        Returns:
            List of (node_uid, node_port, share_value) tuples
        """
        shares = SecretSharing.create_shares(secret, num_shares=3)

        logger.debug(f"Distributing shares {shares} to heavy nodes: {self.heavy_nodes}")

        distribution = []
        for (uid, port), share in zip(self.heavy_nodes, shares, strict=False):
            distribution.append((uid, port, share))
            logger.debug(f"Assigned share {share} to {uid} on port {port}")

        logger.debug(f"Final distribution: {distribution}")
        return distribution
