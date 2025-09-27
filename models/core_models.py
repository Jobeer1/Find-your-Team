"""
Find Your Team - Core Data Models
World-class data structures with comprehensive validation
"""

from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
import uuid
import json

class SkillLevel(str, Enum):
    """Skill proficiency levels"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

class WorkStylePreference(str, Enum):
    """Work style preference levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class CommunicationStyle(str, Enum):
    """Communication style preferences"""
    DIRECT = "direct"
    DIPLOMATIC = "diplomatic"
    SUPPORTIVE = "supportive"

class StructurePreference(str, Enum):
    """Structure preference levels"""
    FLEXIBLE = "flexible"
    MODERATE = "moderate"
    STRUCTURED = "structured"

class UserStatus(str, Enum):
    """User profile status"""
    ONBOARDING = "onboarding"
    READY_FOR_MATCHING = "ready_for_matching"
    MATCHED = "matched"
    ACTIVE_TEAM_MEMBER = "active_team_member"

class Skill(BaseModel):
    """Individual skill with proficiency level"""
    name: str = Field(..., min_length=1, max_length=100)
    level: SkillLevel
    years_experience: Optional[int] = Field(None, ge=0, le=50)
    verified: bool = False
    endorsements: int = Field(0, ge=0)
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        return v.strip().title()

class Values(BaseModel):
    """User's core values and priorities"""
    core: List[str] = Field(..., min_length=1, max_length=10)
    secondary: List[str] = Field(default_factory=list, max_length=15)
    weights: Dict[str, float] = Field(default_factory=dict)
    
    @field_validator('core', 'secondary')
    @classmethod
    def validate_values(cls, v):
        return [value.strip().title() for value in v if value.strip()]
    
    @field_validator('weights')
    @classmethod
    def validate_weights(cls, v):
        # Ensure weights sum to 1.0 if provided
        if v and sum(v.values()) > 0:
            total = sum(v.values())
            return {k: val/total for k, val in v.items()}
        return v

class WorkStyle(BaseModel):
    """User's work style preferences"""
    collaboration: WorkStylePreference = WorkStylePreference.MEDIUM
    autonomy: WorkStylePreference = WorkStylePreference.MEDIUM
    structure: StructurePreference = StructurePreference.MODERATE
    communication: CommunicationStyle = CommunicationStyle.DIPLOMATIC
    
    # Additional work style attributes
    remote_preference: float = Field(0.5, ge=0.0, le=1.0)  # 0=office, 1=remote
    meeting_frequency: WorkStylePreference = WorkStylePreference.MEDIUM
    decision_making: WorkStylePreference = WorkStylePreference.MEDIUM  # consensus vs individual

class Skills(BaseModel):
    """Comprehensive skills profile"""
    technical: List[Skill] = Field(default_factory=list, max_length=20)
    soft: List[Skill] = Field(default_factory=list, max_length=15)
    leadership: List[Skill] = Field(default_factory=list, max_length=10)
    
    @property
    def all_skills(self) -> List[Skill]:
        """Get all skills combined"""
        return self.technical + self.soft + self.leadership
    
    @property
    def skill_count(self) -> int:
        """Total number of skills"""
        return len(self.all_skills)
    
    def get_skills_by_level(self, level: SkillLevel) -> List[Skill]:
        """Get skills filtered by proficiency level"""
        return [skill for skill in self.all_skills if skill.level == level]

class PurposeProfile(BaseModel):
    """Complete purpose profile for a user"""
    values: Values
    work_style: WorkStyle = Field(alias='workStyle')
    skills: Skills
    passions: List[str] = Field(..., min_length=1, max_length=10)
    
    # Additional purpose attributes
    mission_statement: Optional[str] = Field(None, max_length=500)
    impact_areas: List[str] = Field(default_factory=list, max_length=5)
    availability_hours_per_week: Optional[int] = Field(None, ge=1, le=168)
    
    @field_validator('passions')
    @classmethod
    def validate_passions(cls, v):
        return [passion.strip().title() for passion in v if passion.strip()]
    
    @field_validator('mission_statement')
    @classmethod
    def validate_mission(cls, v):
        return v.strip() if v else None

