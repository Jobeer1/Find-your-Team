"""
Comprehensive Test Suite for Task 11 - Error Handling and Resilience

Tests all resilience components including error handling, network resilience,
agent resilience, and data synchronization.
"""

import unittest
import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resilience.error_handling import (
    ResilienceManager, ErrorCategory, ErrorSeverity, RecoveryStrategy,
    CircuitBreaker, RetryManager, resilient_operation, resilient_context,
    ErrorContext, AgentHealth, NetworkHealth, DataSyncConflict
)
from resilience.network_resilience import (
    NetworkResilience, NetworkMonitor, OfflineQueue, ConnectionState,
    RequestPriority, NetworkRequest, BandwidthInfo
)
from resilience.agent_resilience import (
    AgentResilience, AgentType, AgentMode, FallbackStrategy, AgentInstance,
    AgentLoadBalancer, ResponseCache, FallbackEngine
)
from resilience.data_sync_resilience import (
    DataSyncResilience, DataChange, DataOperation, SyncStatus,
    ConflictResolution, OfflineDataStore, ConflictResolver
)

# Suppress logging during tests
logging.disable(logging.CRITICAL)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and resilience management"""
    
    def setUp(self):
        """Set up test environment"""
        self.manager = ResilienceManager()
    
    def test_error_classification(self):
        """Test error severity and category classification"""
        # Test severity classification
        network_error = ConnectionError("Network unavailable")
        error_context = self.manager.log_error(network_error)
        
        self.assertEqual(error_context.category, ErrorCategory.NETWORK)
        self.assertEqual(error_context.severity, ErrorSeverity.HIGH)
        
        # Test agent error classification
        agent_error = Exception("Bedrock agent failed")
        agent_context = self.manager.log_error(agent_error, {'component': 'onboarding_agent'})
        
        self.assertEqual(agent_context.category, ErrorCategory.AGENT)
        self.assertEqual(agent_context.component, 'onboarding_agent')
    
    def test_circuit_breaker(self):
        """Test circuit breaker functionality"""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        
        # Test normal operation
        self.assertEqual(breaker.state, 'CLOSED')
        
        # Simulate failures
        for _ in range(3):
            try:
                breaker.call(lambda: 1/0)  # Causes ZeroDivisionError
            except:
                pass
        
        # Circuit should now be open
        self.assertEqual(breaker.state, 'OPEN')
        
        # Test that circuit breaker blocks calls
        with self.assertRaises(Exception):
            breaker.call(lambda: "success")
    
    def test_agent_health_tracking(self):
        """Test agent health monitoring"""
        agent = AgentHealth(agent_name="test_agent")
        
        # Test successful operation
        agent.update_performance(1.0, True)
        self.assertTrue(agent.is_available)
        self.assertEqual(agent.consecutive_failures, 0)
        
        # Test failed operations
        for _ in range(6):  # Trigger circuit breaker
            agent.update_performance(5.0, False)
        
        self.assertTrue(agent.circuit_breaker_open)
        self.assertFalse(agent.is_available)
    
    def test_network_health_monitoring(self):
        """Test network health tracking"""
        health = NetworkHealth()
        
        # Test good connection
        health.latency_ms = 50
        health.packet_loss = 0
        health.is_connected = True
        health.update_quality()
        
        self.assertEqual(health.connection_quality, "excellent")
        
        # Test poor connection
        health.latency_ms = 1500
        health.packet_loss = 15
        health.update_quality()
        
        self.assertEqual(health.connection_quality, "poor")
    
    def test_data_sync_conflict_detection(self):
        """Test sync conflict detection and auto-resolution"""
        manager = ResilienceManager()
        
        local_data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'updated_at': datetime.utcnow().isoformat()
        }
        
        remote_data = {
            'name': 'John Smith',  # Conflict
            'email': 'john@example.com',
            'updated_at': (datetime.utcnow() + timedelta(seconds=30)).isoformat()
        }
        
        conflict = manager.detect_sync_conflict("user123", "profile", local_data, remote_data)
        
        self.assertIsNotNone(conflict)
        self.assertIn('name', conflict.conflict_fields)
        self.assertNotIn('email', conflict.conflict_fields)
    
    async def test_recovery_strategies(self):
        """Test different error recovery strategies"""
        manager = ResilienceManager()
        
        # Test retry strategy
        error = ConnectionError("Network timeout")
        context = {'component': 'network_test'}
        
        recovery_result = await manager.handle_error(error, context)
        self.assertIn('strategy', recovery_result)
        self.assertIn('error_id', recovery_result)
    
    def test_resilient_operation_decorator(self):
        """Test resilient operation decorator"""
        
        @resilient_operation(component="test_component")
        def test_function():
            return "success"
        
        # Should work normally
        result = test_function()
        self.assertEqual(result, "success")
        
        @resilient_operation(component="test_component")
        def failing_function():
            raise ValueError("Test error")
        
        # Should handle error gracefully
        with self.assertRaises(Exception):
            failing_function()
    
    def test_system_health_reporting(self):
        """Test comprehensive system health reporting"""
        manager = ResilienceManager()
        manager.register_agent("test_agent")
        
        health_report = manager.get_system_health()
        
        self.assertIn('network', health_report)
        self.assertIn('agents', health_report)
        self.assertIn('errors', health_report)
        self.assertIn('timestamp', health_report)


class TestNetworkResilience(unittest.TestCase):
    """Test network resilience functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.network_resilience = NetworkResilience()
        self.monitor = NetworkMonitor()
    
    def test_connection_state_detection(self):
        """Test network connection state detection"""
        # Test offline state
        self.monitor.connection_state = ConnectionState.OFFLINE
        self.assertFalse(self.monitor.is_online())
        
        # Test online state
        self.monitor.connection_state = ConnectionState.ONLINE
        self.assertTrue(self.monitor.is_online())
    
    def test_offline_queue_management(self):
        """Test offline request queuing"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            queue = OfflineQueue(tmp.name)
            
            # Test adding requests
            request = NetworkRequest(
                request_id="test_123",
                url="https://example.com/api",
                method="POST",
                data={"test": "data"},
                priority=RequestPriority.HIGH
            )
            
            success = queue.add_request(request)
            self.assertTrue(success)
            
            # Test retrieving requests
            next_request = queue.get_next_request()
            self.assertIsNotNone(next_request)
            self.assertEqual(next_request.request_id, "test_123")
            
            # Test queue status
            status = queue.get_queue_status()
            self.assertIn('total_requests', status)
            self.assertIn('priority_breakdown', status)
            
            # Cleanup
            os.unlink(tmp.name)
    
    def test_request_priority_ordering(self):
        """Test request priority ordering in offline queue"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            queue = OfflineQueue(tmp.name)
            
            # Add requests with different priorities
            low_req = NetworkRequest("low", "https://example.com", priority=RequestPriority.LOW)
            high_req = NetworkRequest("high", "https://example.com", priority=RequestPriority.CRITICAL)
            normal_req = NetworkRequest("normal", "https://example.com", priority=RequestPriority.NORMAL)
            
            queue.add_request(low_req)
            queue.add_request(high_req)
            queue.add_request(normal_req)
            
            # Should get highest priority first
            next_req = queue.get_next_request()
            self.assertEqual(next_req.request_id, "high")
            
            # Cleanup
            os.unlink(tmp.name)
    
    def test_bandwidth_estimation(self):
        """Test network bandwidth estimation"""
        bandwidth = BandwidthInfo(
            download_mbps=5.0,
            latency_ms=100,
            jitter_ms=20
        )
        
        quality_score = bandwidth.get_quality_score()
        self.assertGreater(quality_score, 0)
        self.assertLessEqual(quality_score, 1)
    
    async def test_adaptive_timeouts(self):
        """Test adaptive timeout configuration"""
        resilience = NetworkResilience()
        
        # Test that timeouts adapt to connection quality
        resilience.monitor.connection_state = ConnectionState.UNSTABLE
        timeout = resilience.adaptive_timeouts[ConnectionState.UNSTABLE]
        
        self.assertGreater(timeout, resilience.adaptive_timeouts[ConnectionState.ONLINE])


