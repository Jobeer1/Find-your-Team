"""
Unit tests for core data models and validation functions
"""

import pytest
from datetime import datetime
from models.core_models import (
    UserProfile, PurposeProfile, TeamPerformance, MatchResult,
    Skill, Skills, Values, WorkStyle, TeamMetrics, TeamTrends,
    SkillLevel, WorkStylePreference, CommunicationStyle, StructurePreference,
    UserStatus, CoachingInsight, TeamOpportunity, MatchExplanation,
    validate_purpose_profile_completeness, calculate_profile_confidence,
    generate_sample_user_profile, generate_sample_team_performance
)


class TestPurposeProfileValidation:
    """Test validation functions for PurposeProfile"""

    def test_validate_complete_profile(self):
        """Test validation of a complete purpose profile"""
        profile = PurposeProfile(
            values=Values(core=["Innovation", "Community", "Sustainability"]),
            workStyle=WorkStyle(),
            skills=Skills(
                technical=[Skill(name="Python", level=SkillLevel.ADVANCED)],
                soft=[Skill(name="Communication", level=SkillLevel.EXPERT)],
                leadership=[Skill(name="Leadership", level=SkillLevel.INTERMEDIATE)]
            ),
            passions=["Technology", "Education"],
            mission_statement="To build sustainable tech solutions"
        )

        result = validate_purpose_profile_completeness(profile)

        assert result['has_core_values'] is True
        assert result['has_skills'] is True
        assert result['has_passions'] is True
        assert result['has_work_style'] is True
        assert result['has_mission'] is True

    def test_validate_incomplete_profile(self):
        """Test validation of an incomplete purpose profile"""
        profile = PurposeProfile(
            values=Values(core=["Innovation"]),  # Only 1 core value
            workStyle=WorkStyle(),
            skills=Skills(),  # No skills
            passions=["Technology"]  # Only 1 passion
        )

        result = validate_purpose_profile_completeness(profile)

        assert result['has_core_values'] is False  # Need >= 3
        assert result['has_skills'] is False  # Need >= 3
        assert result['has_passions'] is False  # Need >= 2
        assert result['has_work_style'] is True
        assert result['has_mission'] is False

    def test_calculate_profile_confidence_high(self):
        """Test confidence calculation for complete profile"""
        profile = PurposeProfile(
            values=Values(core=["Innovation", "Community", "Sustainability", "Education"]),
            workStyle=WorkStyle(),
            skills=Skills(
                technical=[
                    Skill(name="Python", level=SkillLevel.ADVANCED),
                    Skill(name="JavaScript", level=SkillLevel.INTERMEDIATE),
                    Skill(name="SQL", level=SkillLevel.ADVANCED)
                ],
                soft=[Skill(name="Communication", level=SkillLevel.EXPERT)],
                leadership=[Skill(name="Leadership", level=SkillLevel.INTERMEDIATE)]
            ),
            passions=["Technology", "Education", "Community Development"],
            mission_statement="To build sustainable tech solutions for communities"
        )

        confidence = calculate_profile_confidence(profile, 10)  # 10 turns conversation

        assert confidence >= 90  # Should be high confidence

    def test_calculate_profile_confidence_low(self):
        """Test confidence calculation for incomplete profile"""
        profile = PurposeProfile(
            values=Values(core=["Innovation"]),  # Incomplete
            workStyle=WorkStyle(),
            skills=Skills(technical=[Skill(name="Python", level=SkillLevel.BEGINNER)]),  # Few skills
            passions=["Technology"]  # Few passions
        )

        confidence = calculate_profile_confidence(profile, 2)  # Short conversation

        assert confidence < 50  # Should be low confidence