class TeamMetrics(BaseModel):
    """Team performance metrics"""
    productivity: float = Field(..., ge=0.0, le=1.0)
    collaboration: float = Field(..., ge=0.0, le=1.0)
    satisfaction: float = Field(..., ge=0.0, le=1.0)
    goal_achievement: float = Field(..., ge=0.0, le=1.0, alias='goalAchievement')
    
    # Additional metrics
    innovation_score: float = Field(0.0, ge=0.0, le=1.0)
    communication_quality: float = Field(0.0, ge=0.0, le=1.0)
    conflict_resolution: float = Field(0.0, ge=0.0, le=1.0)
    
    @property
    def overall_score(self) -> float:
        """Calculate weighted overall team score"""
        weights = {
            'productivity': 0.25,
            'collaboration': 0.25,
            'satisfaction': 0.20,
            'goal_achievement': 0.15,
            'innovation_score': 0.10,
            'communication_quality': 0.05
        }
        
        return sum(getattr(self, metric) * weight for metric, weight in weights.items())
    
    @property
    def performance_grade(self) -> str:
        """Get letter grade for performance"""
        score = self.overall_score
        if score >= 0.9:
            return "A+"
        elif score >= 0.8:
            return "A"
        elif score >= 0.7:
            return "B"
        elif score >= 0.6:
            return "C"
        else:
            return "D"

class TeamTrends(BaseModel):
    """Team performance trends over time"""
    period: str = Field(..., pattern=r'^\d+\s+(day|week|month)s?$')
    improvement: float = Field(..., ge=-1.0, le=1.0)  # -1 to 1 (decline to improvement)
    challenges: List[str] = Field(default_factory=list, max_length=10)
    successes: List[str] = Field(default_factory=list, max_length=10)
    
    @property
    def trend_direction(self) -> str:
        """Get trend direction as string"""
        if self.improvement > 0.1:
            return "improving"
        elif self.improvement < -0.1:
            return "declining"
        else:
            return "stable"

class CoachingInsight(BaseModel):
    """Individual coaching insight"""
    insight: str = Field(..., min_length=10, max_length=500)
    category: str = Field(..., min_length=1, max_length=50)
    priority: int = Field(..., ge=1, le=5)  # 1=highest, 5=lowest
    actionable: bool = True
    estimated_impact: float = Field(0.5, ge=0.0, le=1.0)

class UserProfile(BaseModel):
    """Complete user profile"""
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias='userId')
    purpose_profile: PurposeProfile = Field(alias='purposeProfile')
    confidence_score: int = Field(..., ge=0, le=100, alias='confidenceScore')
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now, alias='createdAt')
    updated_at: datetime = Field(default_factory=datetime.now, alias='updatedAt')
    status: UserStatus = UserStatus.ONBOARDING
    
    # Optional profile enhancements
    profile_picture_url: Optional[str] = Field(None, alias='profilePictureUrl')
    bio: Optional[str] = Field(None, max_length=1000)
    location: Optional[str] = None
    timezone: Optional[str] = None
    
    @field_validator('confidence_score')
    @classmethod
    def validate_confidence(cls, v):
        return max(0, min(100, v))  # Ensure within bounds
    
    @model_validator(mode='after')
    def update_timestamp(self):
        self.updated_at = datetime.now()
        return self

class MatchExplanation(BaseModel):
    """Explanation for why a match was made"""
    alignment_factors: List[str] = Field(..., min_length=1, alias='alignmentFactors')
    skill_gaps: List[str] = Field(default_factory=list, alias='skillGaps')
    growth_opportunities: List[str] = Field(default_factory=list, alias='growthOpportunities')
    value_alignment: float = Field(..., ge=0.0, le=1.0, alias='valueAlignment')
    skill_complementarity: float = Field(..., ge=0.0, le=1.0, alias='skillComplementarity')
    
    @property
    def explanation_summary(self) -> str:
        """Generate human-readable explanation"""
        return f"This match has {self.value_alignment:.0%} value alignment and {self.skill_complementarity:.0%} skill complementarity."

class TeamOpportunity(BaseModel):
    """Team or project opportunity"""
    opportunity_id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias='opportunityId')
    title: str = Field(..., min_length=5, max_length=100)
    description: str = Field(..., min_length=20, max_length=2000)
    
    # Requirements
    required_skills: List[str] = Field(..., min_length=1, alias='requiredSkills')
    preferred_skills: List[str] = Field(default_factory=list, alias='preferredSkills')
    team_size: int = Field(..., ge=1, le=50, alias='teamSize')
    commitment_hours: int = Field(..., ge=1, le=40, alias='commitmentHours')
    
    # Impact and purpose
    impact_area: str = Field(..., alias='impactArea')
    community_served: str = Field(..., alias='communityServed')
    expected_impact: str = Field(..., alias='expectedImpact')
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now, alias='createdAt')
    deadline: Optional[datetime] = None
    is_active: bool = Field(True, alias='isActive')

