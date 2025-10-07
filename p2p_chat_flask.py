"""
Flask Integration for Advanced P2P Chat System
WhatsApp-like API endpoints with file transfer capabilities
"""

from flask import Blueprint, request, jsonify, session, send_file
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Dict, Any, Optional
import uuid

from p2p_chat_engine import P2PChatEngine, MessageType, UserStatus, ConnectionQuality, MessageStatus

logger = logging.getLogger(__name__)

# Create blueprint for advanced chat routes
advanced_chat_bp = Blueprint('advanced_chat', __name__, url_prefix='/api/chat')

class P2PChatFlaskIntegration:
    """Flask integration for P2P Chat Engine"""
    
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
            """Register user and join relevant chat rooms"""
            try:
                user_id = data.get('user_id')
                username = data.get('username')
                display_name = data.get('display_name')
                avatar_url = data.get('avatar_url')
                
                if not all([user_id, username, display_name]):
                    emit('error', {'message': 'Missing required user data'})
                    return
                
                # Register user
                user = self.chat_engine.register_user(
                    user_id=user_id,
                    username=username,
                    display_name=display_name,
                    avatar_url=avatar_url,
                    session_id=request.sid
                )
                
                # Map session to user
                self.user_sessions[request.sid] = user_id
                
                # Join user's chat rooms
                user_chats = self.chat_engine.get_user_chats(user_id)
                for chat_info in user_chats:
                    join_room(chat_info['chat_id'])
                
                emit('user_registered', {
                    'user': user.__dict__,
                    'chats': user_chats
                })
                
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
                reply_to = data.get('reply_to')
                
                if not all([chat_id, content]):
                    emit('error', {'message': 'Missing message data'})
                    return
                
                # Send message
                message = self.chat_engine.send_message(
                    sender_id=user_id,
                    chat_id=chat_id,
                    content=content,
                    message_type=message_type,
                    reply_to=reply_to
                )
                
                emit('message_sent', message.__dict__)
                
            except Exception as e:
                logger.error(f"Send message error: {e}")
                emit('error', {'message': str(e)})
        
        @self.socketio.on('typing_status')
        def handle_typing_status(data):
            """Handle typing indicators"""
            try:
                user_id = self.user_sessions.get(request.sid)
                if not user_id:
                    return
                
                chat_id = data.get('chat_id')
                is_typing = data.get('is_typing', False)
                
                self.chat_engine.set_typing_status(user_id, chat_id, is_typing)
                
            except Exception as e:
                logger.error(f"Typing status error: {e}")
        
        @self.socketio.on('mark_read')
        def handle_mark_read(data):
            """Handle read receipts"""
            try:
                user_id = self.user_sessions.get(request.sid)
                if not user_id:
                    return
                
                chat_id = data.get('chat_id')
                message_ids = data.get('message_ids', [])
                
                self.chat_engine.mark_messages_as_read(user_id, chat_id, message_ids)
                
            except Exception as e:
                logger.error(f"Mark read error: {e}")
        
        @self.socketio.on('join_chat')
        def handle_join_chat(data):
            """Join a specific chat room"""
            chat_id = data.get('chat_id')
            if chat_id:
                join_room(chat_id)
                emit('joined_chat', {'chat_id': chat_id})
        
        @self.socketio.on('leave_chat')
        def handle_leave_chat(data):
            """Leave a specific chat room"""
            chat_id = data.get('chat_id')
            if chat_id:
                leave_room(chat_id)
                emit('left_chat', {'chat_id': chat_id})

# Global instance (will be initialized in main app)
chat_integration: Optional[P2PChatFlaskIntegration] = None

def init_chat_system(socketio: SocketIO) -> P2PChatFlaskIntegration:
    """Initialize the chat system with SocketIO"""
    global chat_integration
    chat_integration = P2PChatFlaskIntegration(socketio)
    return chat_integration

# REST API Endpoints

