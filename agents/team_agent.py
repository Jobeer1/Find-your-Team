"""
Team Agent - Performance monitoring and coaching insights for teams
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

import boto3
from botocore.exceptions import ClientError

from models.core_models import (
    TeamOpportunity, TeamMember, TeamMatch, MatchScore,
    UserProfile, PurposeProfile, PerformanceMetrics
)
from config import Config

logger = logging.getLogger(__name__)


class CoachingCategory(Enum):
    COMMUNICATION = "communication"
    COLLABORATION = "collaboration"
    LEADERSHIP = "leadership"
    SKILL_DEVELOPMENT = "skill_development"
    TEAM_DYNAMICS = "team_dynamics"
    PRODUCTIVITY = "productivity"


@dataclass
class CoachingInsight:
    category: CoachingCategory
    priority: str  # "high", "medium", "low"
    title: str
    description: str
    recommendations: List[str]
    metrics_affected: List[str]
    confidence_score: float


@dataclass
class TeamPerformanceReport:
    team_id: str
    period_start: datetime
    period_end: datetime
    overall_score: float
    metrics: Dict[str, float]
    insights: List[CoachingInsight]
    recommendations: List[str]
    generated_at: datetime


class TeamAgent:
    """
    AI-powered team performance monitoring and coaching agent.
    Analyzes team dynamics, provides coaching insights, and monitors performance metrics.
    """

    def __init__(self, config: Config):
        self.config = config
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=config.aws_region
        )
        self.dynamodb = boto3.resource('dynamodb', region_name=config.aws_region)
        self.metrics_table = self.dynamodb.Table(config.metrics_table_name)

    async def analyze_team_performance(
        self,
        team_id: str,
        days_back: int = 30
    ) -> TeamPerformanceReport:
        """
        Analyze team performance over a specified period.

        Args:
            team_id: Unique identifier for the team
            days_back: Number of days to analyze (default: 30)

        Returns:
            Comprehensive performance report with insights and recommendations
        """
        try:
            # Get team data
            team_data = await self._get_team_data(team_id)
            if not team_data:
                raise ValueError(f"Team {team_id} not found")

            # Get performance metrics for the period
            metrics = await self._get_performance_metrics(team_id, days_back)

            # Analyze team dynamics
            dynamics_analysis = await self._analyze_team_dynamics(team_data, metrics)

            # Generate coaching insights
            insights = await self._generate_coaching_insights(
                team_data, metrics, dynamics_analysis
            )

            # Calculate overall performance score
            overall_score = self._calculate_overall_score(metrics, insights)

            # Generate recommendations
            recommendations = await self._generate_recommendations(insights, team_data)

            report = TeamPerformanceReport(
                team_id=team_id,
                period_start=datetime.now() - timedelta(days=days_back),
                period_end=datetime.now(),
                overall_score=overall_score,
                metrics=metrics,
                insights=insights,
                recommendations=recommendations,
                generated_at=datetime.now()
            )

            # Store report for historical tracking
            await self._store_performance_report(report)

            return report

        except Exception as e:
            logger.error(f"Error analyzing team performance for {team_id}: {str(e)}")
            raise

    async def monitor_team_health(self, team_id: str) -> Dict[str, Any]:
        """
        Real-time monitoring of team health indicators.

        Args:
            team_id: Unique identifier for the team

        Returns:
            Current health status and alerts
        """
        try:
            # Get recent metrics (last 7 days)
            recent_metrics = await self._get_performance_metrics(team_id, 7)

            # Calculate health indicators
            health_indicators = self._calculate_health_indicators(recent_metrics)

            # Generate alerts if needed
            alerts = self._generate_health_alerts(health_indicators)

            return {
                "team_id": team_id,
                "health_score": health_indicators.get("overall_health", 0.0),
                "indicators": health_indicators,
                "alerts": alerts,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error monitoring team health for {team_id}: {str(e)}")
            raise

    async def provide_coaching_session(
        self,
        team_id: str,
        focus_areas: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate a structured coaching session for the team.

        Args:
            team_id: Team identifier
            focus_areas: Specific areas to focus on (optional)

        Returns:
            Coaching session plan with activities and discussion points
        """
        try:
            # Get team data and recent performance
            team_data = await self._get_team_data(team_id)
            recent_report = await self._get_latest_performance_report(team_id)

            # Generate coaching session content
            session_content = await self._generate_coaching_session_content(
                team_data, recent_report, focus_areas
            )

            return {
                "team_id": team_id,
                "session_title": session_content["title"],
                "objectives": session_content["objectives"],
                "activities": session_content["activities"],
                "discussion_points": session_content["discussion_points"],
                "materials_needed": session_content["materials"],
                "duration_minutes": session_content["duration"],
                "generated_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error generating coaching session for {team_id}: {str(e)}")
            raise

    async def _get_team_data(self, team_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve team data from DynamoDB."""
        try:
            response = self.dynamodb.Table(self.config.teams_table_name).get_item(
                Key={"team_id": team_id}
            )
            return response.get("Item")
        except ClientError as e:
            logger.error(f"Error retrieving team data: {str(e)}")
            return None

    async def _get_performance_metrics(
        self,
        team_id: str,
        days_back: int
    ) -> Dict[str, float]:
        """Retrieve performance metrics for the specified period."""
        try:
            start_date = datetime.now() - timedelta(days=days_back)

            # Query metrics table
            response = self.metrics_table.query(
                KeyConditionExpression="team_id = :team_id AND #ts >= :start_date",
                ExpressionAttributeNames={"#ts": "timestamp"},
                ExpressionAttributeValues={
                    ":team_id": team_id,
                    ":start_date": start_date.isoformat()
                }
            )

            metrics = {}
            items = response.get("Items", [])

            # Aggregate metrics
            for item in items:
                for key, value in item.get("metrics", {}).items():
                    if key not in metrics:
                        metrics[key] = []
                    metrics[key].append(float(value))

            # Calculate averages
            aggregated_metrics = {}
            for key, values in metrics.items():
                aggregated_metrics[key] = sum(values) / len(values) if values else 0.0

            return aggregated_metrics

        except ClientError as e:
            logger.error(f"Error retrieving performance metrics: {str(e)}")
            return {}

    async def _analyze_team_dynamics(
        self,
        team_data: Dict[str, Any],
        metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """Analyze team dynamics using AI."""
        try:
            # Prepare analysis prompt
            prompt = f"""
            Analyze the following team data and performance metrics to understand team dynamics:

            Team Information:
            {json.dumps(team_data, indent=2, default=str)}

            Performance Metrics:
            {json.dumps(metrics, indent=2)}

            Provide analysis of:
            1. Communication patterns
            2. Collaboration effectiveness
            3. Leadership distribution
            4. Skill utilization
            5. Potential conflicts or challenges
            6. Team cohesion indicators

            Format your response as JSON with the following structure:
            {{
                "communication_patterns": "description",
                "collaboration_effectiveness": "description",
                "leadership_distribution": "description",
                "skill_utilization": "description",
                "potential_conflicts": "description",
                "team_cohesion": "description",
                "overall_dynamics_score": 0.0
            }}
            """

            # Call Bedrock for analysis
            response = self.bedrock_client.invoke_model(
                modelId=self.config.bedrock_model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2000,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )

            response_body = json.loads(response["body"].read())
            analysis_text = response_body["content"][0]["text"]

            # Parse JSON response
            return json.loads(analysis_text)

        except Exception as e:
            logger.error(f"Error analyzing team dynamics: {str(e)}")
            return {
                "communication_patterns": "Unable to analyze",
                "collaboration_effectiveness": "Unable to analyze",
                "leadership_distribution": "Unable to analyze",
                "skill_utilization": "Unable to analyze",
                "potential_conflicts": "Unable to analyze",
                "team_cohesion": "Unable to analyze",
                "overall_dynamics_score": 0.5
            }

    async def _generate_coaching_insights(
        self,
        team_data: Dict[str, Any],
        metrics: Dict[str, float],
        dynamics_analysis: Dict[str, Any]
    ) -> List[CoachingInsight]:
        """Generate coaching insights using AI analysis."""
        try:
            prompt = f"""
            Based on the team data, performance metrics, and dynamics analysis below,
            generate specific coaching insights for team improvement.

            Team Data: {json.dumps(team_data, indent=2, default=str)}
            Metrics: {json.dumps(metrics, indent=2)}
            Dynamics: {json.dumps(dynamics_analysis, indent=2)}

            Generate 3-5 coaching insights with the following for each:
            - Category (communication, collaboration, leadership, skill_development, team_dynamics, productivity)
            - Priority (high, medium, low)
            - Title (brief, actionable title)
            - Description (detailed explanation)
            - 2-3 specific recommendations
            - Metrics affected (which performance metrics this addresses)
            - Confidence score (0.0-1.0)

            Format as JSON array of insight objects.
            """

            response = self.bedrock_client.invoke_model(
                modelId=self.config.bedrock_model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 3000,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )

            response_body = json.loads(response["body"].read())
            insights_text = response_body["content"][0]["text"]

            # Parse and convert to CoachingInsight objects
            insights_data = json.loads(insights_text)
            insights = []

            for item in insights_data:
                insight = CoachingInsight(
                    category=CoachingCategory(item["category"]),
                    priority=item["priority"],
                    title=item["title"],
                    description=item["description"],
                    recommendations=item["recommendations"],
                    metrics_affected=item["metrics_affected"],
                    confidence_score=float(item["confidence_score"])
                )
                insights.append(insight)

            return insights

        except Exception as e:
            logger.error(f"Error generating coaching insights: {str(e)}")
            return []

    def _calculate_overall_score(
        self,
        metrics: Dict[str, float],
        insights: List[CoachingInsight]
    ) -> float:
        """Calculate overall team performance score."""
        # Base score from metrics (weighted average)
        metric_weights = {
            "productivity": 0.3,
            "collaboration": 0.25,
            "communication": 0.2,
            "engagement": 0.15,
            "quality": 0.1
        }

        metric_score = 0.0
        total_weight = 0.0

        for metric, weight in metric_weights.items():
            if metric in metrics:
                metric_score += metrics[metric] * weight
                total_weight += weight

        if total_weight > 0:
            metric_score /= total_weight

        # Adjust based on insight priorities
        insight_penalty = 0.0
        for insight in insights:
            if insight.priority == "high":
                insight_penalty += 0.1
            elif insight.priority == "medium":
                insight_penalty += 0.05

        final_score = max(0.0, min(1.0, metric_score - insight_penalty))
        return final_score

    async def _generate_recommendations(
        self,
        insights: List[CoachingInsight],
        team_data: Dict[str, Any]
    ) -> List[str]:
        """Generate high-level recommendations based on insights."""
        recommendations = []

        # Group insights by priority
        high_priority = [i for i in insights if i.priority == "high"]
        medium_priority = [i for i in insights if i.priority == "medium"]

        # Add high-priority recommendations first
        for insight in high_priority:
            recommendations.extend(insight.recommendations[:2])  # Top 2 per insight

        # Add medium-priority recommendations
        for insight in medium_priority[:2]:  # Limit to top 2 medium insights
            recommendations.extend(insight.recommendations[:1])  # 1 per insight

        # Add general recommendations if needed
        if len(recommendations) < 3:
            recommendations.extend([
                "Schedule regular team check-ins to discuss progress and challenges",
                "Consider team-building activities to improve cohesion",
                "Provide opportunities for skill development and growth"
            ])

        return recommendations[:5]  # Limit to 5 recommendations

    def _calculate_health_indicators(self, metrics: Dict[str, float]) -> Dict[str, float]:
        """Calculate real-time health indicators."""
        indicators = {}

        # Communication health
        indicators["communication_health"] = metrics.get("communication", 0.5)

        # Collaboration health
        indicators["collaboration_health"] = metrics.get("collaboration", 0.5)

        # Productivity health
        indicators["productivity_health"] = metrics.get("productivity", 0.5)

        # Engagement health
        indicators["engagement_health"] = metrics.get("engagement", 0.5)

        # Overall health (weighted average)
        weights = {
            "communication_health": 0.25,
            "collaboration_health": 0.25,
            "productivity_health": 0.3,
            "engagement_health": 0.2
        }

        overall_health = sum(
            indicators[key] * weight for key, weight in weights.items()
        )
        indicators["overall_health"] = overall_health

        return indicators

    def _generate_health_alerts(self, indicators: Dict[str, float]) -> List[Dict[str, Any]]:
        """Generate alerts based on health indicators."""
        alerts = []

        thresholds = {
            "communication_health": 0.6,
            "collaboration_health": 0.6,
            "productivity_health": 0.7,
            "engagement_health": 0.6
        }

        for indicator, threshold in thresholds.items():
            if indicators.get(indicator, 1.0) < threshold:
                alert = {
                    "type": "warning",
                    "category": indicator.replace("_health", ""),
                    "message": f"Low {indicator.replace('_health', '')} score detected",
                    "severity": "medium" if indicators[indicator] > threshold * 0.8 else "high",
                    "current_value": indicators[indicator],
                    "threshold": threshold
                }
                alerts.append(alert)

        return alerts

    async def _generate_coaching_session_content(
        self,
        team_data: Dict[str, Any],
        recent_report: Optional[TeamPerformanceReport],
        focus_areas: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Generate content for a coaching session."""
        try:
            prompt = f"""
            Create a structured coaching session plan for this team.

            Team Data: {json.dumps(team_data, indent=2, default=str)}
            Recent Performance: {json.dumps(recent_report.__dict__ if recent_report else {}, indent=2, default=str)}
            Focus Areas: {focus_areas or 'General team development'}

            Create a 60-minute coaching session with:
            - Session title
            - Learning objectives (3-4)
            - Structured activities (3-4 activities with timing)
            - Discussion points (4-6 questions/topics)
            - Materials needed
            - Total duration

            Format as JSON.
            """

            response = self.bedrock_client.invoke_model(
                modelId=self.config.bedrock_model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2000,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )

            response_body = json.loads(response["body"].read())
            content_text = response_body["content"][0]["text"]

            return json.loads(content_text)

        except Exception as e:
            logger.error(f"Error generating coaching session content: {str(e)}")
            return {
                "title": "Team Development Session",
                "objectives": ["Improve team communication", "Enhance collaboration", "Build trust"],
                "activities": ["Icebreaker (10 min)", "Skills assessment (20 min)", "Action planning (20 min)"],
                "discussion_points": ["What are our strengths?", "What challenges do we face?", "How can we improve?"],
                "materials": ["Whiteboard", "Timer", "Note-taking materials"],
                "duration": 60
            }

    async def _store_performance_report(self, report: TeamPerformanceReport) -> None:
        """Store performance report in DynamoDB for historical tracking."""
        try:
            reports_table = self.dynamodb.Table(self.config.performance_reports_table_name)

            item = {
                "team_id": report.team_id,
                "timestamp": report.generated_at.isoformat(),
                "period_start": report.period_start.isoformat(),
                "period_end": report.period_end.isoformat(),
                "overall_score": report.overall_score,
                "metrics": report.metrics,
                "insights": [
                    {
                        "category": insight.category.value,
                        "priority": insight.priority,
                        "title": insight.title,
                        "description": insight.description,
                        "recommendations": insight.recommendations,
                        "metrics_affected": insight.metrics_affected,
                        "confidence_score": insight.confidence_score
                    }
                    for insight in report.insights
                ],
                "recommendations": report.recommendations
            }

            await reports_table.put_item(Item=item)

        except Exception as e:
            logger.error(f"Error storing performance report: {str(e)}")
            # Don't raise - storage failure shouldn't break the analysis

    async def _get_latest_performance_report(
        self,
        team_id: str
    ) -> Optional[TeamPerformanceReport]:
        """Retrieve the most recent performance report for a team."""
        try:
            reports_table = self.dynamodb.Table(self.config.performance_reports_table_name)

            response = reports_table.query(
                KeyConditionExpression="team_id = :team_id",
                ExpressionAttributeValues={":team_id": team_id},
                ScanIndexForward=False,  # Most recent first
                Limit=1
            )

            items = response.get("Items", [])
            if not items:
                return None

            item = items[0]
            # Convert back to TeamPerformanceReport object
            # (Implementation would parse the stored data back into the dataclass)

            return None  # Placeholder - would implement full conversion

        except Exception as e:
            logger.error(f"Error retrieving latest performance report: {str(e)}")
            return None