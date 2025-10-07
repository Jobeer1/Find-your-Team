"""
Comprehensive tests for the Gamification Engine

Tests purpose alignment calculation, talent gap analysis, achievements,
challenges, and user engagement features
"""

import unittest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add the parent directory to the path so we can import the gamification engine
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gamification.engine import (
    GamificationEngine, PurposeAlignment, TalentGap, TalentGapAnalysis,
    Achievement, Milestone, Challenge, UserEngagementProfile,
    AchievementType, DifficultyLevel, ProgressStatus
)


class MockAWSConfig:
    """Mock AWS configuration for testing"""
    
    def __init__(self):
        self.demo_mode = True


class TestGamificationEngine(unittest.TestCase):
    """Test cases for GamificationEngine"""
    
    def setUp(self):
        """Set up test environment"""
        self.aws_config = MockAWSConfig()
        self.engine = GamificationEngine(self.aws_config)
    
    async def test_user_profile_creation(self):
        """Test creating a new user profile"""
        user_id = "test_user_123"
        profile = await self.engine.get_user_profile(user_id)
        
        # Check basic profile structure
        self.assertEqual(profile.user_id, user_id)
        self.assertEqual(profile.level, 1)
        self.assertEqual(profile.total_points, 0)
        self.assertEqual(profile.engagement_streak_days, 0)
        
        # Check purpose alignment initialization
        self.assertEqual(profile.purpose_alignment.overall_score, 0.0)
        self.assertEqual(profile.purpose_alignment.get_grade(), "C-")
        
        # Check talent gap analysis initialization
        self.assertEqual(profile.talent_gap_analysis.overall_readiness, 0.0)
        self.assertEqual(len(profile.talent_gap_analysis.critical_gaps), 0)
        
    async def test_purpose_alignment_calculation(self):
        """Test purpose alignment score calculation"""
        user_id = "test_user_123"
        
        conversation_data = {
            "messages": [
                "I want to help poor communities through education",
                "I value justice, equality, and community support",
                "I have strong communication and teaching skills"
            ],
            "confidence_score": 0.85
        }
        
        alignment = await self.engine.calculate_purpose_alignment(user_id, conversation_data)
        
        # Check that alignment was calculated
        self.assertGreater(alignment.overall_score, 0.0)
        self.assertLessEqual(alignment.overall_score, 1.0)
        
        # Check that values, passions, and skills were identified
        self.assertGreater(alignment.values_alignment, 0.0)
        self.assertGreater(alignment.passion_alignment, 0.0)
        self.assertGreater(alignment.skills_match, 0.0)
        
        # Check grade assignment
        grade = alignment.get_grade()
        self.assertIn(grade, ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-"])
        
    def test_values_extraction(self):
        """Test extracting values from conversation data"""
        conversation_data = {
            "messages": ["I care about helping others and fighting for justice in my community"]
        }
        
        values = self.engine._extract_values(conversation_data)
        
        # Should identify helping_others, justice, and community values
        expected_values = ["helping_others", "justice", "community"]
        for expected_value in expected_values:
            self.assertIn(expected_value, values)
    
    def test_passions_extraction(self):
        """Test extracting passions from conversation data"""
        conversation_data = {
            "messages": ["I'm passionate about education and healthcare for the poor"]
        }
        
        passions = self.engine._extract_passions(conversation_data)
        
        # Should identify education, healthcare, and poverty_alleviation
        expected_passions = ["education", "healthcare", "poverty_alleviation"]
        for expected_passion in expected_passions:
            self.assertIn(expected_passion, passions)
    
    async def test_talent_gap_analysis(self):
        """Test comprehensive talent gap analysis"""
        user_id = "test_user_123"
        user_profile = {
            "skills": {
                "communication": 0.8,  # Strong
                "leadership": 0.4,     # Weak - should be critical gap
                "problem_solving": 0.65,  # Moderate - improvement gap
                "empathy": 0.9,        # Strong
                "technical_skills": 0.3  # Weak - critical gap
            }
        }
        
        analysis = await self.engine.analyze_talent_gaps(user_id, user_profile)
        
        # Check overall readiness calculation
        self.assertGreater(analysis.overall_readiness, 0.0)
        self.assertLessEqual(analysis.overall_readiness, 1.0)
        
        # Check gap categorization
        self.assertGreater(len(analysis.critical_gaps), 0)
        
        # Check that critical gaps are properly identified
        critical_skills = [gap.skill_name for gap in analysis.critical_gaps]
        self.assertIn("leadership", critical_skills)  # Should be critical (0.4 vs 0.8 target)
        
        # Check strength areas
        self.assertIn("communication", analysis.strength_areas)
        self.assertIn("empathy", analysis.strength_areas)
        
        # Check recommended focus
        self.assertGreater(len(analysis.recommended_focus), 0)
        self.assertLessEqual(len(analysis.recommended_focus), 3)
    
    def test_talent_gap_priority_calculation(self):
        """Test talent gap priority scoring"""
        gap = TalentGap(
            skill_name="leadership",
            current_level=0.4,
            target_level=0.8,
            gap_size=0.4,
            importance=0.9,
            improvement_suggestions=[],
            resources=[],
            estimated_time_weeks=12
        )
        
        # Priority should be gap_size * importance
        expected_priority = 0.4 * 0.9
        self.assertAlmostEqual(gap.priority_score, expected_priority, places=2)
        
        # Check percentage calculation
        self.assertEqual(gap.gap_percentage, 40)
    
    async def test_points_and_level_system(self):
        """Test point awarding and level calculation"""
        user_id = "test_user_123"
        
        # Award points
        total_points = await self.engine.award_points(user_id, 150, "Test achievement")
        self.assertEqual(total_points, 150)
        
        # Check level calculation
        profile = await self.engine.get_user_profile(user_id)
        expected_level = max(1, int((150 / 100) ** 0.5))
        self.assertEqual(profile.level, expected_level)
        
        # Award more points to test level up
        await self.engine.award_points(user_id, 250, "More achievements")
        profile = await self.engine.get_user_profile(user_id)
        
        # Should have leveled up - level calculation is 1 + (points // 100)
        new_expected_level = 1 + (400 // 100)
        self.assertEqual(profile.level, new_expected_level)
        
        # Check that level up milestone was created
        level_milestones = [m for m in profile.milestones if "Level" in m.title]
        self.assertGreater(len(level_milestones), 0)
    
    async def test_engagement_streak_tracking(self):
        """Test engagement streak calculation"""
        user_id = "test_user_123"
        
        # First activity sets streak to 0 initially, then update_streak is called which will check
        await self.engine.award_points(user_id, 10, "First activity")
        profile = await self.engine.get_user_profile(user_id)
        
        # Manually update streak after first activity
        await self.engine._update_engagement_streak(profile)
        self.assertEqual(profile.engagement_streak_days, 1)
        
        # Simulate next day activity
        profile.last_activity = datetime.utcnow() - timedelta(days=1)
        await self.engine._update_engagement_streak(profile)
        self.assertEqual(profile.engagement_streak_days, 2)
        
        # Simulate break in streak
        profile.last_activity = datetime.utcnow() - timedelta(days=3)
        await self.engine._update_engagement_streak(profile)
        self.assertEqual(profile.engagement_streak_days, 1)  # Reset to 1
    
    async def test_achievement_system(self):
        """Test achievement checking and awarding"""
        user_id = "test_user_123"
        
        # Test purpose alignment achievement
        conversation_data = {
            "confidence_score": 0.85,  # Should trigger purpose_clarity achievement
            "messages": ["I have a clear sense of my purpose"]
        }
        
        await self.engine.calculate_purpose_alignment(user_id, conversation_data)
        
        # Check if achievements were awarded
        profile = await self.engine.get_user_profile(user_id)
        unlocked_achievements = [ach for ach in profile.achievements if ach.is_unlocked]
        
        # Should have at least some achievements
        self.assertGreater(len(unlocked_achievements), 0)
        
        # Check achievement structure
        if unlocked_achievements:
            achievement = unlocked_achievements[0]
            self.assertIsNotNone(achievement.title)
            self.assertIsNotNone(achievement.description)
            self.assertIsNotNone(achievement.icon)
            self.assertGreater(achievement.points, 0)
            self.assertIsNotNone(achievement.unlocked_at)
    
    def test_achievement_requirements_checking(self):
        """Test achievement requirements validation"""
        user_id = "test_user_123"
        
        # Create a mock profile with specific characteristics
        profile = UserEngagementProfile(
            user_id=user_id,
            total_points=500,
            level=5,
            experience_points=500,
            purpose_alignment=PurposeAlignment(
                overall_score=0.9,
                values_alignment=0.8,
                passion_alignment=0.85,
                skills_match=0.9,
                impact_potential=0.95,
                confidence_level=0.85,
                last_updated=datetime.utcnow()
            ),
            talent_gap_analysis=TalentGapAnalysis(
                user_id=user_id,
                overall_readiness=0.8,
                critical_gaps=[],
                improvement_gaps=[],
                strength_areas=["communication"],
                recommended_focus=[],
                estimated_development_time=0,
                last_updated=datetime.utcnow()
            ),
            achievements=[],
            milestones=[],
            active_challenges=[],
            engagement_streak_days=5,
            last_activity=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Test purpose_clarity achievement requirement
        definition = self.engine.achievement_definitions["purpose_clarity"]
        self.assertTrue(
            self.engine._check_achievement_requirements(profile, definition)
        )
        
        # Test level-based achievement
        definition = self.engine.achievement_definitions["growth_champion"]  # Level 10 required
        self.assertFalse(
            self.engine._check_achievement_requirements(profile, definition)
        )
    
    async def test_personalized_challenges_generation(self):
        """Test generating personalized challenges"""
        user_id = "test_user_123"
        
        # Create profile with talent gaps
        profile = await self.engine.get_user_profile(user_id)
        profile.talent_gap_analysis.recommended_focus = ["leadership", "communication", "empathy"]
        profile.level = 5
        
        # Generate challenges
        challenges = await self.engine.generate_personalized_challenges(user_id, 3)
        
        # Check challenge generation
        self.assertEqual(len(challenges), 3)
        
        for challenge in challenges:
            self.assertIsNotNone(challenge.title)
            self.assertIsNotNone(challenge.description)
            # Check if difficulty is either enum or string value
            if hasattr(challenge.difficulty, 'value'):
                self.assertIn(challenge.difficulty.value, [d.value for d in DifficultyLevel])
            else:
                self.assertIn(challenge.difficulty, [d.value for d in DifficultyLevel])
            self.assertGreater(challenge.points_reward, 0)
            self.assertGreater(challenge.estimated_duration_days, 0)
            self.assertEqual(challenge.status, ProgressStatus.NOT_STARTED)
    
    def test_challenge_difficulty_selection(self):
        """Test appropriate difficulty selection for challenges"""
        # Test beginner level user
        template = self.engine._select_challenge_template("leadership", 2)
        self.assertIn(template["difficulty"], [DifficultyLevel.BEGINNER])
        
        # Test intermediate level user
        template = self.engine._select_challenge_template("leadership", 6)
        self.assertIn(template["difficulty"], [DifficultyLevel.BEGINNER, DifficultyLevel.INTERMEDIATE])
        
        # Test advanced level user
        template = self.engine._select_challenge_template("leadership", 15)
        self.assertIn(template["difficulty"], [DifficultyLevel.ADVANCED, DifficultyLevel.EXPERT])
    
    async def test_progress_summary(self):
        """Test comprehensive progress summary generation"""
        user_id = "test_user_123"
        
        # Set up user with some progress
        await self.engine.award_points(user_id, 300, "Test progress")
        profile = await self.engine.get_user_profile(user_id)
        
        # Add some achievements
        achievement = Achievement(
            achievement_id="test_achievement",
            user_id=user_id,
            achievement_type=AchievementType.PURPOSE_DISCOVERY,
            title="Test Achievement",
            description="Test description",
            icon="🎯",
            points=100,
            unlocked_at=datetime.utcnow(),
            progress=1.0
        )
        profile.achievements.append(achievement)
        
        # Get progress summary
        summary = await self.engine.get_progress_summary(user_id)
        
        # Check summary structure
        self.assertIn("user_id", summary)
        self.assertIn("level", summary)
        self.assertIn("total_points", summary)
        self.assertIn("purpose_alignment", summary)
        self.assertIn("talent_readiness", summary)
        self.assertIn("achievements", summary)
        
        # Check purpose alignment structure
        purpose = summary["purpose_alignment"]
        self.assertIn("score", purpose)
        self.assertIn("grade", purpose)
        self.assertIn("breakdown", purpose)
        
        # Check achievements structure
        achievements = summary["achievements"]
        self.assertIn("total", achievements)
        self.assertIn("recent", achievements)
        self.assertEqual(achievements["total"], 1)  # One unlocked achievement
    
    def test_skill_improvement_suggestions(self):
        """Test skill improvement suggestion generation"""
        # Test communication skill suggestions
        suggestions = self.engine._get_improvement_suggestions("communication")
        self.assertGreater(len(suggestions), 0)
        self.assertIn("active listening", suggestions[0].lower())
        
        # Test leadership skill suggestions
        suggestions = self.engine._get_improvement_suggestions("leadership")
        self.assertGreater(len(suggestions), 0)
        
        # Test unknown skill (should provide generic suggestion)
        suggestions = self.engine._get_improvement_suggestions("unknown_skill")
        self.assertGreater(len(suggestions), 0)
    
    def test_skill_resources_generation(self):
        """Test learning resource generation for skills"""
        # Test communication resources
        resources = self.engine._get_skill_resources("communication")
        self.assertGreater(len(resources), 0)
        
        # Check resource structure
        resource = resources[0]
        self.assertIn("type", resource)
        self.assertIn("title", resource)
        self.assertIn("url", resource)
        
        # Test unknown skill (should provide generic resource)
        resources = self.engine._get_skill_resources("unknown_skill")
        self.assertGreater(len(resources), 0)


class TestGamificationAPI(unittest.TestCase):
    """Test gamification API integration"""
    
    def setUp(self):
        """Set up test Flask app"""
        import tempfile
        import sys
        import os
        
        # Add app directory to path
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)
        
        # Import Flask app
        from app import app, gamification_engine
        
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.engine = gamification_engine
    
    def test_gamification_profile_endpoint(self):
        """Test gamification profile API endpoint"""
        user_id = "test_api_user"
        response = self.client.get(f'/api/gamification/profile/{user_id}')
        
        # Should create profile for new user
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['user_id'], user_id)
        self.assertIn('level', data)
        self.assertIn('total_points', data)
        self.assertIn('purpose_alignment', data)
        self.assertIn('talent_gap_analysis', data)
    
    def test_progress_summary_endpoint(self):
        """Test progress summary API endpoint"""
        user_id = "test_api_user"
        response = self.client.get(f'/api/gamification/progress/{user_id}')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('purpose_alignment', data)
        self.assertIn('talent_readiness', data)
        self.assertIn('achievements', data)
    
    def test_purpose_alignment_endpoint(self):
        """Test purpose alignment calculation endpoint"""
        user_id = "test_api_user"
        conversation_data = {
            "conversation_data": {
                "messages": ["I want to help communities through education"],
                "confidence_score": 0.8
            }
        }
        
        response = self.client.post(
            f'/api/gamification/purpose-alignment/{user_id}',
            data=json.dumps(conversation_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('overall_score', data)
        self.assertIn('grade', data)
        self.assertIn('breakdown', data)
        
        # Check breakdown structure
        breakdown = data['breakdown']
        self.assertIn('values_alignment', breakdown)
        self.assertIn('passion_alignment', breakdown)
        self.assertIn('skills_match', breakdown)
    
    def test_talent_gaps_endpoint(self):
        """Test talent gap analysis endpoint"""
        user_id = "test_api_user"
        request_data = {
            "user_profile": {
                "skills": {
                    "communication": 0.7,
                    "leadership": 0.4
                }
            }
        }
        
        response = self.client.post(
            f'/api/gamification/talent-gaps/{user_id}',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('overall_readiness', data)
        self.assertIn('critical_gaps', data)
        self.assertIn('improvement_gaps', data)
        self.assertIn('strength_areas', data)
    
    def test_achievements_endpoint(self):
        """Test achievements API endpoint"""
        user_id = "test_api_user"
        response = self.client.get(f'/api/gamification/achievements/{user_id}')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('achievements', data)
        self.assertIn('total_unlocked', data)
        self.assertIn('total_points_from_achievements', data)
    
    def test_challenges_endpoint(self):
        """Test challenges API endpoint"""
        user_id = "test_api_user"
        response = self.client.get(f'/api/gamification/challenges/{user_id}?count=3')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('challenges', data)
        
        # Check challenge structure if any challenges exist
        if data['challenges']:
            challenge = data['challenges'][0]
            self.assertIn('title', challenge)
            self.assertIn('description', challenge)
            self.assertIn('difficulty', challenge)
            self.assertIn('points_reward', challenge)
    
    def test_points_awarding_endpoint(self):
        """Test points awarding API endpoint"""
        user_id = "test_api_user"
        points_data = {
            "points": 100,
            "reason": "Test achievement"
        }
        
        response = self.client.post(
            f'/api/gamification/points/{user_id}',
            data=json.dumps(points_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['points_awarded'], 100)
        self.assertIn('total_points', data)
        self.assertEqual(data['reason'], "Test achievement")


def run_async_test(test_func):
    """Helper function to run async tests"""
    async def wrapper():
        test_case = TestGamificationEngine()
        test_case.setUp()
        await test_func(test_case)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(wrapper())
    finally:
        loop.close()


if __name__ == '__main__':
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add synchronous tests
    suite.addTest(TestGamificationEngine('test_values_extraction'))
    suite.addTest(TestGamificationEngine('test_passions_extraction'))
    suite.addTest(TestGamificationEngine('test_talent_gap_priority_calculation'))
    suite.addTest(TestGamificationEngine('test_achievement_requirements_checking'))
    suite.addTest(TestGamificationEngine('test_challenge_difficulty_selection'))
    suite.addTest(TestGamificationEngine('test_skill_improvement_suggestions'))
    suite.addTest(TestGamificationEngine('test_skill_resources_generation'))
    
    # Add API tests
    suite.addTest(TestGamificationAPI('test_gamification_profile_endpoint'))
    suite.addTest(TestGamificationAPI('test_progress_summary_endpoint'))
    suite.addTest(TestGamificationAPI('test_purpose_alignment_endpoint'))
    suite.addTest(TestGamificationAPI('test_talent_gaps_endpoint'))
    suite.addTest(TestGamificationAPI('test_achievements_endpoint'))
    suite.addTest(TestGamificationAPI('test_challenges_endpoint'))
    suite.addTest(TestGamificationAPI('test_points_awarding_endpoint'))
    
    # Run synchronous tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Run async tests manually
    print("\n" + "="*60)
    print("Running Async Tests...")
    print("="*60)
    
    async_tests = [
        'test_user_profile_creation',
        'test_purpose_alignment_calculation',
        'test_talent_gap_analysis',
        'test_points_and_level_system',
        'test_engagement_streak_tracking',
        'test_achievement_system',
        'test_personalized_challenges_generation',
        'test_progress_summary'
    ]
    
    passed = 0
    failed = 0
    
    for test_name in async_tests:
        print(f"\nRunning {test_name}...")
        try:
            test_case = TestGamificationEngine()
            test_case.setUp()
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            test_method = getattr(test_case, test_name)
            loop.run_until_complete(test_method())
            
            loop.close()
            print(f"✓ {test_name} PASSED")
            passed += 1
            
        except Exception as e:
            print(f"✗ {test_name} FAILED: {str(e)}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"Async Tests Summary: {passed} passed, {failed} failed")
    print("="*60)
    
    total_passed = result.testsRun - len(result.failures) - len(result.errors) + passed
    total_failed = len(result.failures) + len(result.errors) + failed
    
    print(f"\nOverall Summary: {total_passed} passed, {total_failed} failed")
    print("All gamification tests completed!")