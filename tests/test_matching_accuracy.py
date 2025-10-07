"""
Tests for Matching Agent accuracy and explanation quality
"""

import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime
import statistics
from models.core_models import (
    UserProfile, PurposeProfile, Values, WorkStyle, Skills, Skill,
    SkillLevel, WorkStylePreference, CommunicationStyle, StructurePreference
)
from agents.matching_agent import MatchingAgent


class TestMatchingAccuracy:
    """Test matching accuracy and explanation quality metrics"""

    @pytest.fixture
    def mock_bedrock_accurate(self):
        """Mock Bedrock client with consistent responses for accuracy testing"""
        mock_client = Mock()
        
        def mock_invoke_model(**kwargs):
            model_id = kwargs.get('modelId', '')
            body = json.loads(kwargs.get('body', '{}'))
            
            if 'titan-embed' in model_id:
                # Generate deterministic embeddings based on input text
                input_text = body.get('inputText', '')
                # Simple hash-based embedding for consistency
                embedding = [(hash(input_text + str(i)) % 1000) / 1000.0 for i in range(1280)]
                
                mock_response = Mock()
                mock_response.__getitem__ = Mock(return_value=Mock())
                mock_response.__getitem__.return_value.read.return_value = json.dumps({
                    "embedding": embedding
                })
                return mock_response
                
            elif 'claude' in model_id:
                # Generate contextual explanations based on prompt content
                messages = body.get('messages', [])
                prompt = messages[0].get('content', '') if messages else ''
                
                # Extract key information from prompt for contextual response
                if 'water' in prompt.lower():
                    explanation = "This team perfectly aligns with your environmental engineering expertise and passion for clean water access. Your advanced skills in environmental engineering and data analysis make you an ideal candidate for this water purification initiative."
                elif 'solar' in prompt.lower() or 'energy' in prompt.lower():
                    explanation = "Your environmental sustainability values and technical skills create excellent synergy with this renewable energy project. The team's focus on community empowerment matches your collaborative work style."
                elif 'education' in prompt.lower():
                    explanation = "Your cross-cultural communication expertise and passion for community development align well with this educational initiative. Your project management skills would be valuable for scaling impact."
                else:
                    explanation = "This opportunity offers strong alignment with your values and skills, providing excellent potential for meaningful impact and professional growth."
                
                mock_response = Mock()
                mock_response.__getitem__ = Mock(return_value=Mock())
                mock_response.__getitem__.return_value.read.return_value = json.dumps({
                    "content": [{"text": explanation}]
                })
                return mock_response
        
        mock_client.invoke_model = mock_invoke_model
        return mock_client

    @pytest.fixture
    def matching_agent_accurate(self, mock_bedrock_accurate):
        """Matching agent configured for accuracy testing"""
        return MatchingAgent(
            bedrock_client=mock_bedrock_accurate,
            opensearch_endpoint="localhost:9200"
        )

    @pytest.fixture
    def test_user_profiles(self):
        """Diverse user profiles for accuracy testing"""
        return [
            # Environmental Engineer Profile
            UserProfile(
                user_id="env-engineer-001",
                purpose_profile=PurposeProfile(
                    values=Values(
                        core=["Environmental Sustainability", "Community Impact", "Innovation"],
                        weights={"Environmental Sustainability": 0.5, "Community Impact": 0.3, "Innovation": 0.2}
                    ),
                    work_style=WorkStyle(
                        collaboration=WorkStylePreference.HIGH,
                        autonomy=WorkStylePreference.MEDIUM,
                        communication=CommunicationStyle.SUPPORTIVE
                    ),
                    skills=Skills(
                        technical=[
                            Skill(name="Environmental Engineering", level=SkillLevel.EXPERT, years_experience=10),
                            Skill(name="Water Systems Design", level=SkillLevel.ADVANCED, years_experience=8),
                            Skill(name="Data Analysis", level=SkillLevel.ADVANCED, years_experience=6)
                        ],
                        soft=[
                            Skill(name="Project Management", level=SkillLevel.ADVANCED, years_experience=7),
                            Skill(name="Community Engagement", level=SkillLevel.EXPERT, years_experience=12)
                        ]
                    ),
                    passions=["Clean Water Access", "Sustainable Development", "Climate Action"],
                    mission_statement="To provide clean water access to underserved communities through innovative engineering solutions.",
                    impact_areas=["Water Access", "Environmental Protection"]
                ),
                confidence_score=95
            ),
            
            # Software Developer Profile
            UserProfile(
                user_id="software-dev-001",
                purpose_profile=PurposeProfile(
                    values=Values(
                        core=["Innovation", "Education", "Technology for Good"],
                        weights={"Innovation": 0.4, "Education": 0.35, "Technology for Good": 0.25}
                    ),
                    work_style=WorkStyle(
                        collaboration=WorkStylePreference.MEDIUM,
                        autonomy=WorkStylePreference.HIGH,
                        communication=CommunicationStyle.DIRECT
                    ),
                    skills=Skills(
                        technical=[
                            Skill(name="Python Programming", level=SkillLevel.EXPERT, years_experience=8),
                            Skill(name="Machine Learning", level=SkillLevel.ADVANCED, years_experience=5),
                            Skill(name="Web Development", level=SkillLevel.ADVANCED, years_experience=6)
                        ],
                        soft=[
                            Skill(name="Problem Solving", level=SkillLevel.EXPERT, years_experience=10),
                            Skill(name="Technical Writing", level=SkillLevel.ADVANCED, years_experience=7)
                        ]
                    ),
                    passions=["Educational Technology", "Open Source", "AI for Social Good"],
                    mission_statement="To democratize access to quality education through innovative technology solutions.",
                    impact_areas=["Education Technology", "Digital Literacy"]
                ),
                confidence_score=88
            ),
            
            # Community Organizer Profile
            UserProfile(
                user_id="community-org-001",
                purpose_profile=PurposeProfile(
                    values=Values(
                        core=["Social Justice", "Community Empowerment", "Equity"],
                        weights={"Social Justice": 0.4, "Community Empowerment": 0.35, "Equity": 0.25}
                    ),
                    work_style=WorkStyle(
                        collaboration=WorkStylePreference.HIGH,
                        autonomy=WorkStylePreference.LOW,
                        communication=CommunicationStyle.SUPPORTIVE
                    ),
                    skills=Skills(
                        soft=[
                            Skill(name="Community Organizing", level=SkillLevel.EXPERT, years_experience=12),
                            Skill(name="Public Speaking", level=SkillLevel.ADVANCED, years_experience=10),
                            Skill(name="Conflict Resolution", level=SkillLevel.ADVANCED, years_experience=8)
                        ],
                        leadership=[
                            Skill(name="Grassroots Leadership", level=SkillLevel.EXPERT, years_experience=15),
                            Skill(name="Coalition Building", level=SkillLevel.ADVANCED, years_experience=9)
                        ]
                    ),
                    passions=["Social Justice", "Community Development", "Policy Advocacy"],
                    mission_statement="To build powerful grassroots movements that create lasting social change and community empowerment.",
                    impact_areas=["Social Justice", "Community Organizing", "Policy Change"]
                ),
                confidence_score=92
            )
        ]

    @pytest.fixture
    def ground_truth_matches(self):
        """Ground truth matches for accuracy evaluation"""
        return {
            "env-engineer-001": [
                {
                    "team_id": "water-initiative",
                    "expected_score_range": (0.85, 1.0),
                    "primary_reasons": ["skills", "values", "purpose"],
                    "explanation_keywords": ["water", "engineering", "environmental", "community"]
                },
                {
                    "team_id": "climate-resilience",
                    "expected_score_range": (0.75, 0.90),
                    "primary_reasons": ["values", "purpose"],
                    "explanation_keywords": ["climate", "sustainability", "impact"]
                }
            ],
            "software-dev-001": [
                {
                    "team_id": "education-platform",
                    "expected_score_range": (0.80, 0.95),
                    "primary_reasons": ["skills", "values", "purpose"],
                    "explanation_keywords": ["education", "technology", "programming", "innovation"]
                },
                {
                    "team_id": "ai-social-good",
                    "expected_score_range": (0.75, 0.90),
                    "primary_reasons": ["skills", "values"],
                    "explanation_keywords": ["ai", "machine learning", "social good"]
                }
            ],
            "community-org-001": [
                {
                    "team_id": "social-justice-coalition",
                    "expected_score_range": (0.85, 1.0),
                    "primary_reasons": ["values", "skills", "purpose"],
                    "explanation_keywords": ["social justice", "community", "organizing", "empowerment"]
                }
            ]
        }

    @patch('requests.post')
    def test_matching_accuracy_metrics(self, mock_requests_post, matching_agent_accurate, 
                                     test_user_profiles, ground_truth_matches):
        """Test overall matching accuracy against ground truth"""
        accuracy_scores = []
        
        for user_profile in test_user_profiles:
            user_id = user_profile.user_id
            expected_matches = ground_truth_matches.get(user_id, [])
            
            if not expected_matches:
                continue
                
            # Mock OpenSearch responses for this user
            mock_hits = []
            for i, expected_match in enumerate(expected_matches):
                mock_hits.append({
                    "_score": 8.5 - i * 0.5,  # Decreasing scores
                    "_source": {
                        "team_id": expected_match["team_id"],
                        "team_name": f"Team {expected_match['team_id']}",
                        "description": f"Description for {expected_match['team_id']}",
                        "required_skills": ["skill1", "skill2"],
                        "team_values": ["value1", "value2"],
                        "impact_area": "Test Impact Area"
                    }
                })
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"hits": {"hits": mock_hits}}
            mock_requests_post.return_value = mock_response
            
            # Get matches from agent
            matches = matching_agent_accurate.find_team_matches(user_profile, limit=len(expected_matches))
            
            # Calculate accuracy for this user
            user_accuracy = self._calculate_user_accuracy(matches, expected_matches)
            accuracy_scores.append(user_accuracy)
        
        # Overall accuracy metrics
        if accuracy_scores:
            overall_accuracy = statistics.mean(accuracy_scores)
            accuracy_std = statistics.stdev(accuracy_scores) if len(accuracy_scores) > 1 else 0
            
            # Accuracy should be reasonably high
            assert overall_accuracy >= 0.7, f"Overall accuracy {overall_accuracy:.2f} below threshold"
            assert accuracy_std <= 0.3, f"Accuracy variance {accuracy_std:.2f} too high"

    def _calculate_user_accuracy(self, actual_matches, expected_matches):
        """Calculate accuracy score for a single user's matches"""
        if not actual_matches or not expected_matches:
            return 0.0
        
        accuracy_components = []
        
        for i, expected in enumerate(expected_matches):
            if i < len(actual_matches):
                actual = actual_matches[i]
                
                # Score range accuracy
                expected_min, expected_max = expected["expected_score_range"]
                actual_score = actual.match_score.overall_score
                score_accuracy = 1.0 if expected_min <= actual_score <= expected_max else 0.5
                
                # Reason accuracy
                expected_reasons = set(expected["primary_reasons"])
                actual_reasons = set(reason.reason_type for reason in actual.match_reasons)
                reason_overlap = len(expected_reasons.intersection(actual_reasons))
                reason_accuracy = reason_overlap / len(expected_reasons)
                
                # Combined accuracy for this match
                match_accuracy = (score_accuracy + reason_accuracy) / 2
                accuracy_components.append(match_accuracy)
        
        return statistics.mean(accuracy_components) if accuracy_components else 0.0

    def test_explanation_quality_metrics(self, matching_agent_accurate, test_user_profiles):
        """Test quality metrics for match explanations"""
        quality_scores = []
        
        for user_profile in test_user_profiles:
            # Test explanation generation
            team_data = {
                "team_name": "Test Team for Quality",
                "mission": "Quality testing mission",
                "description": "Testing explanation quality",
                "required_skills": ["skill1", "skill2"],
                "team_values": ["value1", "value2"]
            }
            
            explanation = matching_agent_accurate._generate_match_explanation(
                user_profile, team_data, 8.0
            )
            
            # Quality metrics
            quality_score = self._calculate_explanation_quality(explanation, user_profile, team_data)
            quality_scores.append(quality_score)
        
        # Overall quality should be good
        avg_quality = statistics.mean(quality_scores)
        assert avg_quality >= 0.7, f"Average explanation quality {avg_quality:.2f} below threshold"

    def _calculate_explanation_quality(self, explanation, user_profile, team_data):
        """Calculate quality score for an explanation"""
        if not explanation or len(explanation) < 20:
            return 0.0
        
        quality_components = []
        
        # Length appropriateness (not too short, not too long)
        length_score = 1.0 if 50 <= len(explanation) <= 500 else 0.5
        quality_components.append(length_score)
        
        # Relevance to user profile
        user_keywords = (
            user_profile.purpose_profile.passions +
            user_profile.purpose_profile.values.core +
            [skill.name.lower() for skill in user_profile.purpose_profile.skills.all_skills[:3]]
        )
        
        explanation_lower = explanation.lower()
        relevance_matches = sum(1 for keyword in user_keywords 
                              if any(word in explanation_lower for word in keyword.lower().split()))
        relevance_score = min(1.0, relevance_matches / max(1, len(user_keywords) * 0.3))
        quality_components.append(relevance_score)
        
        # Positive tone and encouragement
        positive_indicators = ["excellent", "perfect", "great", "ideal", "strong", "good", "well"]
        positive_count = sum(1 for indicator in positive_indicators if indicator in explanation_lower)
        tone_score = min(1.0, positive_count / 2)  # Expect at least 2 positive indicators
        quality_components.append(tone_score)
        
        # Specificity (mentions specific skills, values, or outcomes)
        specific_indicators = ["skill", "experience", "value", "align", "match", "opportunity"]
        specific_count = sum(1 for indicator in specific_indicators if indicator in explanation_lower)
        specificity_score = min(1.0, specific_count / 3)  # Expect at least 3 specific terms
        quality_components.append(specificity_score)
        
        return statistics.mean(quality_components)

    def test_consistency_across_similar_profiles(self, matching_agent_accurate):
        """Test that similar profiles get consistent match scores"""
        # Create two very similar profiles
        base_profile_data = {
            "values": Values(core=["Innovation", "Education"], weights={"Innovation": 0.6, "Education": 0.4}),
            "work_style": WorkStyle(collaboration=WorkStylePreference.HIGH),
            "skills": Skills(technical=[Skill(name="Programming", level=SkillLevel.ADVANCED, years_experience=5)]),
            "passions": ["Technology", "Learning"],
            "mission_statement": "To use technology for educational impact",
            "impact_areas": ["Education Technology"]
        }
        
        profile1 = UserProfile(
            user_id="similar-1",
            purpose_profile=PurposeProfile(**base_profile_data),
            confidence_score=90
        )
        
        profile2 = UserProfile(
            user_id="similar-2", 
            purpose_profile=PurposeProfile(**base_profile_data),
            confidence_score=92  # Slightly different confidence
        )
        
        # Same team data
        team_data = {
            "team_id": "consistency-test",
            "required_skills": ["Programming", "Education"],
            "team_values": ["Innovation", "Education"],
            "impact_area": "Education Technology"
        }
        
        # Calculate scores for both profiles
        score1 = matching_agent_accurate._calculate_compatibility_score(profile1, team_data, 8.0)
        score2 = matching_agent_accurate._calculate_compatibility_score(profile2, team_data, 8.0)
        
        # Scores should be very similar (within 5% difference)
        score_diff = abs(score1.overall_score - score2.overall_score)
        assert score_diff <= 0.05, f"Score difference {score_diff:.3f} too large for similar profiles"

    def test_discrimination_across_different_profiles(self, matching_agent_accurate):
        """Test that different profiles get appropriately different match scores"""
        # Create very different profiles
        tech_profile = UserProfile(
            user_id="tech-focused",
            purpose_profile=PurposeProfile(
                values=Values(core=["Innovation", "Technology"]),
                work_style=WorkStyle(collaboration=WorkStylePreference.LOW),
                skills=Skills(technical=[Skill(name="Programming", level=SkillLevel.EXPERT, years_experience=10)]),
                passions=["Software Development", "AI"],
                mission_statement="To build cutting-edge technology solutions",
                impact_areas=["Technology Innovation"]
            ),
            confidence_score=95
        )
        
        social_profile = UserProfile(
            user_id="social-focused",
            purpose_profile=PurposeProfile(
                values=Values(core=["Social Justice", "Community"]),
                work_style=WorkStyle(collaboration=WorkStylePreference.HIGH),
                skills=Skills(soft=[Skill(name="Community Organizing", level=SkillLevel.EXPERT, years_experience=10)]),
                passions=["Social Change", "Advocacy"],
                mission_statement="To create social change through community organizing",
                impact_areas=["Social Justice"]
            ),
            confidence_score=93
        )
        
        # Tech-focused team
        tech_team = {
            "team_id": "tech-team",
            "required_skills": ["Programming", "Software Architecture"],
            "team_values": ["Innovation", "Technology"],
            "impact_area": "Technology Innovation"
        }
        
        # Social-focused team  
        social_team = {
            "team_id": "social-team",
            "required_skills": ["Community Organizing", "Advocacy"],
            "team_values": ["Social Justice", "Community"],
            "impact_area": "Social Justice"
        }
        
        # Calculate cross-compatibility scores
        tech_to_tech = matching_agent_accurate._calculate_compatibility_score(tech_profile, tech_team, 8.0)
        tech_to_social = matching_agent_accurate._calculate_compatibility_score(tech_profile, social_team, 8.0)
        social_to_social = matching_agent_accurate._calculate_compatibility_score(social_profile, social_team, 8.0)
        social_to_tech = matching_agent_accurate._calculate_compatibility_score(social_profile, tech_team, 8.0)
        
        # Same-domain matches should score higher than cross-domain matches
        assert tech_to_tech.overall_score > tech_to_social.overall_score, "Tech profile should match tech team better"
        assert social_to_social.overall_score > social_to_tech.overall_score, "Social profile should match social team better"
        
        # Differences should be meaningful (at least 20% difference)
        tech_diff = tech_to_tech.overall_score - tech_to_social.overall_score
        social_diff = social_to_social.overall_score - social_to_tech.overall_score
        
        assert tech_diff >= 0.2, f"Tech profile discrimination {tech_diff:.3f} too small"
        assert social_diff >= 0.2, f"Social profile discrimination {social_diff:.3f} too small"

    def test_match_reason_accuracy(self, matching_agent_accurate, test_user_profiles):
        """Test accuracy of match reason generation"""
        for user_profile in test_user_profiles:
            # High-compatibility team data
            team_data = {
                "team_id": "reason-test",
                "required_skills": [skill.name for skill in user_profile.purpose_profile.skills.all_skills[:2]],
                "team_values": user_profile.purpose_profile.values.core[:2],
                "impact_area": user_profile.purpose_profile.impact_areas[0] if user_profile.purpose_profile.impact_areas else "General"
            }
            
            # Calculate match score
            match_score = matching_agent_accurate._calculate_compatibility_score(user_profile, team_data, 8.5)
            
            # Generate reasons
            reasons = matching_agent_accurate._generate_match_reasons(user_profile, team_data, match_score)
            
            # Should have multiple reasons for high-compatibility match
            assert len(reasons) >= 2, "High-compatibility match should have multiple reasons"
            
            # Should include skills and values reasons for this setup
            reason_types = [reason.reason_type for reason in reasons]
            assert "skills" in reason_types, "Should include skills-based reason"
            assert "values" in reason_types, "Should include values-based reason"
            
            # Reason weights should be reasonable
            for reason in reasons:
                assert 0.0 <= reason.weight <= 1.0, f"Reason weight {reason.weight} out of range"
                assert len(reason.description) >= 10, "Reason description too short"

    def test_recommended_actions_relevance(self, matching_agent_accurate, test_user_profiles):
        """Test relevance and quality of recommended actions"""
        for user_profile in test_user_profiles:
            team_data = {
                "team_name": "Action Test Team",
                "required_skills": ["New Skill", "Another Skill"] + [skill.name for skill in user_profile.purpose_profile.skills.all_skills[:1]],
                "team_values": user_profile.purpose_profile.values.core
            }
            
            actions = matching_agent_accurate._generate_recommended_actions(user_profile, team_data)
            
            # Should have multiple actionable recommendations
            assert len(actions) >= 3, "Should provide multiple recommended actions"
            
            # Should include skill development for missing skills
            actions_text = " ".join(actions).lower()
            assert "skill" in actions_text or "develop" in actions_text, "Should mention skill development"
            
            # Should include team connection recommendations
            assert any("connect" in action.lower() or "team" in action.lower() for action in actions), "Should include team connection advice"
            
            # Actions should be specific and actionable
            for action in actions:
                assert len(action) >= 20, f"Action too short: {action}"
                assert not action.endswith('.'), "Actions should not end with period (formatting consistency)"