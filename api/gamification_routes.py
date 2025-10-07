"""
Gamification API Routes

This module contains all API endpoints related to gamification features.
Extracted from app.py for better maintainability.
"""

from flask import Blueprint, request, jsonify
import logging
import json

# Create blueprint for gamification routes
gamification_bp = Blueprint('gamification', __name__, url_prefix='/api/gamification')

logger = logging.getLogger(__name__)

# Import gamification modules
try:
    from gamification.achievements import AchievementEngine
    from gamification.leaderboard import LeaderboardManager
    from gamification.rewards import RewardSystem
    from gamification.engagement import EngagementTracker
    GAMIFICATION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Gamification modules not available: {e}")
    GAMIFICATION_AVAILABLE = False

# Initialize gamification components if available
if GAMIFICATION_AVAILABLE:
    try:
        achievement_engine = AchievementEngine()
        leaderboard_manager = LeaderboardManager()
        reward_system = RewardSystem()
        engagement_tracker = EngagementTracker()
    except Exception as e:
        logger.error(f"Failed to initialize gamification components: {e}")
        GAMIFICATION_AVAILABLE = False


@gamification_bp.route('/achievements/<user_id>')
def get_achievements(user_id):
    """Get user achievements"""
    if not GAMIFICATION_AVAILABLE:
        return jsonify({'error': 'Gamification features not available'}), 503
    
    try:
        achievements = achievement_engine.get_user_achievements(user_id)
        return jsonify({
            'user_id': user_id,
            'achievements': achievements
        })
    except Exception as e:
        logger.error(f"Error getting achievements: {e}")
        return jsonify({'error': str(e)}), 500


@gamification_bp.route('/achievements/progress/<user_id>')
def get_achievement_progress(user_id):
    """Get user achievement progress"""
    if not GAMIFICATION_AVAILABLE:
        return jsonify({'error': 'Gamification features not available'}), 503
    
    try:
        progress = achievement_engine.get_achievement_progress(user_id)
        return jsonify({
            'user_id': user_id,
            'progress': progress
        })
    except Exception as e:
        logger.error(f"Error getting achievement progress: {e}")
        return jsonify({'error': str(e)}), 500


@gamification_bp.route('/leaderboard')
def get_leaderboard():
    """Get current leaderboard"""
    if not GAMIFICATION_AVAILABLE:
        return jsonify({'error': 'Gamification features not available'}), 503
    
    try:
        category = request.args.get('category', 'overall')
        limit = request.args.get('limit', 10, type=int)
        
        leaderboard = leaderboard_manager.get_leaderboard(category, limit)
        return jsonify({
            'category': category,
            'limit': limit,
            'leaderboard': leaderboard
        })
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return jsonify({'error': str(e)}), 500


@gamification_bp.route('/user-stats/<user_id>')
def get_user_stats(user_id):
    """Get comprehensive user statistics"""
    if not GAMIFICATION_AVAILABLE:
        return jsonify({'error': 'Gamification features not available'}), 503
    
    try:
        stats = leaderboard_manager.get_user_stats(user_id)
        return jsonify({
            'user_id': user_id,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return jsonify({'error': str(e)}), 500


@gamification_bp.route('/rewards/<user_id>')
def get_user_rewards(user_id):
    """Get user rewards"""
    if not GAMIFICATION_AVAILABLE:
        return jsonify({'error': 'Gamification features not available'}), 503
    
    try:
        rewards = reward_system.get_user_rewards(user_id)
        return jsonify({
            'user_id': user_id,
            'rewards': rewards
        })
    except Exception as e:
        logger.error(f"Error getting user rewards: {e}")
        return jsonify({'error': str(e)}), 500


@gamification_bp.route('/rewards/claim/<user_id>/<reward_id>', methods=['POST'])
def claim_reward(user_id, reward_id):
    """Claim a reward"""
    if not GAMIFICATION_AVAILABLE:
        return jsonify({'error': 'Gamification features not available'}), 503
    
    try:
        result = reward_system.claim_reward(user_id, reward_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error claiming reward: {e}")
        return jsonify({'error': str(e)}), 500


@gamification_bp.route('/engagement/<user_id>')
def get_engagement_metrics(user_id):
    """Get user engagement metrics"""
    if not GAMIFICATION_AVAILABLE:
        return jsonify({'error': 'Gamification features not available'}), 503
    
    try:
        metrics = engagement_tracker.get_user_engagement(user_id)
        return jsonify({
            'user_id': user_id,
            'engagement': metrics
        })
    except Exception as e:
        logger.error(f"Error getting engagement metrics: {e}")
        return jsonify({'error': str(e)}), 500


@gamification_bp.route('/engagement/track', methods=['POST'])
def track_engagement():
    """Track user engagement event"""
    if not GAMIFICATION_AVAILABLE:
        return jsonify({'error': 'Gamification features not available'}), 503
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        event_type = data.get('event_type')
        event_data = data.get('event_data', {})
        
        if not user_id or not event_type:
            return jsonify({'error': 'user_id and event_type are required'}), 400
        
        result = engagement_tracker.track_event(user_id, event_type, event_data)
        
        # Check for achievements
        if hasattr(achievement_engine, 'check_achievements'):
            achievement_updates = achievement_engine.check_achievements(user_id, event_type, event_data)
            if achievement_updates:
                result['achievements'] = achievement_updates
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error tracking engagement: {e}")
        return jsonify({'error': str(e)}), 500


@gamification_bp.route('/daily-challenges/<user_id>')
def get_daily_challenges(user_id):
    """Get daily challenges for user"""
    if not GAMIFICATION_AVAILABLE:
        return jsonify({'error': 'Gamification features not available'}), 503
    
    try:
        if hasattr(engagement_tracker, 'get_daily_challenges'):
            challenges = engagement_tracker.get_daily_challenges(user_id)
            return jsonify({
                'user_id': user_id,
                'challenges': challenges
            })
        else:
            return jsonify({
                'user_id': user_id,
                'challenges': []
            })
    except Exception as e:
        logger.error(f"Error getting daily challenges: {e}")
        return jsonify({'error': str(e)}), 500


@gamification_bp.route('/team/progress/<team_id>')
def get_team_progress(team_id):
    """Get team progress and achievements"""
    if not GAMIFICATION_AVAILABLE:
        return jsonify({'error': 'Gamification features not available'}), 503
    
    try:
        if hasattr(leaderboard_manager, 'get_team_progress'):
            progress = leaderboard_manager.get_team_progress(team_id)
            return jsonify({
                'team_id': team_id,
                'progress': progress
            })
        else:
            return jsonify({
                'team_id': team_id,
                'progress': {
                    'total_points': 0,
                    'achievements': [],
                    'rank': None
                }
            })
    except Exception as e:
        logger.error(f"Error getting team progress: {e}")
        return jsonify({'error': str(e)}), 500