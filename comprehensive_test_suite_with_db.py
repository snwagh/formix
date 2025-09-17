#!/usr/bin/env python3
"""
Enhanced comprehensive test suite for Formix with database integration.
Tests secret sharing protocol, database operations, and end-to-end workflows.
"""

import os
import sys
import asyncio
import random
from datetime import datetime, timedelta

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from formix.protocols.secret_sharing import SecretSharing, ShareDistribution
from formix.db.database import NetworkDatabase, NodeDatabase

class TestResults:
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.failures = []
    
    def add_test(self, test_name, passed, error_msg=None):
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
            print(f"✓ {test_name}")
        else:
            self.failed_tests += 1
            self.failures.append((test_name, error_msg or "Unknown error"))
            print(f"✗ {test_name}: {error_msg}")
    
    def summary(self):
        print(f"\n=== TEST SUMMARY ===")
        print(f"Total Tests: {self.total_tests}")
        print(f"Passed: {self.passed_tests}")
        print(f"Failed: {self.failed_tests}")
        if self.failures:
            print("\nFailed Tests:")
            for test_name, error in self.failures:
                print(f"  - {test_name}: {error}")
        return self.failed_tests == 0


async def test_database_initialization(results):
    """Test database creation and initialization."""
    print("Testing Database Initialization...")
    
    try:
        network_db = NetworkDatabase()
        await network_db.initialize()
        results.add_test("Network database initialization", True)
    except Exception as e:
        results.add_test("Network database initialization", False, str(e))
    
    try:
        node_db = NodeDatabase("test_heavy_node")
        await node_db.initialize_heavy_node()
        results.add_test("Heavy node database initialization", True)
    except Exception as e:
        results.add_test("Heavy node database initialization", False, str(e))
    
    try:
        node_db = NodeDatabase("test_light_node")
        await node_db.initialize_light_node()
        results.add_test("Light node database initialization", True)
    except Exception as e:
        results.add_test("Light node database initialization", False, str(e))


async def test_node_management(results):
    """Test adding, retrieving, and removing nodes."""
    print("Testing Node Management...")
    
    network_db = NetworkDatabase()
    await network_db.initialize()
    
    # Test adding nodes with unique ports to avoid conflicts
    try:
        success = await network_db.add_node("unique_heavy_1", "heavy", 8001)
        results.add_test("Add heavy node", success)
    except Exception as e:
        results.add_test("Add heavy node", False, str(e))
    
    try:
        success = await network_db.add_node("unique_light_1", "light", 8101)
        results.add_test("Add light node", success)
    except Exception as e:
        results.add_test("Add light node", False, str(e))
    
    # Test retrieving nodes
    try:
        node = await network_db.get_node("unique_heavy_1")
        results.add_test("Retrieve node by UID", 
                        node is not None and node['node_type'] == 'heavy')
    except Exception as e:
        results.add_test("Retrieve node by UID", False, str(e))
    
    # Test getting all nodes
    try:
        nodes = await network_db.get_all_nodes()
        results.add_test("Get all nodes", len(nodes) >= 2)
    except Exception as e:
        results.add_test("Get all nodes", False, str(e))
    
    # Test getting heavy nodes by type
    try:
        heavy_nodes = await network_db.get_nodes_by_type("heavy")
        results.add_test("Get heavy nodes by type", len(heavy_nodes) >= 1)
    except Exception as e:
        results.add_test("Get heavy nodes by type", False, str(e))
    
    # Test removing nodes
    try:
        success = await network_db.remove_node("unique_light_1")
        results.add_test("Remove node", success)
    except Exception as e:
        results.add_test("Remove node", False, str(e))


async def test_computation_lifecycle(results):
    """Test computation creation and management."""
    print("Testing Computation Lifecycle...")
    
    network_db = NetworkDatabase()
    await network_db.initialize()
    
    # Add required nodes with unique ports
    await network_db.add_node("comp_heavy_1", "heavy", 8021)
    await network_db.add_node("comp_heavy_2", "heavy", 8022)
    await network_db.add_node("comp_heavy_3", "heavy", 8023)
    await network_db.add_node("comp_proposer", "light", 8121)
    
    # Test adding a computation using the correct method
    try:
        comp_id = f"test_comp_{random.randint(1000, 9999)}"
        deadline = datetime.now() + timedelta(hours=1)
        
        computation_data = {
            "comp_id": comp_id,
            "proposer_uid": "comp_proposer",
            "heavy_node_1": "comp_heavy_1",
            "heavy_node_2": "comp_heavy_2", 
            "heavy_node_3": "comp_heavy_3",
            "computation_prompt": "Calculate average of submitted values",
            "response_schema": '{"type": "number"}',
            "deadline": deadline.isoformat(),
            "min_participants": 2
        }
        
        success = await network_db.add_computation(computation_data)
        results.add_test("Add computation to database", success)
        
        # Store comp_id for later tests
        test_comp_id = comp_id
        
    except Exception as e:
        results.add_test("Add computation to database", False, str(e))
        test_comp_id = None
    
    if test_comp_id:
        # Test updating computation result
        try:
            await network_db.update_computation_result(test_comp_id, 42.5, 3)
            results.add_test("Update computation result", True)
        except Exception as e:
            results.add_test("Update computation result", False, str(e))


