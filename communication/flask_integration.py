"""
Flask Integration for Multi-Protocol Communication
Provides WebSocket and REST endpoints for real-time communication
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
import eventlet

from .multi_protocol_client import MultiProtocolClient, Message, MessagePriority, ProtocolType, ConnectionStatus

logger = logging.getLogger(__name__)

class CommunicationManager:
    """Manages communication for all connected users"""
    
    def __init__(self, app: Flask, socketio: SocketIO):
        self.app = app
        self.socketio = socketio
        self.clients: Dict[str, MultiProtocolClient] = {}
        self.user_sessions: Dict[str, str] = {}  # user_id -> session_id
        self.session_users: Dict[str, str] = {}  # session_id -> user_id
        
        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # Setup SocketIO event handlers
        self._setup_socketio_handlers()
        
        # Setup REST endpoints
        self._setup_rest_endpoints()
    
    def _setup_socketio_handlers(self):
        """Setup SocketIO event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            logger.info(f"Client connected: {request.sid}")
            emit('connection_status', {'status': 'connected'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            logger.info(f"Client disconnected: {request.sid}")
            
            # Clean up user session
            if request.sid in self.session_users:
                user_id = self.session_users[request.sid]
                self._cleanup_user_session(user_id, request.sid)
        
        @self.socketio.on('join_user')
        def handle_join_user(data):
            """User joins their personal communication channel"""
            user_id = data.get('user_id')
            if not user_id:
                emit('error', {'message': 'User ID required'})
                return
            
            # Store session mapping
            self.user_sessions[user_id] = request.sid
            self.session_users[request.sid] = user_id
            
            # Join user's personal room
            join_room(f"user_{user_id}")
            
            # Initialize multi-protocol client for user
            self._initialize_user_client(user_id)
            
            emit('joined', {'user_id': user_id, 'room': f"user_{user_id}"})
            logger.info(f"User {user_id} joined communication channel")
        
        @self.socketio.on('send_message')
        def handle_send_message(data):
            """Send message via multi-protocol system"""
            if request.sid not in self.session_users:
                emit('error', {'message': 'Not authenticated'})
                return
            
            user_id = self.session_users[request.sid]
            
            try:
                content = data.get('content', '')
                recipient_id = data.get('recipient_id')
                message_type = data.get('message_type', 'chat')
                priority = MessagePriority(data.get('priority', MessagePriority.NORMAL.value))
                
                if not content:
                    emit('error', {'message': 'Message content required'})
                    return
                
                # Send via multi-protocol client
                future = self.executor.submit(
                    self._send_message_async,
                    user_id, content, recipient_id, message_type, priority
                )
                
                # Emit immediate acknowledgment
                emit('message_sent', {
                    'status': 'queued',
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Send message error: {e}")
                emit('error', {'message': str(e)})
        
        @self.socketio.on('get_connection_status')
        def handle_get_connection_status():
            """Get current connection status for user"""
            if request.sid not in self.session_users:
                emit('error', {'message': 'Not authenticated'})
                return
            
            user_id = self.session_users[request.sid]
            
            if user_id in self.clients:
                status = self.clients[user_id].get_connection_status()
                emit('connection_status', status)
            else:
                emit('connection_status', {'status': 'not_initialized'})
        
        @self.socketio.on('join_team')
        def handle_join_team(data):
            """Join team communication channel"""
            team_id = data.get('team_id')
            if not team_id:
                emit('error', {'message': 'Team ID required'})
                return
            
            join_room(f"team_{team_id}")
            emit('joined_team', {'team_id': team_id})
            logger.info(f"User joined team {team_id}")
        
        @self.socketio.on('leave_team')
        def handle_leave_team(data):
            """Leave team communication channel"""
            team_id = data.get('team_id')
            if not team_id:
                emit('error', {'message': 'Team ID required'})
                return
            
            leave_room(f"team_{team_id}")
            emit('left_team', {'team_id': team_id})
            logger.info(f"User left team {team_id}")
    
    def _setup_rest_endpoints(self):
        """Setup REST API endpoints"""
        
        @self.app.route('/api/communication/send', methods=['POST'])
        def send_message_rest():
            """REST endpoint for sending messages"""
            try:
                data = request.get_json()
                user_id = data.get('user_id')
                content = data.get('content')
                recipient_id = data.get('recipient_id')
                message_type = data.get('message_type', 'chat')
                priority = MessagePriority(data.get('priority', MessagePriority.NORMAL.value))
                
                if not user_id or not content:
                    return jsonify({'error': 'User ID and content required'}), 400
                
                # Initialize client if needed
                if user_id not in self.clients:
                    self._initialize_user_client(user_id)
                
                # Send message
                future = self.executor.submit(
                    self._send_message_async,
                    user_id, content, recipient_id, message_type, priority
                )
                
                return jsonify({
                    'status': 'queued',
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"REST send message error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/communication/status/<user_id>', methods=['GET'])
        def get_status_rest(user_id):
            """REST endpoint for getting connection status"""
            try:
                if user_id in self.clients:
                    status = self.clients[user_id].get_connection_status()
                    return jsonify(status)
                else:
                    return jsonify({'status': 'not_initialized'})
                    
            except Exception as e:
                logger.error(f"REST get status error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/communication/queue/<user_id>', methods=['GET'])
        def get_queue_status(user_id):
            """Get offline queue status for user"""
            try:
                if user_id in self.clients:
                    queue_size = self.clients[user_id].offline_queue.get_queue_size()
                    return jsonify({'queue_size': queue_size})
                else:
                    return jsonify({'queue_size': 0})
                    
            except Exception as e:
                logger.error(f"REST get queue error: {e}")
                return jsonify({'error': str(e)}), 500
    
    def _initialize_user_client(self, user_id: str):
        """Initialize multi-protocol client for user"""
        if user_id in self.clients:
            return
        
        try:
            # Create client
            client = MultiProtocolClient(user_id)
            
            # Add message handler
            def handle_message(message: Message):
                self._handle_incoming_message(user_id, message)
            
            client.add_message_handler(handle_message)
            
            # Add status handler
            def handle_status(status_dict):
                self._handle_status_change(user_id, status_dict)
            
            client.add_status_handler(handle_status)
            
            # Store client
            self.clients[user_id] = client
            
            # Initialize protocols asynchronously
            self.executor.submit(self._initialize_protocols_async, user_id, client)
            
            logger.info(f"Initialized communication client for user {user_id}")
            
        except Exception as e:
            logger.error(f"Client initialization error for {user_id}: {e}")
    
    def _initialize_protocols_async(self, user_id: str, client: MultiProtocolClient):
        """Initialize protocols asynchronously"""
        async def init_protocols():
            try:
                # Initialize MQTT
                mqtt_endpoint = self.app.config.get('IOT_ENDPOINT')
                if mqtt_endpoint:
                    await client.initialize_mqtt(mqtt_endpoint)
                
                # Initialize WebRTC
                await client.initialize_webrtc()
                
                logger.info(f"Protocols initialized for user {user_id}")
                
            except Exception as e:
                logger.error(f"Protocol initialization error for {user_id}: {e}")
        
        # Run in new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(init_protocols())
        finally:
            loop.close()
    
    def _send_message_async(self, user_id: str, content: str, recipient_id: str = None,
                           message_type: str = 'chat', priority: MessagePriority = MessagePriority.NORMAL):
        """Send message asynchronously"""
        async def send_message():
            try:
                if user_id not in self.clients:
                    raise Exception("Client not initialized")
                
                client = self.clients[user_id]
                success = await client.send_message(content, recipient_id, message_type, priority)
                
                # Notify via SocketIO
                if user_id in self.user_sessions:
                    session_id = self.user_sessions[user_id]
                    self.socketio.emit('message_delivered', {
                        'success': success,
                        'timestamp': datetime.now().isoformat()
                    }, room=session_id)
                
                return success
                
            except Exception as e:
                logger.error(f"Async send message error: {e}")
                
                # Notify error via SocketIO
                if user_id in self.user_sessions:
                    session_id = self.user_sessions[user_id]
                    self.socketio.emit('message_error', {
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }, room=session_id)
                
                return False
        
        # Run in new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(send_message())
        finally:
            loop.close()
    
    def _handle_incoming_message(self, user_id: str, message: Message):
        """Handle incoming message for user"""
        try:
            # Emit to user's session
            if user_id in self.user_sessions:
                session_id = self.user_sessions[user_id]
                self.socketio.emit('message_received', {
                    'id': message.id,
                    'content': message.content,
                    'sender_id': message.sender_id,
                    'message_type': message.message_type,
                    'timestamp': message.timestamp,
                    'protocol_used': message.protocol_used
                }, room=session_id)
            
            # Also emit to user's room for multiple sessions
            self.socketio.emit('message_received', {
                'id': message.id,
                'content': message.content,
                'sender_id': message.sender_id,
                'message_type': message.message_type,
                'timestamp': message.timestamp,
                'protocol_used': message.protocol_used
            }, room=f"user_{user_id}")
            
            logger.info(f"Message {message.id} delivered to user {user_id}")
            
        except Exception as e:
            logger.error(f"Handle incoming message error: {e}")
    
    def _handle_status_change(self, user_id: str, status_dict: Dict[ProtocolType, ConnectionStatus]):
        """Handle connection status change for user"""
        try:
            # Convert to serializable format
            status_data = {
                'protocols': {protocol.value: status.value for protocol, status in status_dict.items()},
                'timestamp': datetime.now().isoformat()
            }
            
            # Emit to user's session
            if user_id in self.user_sessions:
                session_id = self.user_sessions[user_id]
                self.socketio.emit('status_changed', status_data, room=session_id)
            
            # Also emit to user's room
            self.socketio.emit('status_changed', status_data, room=f"user_{user_id}")
            
            logger.debug(f"Status change emitted for user {user_id}")
            
        except Exception as e:
            logger.error(f"Handle status change error: {e}")
    
    def _cleanup_user_session(self, user_id: str, session_id: str):
        """Clean up user session on disconnect"""
        try:
            # Remove session mappings
            if user_id in self.user_sessions and self.user_sessions[user_id] == session_id:
                del self.user_sessions[user_id]
            
            if session_id in self.session_users:
                del self.session_users[session_id]
            
            # Note: We keep the client running for offline message processing
            # Client cleanup happens when user explicitly logs out or after timeout
            
            logger.info(f"Cleaned up session for user {user_id}")
            
        except Exception as e:
            logger.error(f"Session cleanup error: {e}")
    
    def broadcast_to_team(self, team_id: str, message_data: Dict):
        """Broadcast message to all team members"""
        try:
            self.socketio.emit('team_message', message_data, room=f"team_{team_id}")
            logger.info(f"Broadcast sent to team {team_id}")
            
        except Exception as e:
            logger.error(f"Team broadcast error: {e}")
    
    def get_active_users(self) -> List[str]:
        """Get list of active users"""
        return list(self.user_sessions.keys())
    
    def get_user_rooms(self, user_id: str) -> List[str]:
        """Get rooms that user is in"""
        if user_id not in self.user_sessions:
            return []
        
        session_id = self.user_sessions[user_id]
        return rooms(session_id)
    
    async def shutdown(self):
        """Shutdown communication manager"""
        try:
            # Close all client connections
            for user_id, client in self.clients.items():
                await client.close()
            
            self.clients.clear()
            self.user_sessions.clear()
            self.session_users.clear()
            
            # Shutdown executor
            self.executor.shutdown(wait=True)
            
            logger.info("Communication manager shutdown complete")
            
        except Exception as e:
            logger.error(f"Shutdown error: {e}")

def create_communication_manager(app: Flask) -> CommunicationManager:
    """Factory function to create communication manager"""
    
    # Initialize SocketIO with eventlet
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='eventlet',
        logger=True,
        engineio_logger=True
    )
    
    # Create and return manager
    manager = CommunicationManager(app, socketio)
    
    # Store references in app for access elsewhere
    app.socketio = socketio
    app.communication_manager = manager
    
    return manager

# Example usage in Flask app
def setup_communication(app: Flask):
    """Setup communication system in Flask app"""
    
    # Create communication manager
    manager = create_communication_manager(app)
    
    # Add cleanup handler
    @app.teardown_appcontext
    def cleanup_communication(exception=None):
        if hasattr(app, 'communication_manager'):
            # Schedule cleanup (can't await in teardown)
            pass
    
    return manager