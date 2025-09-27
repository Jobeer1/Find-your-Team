"""
Tests for the Matching Agent
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from models.core_models import (
    UserProfile, PurposeProfile, TeamMatch, TeamOpportunity,
    MatchScore, MatchReason, Values, WorkStyle, Skills, Skill,
    SkillLevel, WorkStylePreference, CommunicationStyle, StructurePreference
)
from agents.matching_agent import MatchingAgent


class TestMatchingAgent:
    """Test cases for the Matching Agent"""

    @pytest.fixture
    def mock_bedrock(self):
        """Mock Bedrock client"""
        mock_client = Mock()
        # Mock embedding response
        mock_response = Mock()
        mock_response.__getitem__ = Mock(return_value=Mock())
        mock_response.__getitem__.return_value.read.return_value = json.dumps({
            "embedding": [0.1, 0.2, 0.3, 0.4, 0.5]
        })
        mock_client.invoke_model.return_value = mock_response
        return mock_client

    @pytest.fixture
    def mock_opensearch_response(self):
        """Mock OpenSearch response"""
        return {
            "hits": {
                "hits": [
                    {
                        "_score": 8.5,
                        "_source": {
                            "team_id": "team-123",
                            "team_name": "Clean Water Initiative",
                            "description": "Building water systems for communities",
                            "required_skills": ["engineering", "project management"],
                            "team_values": ["sustainability", "community impact"],
                            "mission": "Provide clean water access worldwide"
                        }
                    },
                    {
                        "_score": 7.2,
                        "_source": {
                            "team_id": "team-456",
                            "team_name": "Education Access",
                            "description": "Improving education in underserved areas",
                            "required_skills": ["teaching", "curriculum design"],
                            "team_values": ["education", "equality"],
                            "mission": "Ensure quality education for all children"
                        }
                    }
                ]
            }
        }

    @pytest.fixture
    def sample_user_profile(self):
        """Sample user profile for testing"""
        return UserProfile(
            user_id="user-123",
            purposeProfile=PurposeProfile(
                personal_purpose="Help communities access clean water",
                professional_goal="Become a water systems engineer",
                community_impact="Build sustainable water infrastructure",
                values=Values(
                    core=["sustainability", "community impact"],
                    secondary=["innovation", "education"],
                    weights={"sustainability": 0.4, "community impact": 0.4, "innovation": 0.2}
                ),
                skills=Skills(
                    technical=[
                        Skill(name="engineering", level=SkillLevel.ADVANCED, years_experience=5),
                        Skill(name="project management", level=SkillLevel.INTERMEDIATE, years_experience=3)
                    ],
                    soft=[
                        Skill(name="communication", level=SkillLevel.ADVANCED, years_experience=8)
                    ],
                    leadership=[
                        Skill(name="team leadership", level=SkillLevel.INTERMEDIATE, years_experience=4)
                    ]
                ),
                workStyle=WorkStyle(
                    collaboration=WorkStylePreference.HIGH,
                    autonomy=WorkStylePreference.MEDIUM,
                    structure=StructurePreference.MODERATE,
                    communication=CommunicationStyle.SUPPORTIVE
                ),
                passions=["Clean Water Access", "Community Development"],
                mission_statement="To leverage technology for sustainable community development and clean water access.",
                impact_areas=["Water Access", "Technology Transfer"]
            ),
            confidenceScore=85,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    @pytest.fixture
    def matching_agent(self, mock_bedrock):
        """Matching agent instance for testing"""
        return MatchingAgent(
            bedrock_client=mock_bedrock,
            opensearch_endpoint="localhost:9200"
        )

    def test_agent_initialization(self, mock_bedrock):
        """Test agent initialization"""
        agent = MatchingAgent(bedrock_client=mock_bedrock)
        assert agent.bedrock == mock_bedrock
        assert agent.opensearch_index == "team-opportunities"
        assert agent.embedding_model_id == "amazon.titan-embed-text-v1"

    @patch('requests.post')
    def test_find_team_matches_success(self, mock_requests_post, matching_agent,
                                     sample_user_profile, mock_opensearch_response):
        """Test successful team matching"""
        # Mock OpenSearch response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_opensearch_response
        mock_requests_post.return_value = mock_response

        # Mock Claude response for explanation
        mock_claude_response = Mock()
        mock_claude_response.__getitem__ = Mock(return_value=Mock())
        mock_claude_response.__getitem__.return_value.read.return_value = json.dumps({
            "content": [{"text": "This team aligns perfectly with your passion for clean water access."}]
        })
        matching_agent.bedrock.invoke_model.return_value = mock_claude_response

        matches = matching_agent.find_team_matches(sample_user_profile, limit=2)

        assert len(matches) == 2
        assert matches[0].team_id == "team-123"
        assert matches[0].match_score.overall_score <= 1.0
        assert len(matches[0].match_reasons) == 3
        assert len(matches[0].recommended_actions) == 3

    @patch('requests.post')
    def test_find_team_matches_opensearch_error(self, mock_requests_post, matching_agent, sample_user_profile):
        """Test handling of OpenSearch errors"""
        mock_requests_post.side_effect = Exception("Connection failed")

        matches = matching_agent.find_team_matches(sample_user_profile)

        assert matches == []

    def test_generate_profile_embedding_success(self, matching_agent, sample_user_profile):
        """Test successful profile embedding generation"""
        embedding = matching_agent._generate_profile_embedding(sample_user_profile)

        assert isinstance(embedding, list)
        assert len(embedding) == 5  # Mock returns 5 values

    def test_generate_profile_embedding_error(self, matching_agent):
        """Test handling of embedding generation errors"""
        # Create a minimal valid UserProfile
        profile = UserProfile(
            user_id="test",
            purpose_profile=PurposeProfile(
                personal_purpose="Test purpose",
                professional_goal="Test goal",
                community_impact="Test impact",
                values=Values(core=["test"]),
                skills=Skills(technical=[], soft=[], leadership=[]),
                work_style=WorkStyle(
                    collaboration=WorkStylePreference.MEDIUM,
                    autonomy=WorkStylePreference.MEDIUM,
                    structure=StructurePreference.MODERATE,
                    communication=CommunicationStyle.SUPPORTIVE
                ),
                passions=["Test passion"],
                mission_statement="Test mission",
                impact_areas=[]
            ),
            confidence_score=50
        )
        matching_agent.bedrock.invoke_model.side_effect = Exception("Bedrock error")

        embedding = matching_agent._generate_profile_embedding(profile)

        assert embedding == []

    def test_create_profile_text(self, matching_agent, sample_user_profile):
        """Test profile text creation"""
        text = matching_agent._create_profile_text(sample_user_profile)

        assert "Help communities access clean water" in text
        assert "engineering" in text
        assert "sustainability" in text
        assert "COLLABORATIVE" in text

    def test_create_profile_text_no_purpose_profile(self, matching_agent):
        """Test profile text creation without purpose profile"""
        # Create a profile with minimal purpose profile
        profile = UserProfile(
            user_id="test-user",
            purpose_profile=PurposeProfile(
                personal_purpose="",
                professional_goal="",
                community_impact="",
                values=Values(core=["test"]),
                skills=Skills(technical=[], soft=[], leadership=[]),
                workStyle=WorkStyle(
                    collaboration=WorkStylePreference.MEDIUM,
                    autonomy=WorkStylePreference.MEDIUM,
                    structure=StructurePreference.MODERATE,
                    communication=CommunicationStyle.SUPPORTIVE
                ),
                passions=["Test"],
                mission_statement="",
                impact_areas=[]
            ),
            confidence_score=50
        )
        text = matching_agent._create_profile_text(profile)

        assert "test-user" in text
        assert "seeking team opportunities" in text

    @patch('requests.post')
    def test_search_similar_teams_success(self, mock_requests_post, matching_agent, mock_opensearch_response):
        """Test successful team search"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_opensearch_response
        mock_requests_post.return_value = mock_response

        results = matching_agent._search_similar_teams([0.1, 0.2, 0.3], 2)

        assert len(results) == 2
        assert results[0]['_source']['team_id'] == "team-123"
        assert results[0]['_score'] == 8.5

    @patch('requests.post')
    def test_search_similar_teams_error(self, mock_requests_post, matching_agent):
        """Test handling of search errors"""
        mock_requests_post.side_effect = Exception("Search failed")

        results = matching_agent._search_similar_teams([0.1, 0.2, 0.3], 2)

        assert results == []

    @patch('requests.post')
    def test_search_similar_teams_bad_response(self, mock_requests_post, matching_agent):
        """Test handling of bad HTTP responses"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_requests_post.return_value = mock_response

        results = matching_agent._search_similar_teams([0.1, 0.2, 0.3], 2)

        assert results == []

    def test_generate_match_explanation_success(self, matching_agent, sample_user_profile):
        """Test successful explanation generation"""
        team_opportunity = {
            "team_name": "Clean Water Initiative",
            "mission": "Provide clean water worldwide",
            "description": "Building water systems",
            "required_skills": ["engineering"],
            "team_values": ["sustainability"]
        }

        # Mock Claude response
        mock_response = Mock()
        mock_response.__getitem__.return_value.read.return_value = json.dumps({
            "content": [{"text": "This team perfectly matches your engineering skills and passion for clean water."}]
        })
        matching_agent.bedrock.invoke_model.return_value = mock_response

        explanation = matching_agent._generate_match_explanation(sample_user_profile, team_opportunity, 8.5)

        assert "engineering skills" in explanation
        assert "clean water" in explanation

    def test_generate_match_explanation_error(self, matching_agent, sample_user_profile):
        """Test handling of explanation generation errors"""
        team_opportunity = {"team_name": "Test Team"}

        matching_agent.bedrock.invoke_model.side_effect = Exception("Claude error")

        explanation = matching_agent._generate_match_explanation(sample_user_profile, team_opportunity, 5.0)

        assert "aligns well with your skills" in explanation

    def test_call_claude_success(self, matching_agent):
        """Test successful Claude call"""
        mock_response = Mock()
        mock_response.__getitem__ = Mock(return_value=Mock())
        mock_response.__getitem__.return_value.read.return_value = json.dumps({
            "content": [{"text": "Test response from Claude"}]
        })
        matching_agent.bedrock.invoke_model.return_value = mock_response

        response = matching_agent._call_claude("Test prompt")

        assert response == "Test response from Claude"

    def test_call_claude_error(self, matching_agent):
        """Test handling of Claude call errors"""
        matching_agent.bedrock.invoke_model.side_effect = Exception("Bedrock error")

        response = matching_agent._call_claude("Test prompt")

        assert "Unable to generate detailed explanation" in response

    @patch('requests.post')
    def test_index_team_opportunity_success(self, mock_requests_post, matching_agent):
        """Test successful team opportunity indexing"""
        team_opportunity = TeamOpportunity(
            title="Test Team Opportunity",
            description="This is a comprehensive test description for the team opportunity that meets the minimum length requirements for validation.",
            requiredSkills=["skill1", "skill2"],
            teamSize=5,
            commitmentHours=10,
            impactArea="Technology",
            communityServed="Global",
            expectedImpact="Positive change",
            created_at=datetime.utcnow()
        )

        # Mock embedding response
        mock_embed_response = Mock()
        mock_embed_response.__getitem__ = Mock(return_value=Mock())
        mock_embed_response.__getitem__.return_value.read.return_value = json.dumps({
            "embedding": [0.1, 0.2, 0.3]
        })

        # Mock index response
        mock_index_response = Mock()
        mock_index_response.status_code = 201

        def mock_invoke_model(**kwargs):
            if "titan-embed" in kwargs.get("modelId", ""):
                return mock_embed_response
            return mock_index_response

        matching_agent.bedrock.invoke_model = mock_invoke_model
        mock_requests_post.return_value = mock_index_response

        success = matching_agent.index_team_opportunity(team_opportunity)

        assert success is True

    @patch('requests.post')
    def test_index_team_opportunity_error(self, mock_requests_post, matching_agent):
        """Test handling of indexing errors"""
        team_opportunity = TeamOpportunity(
            title="Test Team Opportunity",
            description="This is a comprehensive test description for the team opportunity that meets the minimum length requirements for validation.",
            requiredSkills=["skill1"],
            teamSize=3,
            commitmentHours=5,
            impactArea="Technology",
            communityServed="Local",
            expectedImpact="Positive change",
            created_at=datetime.utcnow()
        )

        matching_agent.bedrock.invoke_model.side_effect = Exception("Embedding error")

        success = matching_agent.index_team_opportunity(team_opportunity)

        assert success is False