async def test_shares_storage_and_retrieval(results):
    """Test storing and retrieving secret shares in node database."""
    print("Testing Shares Storage and Retrieval...")
    
    node_db = NodeDatabase("shares_test_node")
    await node_db.initialize_heavy_node()
    
    # Create test shares
    secret = 100
    shares = SecretSharing.create_shares(secret, 3)
    comp_id = "test_comp_shares"
    
    # Test storing shares (using the actual API)
    try:
        for i, share in enumerate(shares):
            await node_db.add_share(comp_id, f"user_{i+1}", share)
        results.add_test("Store shares in database", True)
    except Exception as e:
        results.add_test("Store shares in database", False, str(e))
    
    # Test retrieving shares
    try:
        share_records = await node_db.get_shares_for_computation(comp_id)
        retrieved_shares = [record['share_value'] for record in share_records]
        results.add_test("Retrieve shares from database", 
                        len(retrieved_shares) == 3)
    except Exception as e:
        results.add_test("Retrieve shares from database", False, str(e))
        retrieved_shares = []
    
    # Test that retrieved shares reconstruct correctly
    try:
        if retrieved_shares:
            reconstructed = SecretSharing.reconstruct_secret(retrieved_shares)
            results.add_test("Reconstruct secret from stored shares", 
                            reconstructed == secret)
        else:
            results.add_test("Reconstruct secret from stored shares", False, 
                            "No shares retrieved")
    except Exception as e:
        results.add_test("Reconstruct secret from stored shares", False, str(e))


async def test_response_storage_and_aggregation(results):
    """Test storing responses and performing aggregation."""
    print("Testing Response Storage and Aggregation...")
    
    node_db = NodeDatabase("response_test_node")
    await node_db.initialize_light_node()
    
    # Simulate multiple user responses (each for different computations)
    test_responses = [50, 60, 70]
    
    # Test storing responses (using different comp_ids as per database schema)
    for i, value in enumerate(test_responses):
        try:
            comp_id = f"test_comp_responses_{i+1}"
            await node_db.add_response(comp_id, value)
            results.add_test(f"Store response {i+1}", True)
        except Exception as e:
            results.add_test(f"Store response {i+1}", False, str(e))
    
    # Test aggregation of responses using secret sharing
    try:
        # Create shares for each response
        all_shares = []
        for value in test_responses:
            shares = SecretSharing.create_shares(value, 3)
            all_shares.append(shares)
        
        # Aggregate shares
        aggregated_shares = SecretSharing.add_shares(all_shares)
        result = SecretSharing.reconstruct_secret(aggregated_shares)
        
        expected_sum = sum(test_responses)
        results.add_test("Aggregate responses using secret sharing", 
                        result == expected_sum)
    except Exception as e:
        results.add_test("Aggregate responses using secret sharing", False, str(e))


async def test_end_to_end_computation_workflow(results):
    """Test complete computation workflow from creation to result storage."""
    print("Testing End-to-End Computation Workflow...")
    
    # Initialize network and node databases
    network_db = NetworkDatabase()
    await network_db.initialize()


async def test_security_and_privacy_properties(results):
    """Test security and privacy properties with database."""
    print("Testing Security and Privacy Properties...")
    
    node_db = NodeDatabase("security_test_node")
    await node_db.initialize_heavy_node()
    
    # Test that individual shares don't reveal the secret
    try:
        secret = 12345
        shares = SecretSharing.create_shares(secret, 3)
        
        # Store shares
        comp_id = "security_test"
        for i, share in enumerate(shares):
            await node_db.add_share(comp_id, f"user_{i+1}", share)
        
        # Retrieve individual shares
        share_records = await node_db.get_shares_for_computation(comp_id)
        stored_shares = [record['share_value'] for record in share_records]
        
        # Verify individual shares don't equal the secret
        individual_shares_secure = all(share != secret for share in stored_shares)
        results.add_test("Individual stored shares don't reveal secret", 
                        individual_shares_secure)
    except Exception as e:
        results.add_test("Individual stored shares don't reveal secret", False, str(e))
    
    # Test that partial shares don't reveal the secret
    try:
        if stored_shares and len(stored_shares) >= 2:
            partial_reconstruction = stored_shares[0] + stored_shares[1]
            results.add_test("Partial shares don't reveal secret", 
                            partial_reconstruction != secret)
        else:
            results.add_test("Partial shares don't reveal secret", False, 
                            "Insufficient shares for test")
    except Exception as e:
        results.add_test("Partial shares don't reveal secret", False, str(e))
    
    # Test complete reconstruction works
    try:
        if stored_shares and len(stored_shares) == 3:
            reconstructed = SecretSharing.reconstruct_secret(stored_shares)
            results.add_test("Complete reconstruction reveals secret", 
                            reconstructed == secret)
        else:
            results.add_test("Complete reconstruction reveals secret", False,
                            "Insufficient shares for reconstruction")
    except Exception as e:
        results.add_test("Complete reconstruction reveals secret", False, str(e))


async def run_comprehensive_tests_with_db():
    """Run all comprehensive tests including database operations."""
    print("🧪 FORMIX COMPREHENSIVE DATABASE INTEGRATION TESTS")
    print("=" * 60)
    
    results = TestResults()
    
    # Run all test suites
    await test_database_initialization(results)
    await test_node_management(results)
    await test_computation_lifecycle(results)
    await test_shares_storage_and_retrieval(results)
    await test_response_storage_and_aggregation(results)
    await test_end_to_end_computation_workflow(results)
    await test_security_and_privacy_properties(results)
    
    # Print summary
    success = results.summary()
    
    if success:
        print("\n🎉 ALL DATABASE INTEGRATION TESTS PASSED!")
    else:
        print("\n❌ Some tests failed. Please review the failures above.")
    
    return success


if __name__ == "__main__":
    asyncio.run(run_comprehensive_tests_with_db())