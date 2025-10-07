#!/usr/bin/env python3
"""
Standalone P2P Chat Test Server
Tests the P2P chat functionality without AWS dependencies
"""

import os
import sys
from flask import Flask, render_template
from flask_socketio import SocketIO
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = 'test-secret-key'

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Import enhanced P2P chat system
try:
    from enhanced_p2p_chat_engine import EnhancedP2PChatEngine
    from simple_p2p_chat import SimpleP2PChatIntegration
    
    # Initialize enhanced P2P chat
    p2p_chat = SimpleP2PChatIntegration(app, socketio)
    p2p_chat.register_routes()
    
    # Replace with enhanced engine
    if hasattr(p2p_chat, 'chat_engine'):
        p2p_chat.chat_engine = EnhancedP2PChatEngine(socketio, user_id="test_user")
        logger.info("Enhanced P2P Chat Engine with local storage initialized")
    
    logger.info("Enhanced P2P Chat system initialized successfully")
    
except ImportError as e:
    logger.error(f"Failed to import enhanced P2P chat system: {e}")
    # Fallback to simple version
    try:
        from simple_p2p_chat import SimpleP2PChatIntegration
        p2p_chat = SimpleP2PChatIntegration(app, socketio)
        p2p_chat.register_routes()
        logger.info("Fallback to simple P2P Chat system")
    except ImportError as e2:
        logger.error(f"Failed to import any P2P chat system: {e2}")
        sys.exit(1)

@app.route('/')
def index():
    """Main page with links to chat systems"""
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>P2P Chat Test Server</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0; padding: 40px; background: #f5f5f5; 
            }
            .container { 
                max-width: 800px; margin: 0 auto; background: white; 
                padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); 
            }
            h1 { color: #007A4D; text-align: center; margin-bottom: 30px; }
            .chat-links { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 30px 0; }
            .chat-card { 
                padding: 30px; border: 2px solid #e0e0e0; border-radius: 12px; 
                text-align: center; transition: all 0.3s ease; cursor: pointer;
                text-decoration: none; color: inherit;
            }
            .chat-card:hover { 
                border-color: #007A4D; transform: translateY(-4px); 
                box-shadow: 0 8px 25px rgba(0,122,77,0.15); 
            }
            .chat-card i { font-size: 48px; color: #007A4D; margin-bottom: 15px; }
            .chat-card h3 { margin: 15px 0 10px 0; color: #1a1a2e; }
            .chat-card p { color: #666; margin: 0; }
            .features { margin-top: 40px; }
            .features h3 { color: #007A4D; }
            .feature-list { 
                display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
                gap: 15px; margin-top: 20px; 
            }
            .feature-item { 
                display: flex; align-items: center; padding: 10px; 
                background: #f9f9f9; border-radius: 6px; 
            }
            .feature-item i { color: #007A4D; margin-right: 12px; width: 20px; }
            .status { 
                background: #e8f5e8; border: 1px solid #c3e6c3; 
                border-radius: 6px; padding: 15px; margin-bottom: 30px; 
            }
            .status h3 { color: #2d5a2d; margin: 0 0 10px 0; }
            .status p { color: #4a6b4a; margin: 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1><i class="fas fa-comments"></i> P2P Chat Test Server</h1>
            
            <div class="status">
                <h3><i class="fas fa-check-circle"></i> System Status: Enhanced & Online</h3>
                <p>Robust P2P Chat system with local storage and bandwidth awareness. Chat history stored locally, minimal AWS usage.</p>
            </div>
            
            <div class="chat-links">
                <a href="/p2p-chat" class="chat-card">
                    <i class="fas fa-comments"></i>
                    <h3>P2P Chat</h3>
                    <p>Advanced WhatsApp-like chat with file sharing</p>
                </a>
                
                <a href="/api/p2p-chat/health" class="chat-card">
                    <i class="fas fa-heartbeat"></i>
                    <h3>Health Check</h3>
                    <p>API health and system status</p>
                </a>
            </div>
            
            <div class="features">
                <h3><i class="fas fa-star"></i> P2P Chat Features</h3>
                <div class="feature-list">
                    <div class="feature-item">
                        <i class="fas fa-database"></i>
                        <span>Local storage priority - chat history on device</span>
                    </div>
                    <div class="feature-item">
                        <i class="fas fa-cloud-download-alt"></i>
                        <span>Minimal AWS usage - only essential data synced</span>
                    </div>
                    <div class="feature-item">
                        <i class="fas fa-signal"></i>
                        <span>Smart bandwidth detection & mode switching</span>
                    </div>
                    <div class="feature-item">
                        <i class="fas fa-eye"></i>
                        <span>Clear mode indicators - know your connection type</span>
                    </div>
                    <div class="feature-item">
                        <i class="fas fa-toggle-on"></i>
                        <span>Manual mode selection - choose your chat mode</span>
                    </div>
                    <div class="feature-item">
                        <i class="fas fa-robot"></i>
                        <span>Agent insights stored locally - never synced to cloud</span>
                    </div>
                    <div class="feature-item">
                        <i class="fas fa-bolt"></i>
                        <span>Real-time messaging with SocketIO</span>
                    </div>
                    <div class="feature-item">
                        <i class="fas fa-file-upload"></i>
                        <span>File & folder transfer with chunking</span>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/p2p-chat')
def p2p_chat_page():
    """P2P Chat interface"""
    return render_template('p2p_chat.html')

@app.errorhandler(404)
def not_found(error):
    """404 error handler"""
    return '''
    <h1>404 - Not Found</h1>
    <p>The requested page was not found.</p>
    <a href="/">← Back to Home</a>
    ''', 404

if __name__ == '__main__':
    print("🚀 Starting P2P Chat Test Server...")
    print("📍 Server will be available at:")
    print("   http://localhost:5000/ - Main page")
    print("   http://localhost:5000/p2p-chat - P2P Chat interface")
    print("   http://localhost:5000/api/p2p-chat/health - Health check")
    print("\n🔧 Features to test:")
    print("   • Real-time messaging")
    print("   • File upload with progress")
    print("   • Bandwidth optimization")
    print("   • Mobile responsiveness")
    print("   • WhatsApp-like interface")
    
    try:
        socketio.run(app, debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")