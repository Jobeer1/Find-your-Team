"""
Integration tests for AgentCore orchestration system

Tests multi-agent workflows, handoffs, error handling, and performance monitoring
"""

import unittest
import asyncio
import json
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add the parent directory to the path so we can import the agents
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.agent_core import (
    BedrockAgentCore, AgentType, AgentConfiguration, AgentContext,
    WorkflowDecision, WorkflowStatus, HandoffTrigger
)


class MockAWSConfig:
    """Mock AWS configuration for testing"""
    
    def __init__(self):
        self.bedrock = Mock()
        self.session = Mock()
        self.demo_mode = True
        
        # Mock Bedrock response
        self.bedrock.invoke_model.return_value = {
            'body': Mock(read=Mock(return_value=json.dumps({
                'content': [{'text': 'Test response with 85% confidence'}]
            }).encode()))
        }
        
        # Mock session client
        mock_client = Mock()
        self.session.client.return_value = mock_client


class TestAgentCore(unittest.TestCase):
    """Test cases for BedrockAgentCore orchestration"""
    
    def setUp(self):
        """Set up test environment"""
        self.aws_config = MockAWSConfig()
        self.agent_core = BedrockAgentCore(self.aws_config)
    
    def test_agent_initialization(self):
        """Test agent configuration initialization"""
        # Check that all agent types are configured
        expected_agents = [AgentType.ONBOARDING, AgentType.MATCHING, AgentType.TEAM]
        
        for agent_type in expected_agents:
            self.assertIn(agent_type, self.agent_core.agents)
            
        # Check agent configurations
        onboarding_config = self.agent_core.agents[AgentType.ONBOARDING]
        self.assertEqual(onboarding_config.agent_type, AgentType.ONBOARDING)
        self.assertEqual(onboarding_config.handoff_threshold, 0.9)
        
    def test_performance_metrics_initialization(self):
        """Test performance metrics are properly initialized"""
        for agent_type in AgentType:
            self.assertIn(agent_type, self.agent_core.performance_metrics)
            metrics = self.agent_core.performance_metrics[agent_type]
            self.assertEqual(metrics.agent_type, agent_type)
            self.assertEqual(metrics.total_invocations, 0)
            self.assertEqual(metrics.successful_invocations, 0)
            
    async def test_workflow_start(self):
        """Test starting a new workflow"""
        user_input = "I want to find my purpose"
        user_id = "test_user"
        
        context = await self.agent_core.start_workflow(user_input, user_id)
        
        # Check context properties
        self.assertEqual(context.user_id, user_id)
        self.assertEqual(context.current_agent, AgentType.ONBOARDING)
        self.assertIn(context.workflow_id, self.agent_core.active_workflows)
        self.assertEqual(len(context.conversation_history), 1)
        self.assertEqual(context.conversation_history[0]['content'], user_input)
        
    async def test_onboarding_agent_invocation(self):
        """Test invoking onboarding agent"""
        # Start workflow
        context = await self.agent_core.start_workflow("Hello", "test_user")
        
        # Invoke onboarding agent
        input_data = {'user_input': 'I want to help poor communities'}
        result = await self.agent_core.invoke_agent(AgentType.ONBOARDING, context, input_data)
        
        # Check result
        self.assertIn('response', result)
        self.assertIn('confidence_score', result)
        self.assertEqual(result['agent'], 'onboarding')
        
        # Check metrics updated
        metrics = self.agent_core.performance_metrics[AgentType.ONBOARDING]
        self.assertEqual(metrics.total_invocations, 1)
        self.assertEqual(metrics.successful_invocations, 1)
        
    async def test_confidence_score_extraction(self):
        """Test confidence score extraction from responses"""
        test_cases = [
            ("I'm 95% confident in this assessment", 0.95),
            ("Confidence: 80%", 0.80),
            ("With 70 percent confidence", 0.70),
            ("No confidence mentioned", 0.85),  # Default for long response
            ("Short", 0.45)  # Default for short response
        ]
        
        for response_text, expected_score in test_cases:
            actual_score = self.agent_core._extract_confidence_score(response_text)
            self.assertAlmostEqual(actual_score, expected_score, places=1)
    
    async def test_handoff_trigger_detection(self):
        """Test handoff trigger detection"""
        context = await self.agent_core.start_workflow("Test", "test_user")
        
        # High confidence should trigger handoff
        high_confidence_result = {
            'confidence_score': 0.95,
            'response': 'I have a clear understanding of your purpose'
        }
        
        handoff = await self.agent_core._check_handoff_triggers(context, high_confidence_result)
        self.assertIsNotNone(handoff)
        self.assertEqual(handoff['trigger'], HandoffTrigger.CONFIDENCE_THRESHOLD.value)
        self.assertEqual(handoff['from_agent'], AgentType.ONBOARDING.value)
        self.assertEqual(handoff['to_agent'], AgentType.MATCHING.value)
        
        # Low confidence should not trigger handoff
        low_confidence_result = {
            'confidence_score': 0.5,
            'response': 'I need more information'
        }
        
        handoff = await self.agent_core._check_handoff_triggers(context, low_confidence_result)
        self.assertIsNone(handoff)
    
    async def test_agent_handoff_execution(self):
        """Test executing agent handoff"""
        context = await self.agent_core.start_workflow("Test", "test_user")
        
        # Execute handoff from onboarding to matching
        handoff_data = {
            'confidence_threshold_met': True,
            'user_profile': {'purpose': 'help communities'}
        }
        
        result = await self.agent_core.execute_handoff(
            context,
            AgentType.ONBOARDING,
            AgentType.MATCHING,
            handoff_data
        )
        
        # Check context updated
        self.assertEqual(context.current_agent, AgentType.MATCHING)
        
        # Check result
        self.assertIn('agent', result)
        self.assertEqual(result['agent'], 'matching')
        
        # Check handoff rate metrics
        onboarding_metrics = self.agent_core.performance_metrics[AgentType.ONBOARDING]
        self.assertGreater(onboarding_metrics.handoff_rate, 0)
    
    async def test_error_handling_and_retry(self):
        """Test error handling and retry mechanism"""
        context = await self.agent_core.start_workflow("Test", "test_user")
        
        # Mock bedrock to raise exception on first call
        call_count = 0
        def mock_invoke_model(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary error")
            return self.aws_config.bedrock.invoke_model.return_value
        
        self.aws_config.bedrock.invoke_model.side_effect = mock_invoke_model
        
        # Should succeed after retry
        input_data = {'user_input': 'Test input'}
        result = await self.agent_core.invoke_agent(AgentType.ONBOARDING, context, input_data)
        
        # Check that retry occurred
        self.assertEqual(call_count, 2)
        self.assertIn('response', result)
        
        # Check error metrics updated
        metrics = self.agent_core.performance_metrics[AgentType.ONBOARDING]
        self.assertEqual(metrics.failed_invocations, 1)  # First attempt failed
        self.assertEqual(metrics.successful_invocations, 1)  # Second attempt succeeded
    
    async def test_workflow_decision_logging(self):
        """Test workflow decision logging"""
        context = await self.agent_core.start_workflow("Test", "test_user")
        
        # Invoke agent to generate decisions
        input_data = {'user_input': 'Test input'}
        await self.agent_core.invoke_agent(AgentType.ONBOARDING, context, input_data)
        
        # Check decision was logged
        workflow_id = context.workflow_id
        self.assertIn(workflow_id, self.agent_core.workflow_decisions)
        
        decisions = self.agent_core.workflow_decisions[workflow_id]
        self.assertEqual(len(decisions), 1)
        
        decision = decisions[0]
        self.assertEqual(decision.agent_type, AgentType.ONBOARDING)
        self.assertEqual(decision.decision_type, 'invoke')
        self.assertTrue(decision.success)
        self.assertIsNotNone(decision.execution_time_ms)
    
    async def test_performance_metrics_updates(self):
        """Test performance metrics are properly updated"""
        context = await self.agent_core.start_workflow("Test", "test_user")
        
        # Initial metrics
        initial_metrics = self.agent_core.performance_metrics[AgentType.ONBOARDING]
        initial_invocations = initial_metrics.total_invocations
        
        # Invoke agent multiple times
        for i in range(3):
            input_data = {'user_input': f'Test input {i}'}
            await self.agent_core.invoke_agent(AgentType.ONBOARDING, context, input_data)
        
        # Check metrics updated
        updated_metrics = self.agent_core.performance_metrics[AgentType.ONBOARDING]
        self.assertEqual(updated_metrics.total_invocations, initial_invocations + 3)
        self.assertEqual(updated_metrics.successful_invocations, initial_invocations + 3)
        self.assertGreater(updated_metrics.average_response_time_ms, 0)
        self.assertGreater(updated_metrics.average_confidence_score, 0)
    
    async def test_workflow_status_retrieval(self):
        """Test getting workflow status"""
        context = await self.agent_core.start_workflow("Test", "test_user")
        workflow_id = context.workflow_id
        
        # Invoke agent to generate some activity
        input_data = {'user_input': 'Test input'}
        await self.agent_core.invoke_agent(AgentType.ONBOARDING, context, input_data)
        
        # Get workflow status
        status = await self.agent_core.get_workflow_status(workflow_id)
        
        self.assertIsNotNone(status)
        self.assertEqual(status['workflow_id'], workflow_id)
        self.assertEqual(status['status'], 'active')
        self.assertEqual(status['current_agent'], AgentType.ONBOARDING.value)
        self.assertEqual(status['decision_count'], 1)
    
    def test_get_performance_metrics(self):
        """Test getting agent performance metrics"""
        metrics = self.agent_core.get_agent_performance_metrics()
        
        # Check all agent types are included
        for agent_type in AgentType:
            self.assertIn(agent_type.value, metrics)
            
        # Check metric structure
        onboarding_metrics = metrics[AgentType.ONBOARDING.value]
        self.assertIn('total_invocations', onboarding_metrics)
        self.assertIn('successful_invocations', onboarding_metrics)
        self.assertIn('failed_invocations', onboarding_metrics)
        self.assertIn('average_response_time_ms', onboarding_metrics)
        self.assertIn('average_confidence_score', onboarding_metrics)
    
    async def test_multi_agent_workflow(self):
        """Test complete multi-agent workflow"""
        # Start with onboarding
        context = await self.agent_core.start_workflow("I want to find my purpose", "test_user")
        
        # Onboarding phase - simulate high confidence
        onboarding_input = {'user_input': 'I want to help poor communities with education'}
        
        # Mock high confidence response for handoff trigger
        self.aws_config.bedrock.invoke_model.return_value = {
            'body': Mock(read=Mock(return_value=json.dumps({
                'content': [{'text': 'I have 95% confidence in your purpose profile'}]
            }).encode()))
        }
        
        onboarding_result = await self.agent_core.invoke_agent(
            AgentType.ONBOARDING, context, onboarding_input
        )
        
        # Should trigger handoff to matching
        self.assertIn('handoff', onboarding_result)
        handoff = onboarding_result['handoff']
        self.assertEqual(handoff['to_agent'], AgentType.MATCHING.value)
        
        # Execute handoff
        handoff_result = await self.agent_core.execute_handoff(
            context,
            AgentType.ONBOARDING,
            AgentType.MATCHING,
            {'user_profile': {'purpose': 'education'}}
        )
        
        # Should now be in matching phase
        self.assertEqual(context.current_agent, AgentType.MATCHING)
        
        # Test matching to team handoff
        matching_result = await self.agent_core.invoke_agent(
            AgentType.MATCHING, context, {'user_profile': {'purpose': 'education'}}
        )
        
        # Check workflow has multiple decisions
        decisions = self.agent_core.workflow_decisions[context.workflow_id]
        self.assertGreaterEqual(len(decisions), 2)
        
        # Check different agents were involved
        agent_types_used = {d.agent_type for d in decisions}
        self.assertIn(AgentType.ONBOARDING, agent_types_used)
        self.assertIn(AgentType.MATCHING, agent_types_used)


class TestAgentCoreIntegrationAPI(unittest.TestCase):
    """Test AgentCore integration with Flask API"""
    
    def setUp(self):
        """Set up test Flask app"""
        import tempfile
        import sys
        import os
        
        # Add app directory to path
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)
        
        # Import Flask app
        from app import app, agent_core
        
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.agent_core = agent_core
    
    def test_agent_core_status_endpoint(self):
        """Test AgentCore status API endpoint"""
        response = self.client.get('/api/agent-core/status')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'active')
        self.assertIn('performance_metrics', data)
        self.assertIn('active_workflows', data)
        self.assertIn('agent_count', data)
        
    def test_chat_with_agent_core(self):
        """Test chat endpoint using AgentCore"""
        chat_data = {
            'message': 'I want to find my purpose',
            'user_id': 'test_user_123'
        }
        
        response = self.client.post('/api/chat',
                                  data=json.dumps(chat_data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('message', data)
        self.assertIn('confidence', data)
        self.assertIn('conversation_id', data)
        self.assertEqual(data['agent'], 'onboarding')


def run_async_test(test_func):
    """Helper function to run async tests"""
    async def wrapper():
        test_case = TestAgentCore()
        test_case.setUp()
        await test_func(test_case)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(wrapper())
    finally:
        loop.close()


if __name__ == '__main__':
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add synchronous tests
    suite.addTest(TestAgentCore('test_agent_initialization'))
    suite.addTest(TestAgentCore('test_performance_metrics_initialization'))
    suite.addTest(TestAgentCore('test_get_performance_metrics'))
    
    # Add API integration tests
    suite.addTest(TestAgentCoreIntegrationAPI('test_agent_core_status_endpoint'))
    suite.addTest(TestAgentCoreIntegrationAPI('test_chat_with_agent_core'))
    
    # Run synchronous tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Run async tests manually
    print("\n" + "="*60)
    print("Running Async Tests...")
    print("="*60)
    
    async_tests = [
        'test_workflow_start',
        'test_onboarding_agent_invocation', 
        'test_confidence_score_extraction',
        'test_handoff_trigger_detection',
        'test_agent_handoff_execution',
        'test_error_handling_and_retry',
        'test_workflow_decision_logging',
        'test_performance_metrics_updates',
        'test_workflow_status_retrieval',
        'test_multi_agent_workflow'
    ]
    
    for test_name in async_tests:
        print(f"\nRunning {test_name}...")
        try:
            test_case = TestAgentCore()
            test_case.setUp()
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            test_method = getattr(test_case, test_name)
            loop.run_until_complete(test_method())
            
            loop.close()
            print(f"✓ {test_name} PASSED")
            
        except Exception as e:
            print(f"✗ {test_name} FAILED: {str(e)}")
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)