class TestModelValidators:
    """Test Pydantic model validators"""

    def test_skill_validation(self):
        """Test Skill model validation"""
        # Valid skill
        skill = Skill(name="Python Programming", level=SkillLevel.ADVANCED, years_experience=5)
        assert skill.name == "Python Programming"
        assert skill.level == SkillLevel.ADVANCED

        # Invalid skill - empty name
        with pytest.raises(ValueError):
            Skill(name="", level=SkillLevel.BEGINNER)

    def test_values_validation(self):
        """Test Values model validation"""
        values = Values(
            core=["innovation", "community", "SUSTAINABILITY"],
            secondary=["education"]
        )

        # Should be title case
        assert "Innovation" in values.core
        assert "Community" in values.core
        assert "Sustainability" in values.core

    def test_work_style_validation(self):
        """Test WorkStyle model validation"""
        work_style = WorkStyle(
            remote_preference=0.8,  # Valid: 0-1
            collaboration=WorkStylePreference.HIGH
        )
        assert work_style.remote_preference == 0.8

        # Invalid remote preference
        with pytest.raises(ValueError):
            WorkStyle(remote_preference=1.5)

    def test_user_profile_validation(self):
        """Test UserProfile model validation"""
        profile = UserProfile(
            purposeProfile=PurposeProfile(
                values=Values(core=["Innovation", "Community", "Sustainability"]),
                workStyle=WorkStyle(),
                skills=Skills(technical=[Skill(name="Python", level=SkillLevel.ADVANCED)]),
                passions=["Technology", "Education"]
            ),
            confidenceScore=95
        )

        assert profile.confidence_score == 95
        assert profile.status == UserStatus.ONBOARDING

        # Invalid confidence score
        with pytest.raises(ValueError):
            UserProfile(
                purposeProfile=profile.purpose_profile,
                confidenceScore=150  # Invalid: > 100
            )

    def test_team_metrics_validation(self):
        """Test TeamMetrics model validation"""
        metrics = TeamMetrics(
            productivity=0.85,
            collaboration=0.90,
            satisfaction=0.88,
            goalAchievement=0.92
        )

        assert metrics.overall_score > 0.7  # Should be around 0.75
        assert metrics.performance_grade in ["A", "A+", "B"]

    def test_match_result_validation(self):
        """Test MatchResult model validation"""
        match_result = MatchResult(
            userId="user-123",
            opportunities=[{"id": "opp-1", "title": "Community Project"}],
            confidence=0.95,
            reasoning="Strong alignment with user's values and skills",
            nextSteps=["Schedule interview", "Review project details"]
        )

        assert match_result.confidence == 0.95
        assert len(match_result.next_steps) >= 1


class TestMockDataGenerators:
    """Test mock data generation functions"""

    def test_generate_sample_user_profile(self):
        """Test sample user profile generation"""
        profile = generate_sample_user_profile()

        assert isinstance(profile, UserProfile)
        assert profile.confidence_score == 92
        assert profile.status == UserStatus.READY_FOR_MATCHING
        assert len(profile.purpose_profile.values.core) >= 3
        assert profile.purpose_profile.skills.skill_count >= 3

    def test_generate_sample_team_performance(self):
        """Test sample team performance generation"""
        performance = generate_sample_team_performance()

        assert isinstance(performance, TeamPerformance)
        assert performance.team_health_score > 0.8
        assert len(performance.members) >= 1
        assert len(performance.agent_recommendations) >= 0


class TestTeamPerformance:
    """Test TeamPerformance specific functionality"""

    def test_team_health_score(self):
        """Test team health score calculation"""
        performance = TeamPerformance(
            teamId="test-team",
            members=["user1", "user2"],
            metrics=TeamMetrics(
                productivity=0.9,
                collaboration=0.85,
                satisfaction=0.95,
                goalAchievement=0.88
            ),
            trends=TeamTrends(period="30 days", improvement=0.1)
        )

        assert performance.team_health_score > 0.7  # Should be around 0.76

    def test_team_trends_direction(self):
        """Test trend direction calculation"""
        # Improving trend
        trends = TeamTrends(period="30 days", improvement=0.2)
        assert trends.trend_direction == "improving"

        # Declining trend
        trends = TeamTrends(period="30 days", improvement=-0.2)
        assert trends.trend_direction == "declining"

        # Stable trend
        trends = TeamTrends(period="30 days", improvement=0.05)
        assert trends.trend_direction == "stable"


class TestMatchExplanation:
    """Test MatchExplanation functionality"""

    def test_explanation_summary(self):
        """Test explanation summary generation"""
        explanation = MatchExplanation(
            alignmentFactors=["Shared values", "Complementary skills"],
            valueAlignment=0.9,
            skillComplementarity=0.85
        )

        summary = explanation.explanation_summary
        assert "90%" in summary
        assert "85%" in summary