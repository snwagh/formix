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
        """Compute the sum of all received shares for Formix."""
        if not self.can_aggregate():
            raise ValueError(f"Insufficient participants: {len(self.received_shares)} < {self.min_participants}")

        # With the simple sharing approach, each share equals the original value
        # So the sum of all received shares equals the sum of all original values
        share_values = list(self.received_shares.values())
        total_sum = sum(share_values)
        
        logger.info(f"Computed total sum: {total_sum} from {len(share_values)} shares")
        return total_sum

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

        # Compute average
        average = total_sum / num_participants

        logger.info(f"Computed average: {average} from sum {total_sum} / {num_participants}")
        return average
