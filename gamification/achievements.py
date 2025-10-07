"""
Achievement Engine for Gamification System
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class Achievement:
    """Basic achievement class"""
    def __init__(self, id: str, name: str, description: str, points: int = 10):
        self.id = id
        self.name = name
        self.description = description
        self.points = points
        self.unlocked_at = None
        self.is_unlocked = False
    
    def unlock(self):
        """Unlock this achievement"""
        self.is_unlocked = True
        self.unlocked_at = datetime.utcnow()


class AchievementEngine:
    """Manages user achievements and progress"""
    
    def __init__(self):
        self.achievements = self._initialize_achievements()
        self.user_achievements = {}  # user_id -> list of achievements
        logger.info("AchievementEngine initialized")
    
    def _initialize_achievements(self) -> Dict[str, Achievement]:
        """Initialize default achievements"""
        achievements = {}
        
        # Chat achievements
        achievements['first_message'] = Achievement(
            'first_message', 'First Steps', 'Send your first message', 10
        )
        achievements['chatty'] = Achievement(
            'chatty', 'Chatty', 'Send 10 messages', 50
        )
        achievements['conversationalist'] = Achievement(
            'conversationalist', 'Conversationalist', 'Send 50 messages', 100
        )
        
        # Engagement achievements
        achievements['team_player'] = Achievement(
            'team_player', 'Team Player', 'Join your first team', 25
        )
        achievements['mentor'] = Achievement(
            'mentor', 'Mentor', 'Help 5 team members', 75
        )
        achievements['leader'] = Achievement(
            'leader', 'Leader', 'Lead a successful project', 150
        )
        
        return achievements
    
    def get_user_achievements(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all achievements for a user"""
        if user_id not in self.user_achievements:
            self.user_achievements[user_id] = []
        
        user_unlocked = {ach.id for ach in self.user_achievements[user_id]}
        
        result = []
        for achievement in self.achievements.values():
            result.append({
                'id': achievement.id,
                'name': achievement.name,
                'description': achievement.description,
                'points': achievement.points,
                'is_unlocked': achievement.id in user_unlocked,
                'unlocked_at': achievement.unlocked_at.isoformat() if achievement.unlocked_at else None
            })
        
        return result
    
    def get_achievement_progress(self, user_id: str) -> Dict[str, Any]:
        """Get achievement progress for a user"""
        achievements = self.get_user_achievements(user_id)
        unlocked_count = sum(1 for ach in achievements if ach['is_unlocked'])
        total_points = sum(ach['points'] for ach in achievements if ach['is_unlocked'])
        
        return {
            'unlocked_count': unlocked_count,
            'total_achievements': len(achievements),
            'total_points': total_points,
            'completion_percentage': (unlocked_count / len(achievements)) * 100 if achievements else 0
        }
    
    def check_achievements(self, user_id: str, event_type: str, event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for new achievements based on user activity"""
        if user_id not in self.user_achievements:
            self.user_achievements[user_id] = []
        
        new_achievements = []
        user_unlocked = {ach.id for ach in self.user_achievements[user_id]}
        
        # Check message-based achievements
        if event_type == 'message_sent':
            message_count = event_data.get('total_messages', 1)
            
            if 'first_message' not in user_unlocked:
                achievement = Achievement(
                    'first_message', 'First Steps', 'Send your first message', 10
                )
                achievement.unlock()
                self.user_achievements[user_id].append(achievement)
                new_achievements.append({
                    'id': achievement.id,
                    'name': achievement.name,
                    'description': achievement.description,
                    'points': achievement.points
                })
            
            if message_count >= 10 and 'chatty' not in user_unlocked:
                achievement = Achievement(
                    'chatty', 'Chatty', 'Send 10 messages', 50
                )
                achievement.unlock()
                self.user_achievements[user_id].append(achievement)
                new_achievements.append({
                    'id': achievement.id,
                    'name': achievement.name,
                    'description': achievement.description,
                    'points': achievement.points
                })
        
        return new_achievements