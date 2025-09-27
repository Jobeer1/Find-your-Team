"""
Unit tests for Onboarding Agent functionality
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from agents.onboarding_agent import OnboardingAgent
from models.core_models import UserStatus


class TestOnboardingAgent:
    """Test OnboardingAgent core functionality"""

    @pytest.fixture
    def mock_bedrock_client(self):
        """Mock Bedrock client for testing"""
        client = Mock()
        # Mock the invoke_model response
        mock_response = {
            'body': Mock()
        }
        mock_response['body'].read.return_value = json.dumps({
            'content': [{'text': 'Hello! How can I help you discover your purpose today?'}]
        })
        client.invoke_model.return_value = mock_response
        return client

    @pytest.fixture
    def mock_dynamodb_table(self):
        """Mock DynamoDB table for testing"""
        table = Mock()
        table.put_item.return_value = None
        table.get_item.return_value = {'Item': None}
        return table

    @pytest.fixture
    def agent(self, mock_bedrock_client, mock_dynamodb_table):
        """Create OnboardingAgent instance with mocked dependencies"""
        with patch('boto3.client') as mock_boto_client, \
             patch('boto3.resource') as mock_boto_resource:

            mock_boto_client.return_value = mock_bedrock_client
            mock_boto_resource.return_value = Mock()
            mock_boto_resource.return_value.Table.return_value = mock_dynamodb_table

            agent = OnboardingAgent()
            agent.bedrock = mock_bedrock_client
            agent.memory_table_resource = mock_dynamodb_table
            return agent

    def test_agent_initialization(self, agent):
        """Test agent initializes correctly"""
        assert agent.model_id == "anthropic.claude-3-5-sonnet-20240620"
        assert agent.memory_table == "ConversationMemory"

    def test_start_conversation(self, agent, mock_dynamodb_table):
        """Test starting a new conversation"""
        user_id = "test-user-123"

        result = agent.start_conversation(user_id)

        assert 'response' in result
        assert 'conversation_id' in result
        assert result['conversation_id'].startswith(f"onboarding-{user_id}")
        assert result['current_stage'] == 'values_discovery'
        assert result['profile_complete'] is False
        assert result['confidence_score'] == 0.0

        # Verify memory was saved
        mock_dynamodb_table.put_item.assert_called_once()
        call_args = mock_dynamodb_table.put_item.call_args[1]['Item']
        assert call_args['user_id'] == user_id
        assert call_args['current_stage'] == 'greeting'

    def test_process_message_greeting_stage(self, agent, mock_dynamodb_table, mock_bedrock_client):
        """Test processing message in greeting stage"""
        conversation_id = "test-conversation-123"

        # Mock existing memory
        mock_memory = {
            'conversation_id': conversation_id,
            'user_id': 'test-user',
            'messages': [],
            'profile_data': {},
            'current_stage': 'greeting',
            'confidence_score': 0.0
        }
        mock_dynamodb_table.get_item.return_value = {'Item': mock_memory}

        user_message = "Hi! I'm looking to find a team that shares my values."

        result = agent.process_message(conversation_id, user_message)

        assert 'response' in result
        assert result['conversation_id'] == conversation_id
        assert result['current_stage'] == 'values_discovery'

        # Verify Claude was called
        mock_bedrock_client.invoke_model.assert_called_once()

        # Verify memory was updated
        assert mock_dynamodb_table.put_item.call_count == 1

    def test_calculate_profile_confidence_complete_profile(self, agent):
        """Test confidence calculation for complete profile"""
        memory = {
            'profile_data': {
                'core_values': ['innovation', 'collaboration', 'sustainability', 'integrity', 'growth'],
                'passions': ['technology', 'education', 'community development', 'sustainability'],
                'technical_skills': ['python', 'javascript', 'data analysis'],
                'soft_skills': ['communication', 'leadership', 'problem solving'],
                'collaboration_preference': 'high',
                'autonomy_preference': 'medium',
                'structure_preference': 'moderate',
                'openness': 85,
                'conscientiousness': 90,
                'extraversion': 75,
                'agreeableness': 88,
                'neuroticism': 45
            }
        }

        confidence = agent._calculate_profile_confidence(memory)

        assert confidence >= 0.8  # Should be high for complete profile

    def test_calculate_profile_confidence_incomplete_profile(self, agent):
        """Test confidence calculation for incomplete profile"""
        memory = {
            'profile_data': {
                'core_values': ['innovation'],
                'passions': ['technology'],
                'technical_skills': [],
                'soft_skills': []
            }
        }

        confidence = agent._calculate_profile_confidence(memory)

        assert confidence < 0.5  # Should be low for incomplete profile

    def test_check_profile_completion_complete(self, agent):
        """Test profile completion check for complete profile"""
        memory = {
            'profile_data': {
                'core_values': ['innovation', 'collaboration', 'sustainability'],
                'passions': ['technology', 'education'],
                'technical_skills': ['python', 'javascript'],
                'soft_skills': ['communication', 'leadership']
            },
            'confidence_score': 0.95
        }

        is_complete = agent._check_profile_completion(memory)

        assert is_complete is True

    def test_check_profile_completion_incomplete(self, agent):
        """Test profile completion check for incomplete profile"""
        memory = {
            'profile_data': {
                'core_values': ['innovation'],
                'passions': [],
                'technical_skills': [],
                'soft_skills': []
            },
            'confidence_score': 0.5
        }

        is_complete = agent._check_profile_completion(memory)

        assert is_complete is False

    @patch('agents.onboarding_agent.datetime')
    def test_get_purpose_profile_complete(self, mock_datetime, agent, mock_dynamodb_table):
        """Test generating complete user profile"""
        mock_datetime.now.return_value = datetime(2024, 1, 1, 12, 0, 0)

        conversation_id = "test-conversation-123"
        mock_memory = {
            'conversation_id': conversation_id,
            'user_id': 'test-user-123',
            'profile_data': {
                'core_values': ['innovation', 'collaboration', 'sustainability'],
                'secondary_values': ['education', 'technology'],
                'passions': ['clean water access', 'education technology'],
                'technical_skills': [{'name': 'Python', 'level': 'advanced', 'years_experience': 5}],
                'soft_skills': [{'name': 'Communication', 'level': 'expert', 'years_experience': 8}],
                'leadership_skills': [{'name': 'Team Leadership', 'level': 'intermediate', 'years_experience': 3}],
                'collaboration_preference': 'high',
                'autonomy_preference': 'medium',
                'structure_preference': 'moderate',
                'communication_style': 'supportive',
                'remote_preference': 0.7,
                'mission_statement': 'To leverage technology for sustainable community development',
                'impact_areas': ['Water Access', 'Education']
            },
            'confidence_score': 0.95
        }
        mock_dynamodb_table.get_item.return_value = {'Item': mock_memory}

        profile = agent.get_purpose_profile(conversation_id)

        assert profile is not None
        assert profile.user_id == 'test-user-123'
        assert profile.confidence_score == 95
        assert profile.status == UserStatus.READY_FOR_MATCHING
        assert len(profile.purpose_profile.values.core) == 3
        assert len(profile.purpose_profile.passions) == 2
        assert profile.purpose_profile.mission_statement == 'To leverage technology for sustainable community development'

    def test_get_purpose_profile_incomplete(self, agent, mock_dynamodb_table):
        """Test getting profile when incomplete"""
        conversation_id = "test-conversation-123"
        mock_memory = {
            'conversation_id': conversation_id,
            'user_id': 'test-user-123',
            'profile_data': {
                'core_values': ['innovation'],
                'passions': []
            },
            'confidence_score': 0.5
        }
        mock_dynamodb_table.get_item.return_value = {'Item': mock_memory}

        profile = agent.get_purpose_profile(conversation_id)

        assert profile is None

    def test_call_claude_success(self, agent, mock_bedrock_client):
        """Test successful Claude API call"""
        prompt = "Test prompt"
        expected_response = "Hello! How can I help you discover your purpose today?"

        result = agent._call_claude(prompt)

        assert result == expected_response
        mock_bedrock_client.invoke_model.assert_called_once()

        # Check the call arguments
        call_args = mock_bedrock_client.invoke_model.call_args
        assert call_args[1]['modelId'] == agent.model_id

        body = json.loads(call_args[1]['body'])
        assert body['messages'][0]['content'] == prompt
        assert body['temperature'] == 0.7

    def test_call_claude_error(self, agent, mock_bedrock_client):
        """Test Claude API call error handling"""
        mock_bedrock_client.invoke_model.side_effect = Exception("API Error")

        result = agent._call_claude("Test prompt")

        assert "sorry" in result.lower()
        assert "trouble" in result.lower()

    def test_save_memory(self, agent, mock_dynamodb_table):
        """Test saving conversation memory"""
        memory = {
            'conversation_id': 'test-123',
            'user_id': 'user-123',
            'messages': [{'role': 'user', 'content': 'Hello'}]
        }

        agent._save_memory(memory)

        mock_dynamodb_table.put_item.assert_called_once_with(Item=memory)

    def test_load_memory_found(self, agent, mock_dynamodb_table):
        """Test loading existing conversation memory"""
        conversation_id = 'test-123'
        expected_memory = {
            'conversation_id': conversation_id,
            'user_id': 'user-123',
            'messages': []
        }
        mock_dynamodb_table.get_item.return_value = {'Item': expected_memory}

        result = agent._load_memory(conversation_id)

        assert result == expected_memory
        mock_dynamodb_table.get_item.assert_called_once_with(Key={'conversation_id': conversation_id})

    def test_load_memory_not_found(self, agent, mock_dynamodb_table):
        """Test loading non-existent conversation memory"""
        mock_dynamodb_table.get_item.return_value = {}

        result = agent._load_memory('non-existent')

        assert result is None

    def test_transition_logic(self, agent):
        """Test conversation stage transition logic"""
        # Test values to passions transition
        memory_values = {'profile_data': {'core_values': ['a', 'b', 'c']}}
        assert agent._should_transition_to_passions(memory_values) is True

        memory_values['profile_data']['core_values'] = ['a']
        assert agent._should_transition_to_passions(memory_values) is False

        # Test passions to work style transition
        memory_passions = {'profile_data': {'passions': ['tech', 'education']}}
        assert agent._should_transition_to_work_style(memory_passions) is True

        memory_passions['profile_data']['passions'] = ['tech']
        assert agent._should_transition_to_work_style(memory_passions) is False

    def test_generate_profile_summary(self, agent):
        """Test profile summary generation"""
        memory = {
            'profile_data': {
                'core_values': ['innovation', 'collaboration'],
                'passions': ['technology', 'education'],
                'technical_skills': ['python', 'javascript'],
                'soft_skills': ['communication'],
                'mission_statement': 'To build educational technology'
            }
        }

        summary = agent._generate_profile_summary(memory)

        assert '**Core Values:**' in summary
        assert '**Passions:**' in summary
        assert '**Key Skills:**' in summary
        assert '**Mission:**' in summary
        assert 'innovation' in summary
        assert 'technology' in summary