class TestAgentResilience(unittest.TestCase):
    """Test agent resilience functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.agent_resilience = AgentResilience()
        self.load_balancer = AgentLoadBalancer()
    
    def test_agent_registration_and_selection(self):
        """Test agent registration and load balancing"""
        # Register test agents
        primary_agent = AgentInstance(
            agent_id="primary_onboarding",
            agent_type=AgentType.ONBOARDING,
            mode=AgentMode.FULL_AI,
            is_primary=True
        )
        
        backup_agent = AgentInstance(
            agent_id="backup_onboarding",
            agent_type=AgentType.ONBOARDING,
            mode=AgentMode.RULE_BASED,
            is_primary=False
        )
        
        self.load_balancer.register_agent(primary_agent)
        self.load_balancer.register_agent(backup_agent)
        
        # Test best agent selection
        best_agent = self.load_balancer.get_best_agent(AgentType.ONBOARDING)
        self.assertIsNotNone(best_agent)
        self.assertTrue(best_agent.is_available)
        
        # Test backup agent selection
        backup = self.load_balancer.get_backup_agent(AgentType.ONBOARDING, exclude_id="primary_onboarding")
        self.assertEqual(backup.agent_id, "backup_onboarding")
    
    def test_agent_health_scoring(self):
        """Test agent health score calculation"""
        agent = AgentInstance(
            agent_id="test_agent",
            agent_type=AgentType.ONBOARDING,
            mode=AgentMode.FULL_AI
        )
        
        # Test with good metrics
        agent.error_rate = 0.1
        agent.last_response_time = 1.0
        agent.load_score = 0.3
        
        health_score = agent.get_health_score()
        self.assertGreater(health_score, 0.5)
        
        # Test with poor metrics
        agent.error_rate = 0.8
        agent.last_response_time = 15.0
        agent.load_score = 0.9
        
        health_score = agent.get_health_score()
        self.assertLess(health_score, 0.3)
    
    def test_response_caching(self):
        """Test agent response caching"""
        cache = ResponseCache(max_size=10)
        
        # Test cache miss
        result = cache.get(AgentType.ONBOARDING, "start_conversation", {})
        self.assertIsNone(result)
        
        # Test cache set and hit
        response_data = {"message": "Hello!", "confidence": 0.8}
        cache.set(AgentType.ONBOARDING, "start_conversation", {}, response_data)
        
        cached_result = cache.get(AgentType.ONBOARDING, "start_conversation", {})
        self.assertIsNotNone(cached_result)
        self.assertTrue(cached_result['cached'])
        self.assertEqual(cached_result['message'], "Hello!")
    
    def test_fallback_engine(self):
        """Test fallback response generation"""
        engine = FallbackEngine()
        
        # Test rule-based response
        response = engine.get_rule_based_response(
            AgentType.ONBOARDING,
            "process_response",
            {"user_input": "I want to help with education"}
        )
        
        self.assertIn('message', response)
        self.assertIn('confidence_score', response)
        self.assertEqual(response['mode'], 'rule_based')
        
        # Test fallback response
        fallback = engine.get_fallback_response(
            AgentType.MATCHING,
            "unknown_action",
            {}
        )
        
        self.assertIn('fallback', fallback)
        self.assertTrue(fallback['fallback'])


class TestDataSyncResilience(unittest.TestCase):
    """Test data synchronization resilience"""
    
    def setUp(self):
        """Set up test environment"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            self.db_path = tmp.name
        
        self.data_sync = DataSyncResilience()
        self.data_sync.offline_store = OfflineDataStore(self.db_path)
    
    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_offline_data_storage(self):
        """Test offline data storage and retrieval"""
        store = OfflineDataStore(self.db_path)
        
        # Test saving changes
        change = DataChange(
            change_id="test_123",
            user_id="user456",
            data_type="profile",
            operation=DataOperation.UPDATE,
            data={"name": "John Doe", "email": "john@example.com"}
        )
        
        store.save_change(change)
        
        # Test retrieving pending changes
        pending = store.get_pending_changes("user456")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].change_id, "test_123")
        
        # Test updating change status
        store.update_change_status("test_123", SyncStatus.SYNCED)
        
        # Should have no pending changes now
        pending_after = store.get_pending_changes("user456")
        self.assertEqual(len(pending_after), 0)
    
    def test_data_caching(self):
        """Test data caching functionality"""
        store = OfflineDataStore(self.db_path)
        
        # Test caching data
        test_data = {"profile": {"name": "John", "age": 30}}
        store.cache_data("user123:profile", "user123", "profile", test_data, ttl_hours=1)
        
        # Test retrieving cached data
        cached = store.get_cached_data("user123:profile")
        self.assertIsNotNone(cached)
        self.assertEqual(cached['data'], test_data)
        self.assertTrue(cached['cached'])
    
    def test_conflict_resolution_strategies(self):
        """Test different conflict resolution strategies"""
        resolver = ConflictResolver()
        
        # Create test conflict
        conflict = DataSyncConflict(
            conflict_id="conflict_123",
            user_id="user456",
            data_type="profile",
            local_version={"name": "John Doe", "age": 30},
            remote_version={"name": "John Smith", "age": 30},
            local_timestamp=datetime.utcnow() - timedelta(minutes=5),
            remote_timestamp=datetime.utcnow(),
            conflict_fields=["name"]
        )
        
        # Test latest timestamp resolution
        result = resolver.resolve_conflict(conflict, ConflictResolution.LATEST_TIMESTAMP)
        self.assertEqual(result["name"], "John Smith")  # Remote is newer
        
        # Test local wins
        result = resolver.resolve_conflict(conflict, ConflictResolution.LOCAL_WINS)
        self.assertEqual(result["name"], "John Doe")
        
        # Test remote wins
        result = resolver.resolve_conflict(conflict, ConflictResolution.REMOTE_WINS)
        self.assertEqual(result["name"], "John Smith")
    
    def test_auto_conflict_resolution(self):
        """Test automatic conflict resolution"""
        conflict = DataSyncConflict(
            conflict_id="auto_123",
            user_id="user789",
            data_type="profile",
            local_version={"name": "John", "status": "active"},
            remote_version={"name": "John", "status": "inactive"},
            local_timestamp=datetime.utcnow() - timedelta(seconds=30),
            remote_timestamp=datetime.utcnow(),
            conflict_fields=["status"]
        )
        
        # Test that recent conflicts can be auto-resolved
        resolved = conflict.auto_resolve()
        self.assertTrue(resolved)
        self.assertIsNotNone(conflict.resolution_data)
    
    async def test_sync_status_tracking(self):
        """Test sync status tracking for users"""
        sync = DataSyncResilience()
        
        # Test saving data
        await sync.save_data("user123", "profile", {"name": "John"})
        
        # Check sync status
        status = sync.get_user_sync_status("user123")
        self.assertIn('user_id', status)
        self.assertIn('overall_status', status)
        self.assertIn('data_types', status)