@advanced_chat_bp.route('/register', methods=['POST'])
def register_user():
    """Register a new user via REST API"""
    try:
        data = request.get_json()
        
        user_id = data.get('user_id')
        username = data.get('username')
        display_name = data.get('display_name')
        avatar_url = data.get('avatar_url')
        
        if not all([user_id, username, display_name]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if not chat_integration:
            return jsonify({'error': 'Chat system not initialized'}), 500
        
        user = chat_integration.chat_engine.register_user(
            user_id=user_id,
            username=username,
            display_name=display_name,
            avatar_url=avatar_url
        )
        
        # Store user_id in session
        session['user_id'] = user_id
        
        return jsonify({
            'success': True,
            'user': user.__dict__
        })
        
    except Exception as e:
        logger.error(f"User registration error: {e}")
        return jsonify({'error': str(e)}), 500

@advanced_chat_bp.route('/users/search', methods=['GET'])
def search_users():
    """Search for users to add to chats"""
    try:
        query = request.args.get('q', '').strip()
        user_id = session.get('user_id')
        
        if not query:
            return jsonify({'users': []})
        
        if not chat_integration:
            return jsonify({'error': 'Chat system not initialized'}), 500
        
        users = chat_integration.chat_engine.search_users(query, exclude_user_id=user_id)
        
        return jsonify({
            'users': [user.__dict__ for user in users]
        })
        
    except Exception as e:
        logger.error(f"User search error: {e}")
        return jsonify({'error': str(e)}), 500

@advanced_chat_bp.route('/chats', methods=['GET'])
def get_user_chats():
    """Get all chats for the current user"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        if not chat_integration:
            return jsonify({'error': 'Chat system not initialized'}), 500
        
        chats = chat_integration.chat_engine.get_user_chats(user_id)
        
        return jsonify({
            'chats': chats
        })
        
    except Exception as e:
        logger.error(f"Get chats error: {e}")
        return jsonify({'error': str(e)}), 500

@advanced_chat_bp.route('/chats/create', methods=['POST'])
def create_chat():
    """Create a new chat"""
    try:
        data = request.get_json()
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        participants = data.get('participants', [])
        chat_name = data.get('chat_name')
        
        if not participants:
            return jsonify({'error': 'At least one participant required'}), 400
        
        if not chat_integration:
            return jsonify({'error': 'Chat system not initialized'}), 500
        
        chat_id = chat_integration.chat_engine.create_chat(
            creator_id=user_id,
            participants=participants,
            chat_name=chat_name
        )
        
        return jsonify({
            'success': True,
            'chat_id': chat_id
        })
        
    except Exception as e:
        logger.error(f"Create chat error: {e}")
        return jsonify({'error': str(e)}), 500

@advanced_chat_bp.route('/chats/<chat_id>/invite', methods=['POST'])
def invite_user():
    """Invite a user to an existing chat"""
    try:
        data = request.get_json()
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        invite_user_id = data.get('user_id')
        if not invite_user_id:
            return jsonify({'error': 'User ID required'}), 400
        
        if not chat_integration:
            return jsonify({'error': 'Chat system not initialized'}), 500
        
        success = chat_integration.chat_engine.invite_user_to_chat(
            chat_id=chat_id,
            inviter_id=user_id,
            user_id=invite_user_id
        )
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to invite user'}), 400
        
    except Exception as e:
        logger.error(f"Invite user error: {e}")
        return jsonify({'error': str(e)}), 500

@advanced_chat_bp.route('/chats/<chat_id>/messages', methods=['GET'])
def get_messages():
    """Get messages from a chat with pagination"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        limit = int(request.args.get('limit', 50))
        before_message_id = request.args.get('before')
        
        if not chat_integration:
            return jsonify({'error': 'Chat system not initialized'}), 500
        
        # Verify user has access to chat
        user_chats = chat_integration.chat_engine.get_user_chats(user_id)
        chat_ids = [chat['chat_id'] for chat in user_chats]
        
        if chat_id not in chat_ids:
            return jsonify({'error': 'Access denied'}), 403
        
        messages = chat_integration.chat_engine.get_chat_messages(
            chat_id=chat_id,
            limit=limit,
            before_message_id=before_message_id
        )
        
        return jsonify({
            'messages': messages
        })
        
    except Exception as e:
        logger.error(f"Get messages error: {e}")
        return jsonify({'error': str(e)}), 500

@advanced_chat_bp.route('/chats/<chat_id>/send', methods=['POST'])
def send_message_rest():
    """Send a message via REST API"""
    try:
        data = request.get_json()
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        content = data.get('content', '').strip()
        message_type = MessageType(data.get('message_type', 'text'))
        reply_to = data.get('reply_to')
        
        if not content:
            return jsonify({'error': 'Message content required'}), 400
        
        if not chat_integration:
            return jsonify({'error': 'Chat system not initialized'}), 500
        
        message = chat_integration.chat_engine.send_message(
            sender_id=user_id,
            chat_id=chat_id,
            content=content,
            message_type=message_type,
            reply_to=reply_to
        )
        
        return jsonify({
            'success': True,
            'message': message.__dict__
        })
        
    except Exception as e:
        logger.error(f"Send message error: {e}")
        return jsonify({'error': str(e)}), 500

@advanced_chat_bp.route('/files/upload', methods=['POST'])
def upload_file():
    """Upload a file for sharing in chat"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        chat_id = request.form.get('chat_id')
        if not chat_id:
            return jsonify({'error': 'Chat ID required'}), 400
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not chat_integration:
            return jsonify({'error': 'Chat system not initialized'}), 500
        
        # Save uploaded file temporarily
        temp_dir = tempfile.gettempdir()
        temp_filename = f"{uuid.uuid4()}_{file.filename}"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        file.save(temp_path)
        
        try:
            # Start file transfer
            transfer_id = chat_integration.chat_engine.start_file_transfer(
                sender_id=user_id,
                chat_id=chat_id,
                file_path=temp_path
            )
            
            return jsonify({
                'success': True,
                'transfer_id': transfer_id
            })
            
        finally:
            # Clean up temp file after transfer starts
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
    except Exception as e:
        logger.error(f"File upload error: {e}")
        return jsonify({'error': str(e)}), 500

@advanced_chat_bp.route('/folders/upload', methods=['POST'])
def upload_folder():
    """Upload a folder as a zip file"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # This would typically be handled by the frontend creating a zip
        # and uploading it as a regular file with folder metadata
        return jsonify({'error': 'Folder upload should be handled via frontend zip creation'}), 400
        
    except Exception as e:
        logger.error(f"Folder upload error: {e}")
        return jsonify({'error': str(e)}), 500

@advanced_chat_bp.route('/transfers/<transfer_id>/status', methods=['GET'])
def get_transfer_status():
    """Get the status of a file transfer"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        if not chat_integration:
            return jsonify({'error': 'Chat system not initialized'}), 500
        
        status = chat_integration.chat_engine.get_transfer_status(transfer_id)
        
        if not status:
            return jsonify({'error': 'Transfer not found'}), 404
        
        return jsonify({
            'transfer': status
        })
        
    except Exception as e:
        logger.error(f"Get transfer status error: {e}")
        return jsonify({'error': str(e)}), 500

@advanced_chat_bp.route('/transfers/<transfer_id>/cancel', methods=['POST'])
def cancel_transfer():
    """Cancel a file transfer"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        if not chat_integration:
            return jsonify({'error': 'Chat system not initialized'}), 500
        
        success = chat_integration.chat_engine.cancel_transfer(transfer_id, user_id)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to cancel transfer'}), 400
        
    except Exception as e:
        logger.error(f"Cancel transfer error: {e}")
        return jsonify({'error': str(e)}), 500

@advanced_chat_bp.route('/bandwidth/update', methods=['POST'])
def update_bandwidth():
    """Update user's connection quality for bandwidth optimization"""
    try:
        data = request.get_json()
        user_id = session.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        connection_quality = ConnectionQuality(data.get('connection_quality', 'high'))
        
        if not chat_integration:
            return jsonify({'error': 'Chat system not initialized'}), 500
        
        chat_integration.chat_engine.update_user_status(
            user_id=user_id,
            status=UserStatus.ONLINE,
            connection_quality=connection_quality
        )
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Update bandwidth error: {e}")
        return jsonify({'error': str(e)}), 500

    def register_routes(self):
        """Register all P2P chat routes with the Flask app"""
        # Register the blueprint with P2P chat routes
        self.app.register_blueprint(advanced_chat_bp, url_prefix='/api/p2p-chat')
        
        # Additional health check route
        @self.app.route('/api/p2p-chat/health')
        def health_check():
            return jsonify({
                'status': 'healthy',
                'engine': 'P2P Chat Engine v1.0',
                'features': [
                    'real-time messaging',
                    'file transfer',
                    'bandwidth optimization', 
                    'user management',
                    'typing indicators',
                    'read receipts'
                ],
                'timestamp': datetime.now().isoformat()
            })
        
        logger.info("P2P Chat routes registered successfully")