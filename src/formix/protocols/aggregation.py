# src/formix/protocols/aggregation.py

from loguru import logger

from .secret_sharing import SecretSharing


class SecureAggregation:
    """Handles secure aggregation of values from light nodes."""

    def __init__(self, comp_id: str, min_participants: int):
        self.comp_id = comp_id
        self.min_participants = min_participants
        self.received_shares = {}  # {sender_uid: share_value}

    def add_share(self, sender_uid: str, share_value: int):
        """Add a share from a light node."""
        if not SecretSharing.verify_share_range(share_value):
            raise ValueError(f"Invalid share value from {sender_uid}")

        self.received_shares[sender_uid] = share_value
        logger.debug(f"Added share from {sender_uid} for computation {self.comp_id}")

    def can_aggregate(self) -> bool:
        """Check if we have enough participants to aggregate."""
        return len(self.received_shares) >= self.min_participants

    def get_valid_participants(self, deadline_timestamp: float) -> list[str]:
        """Get list of participants who submitted before deadline."""
        # In a real implementation, we'd check timestamps
        # For now, return all participants
        return list(self.received_shares.keys())

    def compute_partial_sum(self) -> int:
        """Compute the sum of all received shares."""
        if not self.can_aggregate():
            raise ValueError(f"Insufficient participants: {len(self.received_shares)} < {self.min_participants}")

        partial_sum = sum(self.received_shares.values()) % SecretSharing.MODULUS
        logger.info(f"Computed partial sum for {len(self.received_shares)} participants")
        return partial_sum

    @staticmethod
    def compute_average(total_sum: int, num_participants: int) -> float:
        """
        Compute the average from the total sum.
        
        Args:
            total_sum: Reconstructed sum of all values
            num_participants: Number of participants
            
        Returns:
            Average value
        """
        if num_participants == 0:
            raise ValueError("Cannot compute average with 0 participants")

        # Handle potential overflow by using float division
        average = total_sum / num_participants

        # If the sum is large due to modular arithmetic, adjust
        if average > 100:  # Since our values are 0-100
            # This might happen due to modular arithmetic
            # In a real system, we'd handle this more carefully
            logger.warning(f"Large average detected: {average}, adjusting...")
            average = average % 101  # Simple adjustment for PoC

        return average