class TestResilienceIntegration(unittest.TestCase):
    """Integration tests for resilience system"""
    
    async def test_end_to_end_resilience(self):
        """Test complete resilience workflow"""
        # This would test the entire resilience system working together
        # Including error handling, network resilience, agent failover, and data sync
        
        # For now, just test that all components can be initialized
        from resilience.error_handling import resilience_manager
        from resilience.network_resilience import network_resilience
        from resilience.agent_resilience import agent_resilience
        from resilience.data_sync_resilience import data_sync_resilience
        
        self.assertIsNotNone(resilience_manager)
        self.assertIsNotNone(network_resilience)
        self.assertIsNotNone(agent_resilience)
        self.assertIsNotNone(data_sync_resilience)
    
    def test_resilience_api_integration(self):
        """Test resilience system integration with Flask API"""
        # This would test the API endpoints work correctly
        # For now, just verify the system can be imported
        
        try:
            import app
            self.assertTrue(hasattr(app, 'RESILIENCE_AVAILABLE'))
        except ImportError as e:
            self.skipTest(f"Flask app not available: {e}")


def run_async_test(test_func):
    """Helper function to run async tests"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(test_func())
    finally:
        loop.close()


if __name__ == '__main__':
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestErrorHandling,
        TestNetworkResilience,
        TestAgentResilience,
        TestDataSyncResilience,
        TestResilienceIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Run async tests manually
    print("\n" + "="*60)
    print("Running Async Tests...")
    print("="*60)
    
    async_tests = [
        'test_recovery_strategies',
        'test_adaptive_timeouts',
        'test_sync_status_tracking',
        'test_end_to_end_resilience'
    ]
    
    passed = 0
    failed = 0
    
    for test_name in async_tests:
        print(f"\nRunning {test_name}...")
        try:
            # Find the test method across all test classes
            test_method = None
            test_instance = None
            
            for test_class in test_classes:
                if hasattr(test_class, test_name):
                    test_instance = test_class()
                    test_instance.setUp()
                    test_method = getattr(test_instance, test_name)
                    break
            
            if test_method:
                run_async_test(test_method)
                print(f"✓ {test_name} PASSED")
                passed += 1
            else:
                print(f"? {test_name} NOT FOUND")
                
        except Exception as e:
            print(f"✗ {test_name} FAILED: {str(e)}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"Async Tests Summary: {passed} passed, {failed} failed")
    print("="*60)
    
    total_passed = result.testsRun - len(result.failures) - len(result.errors) + passed
    total_failed = len(result.failures) + len(result.errors) + failed
    
    print(f"\nOverall Summary: {total_passed} passed, {total_failed} failed")
    print("All resilience tests completed!")
    
    # Enable logging again
    logging.disable(logging.NOTSET)