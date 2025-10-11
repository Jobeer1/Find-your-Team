"""
Simple runner for Find Your Team without eventlet dependencies
Compatible with Python 3.13+
"""

import os
import sys
import logging
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('findyourteam.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_simple_app():
    """Create a simple Flask app without eventlet dependencies"""
    
    # Import Flask and basic dependencies
    from flask import Flask, render_template, request, jsonify, session, send_from_directory
    from flask_socketio import SocketIO
    import json
    import uuid
    from datetime import datetime
    import configparser
    
    # Create Flask app
    app = Flask(__name__)
    app.secret_key = 'dev-secret-key-change-in-production'
    
    # Simple SocketIO setup (threading mode)
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
    app.socketio = socketio
    
    # Simple location detection
    def get_user_location():
        """Simple location detection"""
        return {
            'country': 'your location',
            'region': 'your region', 
            'province': 'your province',
            'city': '',
            'location_string': 'your location',
            'timezone': '',
            'ip': 'unknown'
        }
    
    # Basic routes
    @app.route('/')
    def index():
        """Main landing page"""
        location = get_user_location()
        location_text = location.get('location_string', 'your location')
        return render_template('find_your_team.html', 
                             user_location=location_text,
                             location_data=location,
                             show_onboarding=True)
    
    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory('static', 'icon-192.png')
    
    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html')
    
    @app.route('/login')
    def login():
        return render_template('login.html')
    
    @app.route('/signup')
    def signup():
        return render_template('signup.html')
    
    @app.route('/profile')
    def profile():
        return render_template('profile.html')
    
    # API routes
    @app.route('/api/chat', methods=['POST'])
    def handle_chat():
        """Simple chat handler"""
        try:
            data = request.get_json()
            user_input = data.get('message', '').strip()
            
            if not user_input:
                return jsonify({'error': 'Message cannot be empty'}), 400
            
            # Simple demo response
            response = {
                'response': f"Thank you for sharing: '{user_input}'. That's wonderful! Can you tell me more about what specifically excites you about this?",
                'confidence_score': 75,
                'session_id': str(uuid.uuid4()),
                'agent': 'demo'
            }
            
            return jsonify(response)
            
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/api/onboarding/start', methods=['POST'])
    def start_onboarding():
        """Start onboarding conversation"""
        try:
            location = get_user_location()
            location_text = location.get('location_string', 'your location')
            
            welcome_message = f"🌟 Warm welcome to you in {location_text}! 🌟\n\nWe are here to help you find your team and your purpose. No signup needed - let's start your journey right now!\n\nWhat brings you here today? Tell me about something you're passionate about! 💫"
            
            conversation_id = str(uuid.uuid4())
            
            return jsonify({
                'conversation_id': conversation_id,
                'welcome_message': welcome_message,
                'location': location_text
            })
            
        except Exception as e:
            logger.error(f"Onboarding start error: {e}")
            return jsonify({
                'conversation_id': str(uuid.uuid4()),
                'welcome_message': "🌟 Welcome! We are here to help you find your team and your purpose. Are you ready for the journey?",
                'location': "your location"
            }), 200
    
    @app.route('/health')
    @app.route('/api/health')
    def health_check():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0'
        })
    
    # SocketIO events
    @socketio.on('connect')
    def handle_connect():
        logger.info("Client connected")
    
    @socketio.on('disconnect') 
    def handle_disconnect():
        logger.info("Client disconnected")
    
    return app, socketio

def main():
    """Main function to run the application"""
    try:
        # Ensure required directories exist
        Path("audio").mkdir(exist_ok=True)
        Path("data").mkdir(exist_ok=True)
        
        # Create the app
        app, socketio = create_simple_app()
        
        # Configuration
        host = "0.0.0.0"
        port = int(os.getenv('PORT', 5004))
        debug_mode = True
        
        logger.info(f"Starting Find Your Team on {host}:{port}")
        logger.info("🌟 No login required - Mobile optimized - Ready to go!")
        logger.info(f"Access from desktop: http://localhost:{port}")
        logger.info(f"Access from mobile: http://YOUR_IP:{port}")
        
        # Run the application
        socketio.run(app, host=host, port=port, debug=debug_mode, use_reloader=False)
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        print(f"\n❌ Error: {e}")
        print("\n🔧 Try these solutions:")
        print("1. Make sure no other application is using port 5004")
        print("2. Run: pip install flask flask-socketio")
        print("3. Check if templates/find_your_team.html exists")
        return 1
    
    return 0

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)