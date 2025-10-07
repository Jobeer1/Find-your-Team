"""
Tests for Matching Agent RAG (Retrieval-Augmented Generation) capabilities
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import numpy as np
from models.core_models import (
    UserProfile, PurposeProfile, TeamOpportunity, Values, WorkStyle, Skills, Skill,
    SkillLevel, WorkStylePreference, CommunicationStyle, StructurePreference
)
from agents.matching_agent import MatchingAgent


class TestMatchingAgentRAG:
    """Test RAG-specific functionality of the Matching Agent"""

    @pytest.fixture
    def mock_bedrock_with_embeddings(self):
        """Mock Bedrock client with embedding responses"""
        mock_client = Mock()
        
        def mock_invoke_model(**kwargs):
            model_id = kwargs.get('modelId', '')
            
            if 'titan-embed' in model_id:
                # Mock embedding response
                mock_response = Mock()
                mock_response.__getitem__ = Mock(return_value=Mock())
                mock_response.__getitem__.return_value.read.return_value = json.dumps({
                    "embedding": [0.1, 0.2, 0.3, 0.4, 0.5] * 256  # Realistic embedding size
                })
                return mock_response
            elif 'claude' in model_id:
                # Mock Claude response
                mock_response = Mock()
                mock_response.__getitem__ = Mock(return_value=Mock())
                mock_response.__getitem__.return_value.read.return_value = json.dumps({
                    "content": [{"text": "This is an excellent match based on shared values and complementary skills."}]
                })
                return mock_response
            
        mock_client.invoke_model = mock_invoke_model
        return mock_client

    @pytest.fixture
    def matching_agent_rag(self, mock_bedrock_with_embeddings):
        """Matching agent with RAG capabilities"""
        return MatchingAgent(
            bedrock_client=mock_bedrock_with_embeddings,
            opensearch_endpoint="localhost:9200"
        )

    @pytest.fixture
    def comprehensive_user_profile(self):
        """Comprehensive user profile for RAG testing"""
        return UserProfile(
            user_id="rag-test-user",
            purpose_profile=PurposeProfile(
                values=Values(
                    core=["Environmental Sustainability", "Community Impact", "Innovation"],
                    secondary=["Education", "Technology", "Social Justice"],
                    weights={
                        "Environmental Sustainability": 0.4,
                        "Community Impact": 0.35,
                        "Innovation": 0.25
                    }
                ),
                work_style=WorkStyle(
                    collaboration=WorkStylePreference.HIGH,
                    autonomy=WorkStylePreference.MEDIUM,
                    structure=StructurePreference.MODERATE,
                    communication=CommunicationStyle.SUPPORTIVE,
                    remote_preference=0.7,
                    meeting_frequency=WorkStylePreference.MEDIUM
                ),
                skills=Skills(
                    technical=[
                        Skill(name="Environmental Engineering", level=SkillLevel.ADVANCED, years_experience=7),
                        Skill(name="Data Analysis", level=SkillLevel.EXPERT, years_experience=10),
                        Skill(name="GIS Mapping", level=SkillLevel.INTERMEDIATE, years_experience=4),
                        Skill(name="Python Programming", level=SkillLevel.ADVANCED, years_experience=6)
                    ],
                    soft=[
                        Skill(name="Project Management", level=SkillLevel.ADVANCED, years_experience=8),
                        Skill(name="Cross-cultural Communication", level=SkillLevel.EXPERT, years_experience=12),
                        Skill(name="Stakeholder Engagement", level=SkillLevel.ADVANCED, years_experience=9)
                    ],
                    leadership=[
                        Skill(name="Team Leadership", level=SkillLevel.ADVANCED, years_experience=6),
                        Skill(name="Strategic Planning", level=SkillLevel.INTERMEDIATE, years_experience=4)
                    ]
                ),
                passions=[
                    "Clean Water Access", "Renewable Energy", "Community Development",
                    "Climate Change Mitigation", "Sustainable Agriculture"
                ],
                mission_statement="To leverage technology and engineering expertise for sustainable environmental solutions that empower communities and combat climate change.",
                impact_areas=["Water Access", "Renewable Energy", "Climate Resilience", "Community Empowerment"],
                availability_hours_per_week=25
            ),
            confidence_score=94
        )

    @pytest.fixture
    def diverse_team_opportunities(self):
        """Diverse set of team opportunities for RAG testing"""
        return [
            TeamOpportunity(
                title="Global Clean Water Initiative",
                description="Developing innovative water purification systems for underserved communities worldwide. We combine cutting-edge technology with community-centered design to ensure sustainable access to clean drinking water.",
                required_skills=["Environmental Engineering", "Project Management", "Community Engagement"],
                preferred_skills=["Data Analysis", "GIS Mapping", "Cross-cultural Communication"],
                team_size=8,
                commitment_hours=20,
                impact_area="Water Access",
                community_served="Global - Rural Communities",
                expected_impact="Provide clean water access to 50,000 people within 2 years"
            ),
            TeamOpportunity(
                title="Urban Solar Energy Cooperative",
                description="Building community-owned solar energy systems in urban areas to reduce energy costs and carbon footprint. Focus on equitable energy access and community ownership models.",
                required_skills=["Renewable Energy Systems", "Community Organizing", "Financial Planning"],
                preferred_skills=["Data Analysis", "Policy Advocacy", "Project Management"],
                team_size=6,
                commitment_hours=15,
                impact_area="Renewable Energy",
                community_served="Urban Communities",
                expected_impact="Install 100 community solar systems, reducing energy costs by 40%"
            ),
            TeamOpportunity(
                title="Climate Resilience Education Platform",
                description="Creating educational resources and training programs to help communities adapt to climate change impacts. Combining scientific knowledge with local wisdom and practical solutions.",
                required_skills=["Climate Science", "Educational Design", "Community Training"],
                preferred_skills=["Digital Platform Development", "Multilingual Communication"],
                team_size=5,
                commitment_hours=12,
                impact_area="Climate Education",
                community_served="Vulnerable Communities",
                expected_impact="Train 1,000 community leaders in climate adaptation strategies"
            ),
            TeamOpportunity(
                title="Sustainable Agriculture Tech Hub",
                description="Developing precision agriculture technologies to help small-scale farmers increase yields while reducing environmental impact. Focus on affordable, locally-adaptable solutions.",
                required_skills=["Agricultural Engineering", "IoT Development", "Farmer Engagement"],
                preferred_skills=["Data Science", "Supply Chain Management"],
                team_size=7,
                commitment_hours=18,
                impact_area="Sustainable Agriculture",
                community_served="Small-scale Farmers",
                expected_impact="Increase crop yields by 30% while reducing water usage by 25%"
            )
        ]

    def test_comprehensive_profile_embedding_generation(self, matching_agent_rag, comprehensive_user_profile):
        """Test embedding generation for comprehensive user profile"""
        embedding = matching_agent_rag._generate_profile_embedding(comprehensive_user_profile)
        
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, (int, float)) for x in embedding)

    def test_profile_text_creation_comprehensive(self, matching_agent_rag, comprehensive_user_profile):
        """Test comprehensive profile text creation"""
        profile_text = matching_agent_rag._create_profile_text(comprehensive_user_profile)
        
        # Check that all major profile elements are included
        assert "Environmental Sustainability" in profile_text
        assert "Community Impact" in profile_text
        assert "Environmental Engineering" in profile_text
        assert "Clean Water Access" in profile_text
        assert "leverage technology and engineering" in profile_text
        assert "HIGH collaboration" in profile_text
        assert "Water Access" in profile_text

    @patch('requests.post')
    def test_semantic_search_functionality(self, mock_requests_post, matching_agent_rag):
        """Test semantic search with realistic OpenSearch responses"""
        # Mock realistic OpenSearch response with vector similarity scores
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "hits": {
                "total": {"value": 4},
                "hits": [
                    {
                        "_score": 1.85,  # High similarity
                        "_source": {
                            "team_id": "water-initiative-001",
                            "team_name": "Global Clean Water Initiative",
                            "description": "Developing water purification systems",
                            "required_skills": ["Environmental Engineering", "Project Management"],
                            "team_values": ["Environmental Sustainability", "Community Impact"],
                            "impact_area": "Water Access",
                            "community_served": "Global - Rural Communities"
                        }
                    },
                    {
                        "_score": 1.72,  # Good similarity
                        "_source": {
                            "team_id": "solar-coop-002",
                            "team_name": "Urban Solar Energy Cooperative",
                            "description": "Community-owned solar energy systems",
                            "required_skills": ["Renewable Energy Systems", "Community Organizing"],
                            "team_values": ["Environmental Sustainability", "Community Empowerment"],
                            "impact_area": "Renewable Energy"
                        }
                    },
                    {
                        "_score": 1.45,  # Moderate similarity
                        "_source": {
                            "team_id": "climate-edu-003",
                            "team_name": "Climate Resilience Education Platform",
                            "description": "Educational resources for climate adaptation",
                            "required_skills": ["Climate Science", "Educational Design"],
                            "team_values": ["Education", "Community Resilience"],
                            "impact_area": "Climate Education"
                        }
                    }
                ]
            }
        }
        mock_requests_post.return_value = mock_response
        
        # Test semantic search
        embedding = [0.1] * 1280  # Realistic embedding size
        results = matching_agent_rag._search_similar_teams(embedding, 5)
        
        assert len(results) == 3
        assert results[0]['_score'] == 1.85
        assert results[0]['_source']['team_id'] == "water-initiative-001"
        assert results[1]['_score'] == 1.72
        assert results[2]['_score'] == 1.45

    @patch('requests.post')
    def test_end_to_end_rag_matching(self, mock_requests_post, matching_agent_rag, 
                                   comprehensive_user_profile):
        """Test complete end-to-end RAG matching process"""
        # Mock OpenSearch response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "hits": {
                "hits": [
                    {
                        "_score": 1.85,
                        "_source": {
                            "team_id": "water-initiative-001",
                            "team_name": "Global Clean Water Initiative",
                            "description": "Developing innovative water purification systems",
                            "required_skills": ["Environmental Engineering", "Project Management", "Community Engagement"],
                            "team_values": ["Environmental Sustainability", "Community Impact"],
                            "impact_area": "Water Access",
                            "mission": "Provide clean water access to underserved communities"
                        }
                    }
                ]
            }
        }
        mock_requests_post.return_value = mock_response
        
        # Execute end-to-end matching
        matches = matching_agent_rag.find_team_matches(comprehensive_user_profile, limit=1)
        
        assert len(matches) == 1
        match = matches[0]
        
        # Verify match structure
        assert match.team_id == "water-initiative-001"
        assert match.user_id == comprehensive_user_profile.user_id
        assert isinstance(match.match_score.overall_score, float)
        assert 0.0 <= match.match_score.overall_score <= 1.0
        assert len(match.match_reasons) >= 1
        assert len(match.recommended_actions) >= 3
        
        # Verify high-quality match due to alignment
        assert match.match_score.skill_alignment > 0.6  # Should have good skill alignment
        assert match.match_score.value_alignment > 0.6  # Should have good value alignment

    def test_explainable_ai_summary_generation(self, matching_agent_rag, comprehensive_user_profile):
        """Test XAI summary generation with Claude"""
        team_data = {
            "team_name": "Global Clean Water Initiative",
            "mission": "Provide clean water access to underserved communities worldwide",
            "description": "Developing innovative water purification systems for rural communities",
            "required_skills": ["Environmental Engineering", "Project Management", "Community Engagement"],
            "team_values": ["Environmental Sustainability", "Community Impact", "Innovation"]
        }
        
        explanation = matching_agent_rag._generate_match_explanation(
            comprehensive_user_profile, team_data, 1.85
        )
        
        assert isinstance(explanation, str)
        assert len(explanation) > 50  # Should be substantial explanation
        # Should mention key alignment factors
        assert any(keyword in explanation.lower() for keyword in 
                  ["match", "align", "skill", "value", "experience"])

    @patch('requests.put')
    def test_team_opportunity_indexing(self, mock_requests_put, matching_agent_rag, diverse_team_opportunities):
        """Test indexing team opportunities with embeddings"""
        # Mock successful indexing response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_requests_put.return_value = mock_response
        
        # Test indexing first opportunity
        opportunity = diverse_team_opportunities[0]
        success = matching_agent_rag.index_team_opportunity(opportunity)
        
        assert success is True
        
        # Verify the request was made with correct data
        mock_requests_put.assert_called_once()
        call_args = mock_requests_put.call_args
        
        # Check URL
        expected_url = f"http://localhost:9200/team-opportunities/_doc/{opportunity.opportunity_id}"
        assert call_args[1]['url'] == expected_url
        
        # Check document structure
        doc = call_args[1]['json']
        assert doc['team_id'] == opportunity.opportunity_id
        assert doc['team_name'] == opportunity.title
        assert doc['description'] == opportunity.description
        assert doc['required_skills'] == opportunity.required_skills
        assert doc['impact_area'] == opportunity.impact_area
        assert 'embedding' in doc
        assert isinstance(doc['embedding'], list)

    def test_opportunity_text_creation_comprehensive(self, matching_agent_rag, diverse_team_opportunities):
        """Test comprehensive opportunity text creation for embedding"""
        opportunity = diverse_team_opportunities[0]  # Global Clean Water Initiative
        
        text = matching_agent_rag._create_opportunity_text(opportunity)
        
        # Verify all key elements are included
        assert "Global Clean Water Initiative" in text
        assert "water purification systems" in text
        assert "Environmental Engineering" in text
        assert "Project Management" in text
        assert "Water Access" in text
        assert "Global - Rural Communities" in text
        assert "8 members" in text
        assert "20 hours" in text

    def test_compatibility_scoring_algorithm(self, matching_agent_rag, comprehensive_user_profile):
        """Test detailed compatibility scoring algorithm"""
        # High compatibility team
        high_compat_team = {
            "team_id": "high-compat",
            "required_skills": ["Environmental Engineering", "Data Analysis", "Project Management"],
            "team_values": ["Environmental Sustainability", "Community Impact", "Innovation"],
            "impact_area": "Water Access"
        }
        
        # Low compatibility team
        low_compat_team = {
            "team_id": "low-compat", 
            "required_skills": ["Marketing", "Sales", "Business Development"],
            "team_values": ["Profit Maximization", "Market Dominance"],
            "impact_area": "Financial Services"
        }
        
        high_score = matching_agent_rag._calculate_compatibility_score(
            comprehensive_user_profile, high_compat_team, 8.5
        )
        
        low_score = matching_agent_rag._calculate_compatibility_score(
            comprehensive_user_profile, low_compat_team, 3.2
        )
        
        # High compatibility should score significantly higher
        assert high_score.overall_score > low_score.overall_score
        assert high_score.skill_alignment > low_score.skill_alignment
        assert high_score.value_alignment > low_score.value_alignment
        assert high_score.purpose_alignment > low_score.purpose_alignment
        
        # High compatibility should have good scores across dimensions
        assert high_score.skill_alignment > 0.6
        assert high_score.value_alignment > 0.6
        assert high_score.purpose_alignment > 0.6

    def test_match_ranking_and_recommendation_system(self, matching_agent_rag, comprehensive_user_profile):
        """Test opportunity ranking and recommendation system"""
        # Create multiple team opportunities with different compatibility levels
        teams_data = [
            {
                "team_id": "perfect-match",
                "team_name": "Perfect Environmental Team",
                "required_skills": ["Environmental Engineering", "Data Analysis"],
                "team_values": ["Environmental Sustainability", "Community Impact"],
                "impact_area": "Water Access",
                "description": "Exactly matches user profile"
            },
            {
                "team_id": "good-match", 
                "team_name": "Good Environmental Team",
                "required_skills": ["Environmental Engineering"],
                "team_values": ["Environmental Sustainability"],
                "impact_area": "Renewable Energy",
                "description": "Good but not perfect match"
            },
            {
                "team_id": "poor-match",
                "team_name": "Unrelated Team",
                "required_skills": ["Marketing"],
                "team_values": ["Profit"],
                "impact_area": "Finance",
                "description": "Poor match for user"
            }
        ]
        
        # Calculate scores for all teams
        scores = []
        for team_data in teams_data:
            score = matching_agent_rag._calculate_compatibility_score(
                comprehensive_user_profile, team_data, 7.0
            )
            scores.append((team_data["team_id"], score.overall_score))
        
        # Sort by score (descending)
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Verify ranking order
        assert scores[0][0] == "perfect-match"  # Should rank highest
        assert scores[1][0] == "good-match"     # Should rank second
        assert scores[2][0] == "poor-match"     # Should rank lowest
        
        # Verify score differences are meaningful
        assert scores[0][1] > scores[1][1] > scores[2][1]

    def test_rag_performance_with_large_dataset(self, matching_agent_rag):
        """Test RAG performance considerations with larger datasets"""
        # Simulate processing multiple embeddings
        embeddings = [[0.1 + i*0.01] * 1280 for i in range(100)]
        
        # Test embedding generation doesn't fail with multiple calls
        for i, embedding in enumerate(embeddings[:5]):  # Test first 5
            text = f"Test opportunity {i} with various skills and impact areas"
            result_embedding = matching_agent_rag._generate_text_embedding(text)
            assert isinstance(result_embedding, list)

    def test_match_explanation_quality_metrics(self, matching_agent_rag, comprehensive_user_profile):
        """Test quality metrics for match explanations"""
        team_data = {
            "team_name": "Environmental Innovation Lab",
            "mission": "Develop breakthrough environmental technologies",
            "description": "Research and development of sustainable solutions",
            "required_skills": ["Environmental Engineering", "Research", "Innovation"],
            "team_values": ["Environmental Sustainability", "Innovation", "Scientific Rigor"]
        }
        
        explanation = matching_agent_rag._generate_match_explanation(
            comprehensive_user_profile, team_data, 8.7
        )
        
        # Quality checks for explanation
        assert len(explanation) >= 50  # Substantial content
        assert len(explanation.split()) >= 10  # Multiple words
        
        # Should mention relevant concepts
        explanation_lower = explanation.lower()
        quality_indicators = [
            any(skill_word in explanation_lower for skill_word in 
                ["engineering", "environmental", "skill", "experience"]),
            any(value_word in explanation_lower for value_word in 
                ["sustainability", "innovation", "value", "align"]),
            any(match_word in explanation_lower for match_word in 
                ["match", "fit", "compatible", "suitable"])
        ]
        
        # At least 2 out of 3 quality indicators should be present
        assert sum(quality_indicators) >= 2