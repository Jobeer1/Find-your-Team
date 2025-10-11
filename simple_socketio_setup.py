"""
Simple SocketIO setup without eventlet dependency
Compatible with Python 3.13+
"""

from flask_socketio import SocketIO
import logging

logger = logging.getLogger(__name__)

def setup_simple_socketio(app):
    """Setup SocketIO without eventlet - uses threading mode"""
    try:
        # Use threading mode instead of eventlet
        socketio = SocketIO(
            app, 
            cors_allowed_origins="*",
            async_mode='threading',  # Use threading instead of eventlet
            logger=False,
            engineio_logger=False
        )
        
        @socketio.on('connect')
        def handle_connect():
            logger.info(f"Client connected")
            
        @socketio.on('disconnect')
        def handle_disconnect():
            logger.info(f"Client disconnected")
            
        @socketio.on('chat_message')
        def handle_chat_message(data):
            logger.info(f"Chat message received: {data}")
            socketio.emit('chat_response', {
                'message': f"Echo: {data.get('message', '')}",
                'timestamp': data.get('timestamp')
            })
        
        app.socketio = socketio
        logger.info("SocketIO setup complete (threading mode)")
        return socketio
        
    except Exception as e:
        logger.error(f"SocketIO setup failed: {e}")
        return None