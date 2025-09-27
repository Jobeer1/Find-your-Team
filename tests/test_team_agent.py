"""
Tests for Team Agent - Performance monitoring and coaching insights
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

from agents.team_agent import (
    TeamAgent, CoachingInsight, TeamPerformanceReport,
    CoachingCategory
)
from models.core_models import TeamOpportunity, TeamMember, UserProfile
from config import Config


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    config = MagicMock(spec=Config)
    config.aws_region = "us-east-1"
    config.bedrock_model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    config.metrics_table_name = "team-metrics"
    config.teams_table_name = "teams"
    config.performance_reports_table_name = "performance-reports"
    return config


@pytest.fixture
def team_agent(mock_config):
    """Team Agent instance for testing."""
    return TeamAgent(mock_config)


@pytest.fixture
def sample_team_data():
    """Sample team data for testing."""
    return {
        "team_id": "team-123",
        "title": "AI Development Team",
        "description": "Building next-gen AI solutions",
        "members": [
            {
                "user_id": "user-1",
                "role": "Team Lead",
                "skills": ["Python", "ML", "Leadership"]
            },
            {
                "user_id": "user-2",
                "role": "ML Engineer",
                "skills": ["Python", "TensorFlow", "Data Science"]
            }
        ],
        "created_at": "2024-01-01T00:00:00Z"
    }


@pytest.fixture
def sample_metrics():
    """Sample performance metrics for testing."""
    return {
        "productivity": 0.8,
        "collaboration": 0.7,
        "communication": 0.6,
        "engagement": 0.9,
        "quality": 0.75
    }


@pytest.fixture
def mock_bedrock_response():
    """Mock Bedrock API response."""
    return {
        "content": [
            {
                "text": json.dumps({
                    "communication_patterns": "Team shows good written communication but could improve verbal communication",
                    "collaboration_effectiveness": "Strong cross-functional collaboration observed",
                    "leadership_distribution": "Leadership is concentrated in team lead",
                    "skill_utilization": "All team members are utilizing their primary skills effectively",
                    "potential_conflicts": "No major conflicts detected",
                    "team_cohesion": "High team cohesion with good interpersonal relationships",
                    "overall_dynamics_score": 0.85
                })
            }
        ]
    }


@pytest.fixture
def mock_coaching_insights():
    """Mock coaching insights response."""
    return [
        {
            "category": "communication",
            "priority": "high",
            "title": "Improve Verbal Communication",
            "description": "Team needs to enhance verbal communication during meetings",
            "recommendations": [
                "Schedule regular stand-up meetings",
                "Use video calls for important discussions"
            ],
            "metrics_affected": ["communication", "collaboration"],
            "confidence_score": 0.9
        },
        {
            "category": "leadership",
            "priority": "medium",
            "title": "Distribute Leadership Responsibilities",
            "description": "Leadership should be shared among team members",
            "recommendations": [
                "Assign project leads for different initiatives",
                "Rotate meeting facilitation roles"
            ],
            "metrics_affected": ["engagement", "productivity"],
            "confidence_score": 0.8
        }
    ]


class TestTeamAgent:
    """Test suite for TeamAgent class."""

    @pytest.mark.asyncio
    async def test_analyze_team_performance_success(
        self, team_agent, sample_team_data, sample_metrics,
        mock_bedrock_response, mock_coaching_insights
    ):
        """Test successful team performance analysis."""
        # Convert mock insights to CoachingInsight objects
        insights = []
        for item in mock_coaching_insights:
            insight = CoachingInsight(
                category=CoachingCategory(item["category"]),
                priority=item["priority"],
                title=item["title"],
                description=item["description"],
                recommendations=item["recommendations"],
                metrics_affected=item["metrics_affected"],
                confidence_score=item["confidence_score"]
            )
            insights.append(insight)

        with patch.object(team_agent, '_get_team_data', return_value=sample_team_data), \
             patch.object(team_agent, '_get_performance_metrics', return_value=sample_metrics), \
             patch.object(team_agent, '_analyze_team_dynamics', return_value=mock_bedrock_response), \
             patch.object(team_agent, '_generate_coaching_insights', return_value=insights), \
             patch.object(team_agent, '_generate_recommendations', return_value=["Rec 1", "Rec 2"]), \
             patch.object(team_agent, '_store_performance_report'):

            report = await team_agent.analyze_team_performance("team-123", 30)

            assert isinstance(report, TeamPerformanceReport)
            assert report.team_id == "team-123"
            assert isinstance(report.overall_score, float)
            assert 0.0 <= report.overall_score <= 1.0
            assert report.metrics == sample_metrics
            assert len(report.insights) == 2
            assert len(report.recommendations) == 2

    @pytest.mark.asyncio
    async def test_analyze_team_performance_team_not_found(self, team_agent):
        """Test analysis when team is not found."""
        with patch.object(team_agent, '_get_team_data', return_value=None):
            with pytest.raises(ValueError, match="Team team-123 not found"):
                await team_agent.analyze_team_performance("team-123")

    @pytest.mark.asyncio
    async def test_monitor_team_health_success(self, team_agent, sample_metrics):
        """Test successful team health monitoring."""
        with patch.object(team_agent, '_get_performance_metrics', return_value=sample_metrics):
            health_status = await team_agent.monitor_team_health("team-123")

            assert health_status["team_id"] == "team-123"
            assert "health_score" in health_status
            assert "indicators" in health_status
            assert "alerts" in health_status
            assert "timestamp" in health_status

            # Check health indicators
            indicators = health_status["indicators"]
            expected_indicators = [
                "communication_health", "collaboration_health",
                "productivity_health", "engagement_health", "overall_health"
            ]
            for indicator in expected_indicators:
                assert indicator in indicators

    @pytest.mark.asyncio
    async def test_monitor_team_health_with_alerts(self, team_agent):
        """Test health monitoring that generates alerts."""
        # Low metrics that should trigger alerts
        low_metrics = {
            "communication": 0.4,  # Below 0.6 threshold
            "collaboration": 0.5,  # Below 0.6 threshold
            "productivity": 0.5,   # Below 0.7 threshold
            "engagement": 0.8      # Above threshold
        }

        with patch.object(team_agent, '_get_performance_metrics', return_value=low_metrics):
            health_status = await team_agent.monitor_team_health("team-123")

            alerts = health_status["alerts"]
            assert len(alerts) >= 2  # Should have alerts for communication and productivity

            # Check alert structure
            for alert in alerts:
                assert "type" in alert
                assert "category" in alert
                assert "message" in alert
                assert "severity" in alert
                assert "current_value" in alert
                assert "threshold" in alert

    @pytest.mark.asyncio
    async def test_provide_coaching_session_success(self, team_agent, sample_team_data):
        """Test successful coaching session generation."""
        mock_report = TeamPerformanceReport(
            team_id="team-123",
            period_start=datetime.now() - timedelta(days=30),
            period_end=datetime.now(),
            overall_score=0.8,
            metrics={"productivity": 0.8},
            insights=[],
            recommendations=["Rec 1"],
            generated_at=datetime.now()
        )

        mock_session_content = {
            "title": "Team Communication Workshop",
            "objectives": ["Improve communication", "Build trust"],
            "activities": ["Icebreaker (10 min)", "Role-playing (30 min)"],
            "discussion_points": ["What works well?", "What needs improvement?"],
            "materials": ["Whiteboard", "Timer"],
            "duration": 60
        }

        with patch.object(team_agent, '_get_team_data', return_value=sample_team_data), \
             patch.object(team_agent, '_get_latest_performance_report', return_value=mock_report), \
             patch.object(team_agent, '_generate_coaching_session_content', return_value=mock_session_content):

            session = await team_agent.provide_coaching_session("team-123")

            assert session["team_id"] == "team-123"
            assert session["session_title"] == "Team Communication Workshop"
            assert "objectives" in session
            assert "activities" in session
            assert "discussion_points" in session
            assert "materials_needed" in session
            assert session["duration_minutes"] == 60

    @pytest.mark.asyncio
    async def test_get_team_data_success(self, team_agent, sample_team_data):
        """Test successful team data retrieval."""
        with patch.object(team_agent.dynamodb, 'Table') as mock_table_class:
            mock_table = MagicMock()
            mock_table_class.return_value = mock_table
            mock_table.get_item.return_value = {"Item": sample_team_data}

            result = await team_agent._get_team_data("team-123")

            assert result == sample_team_data
            mock_table.get_item.assert_called_once_with(Key={"team_id": "team-123"})

    @pytest.mark.asyncio
    async def test_get_team_data_not_found(self, team_agent):
        """Test team data retrieval when team not found."""
        with patch.object(team_agent.dynamodb, 'Table') as mock_table_class:
            mock_table = MagicMock()
            mock_table_class.return_value = mock_table
            mock_table.get_item.return_value = {}

            result = await team_agent._get_team_data("team-123")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_performance_metrics_success(self, team_agent):
        """Test successful performance metrics retrieval."""
        mock_items = [
            {
                "team_id": "team-123",
                "timestamp": "2024-01-15T00:00:00Z",
                "metrics": {"productivity": 0.8, "communication": 0.7}
            },
            {
                "team_id": "team-123",
                "timestamp": "2024-01-20T00:00:00Z",
                "metrics": {"productivity": 0.9, "communication": 0.6}
            }
        ]

        with patch.object(team_agent.metrics_table, 'query') as mock_query:
            mock_query.return_value = {"Items": mock_items}

            metrics = await team_agent._get_performance_metrics("team-123", 30)

            assert "productivity" in metrics
            assert "communication" in metrics
            # Should be averages: (0.8 + 0.9) / 2 = 0.85, (0.7 + 0.6) / 2 = 0.65
            assert abs(metrics["productivity"] - 0.85) < 0.001
            assert abs(metrics["communication"] - 0.65) < 0.001

    @pytest.mark.asyncio
    async def test_analyze_team_dynamics_success(self, team_agent, sample_team_data, sample_metrics, mock_bedrock_response):
        """Test successful team dynamics analysis."""
        with patch.object(team_agent.bedrock_client, 'invoke_model') as mock_invoke:
            mock_response = MagicMock()
            mock_response.__getitem__.return_value.read.return_value = json.dumps(mock_bedrock_response).encode()
            mock_invoke.return_value = {"body": mock_response}

            result = await team_agent._analyze_team_dynamics(sample_team_data, sample_metrics)

            assert "communication_patterns" in result
            assert "collaboration_effectiveness" in result
            assert "overall_dynamics_score" in result
            assert isinstance(result["overall_dynamics_score"], float)

    @pytest.mark.asyncio
    async def test_analyze_team_dynamics_error_handling(self, team_agent, sample_team_data, sample_metrics):
        """Test error handling in team dynamics analysis."""
        with patch.object(team_agent.bedrock_client, 'invoke_model', side_effect=Exception("API Error")):
            result = await team_agent._analyze_team_dynamics(sample_team_data, sample_metrics)

            # Should return default values on error
            assert result["communication_patterns"] == "Unable to analyze"
            assert result["overall_dynamics_score"] == 0.5

    @pytest.mark.asyncio
    async def test_generate_coaching_insights_success(self, team_agent, sample_team_data, sample_metrics, mock_bedrock_response, mock_coaching_insights):
        """Test successful coaching insights generation."""
        # Create the expected response structure
        bedrock_response = {
            "content": [{"text": json.dumps(mock_coaching_insights)}]
        }

        # Create a mock response that behaves like the real Bedrock response
        class MockResponseBody:
            def read(self):
                return json.dumps(bedrock_response).encode()

        with patch.object(team_agent.bedrock_client, 'invoke_model') as mock_invoke:
            mock_invoke.return_value = {"body": MockResponseBody()}

            insights = await team_agent._generate_coaching_insights(
                sample_team_data, sample_metrics, mock_bedrock_response
            )

            assert len(insights) == 2
            assert all(isinstance(insight, CoachingInsight) for insight in insights)
            assert insights[0].category == CoachingCategory.COMMUNICATION
            assert insights[0].priority == "high"
            assert insights[1].category == CoachingCategory.LEADERSHIP

    def test_calculate_overall_score(self, team_agent, sample_metrics, mock_coaching_insights):
        """Test overall score calculation."""
        # Convert mock data to CoachingInsight objects
        insights = []
        for item in mock_coaching_insights:
            insight = CoachingInsight(
                category=CoachingCategory(item["category"]),
                priority=item["priority"],
                title=item["title"],
                description=item["description"],
                recommendations=item["recommendations"],
                metrics_affected=item["metrics_affected"],
                confidence_score=item["confidence_score"]
            )
            insights.append(insight)

        score = team_agent._calculate_overall_score(sample_metrics, insights)

        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        # Score should be reduced due to high-priority insight
        assert score < 0.8  # Base metric score would be higher

    @pytest.mark.asyncio
    async def test_generate_recommendations(self, team_agent, mock_coaching_insights):
        """Test recommendations generation."""
        insights = []
        for item in mock_coaching_insights:
            insight = CoachingInsight(
                category=CoachingCategory(item["category"]),
                priority=item["priority"],
                title=item["title"],
                description=item["description"],
                recommendations=item["recommendations"],
                metrics_affected=item["metrics_affected"],
                confidence_score=item["confidence_score"]
            )
            insights.append(insight)

        recommendations = await team_agent._generate_recommendations(insights, {})

        assert isinstance(recommendations, list)
        assert len(recommendations) <= 5  # Should be limited to 5
        # Should include recommendations from high-priority insights first
        assert "Schedule regular stand-up meetings" in recommendations

    def test_calculate_health_indicators(self, team_agent, sample_metrics):
        """Test health indicators calculation."""
        indicators = team_agent._calculate_health_indicators(sample_metrics)

        expected_keys = [
            "communication_health", "collaboration_health",
            "productivity_health", "engagement_health", "overall_health"
        ]

        for key in expected_keys:
            assert key in indicators
            assert isinstance(indicators[key], float)
            assert 0.0 <= indicators[key] <= 1.0

        # Overall health should be weighted average
        expected_overall = (
            sample_metrics["communication"] * 0.25 +
            sample_metrics["collaboration"] * 0.25 +
            sample_metrics["productivity"] * 0.3 +
            sample_metrics["engagement"] * 0.2
        )
        assert abs(indicators["overall_health"] - expected_overall) < 0.001

    def test_generate_health_alerts(self, team_agent):
        """Test health alerts generation."""
        # Test with low indicators
        low_indicators = {
            "communication_health": 0.4,
            "collaboration_health": 0.8,
            "productivity_health": 0.5,
            "engagement_health": 0.7,
            "overall_health": 0.6
        }

        alerts = team_agent._generate_health_alerts(low_indicators)

        assert len(alerts) >= 2  # Should alert on communication and productivity

        for alert in alerts:
            assert alert["type"] == "warning"
            assert "severity" in alert
            assert "current_value" in alert
            assert "threshold" in alert

    @pytest.mark.asyncio
    async def test_generate_coaching_session_content_success(self, team_agent, sample_team_data):
        """Test successful coaching session content generation."""
        mock_session_data = {
            "title": "Team Building Workshop",
            "objectives": ["Build trust", "Improve communication"],
            "activities": ["Trust exercises", "Communication games"],
            "discussion_points": ["What worked?", "What to improve?"],
            "materials": ["Cards", "Timer"],
            "duration": 90
        }

        # Create the expected response structure
        bedrock_response = {
            "content": [{"text": json.dumps(mock_session_data)}]
        }

        # Create a mock response that behaves like the real Bedrock response
        class MockResponseBody:
            def read(self):
                return json.dumps(bedrock_response).encode()

        with patch.object(team_agent.bedrock_client, 'invoke_model') as mock_invoke:
            mock_invoke.return_value = {"body": MockResponseBody()}

            content = await team_agent._generate_coaching_session_content(
                sample_team_data, None, None
            )

            assert content["title"] == "Team Building Workshop"
            assert content["duration"] == 90
            assert "objectives" in content
            assert "activities" in content

    @pytest.mark.asyncio
    async def test_generate_coaching_session_content_error_handling(self, team_agent, sample_team_data):
        """Test error handling in coaching session content generation."""
        with patch.object(team_agent.bedrock_client, 'invoke_model', side_effect=Exception("API Error")):
            content = await team_agent._generate_coaching_session_content(
                sample_team_data, None, None
            )

            # Should return default content on error
            assert content["title"] == "Team Development Session"
            assert content["duration"] == 60
            assert len(content["objectives"]) == 3

    @pytest.mark.asyncio
    async def test_store_performance_report(self, team_agent):
        """Test performance report storage."""
        report = TeamPerformanceReport(
            team_id="team-123",
            period_start=datetime.now() - timedelta(days=30),
            period_end=datetime.now(),
            overall_score=0.8,
            metrics={"productivity": 0.8},
            insights=[],
            recommendations=["Rec 1"],
            generated_at=datetime.now()
        )

        with patch.object(team_agent.dynamodb, 'Table') as mock_table_class:
            mock_table = MagicMock()
            mock_table_class.return_value = mock_table

            await team_agent._store_performance_report(report)

            # Verify the table was called with correct data structure
            call_args = mock_table.put_item.call_args[1]["Item"]
            assert call_args["team_id"] == "team-123"
            assert "overall_score" in call_args
            assert "metrics" in call_args
            assert "recommendations" in call_args

    @pytest.mark.asyncio
    async def test_get_latest_performance_report(self, team_agent):
        """Test retrieval of latest performance report."""
        with patch.object(team_agent.dynamodb, 'Table') as mock_table_class:
            mock_table = MagicMock()
            mock_table_class.return_value = mock_table
            mock_table.query.return_value = {"Items": []}  # No reports found

            result = await team_agent._get_latest_performance_report("team-123")

            assert result is None
            mock_table.query.assert_called_once()


class TestCoachingInsight:
    """Test CoachingInsight dataclass."""

    def test_coaching_insight_creation(self):
        """Test creating a CoachingInsight instance."""
        insight = CoachingInsight(
            category=CoachingCategory.COMMUNICATION,
            priority="high",
            title="Improve Meeting Communication",
            description="Team meetings lack structure and clear communication",
            recommendations=["Use agendas", "Assign action items"],
            metrics_affected=["communication", "productivity"],
            confidence_score=0.85
        )

        assert insight.category == CoachingCategory.COMMUNICATION
        assert insight.priority == "high"
        assert insight.title == "Improve Meeting Communication"
        assert len(insight.recommendations) == 2
        assert insight.confidence_score == 0.85


class TestTeamPerformanceReport:
    """Test TeamPerformanceReport dataclass."""

    def test_performance_report_creation(self):
        """Test creating a TeamPerformanceReport instance."""
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        report = TeamPerformanceReport(
            team_id="team-123",
            period_start=start_date,
            period_end=end_date,
            overall_score=0.75,
            metrics={"productivity": 0.8, "communication": 0.7},
            insights=[],
            recommendations=["Improve documentation", "Regular check-ins"],
            generated_at=datetime.now()
        )

        assert report.team_id == "team-123"
        assert report.overall_score == 0.75
        assert len(report.metrics) == 2
        assert len(report.recommendations) == 2


class TestCoachingCategory:
    """Test CoachingCategory enum."""

    def test_coaching_categories(self):
        """Test all coaching category values."""
        assert CoachingCategory.COMMUNICATION.value == "communication"
        assert CoachingCategory.COLLABORATION.value == "collaboration"
        assert CoachingCategory.LEADERSHIP.value == "leadership"
        assert CoachingCategory.SKILL_DEVELOPMENT.value == "skill_development"
        assert CoachingCategory.TEAM_DYNAMICS.value == "team_dynamics"
        assert CoachingCategory.PRODUCTIVITY.value == "productivity"