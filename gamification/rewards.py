"""
Reward System for Gamification
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class Reward:
    """Represents a reward that users can earn"""
    def __init__(self, id: str, name: str, description: str, reward_type: str, value: Any):
        self.id = id
        self.name = name
        self.description = description
        self.reward_type = reward_type  # 'badge', 'points', 'feature_unlock', 'cosmetic'
        self.value = value
        self.earned_at = None
        self.claimed_at = None
        self.is_claimed = False


class RewardSystem:
    """Manages user rewards and redemption"""
    
    def __init__(self):
        self.rewards = self._initialize_rewards()
        self.user_rewards = {}  # user_id -> list of rewards
        logger.info("RewardSystem initialized")
    
    def _initialize_rewards(self) -> Dict[str, Reward]:
        """Initialize available rewards"""
        rewards = {}
        
        # Badge rewards
        rewards['newcomer_badge'] = Reward(
            'newcomer_badge', 'Newcomer Badge', 'Welcome to the team!', 'badge', 'newcomer'
        )
        rewards['contributor_badge'] = Reward(
            'contributor_badge', 'Contributor Badge', 'Active team contributor', 'badge', 'contributor'
        )
        rewards['leader_badge'] = Reward(
            'leader_badge', 'Leader Badge', 'Natural team leader', 'badge', 'leader'
        )
        
        # Feature unlocks
        rewards['advanced_chat'] = Reward(
            'advanced_chat', 'Advanced Chat Features', 'Unlock emoji and file sharing', 'feature_unlock', 'advanced_chat'
        )
        rewards['team_analytics'] = Reward(
            'team_analytics', 'Team Analytics', 'Access detailed team performance', 'feature_unlock', 'analytics'
        )
        
        # Point bonuses
        rewards['bonus_100'] = Reward(
            'bonus_100', '100 Point Bonus', 'Extra points for great work!', 'points', 100
        )
        rewards['bonus_250'] = Reward(
            'bonus_250', '250 Point Bonus', 'Exceptional contribution!', 'points', 250
        )
        
        return rewards
    
    def get_user_rewards(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all rewards for a user"""
        if user_id not in self.user_rewards:
            self.user_rewards[user_id] = []
        
        return [
            {
                'id': reward.id,
                'name': reward.name,
                'description': reward.description,
                'reward_type': reward.reward_type,
                'value': reward.value,
                'earned_at': reward.earned_at.isoformat() if reward.earned_at else None,
                'claimed_at': reward.claimed_at.isoformat() if reward.claimed_at else None,
                'is_claimed': reward.is_claimed
            }
            for reward in self.user_rewards[user_id]
        ]
    
    def award_reward(self, user_id: str, reward_id: str) -> Dict[str, Any]:
        """Award a reward to a user"""
        if user_id not in self.user_rewards:
            self.user_rewards[user_id] = []
        
        if reward_id not in self.rewards:
            return {'success': False, 'error': 'Reward not found'}
        
        # Check if user already has this reward
        user_reward_ids = [r.id for r in self.user_rewards[user_id]]
        if reward_id in user_reward_ids:
            return {'success': False, 'error': 'User already has this reward'}
        
        # Create new reward instance
        template = self.rewards[reward_id]
        reward = Reward(
            template.id, template.name, template.description,
            template.reward_type, template.value
        )
        reward.earned_at = datetime.utcnow()
        
        self.user_rewards[user_id].append(reward)
        
        logger.info(f"Awarded reward {reward_id} to user {user_id}")
        
        return {
            'success': True,
            'reward': {
                'id': reward.id,
                'name': reward.name,
                'description': reward.description,
                'reward_type': reward.reward_type,
                'value': reward.value
            }
        }
    
    def claim_reward(self, user_id: str, reward_id: str) -> Dict[str, Any]:
        """Claim a reward"""
        if user_id not in self.user_rewards:
            return {'success': False, 'error': 'No rewards found for user'}
        
        # Find the reward
        reward = None
        for r in self.user_rewards[user_id]:
            if r.id == reward_id:
                reward = r
                break
        
        if not reward:
            return {'success': False, 'error': 'Reward not found'}
        
        if reward.is_claimed:
            return {'success': False, 'error': 'Reward already claimed'}
        
        # Claim the reward
        reward.is_claimed = True
        reward.claimed_at = datetime.utcnow()
        
        logger.info(f"User {user_id} claimed reward {reward_id}")
        
        return {
            'success': True,
            'message': f'Successfully claimed {reward.name}',
            'reward_type': reward.reward_type,
            'value': reward.value
        }