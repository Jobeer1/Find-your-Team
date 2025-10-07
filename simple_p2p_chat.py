"""
Simple P2P Chat Flask Integration
Simplified version for testing
"""

from flask import Blueprint, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional
import uuid

from p2p_chat_engine import P2PChatEngine, MessageType, UserStatus, ConnectionQuality

logger = logging.getLogger(__name__)

class SimpleP2PChatIntegration:
    """Simplified Flask integration for P2P Chat Engine"""
    
    def __init__(self, app, socketio: SocketIO):
        self.app = app
        self.socketio = socketio
        self.chat_engine = P2PChatEngine(socketio)
        self.user_sessions: Dict[str, str] = {}  # session_id -> user_id
        
        # Setup SocketIO event handlers
        self._setup_socketio_handlers()
    
    def _setup_socketio_handlers(self):
        """Setup SocketIO event handlers for real-time features"""
        
        @self.socketio.on('connect')
        def handle_connect():
            logger.info(f"Client connected: {request.sid}")
            emit('connection_status', {'status': 'connected'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            logger.info(f"Client disconnected: {request.sid}")
            
            # Update user status to offline
            user_id = self.user_sessions.get(request.sid)
            if user_id:
                self.chat_engine.update_user_status(user_id, UserStatus.OFFLINE)
                del self.user_sessions[request.sid]
        
        @self.socketio.on('user_register')
        def handle_user_register(data):
            """Handle user registration for chat"""
            try:
                user_id = data.get('user_id')
                username = data.get('username', f'User-{user_id}')
                
                if not user_id:
                    emit('error', {'message': 'User ID required'})
                    return
                
                # Register user
                self.chat_engine.register_user(user_id, username)
                self.user_sessions[request.sid] = user_id
                
                # Join user to their personal room
                join_room(f'user_{user_id}')
                
                emit('user_registered', {'user_id': user_id, 'username': username})
                
            except Exception as e:
                logger.error(f"User registration error: {e}")
                emit('error', {'message': str(e)})
        
        @self.socketio.on('send_message')
        def handle_send_message(data):
            """Handle real-time message sending"""
            try:
                user_id = self.user_sessions.get(request.sid)
                if not user_id:
                    emit('error', {'message': 'User not registered'})
                    return
                
                chat_id = data.get('chat_id')
                content = data.get('content')
                message_type = MessageType(data.get('message_type', 'text'))
                
                if not all([chat_id, content]):
                    emit('error', {'message': 'Missing message data'})
                    return
                
                # Send message
                message = self.chat_engine.send_message(
                    sender_id=user_id,
                    chat_id=chat_id,
                    content=content,
                    message_type=message_type
                )
                
                emit('message_sent', message.__dict__)
                
            except Exception as e:
                logger.error(f"Send message error: {e}")
                emit('error', {'message': str(e)})
    
    def register_routes(self):
        """Register all P2P chat routes with the Flask app"""
        
        @self.app.route('/api/p2p-chat/health')
        def p2p_health_check():
            return jsonify({
                'status': 'healthy',
                'engine': 'Simple P2P Chat Engine v1.0',
                'features': [
                    'real-time messaging',
                    'user management',
                    'typing indicators'
                ],
                'timestamp': datetime.now().isoformat()
            })
        
        @self.app.route('/api/p2p-chat/users', methods=['POST'])
        def create_user():
            """Create a new user"""
            try:
                data = request.get_json()
                user_id = data.get('user_id', str(uuid.uuid4()))
                username = data.get('username', f'User-{user_id[:8]}')
                
                # Register user
                self.chat_engine.register_user(user_id, username)
                
                return jsonify({
                    'success': True,
                    'user_id': user_id,
                    'username': username
                })
                
            except Exception as e:
                logger.error(f"Create user error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/p2p-chat/chats', methods=['POST'])
        def create_chat():
            """Create a new chat"""
            try:
                data = request.get_json()
                creator_id = data.get('creator_id')
                participants = data.get('participants', [])
                chat_name = data.get('chat_name', 'New Chat')
                
                if not creator_id:
                    return jsonify({'error': 'Creator ID required'}), 400
                
                # Create chat
                chat = self.chat_engine.create_chat(
                    creator_id=creator_id,
                    participants=participants,
                    chat_name=chat_name
                )
                
                return jsonify({
                    'success': True,
                    'chat': chat.__dict__
                })
                
            except Exception as e:
                logger.error(f"Create chat error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/p2p-chat/users/search')
        def search_users():
            """Search for users"""
            try:
                query = request.args.get('q', '').strip()
                
                if not query:
                    return jsonify({'users': []})
                
                # Search users
                users = self.chat_engine.search_users(query)
                
                return jsonify({
                    'users': [user.__dict__ for user in users]
                })
                
            except Exception as e:
                logger.error(f"Search users error: {e}")
                return jsonify({'error': str(e)}), 500
        
        logger.info("Simple P2P Chat routes registered successfully")