class MatchResult(BaseModel):
    """Result of team matching process"""
    user_id: str = Field(..., alias='userId')
    opportunities: List[Dict[str, Any]] = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., min_length=10)
    next_steps: List[str] = Field(..., min_length=1, alias='nextSteps')
    
    # Match metadata
    generated_at: datetime = Field(default_factory=datetime.now, alias='generatedAt')
    algorithm_version: str = Field("1.0", alias='algorithmVersion')

class TeamPerformance(BaseModel):
    """Team performance tracking"""
    team_id: str = Field(..., alias='teamId')
    members: List[str] = Field(..., min_length=1)
    metrics: TeamMetrics
    trends: TeamTrends
    agent_recommendations: List[CoachingInsight] = Field(default_factory=list, alias='agentRecommendations')
    
    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.now)
    last_assessment: datetime = Field(default_factory=datetime.now, alias='lastAssessment')
    
    @property
    def team_health_score(self) -> float:
        """Overall team health score"""
        return self.metrics.overall_score

class MatchScore(BaseModel):
    """Detailed scoring for team matches"""
    overall_score: float = Field(..., ge=0.0, le=1.0, alias='overallScore')
    skill_alignment: float = Field(..., ge=0.0, le=1.0, alias='skillAlignment')
    value_alignment: float = Field(..., ge=0.0, le=1.0, alias='valueAlignment')
    work_style_compatibility: float = Field(..., ge=0.0, le=1.0, alias='workStyleCompatibility')
    purpose_alignment: float = Field(..., ge=0.0, le=1.0, alias='purposeAlignment')

class MatchReason(BaseModel):
    """Reason for a match recommendation"""
    reason_type: str = Field(..., alias='reasonType')  # skills, values, purpose, etc.
    description: str = Field(..., min_length=10)
    weight: float = Field(..., ge=0.0, le=1.0)

class TeamMatch(BaseModel):
    """Complete team match result"""
    team_id: str = Field(..., alias='teamId')
    user_id: str = Field(..., alias='userId')
    match_score: MatchScore = Field(..., alias='matchScore')
    match_reasons: List[MatchReason] = Field(..., min_length=1, alias='matchReasons')
    recommended_actions: List[str] = Field(..., min_length=1, alias='recommendedActions')
    created_at: datetime = Field(default_factory=datetime.now, alias='createdAt')
    expires_at: datetime = Field(..., alias='expiresAt')

class TeamMember(BaseModel):
    """Team member information"""
    user_id: str = Field(..., alias='userId')
    role: str = Field(..., min_length=1)
    joined_at: datetime = Field(default_factory=datetime.now, alias='joinedAt')
    contribution_score: float = Field(default=0.0, ge=0.0, le=1.0, alias='contributionScore')

