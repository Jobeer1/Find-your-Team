"""
Gamification Engine for Find Your Team

This module provides comprehensive gamification features including:
- Purpose Alignment Score calculation and display
- Talent Gap Score visualization with improvement suggestions
- Achievement and milestone tracking system
- Progress indicators and user feedback mechanisms
- Personalized challenge and growth opportunity systems
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import math

logger = logging.getLogger(__name__)

class AchievementType(Enum):
    """Types of achievements users can earn"""
    PURPOSE_DISCOVERY = "purpose_discovery"
    TEAM_MATCHING = "team_matching"
    SKILL_DEVELOPMENT = "skill_development"
    COMMUNITY_IMPACT = "community_impact"
    COLLABORATION = "collaboration"
    LEADERSHIP = "leadership"
    MENTORING = "mentoring"
    GROWTH_MILESTONE = "growth_milestone"

class DifficultyLevel(Enum):
    """Difficulty levels for challenges"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

class ProgressStatus(Enum):
    """Status of progress items"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"

@dataclass
class PurposeAlignment:
    """Purpose alignment score and breakdown"""
    overall_score: float  # 0.0 to 1.0
    values_alignment: float
    passion_alignment: float
    skills_match: float
    impact_potential: float
    confidence_level: float
    last_updated: datetime
    
    def get_percentage(self) -> int:
        """Get overall score as percentage"""
        return int(self.overall_score * 100)
    
    def get_grade(self) -> str:
        """Get letter grade for alignment"""
        if self.overall_score >= 0.9:
            return "A+"
        elif self.overall_score >= 0.85:
            return "A"
        elif self.overall_score >= 0.8:
            return "A-"
        elif self.overall_score >= 0.75:
            return "B+"
        elif self.overall_score >= 0.7:
            return "B"
        elif self.overall_score >= 0.65:
            return "B-"
        elif self.overall_score >= 0.6:
            return "C+"
        elif self.overall_score >= 0.55:
            return "C"
        else:
            return "C-"

@dataclass
class TalentGap:
    """Individual talent gap with improvement suggestions"""
    skill_name: str
    current_level: float  # 0.0 to 1.0
    target_level: float   # 0.0 to 1.0
    gap_size: float       # target - current
    importance: float     # 0.0 to 1.0 (how important this skill is)
    improvement_suggestions: List[str]
    resources: List[Dict[str, str]]  # {"type": "course", "title": "...", "url": "..."}
    estimated_time_weeks: int
    
    @property
    def gap_percentage(self) -> int:
        """Gap as percentage"""
        return int(self.gap_size * 100)
    
    @property
    def priority_score(self) -> float:
        """Priority score for addressing this gap"""
        return self.gap_size * self.importance

@dataclass
class TalentGapAnalysis:
    """Complete talent gap analysis"""
    user_id: str
    overall_readiness: float  # 0.0 to 1.0
    critical_gaps: List[TalentGap]
    improvement_gaps: List[TalentGap]
    strength_areas: List[str]
    recommended_focus: List[str]
    estimated_development_time: int  # weeks
    last_updated: datetime
    
    def get_readiness_percentage(self) -> int:
        """Get readiness as percentage"""
        return int(self.overall_readiness * 100)

@dataclass
class Achievement:
    """User achievement definition"""
    achievement_id: str
    user_id: str
    achievement_type: AchievementType
    title: str
    description: str
    icon: str
    points: int
    unlocked_at: Optional[datetime] = None
    progress: float = 0.0  # 0.0 to 1.0
    requirements: Dict[str, Any] = None
    
    @property
    def is_unlocked(self) -> bool:
        """Check if achievement is unlocked"""
        return self.unlocked_at is not None
    
    @property
    def progress_percentage(self) -> int:
        """Progress as percentage"""
        return int(self.progress * 100)

@dataclass
class Milestone:
    """User milestone definition"""
    milestone_id: str
    user_id: str
    title: str
    description: str
    target_date: datetime
    completion_date: Optional[datetime] = None
    progress: float = 0.0
    points_reward: int = 0
    celebration_message: str = ""
    
    @property
    def is_completed(self) -> bool:
        """Check if milestone is completed"""
        return self.completion_date is not None
    
    @property
    def days_until_target(self) -> int:
        """Days until target date"""
        return (self.target_date - datetime.utcnow()).days
    
    @property
    def is_overdue(self) -> bool:
        """Check if milestone is overdue"""
        return not self.is_completed and datetime.utcnow() > self.target_date

@dataclass
class Challenge:
    """Personalized challenge for user growth"""
    challenge_id: str
    user_id: str
    title: str
    description: str
    difficulty: DifficultyLevel
    category: str
    points_reward: int
    estimated_duration_days: int
    created_at: datetime
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    success_criteria: List[str] = None
    
    @property
    def is_accepted(self) -> bool:
        """Check if challenge is accepted"""
        return self.accepted_at is not None
    
    @property
    def is_completed(self) -> bool:
        """Check if challenge is completed"""
        return self.completed_at is not None
    
    @property
    def status(self) -> ProgressStatus:
        """Get challenge status"""
        if self.is_completed:
            return ProgressStatus.COMPLETED
        elif self.is_accepted:
            if self.accepted_at and (datetime.utcnow() - self.accepted_at).days > self.estimated_duration_days:
                return ProgressStatus.OVERDUE
            return ProgressStatus.IN_PROGRESS
        return ProgressStatus.NOT_STARTED

@dataclass
class UserEngagementProfile:
    """Complete user engagement and gamification profile"""
    user_id: str
    total_points: int
    level: int
    experience_points: int
    purpose_alignment: PurposeAlignment
    talent_gap_analysis: TalentGapAnalysis
    achievements: List[Achievement]
    milestones: List[Milestone]
    active_challenges: List[Challenge]
    engagement_streak_days: int
    last_activity: datetime
    created_at: datetime
    updated_at: datetime

class GamificationEngine:
    """Main gamification engine for Find Your Team"""
    
    def __init__(self, aws_config=None):
        self.aws_config = aws_config
        
        # Achievement definitions
        self.achievement_definitions = self._initialize_achievements()
        
        # Challenge templates
        self.challenge_templates = self._initialize_challenge_templates()
        
        # User profiles cache (in production, this would be in database)
        self.user_profiles: Dict[str, UserEngagementProfile] = {}
        
    def _initialize_achievements(self) -> Dict[str, Dict[str, Any]]:
        """Initialize achievement definitions"""
        return {
            "first_conversation": {
                "type": AchievementType.PURPOSE_DISCOVERY,
                "title": "First Steps",
                "description": "Started your first conversation with the onboarding agent",
                "icon": "🌱",
                "points": 50,
                "requirements": {"conversations": 1}
            },
            "purpose_clarity": {
                "type": AchievementType.PURPOSE_DISCOVERY,
                "title": "Purpose Seeker",
                "description": "Achieved 80% purpose alignment confidence",
                "icon": "🎯",
                "points": 200,
                "requirements": {"purpose_confidence": 0.8}
            },
            "first_match": {
                "type": AchievementType.TEAM_MATCHING,
                "title": "Team Explorer",
                "description": "Found your first team match",
                "icon": "🤝",
                "points": 100,
                "requirements": {"team_matches": 1}
            },
            "skill_developer": {
                "type": AchievementType.SKILL_DEVELOPMENT,
                "title": "Skill Builder",
                "description": "Completed a skill development challenge",
                "icon": "📚",
                "points": 150,
                "requirements": {"skill_challenges_completed": 1}
            },
            "community_champion": {
                "type": AchievementType.COMMUNITY_IMPACT,
                "title": "Community Champion",
                "description": "Made measurable impact in your community",
                "icon": "🌟",
                "points": 300,
                "requirements": {"community_impact_projects": 1}
            },
            "collaboration_master": {
                "type": AchievementType.COLLABORATION,
                "title": "Collaboration Master",
                "description": "Successfully collaborated on 5 team projects",
                "icon": "🤝",
                "points": 250,
                "requirements": {"team_projects": 5}
            },
            "mentor": {
                "type": AchievementType.MENTORING,
                "title": "Mentor",
                "description": "Mentored another team member",
                "icon": "🧑‍🏫",
                "points": 200,
                "requirements": {"mentees": 1}
            },
            "growth_champion": {
                "type": AchievementType.GROWTH_MILESTONE,
                "title": "Growth Champion",
                "description": "Reached Level 10",
                "icon": "🚀",
                "points": 500,
                "requirements": {"level": 10}
            }
        }
    
    def _initialize_challenge_templates(self) -> List[Dict[str, Any]]:
        """Initialize challenge templates"""
        return [
            {
                "title": "Define Your Values",
                "description": "Identify and articulate your top 5 core values",
                "difficulty": DifficultyLevel.BEGINNER,
                "category": "Purpose Discovery",
                "points": 100,
                "duration_days": 7,
                "criteria": ["List 5 core values", "Explain why each value matters", "Share with team"]
            },
            {
                "title": "Skill Gap Analysis",
                "description": "Complete a comprehensive skill assessment",
                "difficulty": DifficultyLevel.INTERMEDIATE,
                "category": "Skill Development",
                "points": 150,
                "duration_days": 14,
                "criteria": ["Take skill assessment", "Identify top 3 gaps", "Create improvement plan"]
            },
            {
                "title": "Community Research Project",
                "description": "Research a local community need and propose solutions",
                "difficulty": DifficultyLevel.ADVANCED,
                "category": "Community Impact",
                "points": 300,
                "duration_days": 21,
                "criteria": ["Research community need", "Interview stakeholders", "Present solution proposal"]
            },
            {
                "title": "Leadership Challenge",
                "description": "Lead a team initiative for 30 days",
                "difficulty": DifficultyLevel.EXPERT,
                "category": "Leadership Development", 
                "points": 500,
                "duration_days": 30,
                "criteria": ["Define team goals", "Coordinate activities", "Achieve measurable results"]
            }
        ]
    
    async def get_user_profile(self, user_id: str) -> UserEngagementProfile:
        """Get or create user engagement profile"""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = await self._create_user_profile(user_id)
        
        return self.user_profiles[user_id]
    
    async def _create_user_profile(self, user_id: str) -> UserEngagementProfile:
        """Create new user engagement profile"""
        now = datetime.utcnow()
        
        # Initialize purpose alignment
        purpose_alignment = PurposeAlignment(
            overall_score=0.0,
            values_alignment=0.0,
            passion_alignment=0.0,
            skills_match=0.0,
            impact_potential=0.0,
            confidence_level=0.0,
            last_updated=now
        )
        
        # Initialize talent gap analysis
        talent_gap_analysis = TalentGapAnalysis(
            user_id=user_id,
            overall_readiness=0.0,
            critical_gaps=[],
            improvement_gaps=[],
            strength_areas=[],
            recommended_focus=[],
            estimated_development_time=0,
            last_updated=now
        )
        
        return UserEngagementProfile(
            user_id=user_id,
            total_points=0,
            level=1,
            experience_points=0,
            purpose_alignment=purpose_alignment,
            talent_gap_analysis=talent_gap_analysis,
            achievements=[],
            milestones=[],
            active_challenges=[],
            engagement_streak_days=0,
            last_activity=now,
            created_at=now,
            updated_at=now
        )
    
    async def calculate_purpose_alignment(self, user_id: str, conversation_data: Dict[str, Any]) -> PurposeAlignment:
        """Calculate purpose alignment score from conversation data"""
        profile = await self.get_user_profile(user_id)
        
        # Extract values, passions, and skills from conversation
        values_mentioned = self._extract_values(conversation_data)
        passions_identified = self._extract_passions(conversation_data)
        skills_assessed = self._extract_skills(conversation_data)
        
        # Calculate component scores
        values_alignment = self._calculate_values_alignment(values_mentioned)
        passion_alignment = self._calculate_passion_alignment(passions_identified)
        skills_match = self._calculate_skills_match(skills_assessed)
        impact_potential = self._calculate_impact_potential(conversation_data)
        confidence_level = conversation_data.get('confidence_score', 0.0)
        
        # Calculate overall score (weighted average)
        overall_score = (
            values_alignment * 0.25 +
            passion_alignment * 0.25 +
            skills_match * 0.20 +
            impact_potential * 0.20 +
            confidence_level * 0.10
        )
        
        purpose_alignment = PurposeAlignment(
            overall_score=min(overall_score, 1.0),
            values_alignment=values_alignment,
            passion_alignment=passion_alignment,
            skills_match=skills_match,
            impact_potential=impact_potential,
            confidence_level=confidence_level,
            last_updated=datetime.utcnow()
        )
        
        # Update user profile
        profile.purpose_alignment = purpose_alignment
        profile.updated_at = datetime.utcnow()
        
        # Check for achievements
        await self._check_purpose_achievements(profile)
        
        return purpose_alignment
    
    async def analyze_talent_gaps(self, user_id: str, user_profile: Dict[str, Any], team_requirements: Dict[str, Any] = None) -> TalentGapAnalysis:
        """Analyze talent gaps and provide improvement suggestions"""
        profile = await self.get_user_profile(user_id)
        
        # Define key skills for community impact work
        key_skills = {
            "communication": {"weight": 0.9, "description": "Clear and empathetic communication"},
            "leadership": {"weight": 0.8, "description": "Ability to guide and inspire others"},
            "problem_solving": {"weight": 0.85, "description": "Creative solution finding"},
            "project_management": {"weight": 0.7, "description": "Planning and execution skills"},
            "community_engagement": {"weight": 0.9, "description": "Building community relationships"},
            "technical_skills": {"weight": 0.6, "description": "Relevant technical capabilities"},
            "cultural_awareness": {"weight": 0.8, "description": "Understanding diverse perspectives"},
            "empathy": {"weight": 0.95, "description": "Deep understanding of others' needs"}
        }
        
        critical_gaps = []
        improvement_gaps = []
        strength_areas = []
        
        overall_readiness = 0.0
        total_weight = 0.0
        
        for skill, config in key_skills.items():
            # Get current level from user profile
            current_level = self._get_skill_level(user_profile, skill)
            target_level = 0.8  # Target 80% proficiency
            
            if team_requirements and skill in team_requirements:
                target_level = team_requirements[skill]
            
            gap_size = max(0, target_level - current_level)
            
            # Calculate weighted readiness
            skill_readiness = min(current_level / target_level, 1.0) if target_level > 0 else 1.0
            overall_readiness += skill_readiness * config["weight"]
            total_weight += config["weight"]
            
            if current_level >= 0.8:
                strength_areas.append(skill)
            elif gap_size >= 0.3:
                # Critical gap
                critical_gaps.append(TalentGap(
                    skill_name=skill,
                    current_level=current_level,
                    target_level=target_level,
                    gap_size=gap_size,
                    importance=config["weight"],
                    improvement_suggestions=self._get_improvement_suggestions(skill),
                    resources=self._get_skill_resources(skill),
                    estimated_time_weeks=int(gap_size * 12)  # Rough estimate
                ))
            elif gap_size > 0:
                # Improvement gap
                improvement_gaps.append(TalentGap(
                    skill_name=skill,
                    current_level=current_level,
                    target_level=target_level,
                    gap_size=gap_size,
                    importance=config["weight"],
                    improvement_suggestions=self._get_improvement_suggestions(skill),
                    resources=self._get_skill_resources(skill),
                    estimated_time_weeks=int(gap_size * 8)
                ))
        
        # Normalize overall readiness
        if total_weight > 0:
            overall_readiness /= total_weight
        
        # Sort gaps by priority
        critical_gaps.sort(key=lambda x: x.priority_score, reverse=True)
        improvement_gaps.sort(key=lambda x: x.priority_score, reverse=True)
        
        # Generate recommended focus areas
        recommended_focus = [gap.skill_name for gap in critical_gaps[:3]]
        if len(recommended_focus) < 3:
            recommended_focus.extend([gap.skill_name for gap in improvement_gaps[:3-len(recommended_focus)]])
        
        # Calculate total estimated development time
        estimated_time = sum(gap.estimated_time_weeks for gap in critical_gaps[:3])
        
        talent_analysis = TalentGapAnalysis(
            user_id=user_id,
            overall_readiness=overall_readiness,
            critical_gaps=critical_gaps,
            improvement_gaps=improvement_gaps,
            strength_areas=strength_areas,
            recommended_focus=recommended_focus,
            estimated_development_time=estimated_time,
            last_updated=datetime.utcnow()
        )
        
        # Update user profile
        profile.talent_gap_analysis = talent_analysis
        profile.updated_at = datetime.utcnow()
        
        return talent_analysis
    
    def _extract_values(self, conversation_data: Dict[str, Any]) -> List[str]:
        """Extract values from conversation data"""
        values_keywords = {
            "helping_others": ["help", "support", "assist", "care"],
            "justice": ["justice", "fair", "equality", "rights"],
            "community": ["community", "together", "collective", "social"],
            "education": ["education", "learning", "teaching", "knowledge"],
            "innovation": ["innovation", "creative", "new", "improve"],
            "sustainability": ["sustainable", "environment", "future", "green"]
        }
        
        text = json.dumps(conversation_data).lower()
        identified_values = []
        
        for value, keywords in values_keywords.items():
            if any(keyword in text for keyword in keywords):
                identified_values.append(value)
        
        return identified_values
    
    def _extract_passions(self, conversation_data: Dict[str, Any]) -> List[str]:
        """Extract passions from conversation data"""
        # Similar to values extraction but for passion areas
        passion_keywords = {
            "poverty_alleviation": ["poverty", "poor", "disadvantaged", "underprivileged"],
            "education": ["education", "teaching", "learning", "school"],
            "healthcare": ["health", "medical", "wellness", "care"],
            "technology": ["technology", "tech", "digital", "software"],
            "environment": ["environment", "climate", "nature", "conservation"],
            "arts": ["art", "creative", "music", "culture"]
        }
        
        text = json.dumps(conversation_data).lower()
        identified_passions = []
        
        for passion, keywords in passion_keywords.items():
            if any(keyword in text for keyword in keywords):
                identified_passions.append(passion)
        
        return identified_passions
    
    def _extract_skills(self, conversation_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract skill levels from conversation data"""
        # This would be more sophisticated in a real implementation
        return {
            "communication": 0.7,
            "leadership": 0.6,
            "problem_solving": 0.75,
            "project_management": 0.5,
            "technical_skills": 0.65
        }
    
    def _calculate_values_alignment(self, values: List[str]) -> float:
        """Calculate values alignment score"""
        if not values:
            return 0.0
        
        # More values identified = higher alignment
        return min(len(values) / 5.0, 1.0)
    
    def _calculate_passion_alignment(self, passions: List[str]) -> float:
        """Calculate passion alignment score"""
        if not passions:
            return 0.0
        
        return min(len(passions) / 3.0, 1.0)
    
    def _calculate_skills_match(self, skills: Dict[str, float]) -> float:
        """Calculate skills match score"""
        if not skills:
            return 0.0
        
        return sum(skills.values()) / len(skills)
    
    def _calculate_impact_potential(self, conversation_data: Dict[str, Any]) -> float:
        """Calculate potential for community impact"""
        # Look for indicators of impact orientation
        text = json.dumps(conversation_data).lower()
        impact_indicators = ["impact", "change", "difference", "improve", "help", "community"]
        
        score = sum(1 for indicator in impact_indicators if indicator in text) / len(impact_indicators)
        return min(score, 1.0)
    
    def _get_skill_level(self, user_profile: Dict[str, Any], skill: str) -> float:
        """Get current skill level from user profile"""
        skills = user_profile.get('skills', {})
        return skills.get(skill, 0.3)  # Default to 30% if not specified
    
    def _get_improvement_suggestions(self, skill: str) -> List[str]:
        """Get improvement suggestions for a skill"""
        suggestions_map = {
            "communication": [
                "Practice active listening in daily conversations",
                "Join a public speaking group like Toastmasters",
                "Write regular blog posts about your experiences",
                "Volunteer to present at team meetings"
            ],
            "leadership": [
                "Volunteer to lead a small team project",
                "Take on mentoring responsibilities",
                "Read leadership books and apply concepts",
                "Seek feedback from current and former colleagues"
            ],
            "problem_solving": [
                "Practice design thinking methodologies",
                "Work on challenging puzzles and brain teasers",
                "Study case studies in your field",
                "Collaborate on complex projects with diverse teams"
            ],
            "project_management": [
                "Get certified in agile or scrum methodologies",
                "Use project management tools daily",
                "Lead a small volunteer project from start to finish",
                "Shadow an experienced project manager"
            ],
            "community_engagement": [
                "Volunteer with local community organizations",
                "Attend community meetings and forums",
                "Start a neighborhood initiative",
                "Connect with community leaders"
            ],
            "technical_skills": [
                "Take online courses in relevant technologies",
                "Build small projects to practice skills",
                "Contribute to open source projects",
                "Find a technical mentor"
            ],
            "cultural_awareness": [
                "Read books about different cultures",
                "Attend cultural events and festivals",
                "Learn basic phrases in other languages",
                "Travel or connect with people from different backgrounds"
            ],
            "empathy": [
                "Practice perspective-taking exercises",
                "Volunteer with vulnerable populations",
                "Read stories and memoirs from diverse authors",
                "Engage in deep listening conversations"
            ]
        }
        
        return suggestions_map.get(skill, ["Seek relevant training and practice opportunities"])
    
    def _get_skill_resources(self, skill: str) -> List[Dict[str, str]]:
        """Get learning resources for a skill"""
        resources_map = {
            "communication": [
                {"type": "course", "title": "Effective Communication Skills", "url": "https://coursera.org/communication"},
                {"type": "book", "title": "Crucial Conversations", "url": "https://amazon.com/crucial-conversations"},
                {"type": "practice", "title": "Toastmasters International", "url": "https://toastmasters.org"}
            ],
            "leadership": [
                {"type": "course", "title": "Leadership in the 21st Century", "url": "https://edx.org/leadership"},
                {"type": "book", "title": "The 7 Habits of Highly Effective People", "url": "https://amazon.com/7-habits"},
                {"type": "assessment", "title": "StrengthsFinder 2.0", "url": "https://gallup.com/strengthsfinder"}
            ],
            "problem_solving": [
                {"type": "course", "title": "Design Thinking", "url": "https://ideo.com/design-thinking"},
                {"type": "book", "title": "The Lean Startup", "url": "https://amazon.com/lean-startup"},
                {"type": "practice", "title": "Case Study Practice", "url": "https://hbr.org/case-studies"}
            ]
        }
        
        return resources_map.get(skill, [
            {"type": "search", "title": f"Online courses for {skill}", "url": f"https://coursera.org/search?query={skill}"}
        ])
    
    async def award_points(self, user_id: str, points: int, reason: str = "") -> int:
        """Award points to user and check for level up"""
        profile = await self.get_user_profile(user_id)
        
        profile.total_points += points
        profile.experience_points += points
        profile.last_activity = datetime.utcnow()
        profile.updated_at = datetime.utcnow()
        
        # Check for level up
        old_level = profile.level
        new_level = self._calculate_level(profile.total_points)
        
        if new_level > old_level:
            profile.level = new_level
            await self._handle_level_up(profile, old_level, new_level)
        
        # Update engagement streak
        await self._update_engagement_streak(profile)
        
        return profile.total_points
    
    def _calculate_level(self, total_points: int) -> int:
        """Calculate user level based on total points"""
        # Level formula: level = sqrt(points / 100)
        return max(1, int(math.sqrt(total_points / 100)))
    
    async def _handle_level_up(self, profile: UserEngagementProfile, old_level: int, new_level: int):
        """Handle level up event"""
        logger.info(f"User {profile.user_id} leveled up from {old_level} to {new_level}")
        
        # Check for level-based achievements
        await self._check_level_achievements(profile)
        
        # Generate celebration milestone
        celebration_milestone = Milestone(
            milestone_id=str(uuid.uuid4()),
            user_id=profile.user_id,
            title=f"Reached Level {new_level}!",
            description=f"Congratulations on advancing from level {old_level} to level {new_level}!",
            target_date=datetime.utcnow(),
            completion_date=datetime.utcnow(),
            progress=1.0,
            points_reward=new_level * 10,
            celebration_message=f"🎉 Amazing progress! You've reached level {new_level}!"
        )
        
        profile.milestones.append(celebration_milestone)
    
    async def _update_engagement_streak(self, profile: UserEngagementProfile):
        """Update user's engagement streak"""
        now = datetime.utcnow()
        last_activity = profile.last_activity
        
        if last_activity:
            days_since_last = (now - last_activity).days
            
            if days_since_last == 1:
                # Consecutive day - increment streak
                profile.engagement_streak_days += 1
            elif days_since_last > 1:
                # Streak broken - reset
                profile.engagement_streak_days = 1
            # If same day (days_since_last == 0), keep current streak
        else:
            profile.engagement_streak_days = 1
        
        profile.last_activity = now
    
    async def check_achievements(self, user_id: str, action_data: Dict[str, Any] = None) -> List[Achievement]:
        """Check and award achievements based on user actions"""
        profile = await self.get_user_profile(user_id)
        new_achievements = []
        
        for achievement_id, definition in self.achievement_definitions.items():
            # Check if already unlocked
            if any(ach.achievement_id == achievement_id and ach.is_unlocked for ach in profile.achievements):
                continue
            
            # Check requirements
            if self._check_achievement_requirements(profile, definition, action_data):
                achievement = Achievement(
                    achievement_id=achievement_id,
                    user_id=user_id,
                    achievement_type=definition["type"],
                    title=definition["title"],
                    description=definition["description"],
                    icon=definition["icon"],
                    points=definition["points"],
                    unlocked_at=datetime.utcnow(),
                    progress=1.0,
                    requirements=definition["requirements"]
                )
                
                profile.achievements.append(achievement)
                new_achievements.append(achievement)
                
                # Award points
                await self.award_points(user_id, definition["points"], f"Achievement: {definition['title']}")
        
        return new_achievements
    
    def _check_achievement_requirements(self, profile: UserEngagementProfile, definition: Dict[str, Any], action_data: Dict[str, Any] = None) -> bool:
        """Check if achievement requirements are met"""
        requirements = definition.get("requirements", {})
        
        for req_type, req_value in requirements.items():
            if req_type == "conversations":
                # Count conversations (simplified - would track in real implementation)
                return True  # Assume met for demo
            elif req_type == "purpose_confidence":
                return profile.purpose_alignment.confidence_level >= req_value
            elif req_type == "team_matches":
                # Would track team matches in real implementation
                return True  # Assume met for demo
            elif req_type == "level":
                return profile.level >= req_value
            # Add other requirement types as needed
        
        return True
    
    async def _check_purpose_achievements(self, profile: UserEngagementProfile):
        """Check for purpose-related achievements"""
        await self.check_achievements(profile.user_id, {"purpose_confidence": profile.purpose_alignment.confidence_level})
    
    async def _check_level_achievements(self, profile: UserEngagementProfile):
        """Check for level-based achievements"""
        await self.check_achievements(profile.user_id, {"level": profile.level})
    
    async def generate_personalized_challenges(self, user_id: str, count: int = 3) -> List[Challenge]:
        """Generate personalized challenges based on user profile"""
        profile = await self.get_user_profile(user_id)
        challenges = []
        
        # Focus on talent gaps for challenge generation
        focus_areas = profile.talent_gap_analysis.recommended_focus[:count]
        
        for i, skill in enumerate(focus_areas):
            template = self._select_challenge_template(skill, profile.level)
            
            challenge = Challenge(
                challenge_id=str(uuid.uuid4()),
                user_id=user_id,
                title=f"{template['title']} ({skill.replace('_', ' ').title()})",
                description=f"{template['description']} Focus on improving your {skill.replace('_', ' ')} skills.",
                difficulty=template["difficulty"],
                category=template["category"],
                points_reward=template["points"] + (profile.level * 10),
                estimated_duration_days=template["duration_days"],
                created_at=datetime.utcnow(),
                success_criteria=template["criteria"]
            )
            
            challenges.append(challenge)
        
        return challenges
    
    def _select_challenge_template(self, skill: str, user_level: int) -> Dict[str, Any]:
        """Select appropriate challenge template based on skill and user level"""
        # Filter templates by difficulty appropriate for user level
        if user_level <= 3:
            difficulty_filter = [DifficultyLevel.BEGINNER]
        elif user_level <= 7:
            difficulty_filter = [DifficultyLevel.BEGINNER, DifficultyLevel.INTERMEDIATE]
        elif user_level <= 12:
            difficulty_filter = [DifficultyLevel.INTERMEDIATE, DifficultyLevel.ADVANCED]
        else:
            difficulty_filter = [DifficultyLevel.ADVANCED, DifficultyLevel.EXPERT]
        
        # Find suitable templates
        suitable_templates = [
            template for template in self.challenge_templates
            if template["difficulty"] in difficulty_filter
        ]
        
        # Return first suitable template (in real implementation, would be more sophisticated)
        return suitable_templates[0] if suitable_templates else self.challenge_templates[0]
    
    async def get_progress_summary(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive progress summary for user"""
        profile = await self.get_user_profile(user_id)
        
        return {
            "user_id": user_id,
            "level": profile.level,
            "total_points": profile.total_points,
            "engagement_streak": profile.engagement_streak_days,
            "purpose_alignment": {
                "score": profile.purpose_alignment.get_percentage(),
                "grade": profile.purpose_alignment.get_grade(),
                "breakdown": {
                    "values": int(profile.purpose_alignment.values_alignment * 100),
                    "passion": int(profile.purpose_alignment.passion_alignment * 100),
                    "skills": int(profile.purpose_alignment.skills_match * 100),
                    "impact": int(profile.purpose_alignment.impact_potential * 100)
                }
            },
            "talent_readiness": {
                "overall": profile.talent_gap_analysis.get_readiness_percentage(),
                "critical_gaps": len(profile.talent_gap_analysis.critical_gaps),
                "focus_areas": profile.talent_gap_analysis.recommended_focus,
                "estimated_development_weeks": profile.talent_gap_analysis.estimated_development_time
            },
            "achievements": {
                "total": len([ach for ach in profile.achievements if ach.is_unlocked]),
                "recent": [
                    {
                        "title": ach.title,
                        "icon": ach.icon,
                        "points": ach.points,
                        "unlocked_at": ach.unlocked_at.isoformat() if ach.unlocked_at else None
                    }
                    for ach in sorted(profile.achievements, key=lambda x: x.unlocked_at or datetime.min, reverse=True)[:3]
                    if ach.is_unlocked
                ]
            },
            "active_challenges": len(profile.active_challenges),
            "completed_milestones": len([m for m in profile.milestones if m.is_completed])
        }