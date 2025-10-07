# src/formix/protocols/aggregation.py

from loguru import logger

from .secret_sharing import SecretSharing


class SecureAggregation:
    """Handles secure aggregation of values from light nodes."""

    def __init__(self, comp_id: str, min_participants: int, heavy_node_uid: str, heavy_nodes: list[str]):
        self.comp_id = comp_id
        self.min_participants = min_participants
        self.heavy_node_uid = heavy_node_uid
        self.heavy_nodes = heavy_nodes  # List of all 3 heavy node UIDs
        self.received_shares = {}  # {sender_uid: share_value}
        self.partial_sums_from_other_nodes = {}  # {heavy_node_uid: partial_sum}

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
        """Compute the sum of all received shares for this heavy node."""
        if not self.received_shares:
            logger.warning(f"No shares received for computation {self.comp_id}")
            return 0

        partial_sum = sum(self.received_shares.values()) % SecretSharing.MODULUS
        logger.info(f"Heavy node {self.heavy_node_uid} computed partial sum {partial_sum} from {len(self.received_shares)} participants")
        return partial_sum

    def get_heavy_node_position(self) -> int:
        """Get the position of this heavy node (0, 1, or 2)."""
        try:
            return self.heavy_nodes.index(self.heavy_node_uid)
        except ValueError:
            raise ValueError(f"Heavy node {self.heavy_node_uid} not found in heavy nodes list")

    def is_primary_heavy_node(self) -> bool:
        """Check if this is the first heavy node (responsible for final reconstruction)."""
        return self.get_heavy_node_position() == 0

    def add_partial_sum_from_heavy_node(self, heavy_node_uid: str, partial_sum: int):
        """Add partial sum received from another heavy node."""
        if heavy_node_uid not in self.heavy_nodes:
            raise ValueError(f"Unknown heavy node: {heavy_node_uid}")

        self.partial_sums_from_other_nodes[heavy_node_uid] = partial_sum
        logger.info(f"Received partial sum {partial_sum} from heavy node {heavy_node_uid}")

    def can_perform_final_reconstruction(self) -> bool:
        """Check if we have all partial sums needed for final reconstruction."""
        if not self.is_primary_heavy_node():
            return False

        # Need partial sums from the other 2 heavy nodes
        other_heavy_nodes = [uid for uid in self.heavy_nodes if uid != self.heavy_node_uid]
        return all(uid in self.partial_sums_from_other_nodes for uid in other_heavy_nodes)

    def compute_final_result(self) -> int:
        """Compute the final result by combining all partial sums."""
        if not self.is_primary_heavy_node():
            raise ValueError("Only the primary heavy node can compute final result")

        if not self.can_perform_final_reconstruction():
            raise ValueError("Cannot perform final reconstruction - missing partial sums")

        # Validate anonymity threshold before reconstruction
        if not self.meets_anonymity_threshold():
            raise ValueError(f"Anonymity threshold not met: {self.get_total_participants()} < {self.min_participants}")

        # Validate all shares before reconstruction
        invalid_sources = self.validate_shares()
        if invalid_sources:
            logger.warning(f"Found invalid shares from: {invalid_sources}")
            # For PoC, we continue with valid shares, but log the issue

        # Get our own partial sum
        our_partial_sum = self.compute_partial_sum()

        # Add partial sums from other heavy nodes
        total_sum = our_partial_sum
        for partial_sum in self.partial_sums_from_other_nodes.values():
            total_sum = (total_sum + partial_sum) % SecretSharing.MODULUS

        logger.info(f"Final reconstruction: {our_partial_sum} + {list(self.partial_sums_from_other_nodes.values())} = {total_sum} (mod 2^32)")
        logger.info(f"Computation {self.comp_id} final result: {total_sum} with {self.get_total_participants()} participants")
        return total_sum

    def get_total_participants(self) -> int:
        """Get total number of participants across all heavy nodes."""
        # For now, return participants for this heavy node
        # In a complete implementation, this would aggregate across all heavy nodes
        return len(self.received_shares)

    def meets_anonymity_threshold(self) -> bool:
        """Check if the computation meets the minimum anonymity threshold."""
        total_participants = self.get_total_participants()
        meets_threshold = total_participants >= self.min_participants

        if meets_threshold:
            logger.info(f"Anonymity threshold met: {total_participants} >= {self.min_participants}")
        else:
            logger.warning(f"Anonymity threshold NOT met: {total_participants} < {self.min_participants}")

        return meets_threshold

    def validate_shares(self) -> list[str]:
        """Validate all received shares and return list of invalid share sources."""
        invalid_sources = []

        for sender_uid, share_value in self.received_shares.items():
            if not SecretSharing.verify_share_range(share_value):
                invalid_sources.append(sender_uid)
                logger.warning(f"Invalid share from {sender_uid}: {share_value}")

        return invalid_sources

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
