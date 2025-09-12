#!/usr/bin/env python3
"""
Simple test to verify Formix cryptographic functionality.
"""
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from formix.protocols.secret_sharing import SecretSharing, ShareDistribution

def test_secret_sharing():
    """Test the secret sharing functionality."""
    print("=== Secret Sharing Test ===")

    # Test basic secret sharing
    secret = 42
    shares = SecretSharing.create_shares(secret, num_shares=3)
    print(f"✓ Created shares for secret {secret}: {shares}")

    # Test reconstruction
    reconstructed = SecretSharing.reconstruct_secret(shares)
    print(f"✓ Reconstructed secret: {reconstructed}")

    if reconstructed == secret:
        print("✅ Secret sharing works correctly!")
    else:
        print(f"❌ Secret sharing failed: expected {secret}, got {reconstructed}")
        return False

    # Test share addition (for aggregation)
    secret2 = 58
    shares2 = SecretSharing.create_shares(secret2, num_shares=3)
    print(f"✓ Created shares for secret {secret2}: {shares2}")

    # Add corresponding shares
    added_shares = SecretSharing.add_shares([shares, shares2])
    print(f"✓ Added shares: {added_shares}")

    # Reconstruct the sum
    total = SecretSharing.reconstruct_secret(added_shares)
    expected_total = secret + secret2
    print(f"✓ Reconstructed total: {total} (expected: {expected_total})")

    if total == expected_total:
        print("✅ Share addition works correctly!")
        return True
    else:
        print(f"❌ Share addition failed: expected {expected_total}, got {total}")
        return False

def test_end_to_end_formix_simulation():
    """Test complete Formix flow simulation."""
    print("\n=== End-to-End Formix Simulation ===")

    # Simulate the exact scenario from the test
    light_values = [82, 60]  # From the test_basic.py output
    heavy_nodes = [
        ("TEST_HEAVY", 9000),
        ("TEST_HEAVY2", 9003),
        ("TEST_HEAVY3", 9004)
    ]

    print(f"✓ Light node values: {light_values}")
    print(f"✓ Heavy nodes: {[uid for uid, _ in heavy_nodes]}")

    # Each light node creates shares and distributes to heavy nodes
    heavy_received = {uid: [] for uid, _ in heavy_nodes}

    for i, value in enumerate(light_values):
        light_uid = f"TEST_LIGHT{i+1}"
        distribution = ShareDistribution(heavy_nodes)
        shares = distribution.distribute(value)

        print(f"✓ {light_uid} (value={value}) distributed shares:")
        for heavy_uid, _, share in shares:
            heavy_received[heavy_uid].append((light_uid, share))
            print(f"  → {heavy_uid}: {share}")

    # Each heavy node sums its received shares
    for heavy_uid, shares in heavy_received.items():
        print(f"\n--- {heavy_uid} ---")
        print(f"✓ Received shares: {shares}")

        if len(shares) == len(light_values):
            share_values = [share for _, share in shares]
            raw_sum = sum(share_values)
            mod_sum = raw_sum % SecretSharing.MODULUS

            expected_sum = sum(light_values)

            print(f"✓ Share values: {share_values}")
            print(f"✓ Raw sum: {raw_sum}")
            print(f"✓ Sum % MODULUS: {mod_sum}")
            print(f"✓ Expected sum: {expected_sum}")

            if mod_sum == expected_sum:
                print(f"✅ {heavy_uid} SUCCESS!")
                return True
            else:
                print(f"❌ {heavy_uid} FAILED!")
                return False
        else:
            print(f"❌ {heavy_uid} received {len(shares)} shares, expected {len(light_values)}")
            return False

    return False

if __name__ == "__main__":
    print("Running cryptographic tests...")
    
    success1 = test_end_to_end_formix_simulation()
    
    if success1:
        print("\n🎉 All tests passed!")
    else:
        print("\n❌ Some tests failed!")
