"""
Tests for the Matching Agent with RAG capabilities
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

    def test_calculate_compatibility_score_comprehensive(self, matching_agent, sample_user_profile):
        """Test comprehensive compatibility score calculation"""
        team_data = {
            "team_id": "test-team",
            "team_name": "Environmental Tech Team",
            "required_skills": ["engineering", "project management"],
            "team_values": ["sustainability", "community impact"],
            "impact_area": "Water Access"
        }
        
        match_score = matching_agent._calculate_compatibility_score(
            sample_user_profile, team_data, 8.5
        )
        
        assert isinstance(match_score, MatchScore)
        assert 0.0 <= match_score.overall_score <= 1.0
        assert 0.0 <= match_score.skill_alignment <= 1.0
        assert 0.0 <= match_score.value_alignment <= 1.0
        assert match_score.skill_alignment > 0.5  # Should have good skill alignment
        assert match_score.value_alignment > 0.5  # Should have good value alignment

    def test_generate_match_reasons_comprehensive(self, matching_agent, sample_user_profile):
        """Test comprehensive match reason generation"""
        team_data = {
            "team_name": "Clean Water Initiative",
            "required_skills": ["engineering", "project management"],
            "team_values": ["sustainability", "community impact"],
            "impact_area": "Water Access"
        }
        
        match_score = MatchScore(
            overallScore=0.85,
            skillAlignment=0.8,
            valueAlignment=0.9,
            workStyleCompatibility=0.7,
            purposeAlignment=0.8
        )
        
        reasons = matching_agent._generate_match_reasons(sample_user_profile, team_data, match_score)
        
        assert len(reasons) >= 1
        assert all(isinstance(reason, MatchReason) for reason in reasons)
        assert all(0.0 <= reason.weight <= 1.0 for reason in reasons)
        
        # Check that high-scoring aspects generate reasons
        reason_types = [reason.reason_type for reason in reasons]
        assert "skills" in reason_types  # Should have skill reason due to high alignment
        assert "values" in reason_types  # Should have value reason due to high alignment

    def test_generate_recommended_actions_with_skill_gaps(self, matching_agent, sample_user_profile):
        """Test recommended action generation with skill gaps"""
        team_data = {
            "team_name": "AI Research Team",
            "required_skills": ["machine learning", "data science", "python programming"],
            "team_values": ["innovation", "research"]
        }
        
        actions = matching_agent._generate_recommended_actions(sample_user_profile, team_data)
        
        assert len(actions) >= 3
        assert any("Review" in action for action in actions)
        assert any("Connect" in action for action in actions)
        assert any("Consider developing skills" in action for action in actions)

    def test_create_opportunity_text(self, matching_agent):
        """Test opportunity text creation for embedding"""
        team_opportunity = TeamOpportunity(
            title="Environmental Conservation Team",
            description="Working on sustainable solutions for environmental challenges",
            requiredSkills=["environmental science", "project management"],
            preferredSkills=["data analysis"],
            teamSize=5,
            commitmentHours=15,
            impactArea="Environment",
            communityServed="Global",
            expectedImpact="Reduce carbon footprint by 20%",
            created_at=datetime.utcnow()
        )
        
        text = matching_agent._create_opportunity_text(team_opportunity)
        
        assert "Environmental Conservation Team" in text
        assert "environmental science" in text
        assert "Environment" in text
        assert "5 members" in text
        assert "15 hours" in text

    @patch('requests.post')
    def test_search_similar_teams_with_filters(self, mock_requests_post, matching_agent):
        """Test team search with various filter scenarios"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "hits": {
                "hits": [
                    {
                        "_score": 9.2,
                        "_source": {
                            "team_id": "high-match-team",
                            "team_name": "Perfect Match Team",
                            "impact_area": "Technology"
                        }
                    }
                ]
            }
        }
        mock_requests_post.return_value = mock_response
        
        results = matching_agent._search_similar_teams([0.1, 0.2, 0.3], 5)
        
        assert len(results) == 1
        assert results[0]['_score'] == 9.2
        assert results[0]['_source']['team_id'] == "high-match-team"

    def test_get_match_analytics(self, matching_agent):
        """Test match analytics functionality"""
        analytics = matching_agent.get_match_analytics("test-user", 30)
        
        assert analytics["user_id"] == "test-user"
        assert analytics["period_days"] == 30
        assert "total_matches_found" in analytics
        assert "average_match_score" in analytics
        assert "recommendation_accuracy" in analytics
        assert isinstance(analytics["top_match_categories"], list)

    def test_generate_text_embedding_success(self, matching_agent):
        """Test successful text embedding generation"""
        # Mock successful embedding response
        mock_response = Mock()
        mock_response.__getitem__ = Mock(return_value=Mock())
        mock_response.__getitem__.return_value.read.return_value = json.dumps({
            "embedding": [0.1, 0.2, 0.3, 0.4, 0.5]
        })
        matching_agent.bedrock.invoke_model.return_value = mock_response
        
        embedding = matching_agent._generate_text_embedding("Test text for embedding")
        
        assert isinstance(embedding, list)
        assert len(embedding) == 5
        assert all(isinstance(x, float) for x in embedding)

    def test_generate_text_embedding_error(self, matching_agent):
        """Test text embedding generation error handling"""
        matching_agent.bedrock.invoke_model.side_effect = Exception("Bedrock error")
        
        embedding = matching_agent._generate_text_embedding("Test text")
        
        assert embedding == []

    def test_compatibility_score_edge_cases(self, matching_agent):
        """Test compatibility score calculation with edge cases"""
        # Create minimal user profile
        minimal_profile = UserProfile(
            user_id="minimal-user",
            purpose_profile=PurposeProfile(
                values=Values(core=["test"]),
                work_style=WorkStyle(),
                skills=Skills(),
                passions=["testing"]
            ),
            confidence_score=50
        )
        
        # Test with empty team data
        empty_team_data = {}
        
        match_score = matching_agent._calculate_compatibility_score(
            minimal_profile, empty_team_data, 5.0
        )
        
        assert isinstance(match_score, MatchScore)
        assert 0.0 <= match_score.overall_score <= 1.0

    def test_match_explanation_fallback(self, matching_agent, sample_user_profile):
        """Test match explanation with Claude service unavailable"""
        team_data = {
            "team_name": "Test Team",
            "mission": "Test mission",
            "description": "Test description"
        }
        
        # Mock Claude failure
        matching_agent.bedrock.invoke_model.side_effect = Exception("Service unavailable")
        
        explanation = matching_agent._generate_match_explanation(
            sample_user_profile, team_data, 7.5
        )
        
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert "7.5" in explanation or "compatibility" in explanation.lower()

    @patch('requests.post')
    def test_find_team_matches_no_results(self, mock_requests_post, matching_agent, sample_user_profile):
        """Test team matching when no results are found"""
        # Mock empty OpenSearch response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"hits": {"hits": []}}
        mock_requests_post.return_value = mock_response
        
        matches = matching_agent.find_team_matches(sample_user_profile)
        
        assert matches == []

    @patch('requests.post')
    def test_find_team_matches_service_error(self, mock_requests_post, matching_agent, sample_user_profile):
        """Test team matching when services are unavailable"""
        # Mock embedding generation failure
        matching_agent.bedrock.invoke_model.side_effect = Exception("Bedrock unavailable")
        
        matches = matching_agent.find_team_matches(sample_user_profile)
        
        assert matches == []

    def test_match_reasons_fallback(self, matching_agent, sample_user_profile):
        """Test match reason generation fallback behavior"""
        team_data = {"team_name": "Test Team"}
        
        # Create low-scoring match
        low_match_score = MatchScore(
            overallScore=0.3,
            skillAlignment=0.2,
            valueAlignment=0.1,
            workStyleCompatibility=0.4,
            purposeAlignment=0.2
        )
        
        reasons = matching_agent._generate_match_reasons(sample_user_profile, team_data, low_match_score)
        
        # Should still generate at least one reason
        assert len(reasons) >= 1
        assert reasons[0].reason_type == "general"