class PerformanceMetrics(BaseModel):
    """Performance metrics for tracking team and individual performance over time"""
    team_id: str
    user_id: Optional[str] = None  # None for team-level metrics
    timestamp: datetime = Field(default_factory=datetime.now)

    # Core performance indicators
    productivity: float = Field(..., ge=0.0, le=1.0)
    communication: float = Field(..., ge=0.0, le=1.0)
    collaboration: float = Field(..., ge=0.0, le=1.0)
    engagement: float = Field(..., ge=0.0, le=1.0)
    quality: float = Field(..., ge=0.0, le=1.0)

    # Additional metrics
    satisfaction: Optional[float] = Field(None, ge=0.0, le=1.0)
    innovation: Optional[float] = Field(None, ge=0.0, le=1.0)
    leadership: Optional[float] = Field(None, ge=0.0, le=1.0)
    adaptability: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Context
    period_days: int = Field(default=7, ge=1, le=365)  # Period this metric covers
    source: str = Field(default="system")  # Source of the metric (system, survey, manual)

    @property
    def overall_score(self) -> float:
        """Calculate overall performance score from available metrics"""
        metrics = [self.productivity, self.communication, self.collaboration,
                  self.engagement, self.quality]
        valid_metrics = [m for m in metrics if m is not None]

        if not valid_metrics:
            return 0.0

        return sum(valid_metrics) / len(valid_metrics)

    @field_validator('timestamp', mode='before')
    @classmethod
    def validate_timestamp(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v


# Validation functions for data integrity
def validate_purpose_profile_completeness(profile: PurposeProfile) -> Dict[str, bool]:
    """Validate if purpose profile is complete enough for matching"""
    checks = {
        'has_core_values': len(profile.values.core) >= 3,
        'has_skills': profile.skills.skill_count >= 3,
        'has_passions': len(profile.passions) >= 2,
        'has_work_style': True,  # Always true if object exists
        'has_mission': profile.mission_statement is not None
    }
    
    return checks

def calculate_profile_confidence(profile: PurposeProfile, conversation_length: int) -> int:
    """Calculate confidence score based on profile completeness"""
    completeness = validate_purpose_profile_completeness(profile)
    
    base_score = sum(completeness.values()) * 15  # Max 75 from completeness
    conversation_bonus = min(25, conversation_length * 2)  # Max 25 from conversation
    
    return min(100, base_score + conversation_bonus)

# Mock data generators for testing
def generate_sample_user_profile() -> UserProfile:
    """Generate a sample user profile for testing"""
    return UserProfile(
        purposeProfile=PurposeProfile(
            values=Values(
                core=["Community Service", "Innovation", "Sustainability"],
                secondary=["Education", "Technology", "Health"],
                weights={"Community Service": 0.4, "Innovation": 0.35, "Sustainability": 0.25}
            ),
            workStyle=WorkStyle(
                collaboration=WorkStylePreference.HIGH,
                autonomy=WorkStylePreference.MEDIUM,
                structure=StructurePreference.MODERATE,
                communication=CommunicationStyle.SUPPORTIVE
            ),
            skills=Skills(
                technical=[
                    Skill(name="Python Programming", level=SkillLevel.ADVANCED, years_experience=5),
                    Skill(name="Data Analysis", level=SkillLevel.INTERMEDIATE, years_experience=3)
                ],
                soft=[
                    Skill(name="Communication", level=SkillLevel.ADVANCED, years_experience=8),
                    Skill(name="Problem Solving", level=SkillLevel.EXPERT, years_experience=10)
                ],
                leadership=[
                    Skill(name="Team Leadership", level=SkillLevel.INTERMEDIATE, years_experience=4)
                ]
            ),
            passions=["Clean Water Access", "Education Technology", "Community Development"],
            mission_statement="To leverage technology for sustainable community development and education access.",
            impact_areas=["Water Access", "Education", "Technology Transfer"]
        ),
        confidenceScore=92,
        status=UserStatus.READY_FOR_MATCHING
    )

def generate_sample_team_performance() -> TeamPerformance:
    """Generate sample team performance data"""
    return TeamPerformance(
        teamId="community-dev-001",
        members=["user-001", "user-002", "user-003"],
        metrics=TeamMetrics(
            productivity=0.87,
            collaboration=0.92,
            satisfaction=0.89,
            goalAchievement=0.94,
            innovation_score=0.85,
            communication_quality=0.91
        ),
        trends=TeamTrends(
            period="30 days",
            improvement=0.15,
            challenges=["Cross-cultural communication", "Time zone coordination"],
            successes=["Delivered clean water to 3 communities", "Exceeded productivity targets"]
        ),
        agent_recommendations=[
            CoachingInsight(
                insight="Schedule regular cultural exchange sessions to improve cross-cultural understanding",
                category="Communication",
                priority=2,
                estimated_impact=0.8
            )
        ]
    )

# Export all models for easy importing
__all__ = [
    'UserProfile', 'PurposeProfile', 'TeamPerformance', 'MatchResult',
    'TeamMetrics', 'Skills', 'Skill', 'Values', 'WorkStyle',
    'SkillLevel', 'WorkStylePreference', 'CommunicationStyle', 'StructurePreference',
    'UserStatus', 'CoachingInsight', 'TeamOpportunity', 'MatchExplanation',
    'validate_purpose_profile_completeness', 'calculate_profile_confidence',
    'generate_sample_user_profile', 'generate_sample_team_performance',
    'MatchScore', 'MatchReason', 'TeamMatch', 'TeamMember', 'PerformanceMetrics'
]