"""
Leaderboard Manager for Gamification System
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class LeaderboardManager:
    """Manages leaderboards and user statistics"""
    
    def __init__(self):
        self.user_stats = {}  # user_id -> stats dict
        logger.info("LeaderboardManager initialized")
    
    def get_leaderboard(self, category: str = 'overall', limit: int = 10) -> List[Dict[str, Any]]:
        """Get leaderboard for specified category"""
        if not self.user_stats:
            return []
        
        # Sort users by the specified category
        if category == 'overall':
            sorted_users = sorted(
                self.user_stats.items(),
                key=lambda x: x[1].get('total_points', 0),
                reverse=True
            )
        elif category == 'messages':
            sorted_users = sorted(
                self.user_stats.items(),
                key=lambda x: x[1].get('message_count', 0),
                reverse=True
            )
        elif category == 'achievements':
            sorted_users = sorted(
                self.user_stats.items(),
                key=lambda x: x[1].get('achievement_count', 0),
                reverse=True
            )
        else:
            sorted_users = list(self.user_stats.items())
        
        # Build leaderboard
        leaderboard = []
        for i, (user_id, stats) in enumerate(sorted_users[:limit]):
            leaderboard.append({
                'rank': i + 1,
                'user_id': user_id,
                'display_name': stats.get('display_name', f'User {user_id[:8]}'),
                'total_points': stats.get('total_points', 0),
                'message_count': stats.get('message_count', 0),
                'achievement_count': stats.get('achievement_count', 0),
                'level': stats.get('level', 1)
            })
        
        return leaderboard
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive stats for a user"""
        if user_id not in self.user_stats:
            self.user_stats[user_id] = {
                'total_points': 0,
                'message_count': 0,
                'achievement_count': 0,
                'level': 1,
                'created_at': datetime.utcnow().isoformat(),
                'last_activity': datetime.utcnow().isoformat()
            }
        
        stats = self.user_stats[user_id].copy()
        
        # Calculate level based on points
        total_points = stats.get('total_points', 0)
        level = max(1, total_points // 100 + 1)  # Level up every 100 points
        stats['level'] = level
        
        # Add rank information
        leaderboard = self.get_leaderboard('overall', 1000)  # Get full leaderboard
        user_rank = None
        for entry in leaderboard:
            if entry['user_id'] == user_id:
                user_rank = entry['rank']
                break
        
        stats['rank'] = user_rank
        stats['total_users'] = len(self.user_stats)
        
        return stats
    
    def update_user_stats(self, user_id: str, updates: Dict[str, Any]):
        """Update user statistics"""
        if user_id not in self.user_stats:
            self.user_stats[user_id] = {
                'total_points': 0,
                'message_count': 0,
                'achievement_count': 0,
                'level': 1,
                'created_at': datetime.utcnow().isoformat()
            }
        
        self.user_stats[user_id].update(updates)
        self.user_stats[user_id]['last_activity'] = datetime.utcnow().isoformat()
        
        logger.info(f"Updated stats for user {user_id}: {updates}")
    
    def get_team_progress(self, team_id: str) -> Dict[str, Any]:
        """Get team progress and achievements"""
        # Mock team progress for now
        return {
            'total_points': 500,
            'team_level': 3,
            'member_count': 5,
            'achievements': [
                'First Collaboration',
                'Team Player',
                'Goal Achiever'
            ],
            'rank': 7,
            'completion_percentage': 65
        }