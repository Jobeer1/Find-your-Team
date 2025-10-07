"""
Core Chat Routes

This module contains the main chat functionality endpoints.
Extracted from app.py for better maintainability.
"""

from flask import Blueprint, request, jsonify, session
import json
import logging
import os
from datetime import datetime
import uuid

# Create blueprint for chat routes (no URL prefix for compatibility)
chat_bp = Blueprint('chat', __name__)

logger = logging.getLogger(__name__)

# Chat storage (in production, use proper database)
chat_messages = []
MESSAGES_FILE = 'chat_messages.json'

# Load existing messages
def load_messages():
    """Load messages from file"""
    global chat_messages
    try:
        if os.path.exists(MESSAGES_FILE):
            with open(MESSAGES_FILE, 'r') as f:
                chat_messages = json.load(f)
    except Exception as e:
        logger.error(f"Error loading messages: {e}")
        chat_messages = []

# Save messages
def save_messages():
    """Save messages to file"""
    try:
        with open(MESSAGES_FILE, 'w') as f:
            json.dump(chat_messages, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving messages: {e}")

# Load messages on startup
load_messages()


@chat_bp.route('/send_message', methods=['POST'])
@chat_bp.route('/send-message', methods=['POST'])
def send_message():
    """Send a new chat message"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Get user from session or request
        user_id = session.get('user_id') or data.get('user_id', 'anonymous')
        message_text = data.get('message', '').strip()
        
        if not message_text:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Create message object
        message = {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'message': message_text,
            'timestamp': datetime.utcnow().isoformat(),
            'type': 'user_message'
        }
        
        # Add message to storage
        chat_messages.append(message)
        save_messages()
        
        # Track engagement if gamification is available
        try:
            from gamification.engagement import EngagementTracker
            engagement_tracker = EngagementTracker()
            engagement_tracker.track_event(user_id, 'message_sent', {
                'message_length': len(message_text),
                'timestamp': message['timestamp']
            })
        except ImportError:
            pass
        
        return jsonify({
            'success': True,
            'message': 'Message sent successfully',
            'message_id': message['id']
        })
    
    except Exception as e:
        logger.error(f"Send message error: {e}")
        return jsonify({'error': 'Failed to send message'}), 500


@chat_bp.route('/get_messages')
@chat_bp.route('/get-messages')
def get_messages():
    """Get chat messages"""
    try:
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        user_id = request.args.get('user_id')
        
        # Filter messages
        filtered_messages = chat_messages
        if user_id:
            filtered_messages = [msg for msg in chat_messages if msg.get('user_id') == user_id]
        
        # Apply pagination
        total_messages = len(filtered_messages)
        paginated_messages = filtered_messages[offset:offset + limit]
        
        return jsonify({
            'messages': paginated_messages,
            'total': total_messages,
            'limit': limit,
            'offset': offset,
            'has_more': (offset + limit) < total_messages
        })
    
    except Exception as e:
        logger.error(f"Get messages error: {e}")
        return jsonify({'error': 'Failed to get messages'}), 500


@chat_bp.route('/delete-message/<message_id>', methods=['DELETE'])
def delete_message(message_id):
    """Delete a specific message"""
    try:
        # Check authentication
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Find and remove message
        global chat_messages
        original_length = len(chat_messages)
        chat_messages = [msg for msg in chat_messages 
                        if not (msg.get('id') == message_id and msg.get('user_id') == user_id)]
        
        if len(chat_messages) == original_length:
            return jsonify({'error': 'Message not found or unauthorized'}), 404
        
        save_messages()
        
        return jsonify({
            'success': True,
            'message': 'Message deleted successfully'
        })
    
    except Exception as e:
        logger.error(f"Delete message error: {e}")
        return jsonify({'error': 'Failed to delete message'}), 500


@chat_bp.route('/clear-history', methods=['POST'])
def clear_chat_history():
    """Clear chat history for user"""
    try:
        # Check authentication
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        data = request.get_json() or {}
        confirm = data.get('confirm', False)
        
        if not confirm:
            return jsonify({'error': 'Confirmation required'}), 400
        
        # Remove user's messages
        global chat_messages
        original_length = len(chat_messages)
        chat_messages = [msg for msg in chat_messages if msg.get('user_id') != user_id]
        
        deleted_count = original_length - len(chat_messages)
        save_messages()
        
        return jsonify({
            'success': True,
            'message': f'Cleared {deleted_count} messages',
            'deleted_count': deleted_count
        })
    
    except Exception as e:
        logger.error(f"Clear history error: {e}")
        return jsonify({'error': 'Failed to clear history'}), 500


@chat_bp.route('/search-messages')
def search_messages():
    """Search chat messages"""
    try:
        query = request.args.get('q', '').strip()
        user_id = request.args.get('user_id')
        limit = request.args.get('limit', 20, type=int)
        
        if not query:
            return jsonify({'error': 'Search query required'}), 400
        
        # Filter and search messages
        filtered_messages = chat_messages
        if user_id:
            filtered_messages = [msg for msg in chat_messages if msg.get('user_id') == user_id]
        
        # Simple text search (in production, use proper search engine)
        search_results = []
        query_lower = query.lower()
        
        for msg in filtered_messages:
            message_text = msg.get('message', '').lower()
            if query_lower in message_text:
                search_results.append(msg)
                if len(search_results) >= limit:
                    break
        
        return jsonify({
            'results': search_results,
            'query': query,
            'total_found': len(search_results),
            'limit': limit
        })
    
    except Exception as e:
        logger.error(f"Search messages error: {e}")
        return jsonify({'error': 'Failed to search messages'}), 500


@chat_bp.route('/message-stats')
def get_message_stats():
    """Get message statistics"""
    try:
        user_id = request.args.get('user_id')
        
        # Filter messages
        filtered_messages = chat_messages
        if user_id:
            filtered_messages = [msg for msg in chat_messages if msg.get('user_id') == user_id]
        
        # Calculate stats
        total_messages = len(filtered_messages)
        total_chars = sum(len(msg.get('message', '')) for msg in filtered_messages)
        
        # Get recent activity (last 24 hours)
        from datetime import datetime, timedelta
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        recent_messages = []
        
        for msg in filtered_messages:
            try:
                msg_time = datetime.fromisoformat(msg.get('timestamp', '').replace('Z', '+00:00'))
                if msg_time > twenty_four_hours_ago:
                    recent_messages.append(msg)
            except (ValueError, AttributeError):
                pass
        
        return jsonify({
            'total_messages': total_messages,
            'total_characters': total_chars,
            'recent_messages_24h': len(recent_messages),
            'average_message_length': total_chars / total_messages if total_messages > 0 else 0,
            'user_id': user_id
        })
    
    except Exception as e:
        logger.error(f"Message stats error: {e}")
        return jsonify({'error': 'Failed to get message stats'}), 500