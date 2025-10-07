"""
Engagement Tracker for Gamification System
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class EngagementTracker:
    """Tracks user engagement and generates insights"""
    
    def __init__(self):
        self.user_engagement = {}  # user_id -> engagement data
        self.daily_challenges = self._initialize_daily_challenges()
        logger.info("EngagementTracker initialized")
    
    def _initialize_daily_challenges(self) -> List[Dict[str, Any]]:
        """Initialize daily challenges"""
        return [
            {
                'id': 'daily_chat',
                'name': 'Daily Chatter',
                'description': 'Send 5 messages today',
                'target': 5,
                'reward_points': 25,
                'expires_at': (datetime.utcnow() + timedelta(hours=24)).isoformat()
            },
            {
                'id': 'team_helper',
                'name': 'Team Helper',
                'description': 'Help 2 team members today',
                'target': 2,
                'reward_points': 50,
                'expires_at': (datetime.utcnow() + timedelta(hours=24)).isoformat()
            },
            {
                'id': 'goal_setter',
                'name': 'Goal Setter',
                'description': 'Set a personal goal today',
                'target': 1,
                'reward_points': 30,
                'expires_at': (datetime.utcnow() + timedelta(hours=24)).isoformat()
            }
        ]
    
    def track_event(self, user_id: str, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Track user engagement event"""
        if user_id not in self.user_engagement:
            self.user_engagement[user_id] = {
                'total_events': 0,
                'message_count': 0,
                'session_count': 0,
                'last_activity': None,
                'daily_streaks': 0,
                'achievements_unlocked': 0,
                'total_points_earned': 0
            }
        
        engagement = self.user_engagement[user_id]
        engagement['total_events'] += 1
        engagement['last_activity'] = datetime.utcnow().isoformat()
        
        # Track specific events
        if event_type == 'message_sent':
            engagement['message_count'] += 1
            points_earned = event_data.get('points', 1)
            engagement['total_points_earned'] += points_earned
        elif event_type == 'session_start':
            engagement['session_count'] += 1
        elif event_type == 'achievement_unlocked':
            engagement['achievements_unlocked'] += 1
            points_earned = event_data.get('points', 10)
            engagement['total_points_earned'] += points_earned
        
        logger.info(f"Tracked {event_type} for user {user_id}")
        
        return {
            'success': True,
            'event_type': event_type,
            'user_engagement': self.get_user_engagement(user_id)
        }
    
    def get_user_engagement(self, user_id: str) -> Dict[str, Any]:
        """Get engagement metrics for a user"""
        if user_id not in self.user_engagement:
            return {
                'total_events': 0,
                'message_count': 0,
                'session_count': 0,
                'last_activity': None,
                'daily_streaks': 0,
                'achievements_unlocked': 0,
                'total_points_earned': 0,
                'engagement_score': 0,
                'engagement_level': 'New'
            }
        
        engagement = self.user_engagement[user_id].copy()
        
        # Calculate engagement score (0-100)
        score = min(100, (
            engagement['message_count'] * 2 +
            engagement['session_count'] * 5 +
            engagement['achievements_unlocked'] * 10 +
            engagement['daily_streaks'] * 15
        ))
        
        engagement['engagement_score'] = score
        
        # Determine engagement level
        if score >= 80:
            engagement['engagement_level'] = 'Highly Engaged'
        elif score >= 60:
            engagement['engagement_level'] = 'Engaged'
        elif score >= 40:
            engagement['engagement_level'] = 'Moderately Engaged'
        elif score >= 20:
            engagement['engagement_level'] = 'Somewhat Engaged'
        else:
            engagement['engagement_level'] = 'New'
        
        return engagement
    
    def get_daily_challenges(self, user_id: str) -> List[Dict[str, Any]]:
        """Get daily challenges for a user"""
        if user_id not in self.user_engagement:
            progress = {}
        else:
            engagement = self.user_engagement[user_id]
            progress = {
                'daily_chat': min(engagement.get('message_count', 0), 5),
                'team_helper': 0,  # Would track this separately
                'goal_setter': 0   # Would track this separately
            }
        
        # Add progress to challenges
        challenges = []
        for challenge in self.daily_challenges:
            challenge_copy = challenge.copy()
            challenge_copy['current_progress'] = progress.get(challenge['id'], 0)
            challenge_copy['is_completed'] = challenge_copy['current_progress'] >= challenge['target']
            challenges.append(challenge_copy)
        
        return challenges
    
    def complete_daily_challenge(self, user_id: str, challenge_id: str) -> Dict[str, Any]:
        """Mark a daily challenge as completed"""
        challenge = None
        for c in self.daily_challenges:
            if c['id'] == challenge_id:
                challenge = c
                break
        
        if not challenge:
            return {'success': False, 'error': 'Challenge not found'}
        
        # Award points
        if user_id not in self.user_engagement:
            self.user_engagement[user_id] = {
                'total_events': 0,
                'message_count': 0,
                'session_count': 0,
                'last_activity': None,
                'daily_streaks': 0,
                'achievements_unlocked': 0,
                'total_points_earned': 0
            }
        
        self.user_engagement[user_id]['total_points_earned'] += challenge['reward_points']
        
        return {
            'success': True,
            'challenge': challenge,
            'points_awarded': challenge['reward_points']
        }