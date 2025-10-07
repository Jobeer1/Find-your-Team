#!/usr/bin/env python3
"""
Quick gamification system verification test
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gamification.engine import GamificationEngine
from aws_config import AWSConfig

async def test_gamification():
    print('🎯 Testing Gamification System...')
    
    # Initialize
    aws_config = AWSConfig()
    engine = GamificationEngine(aws_config)
    
    # Test user profile creation
    user_id = 'test_user_123'
    profile = await engine.get_user_profile(user_id)
    print(f'✓ User profile created: Level {profile.level}, Points: {profile.total_points}')
    
    # Test purpose alignment
    conversation_data = {
        'messages': ['I want to help communities through education and empowerment'],
        'confidence_score': 0.85
    }
    alignment = await engine.calculate_purpose_alignment(user_id, conversation_data)
    print(f'✓ Purpose alignment calculated: {alignment.overall_score:.2f} (Grade: {alignment.get_grade()})')
    
    # Test talent gap analysis
    user_profile_data = {
        'skills': {
            'communication': 0.8,
            'leadership': 0.4,
            'empathy': 0.9,
            'problem_solving': 0.6
        }
    }
    gaps = await engine.analyze_talent_gaps(user_id, user_profile_data)
    print(f'✓ Talent gaps analyzed: {gaps.overall_readiness:.2f} readiness, {len(gaps.critical_gaps)} critical gaps')
    
    # Test points and achievements
    points = await engine.award_points(user_id, 150, 'Test achievement')
    print(f'✓ Points awarded: {points} total points')
    
    # Test challenges
    challenges = await engine.generate_personalized_challenges(user_id, 2)
    print(f'✓ Challenges generated: {len(challenges)} personalized challenges')
    
    # Test progress summary
    summary = await engine.get_progress_summary(user_id)
    level = summary.get('level', 0)
    purpose_grade = summary.get('purpose_alignment', {}).get('grade', 'N/A')
    print(f'✓ Progress summary: Level {level}, Purpose: {purpose_grade}')
    
    print('🎉 All gamification components working successfully!')

if __name__ == '__main__':
    # Run the test
    asyncio.run(test_gamification())