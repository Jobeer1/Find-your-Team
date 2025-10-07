"""
Find Your Team - AWS-Powered Flask Application
Transformed from existing app.py to use AWS services for hackathon demo
"""

# Note: We avoid using eventlet monkey-patching in this development setup to
# prevent Werkzeug LocalProxy upgrade issues during import. Socket.IO will
# run using the 'threading' async mode by default which works with the dev server.
# Note: eventlet monkey-patching is performed lazily inside the communication
# integration to avoid upgrading werkzeug LocalProxy objects too early. See
# communication/flask_integration.create_communication_manager for details.

import os
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import configparser

import boto3
from flask import Flask, request, jsonify, render_template, send_from_directory, session
from botocore.exceptions import ClientError
import requests
from dotenv import load_dotenv

# Import communication setup with error handling
try:
    from communication.flask_integration import setup_communication
    COMMUNICATION_AVAILABLE = True
except ImportError as e:
    print(f"Communication dependencies not available: {e}")
    COMMUNICATION_AVAILABLE = False
    
    def setup_communication(app):
        """Stub for when communication is not available"""
        print("Communication setup skipped - dependencies not available")
        return None

# Import enhanced P2P chat system with error handling
try:
    from enhanced_p2p_chat_engine import EnhancedP2PChatEngine
    from simple_p2p_chat import SimpleP2PChatIntegration
    P2P_CHAT_AVAILABLE = True
except ImportError as e:
    print(f"Enhanced P2P Chat dependencies not available: {e}")
    P2P_CHAT_AVAILABLE = False
    
    class SimpleP2PChatIntegration:
        """Stub for when P2P chat is not available"""
        def __init__(self, app, socketio):
            print("Enhanced P2P Chat setup skipped - dependencies not available")
        
        def register_routes(self):
            pass

# Load environment variables
load_dotenv()

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

class AWSConfig:
    """AWS Configuration Manager"""
    
    def __init__(self):
        # Load config from config.ini
        self.config = configparser.ConfigParser()
        config_file = Path('config.ini')
        
        if config_file.exists():
            self.config.read(config_file)
        
        # AWS settings with environment variable fallback
        self.region = self._get_config_value('AWS', 'aws_region', os.getenv('AWS_DEFAULT_REGION', 'us-west-2'))
        self.access_key = self._get_config_value('AWS', 'aws_access_key_id', os.getenv('AWS_ACCESS_KEY_ID'))
        self.secret_key = self._get_config_value('AWS', 'aws_secret_access_key', os.getenv('AWS_SECRET_ACCESS_KEY'))
        
        # Table names
        self.user_profiles_table = self._get_config_value('AWS', 'dynamodb_table_users', 'find-your-team-users')
        self.team_performance_table = self._get_config_value('AWS', 'dynamodb_table_teams', 'find-your-team-teams')
        self.integrations_table = self._get_config_value('AWS', 'dynamodb_table_integrations', 'find-your-team-integrations')
        
        # Bedrock settings
        self.bedrock_model_id = self._get_config_value('AWS', 'bedrock_model_id', 'anthropic.claude-3-5-sonnet-20240620-v1:0')
        self.bedrock_region = self._get_config_value('AWS', 'bedrock_region', self.region)
        
        # OpenSearch settings
        self.opensearch_domain = self._get_config_value('AWS', 'opensearch_domain_name', 'find-your-team-search')
        self.opensearch_region = self._get_config_value('AWS', 'opensearch_region', self.region)
        
        # IoT settings
        self.iot_endpoint = self._get_config_value('AWS', 'iot_endpoint')
        self.iot_topic_prefix = self._get_config_value('AWS', 'iot_topic_prefix', 'find-your-team/')
        
        # App settings
        self.debug = self._get_config_value('APP', 'debug', 'false').lower() == 'true'
        self.host = self._get_config_value('APP', 'host', '0.0.0.0')
        port = int(os.getenv('PORT', 5003))
        self.secret_key = self._get_config_value('APP', 'secret_key', 'dev-secret-key-change-in-production')
        
        # Agent settings
        self.onboarding_agent_enabled = self._get_config_value('AGENTS', 'onboarding_agent_enabled', 'true').lower() == 'true'
        self.matching_agent_enabled = self._get_config_value('AGENTS', 'matching_agent_enabled', 'true').lower() == 'true'
        self.team_agent_enabled = self._get_config_value('AGENTS', 'team_agent_enabled', 'true').lower() == 'true'
        self.integration_agent_enabled = self._get_config_value('AGENTS', 'integration_agent_enabled', 'true').lower() == 'true'
        
        self.agent_timeout = int(self._get_config_value('AGENTS', 'agent_timeout', '30'))
        self.max_retries = int(self._get_config_value('AGENTS', 'max_retries', '3'))
        
        # Validate required AWS credentials (allow demo mode)
        self.demo_mode = False
        if not self.access_key or not self.secret_key or self.access_key.startswith('YOUR_'):
            logger.warning("AWS credentials not configured. Running in demo mode.")
            self.demo_mode = True
        
        # Initialize AWS clients (skip in demo mode)
        if not self.demo_mode:
            try:
                self.dynamodb = boto3.resource(
                    'dynamodb',
                    region_name=self.region,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key
                )
                self.bedrock = boto3.client(
                    'bedrock-runtime',
                    region_name=self.bedrock_region,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key
                )
                self.iot_data = None
                # Only initialize IoT client if endpoint is properly configured
                iot_endpoint = self._get_config_value('AWS', 'iot_endpoint')
                if iot_endpoint and not iot_endpoint.startswith('YOUR_'):
                    self.iot_data = boto3.client(
                        'iot-data',
                        region_name=self.region,
                        aws_access_key_id=self.access_key,
                        aws_secret_access_key=self.secret_key,
                        endpoint_url=f"https://{iot_endpoint}"
                    )
                self.lambda_client = boto3.client(
                    'lambda',
                    region_name=self.region,
                    aws_access_key_id=self.access_key,
                    aws_secret_access_key=self.secret_key
                )
                
                # Get table references
                self.user_profiles_table_ref = self.dynamodb.Table(self.user_profiles_table)
                self.team_performance_table_ref = self.dynamodb.Table(self.team_performance_table)
                self.integrations_table_ref = self.dynamodb.Table(self.integrations_table)
                
                logger.info("AWS services initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize AWS services: {e}")
                self.demo_mode = True
        else:
            # Demo mode - set clients to None
            self.dynamodb = None
            self.bedrock = None
            self.iot_data = None
            self.lambda_client = None
            self.user_profiles_table_ref = None
            self.team_performance_table_ref = None
            self.integrations_table_ref = None
    
    def _get_config_value(self, section: str, key: str, default: str = '') -> str:
        """Get configuration value from config.ini or environment variable"""
        # First try environment variable
        env_key = f"{section.upper()}_{key.upper()}"
        env_value = os.getenv(env_key)
        if env_value:
            return env_value
        
        # Then try config file
        try:
            return self.config.get(section, key, fallback=default)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

class BedrockAgentService:
    """Service for interacting with Amazon Bedrock agents"""
    
    def __init__(self, aws_config: AWSConfig):
        self.aws_config = aws_config
        self.bedrock = aws_config.bedrock
        
    def invoke_onboarding_agent(self, user_input: str, session_id: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Invoke the Onboarding Agent using Bedrock with conversation history"""
        try:
            if self.aws_config.demo_mode:
                # Enhanced demo mode with history awareness
                history_context = ""
                if conversation_history:
                    prev_messages = [msg['message'] for msg in conversation_history[-5:]]  # Last 5 messages
                    history_context = f"Previous conversation context: {'; '.join(prev_messages)}. "
                
                return {
                    'response': f"Demo mode: {history_context}I understand you're interested in '{user_input}'. That's great! Based on our previous conversations, I can see you're passionate about meaningful work. What specific skills do you have that could help in this area?",
                    'confidence_score': 80 if conversation_history else 75,
                    'session_id': session_id,
                    'agent': 'onboarding'
                }
            
            # For hackathon demo, we'll use Claude directly
            # In production, this would use Bedrock AgentCore
            
            prompt = f"""You are the Onboarding Agent for Find Your Team, a platform that helps people discover their purpose and connect with meaningful teams. Your goal is to build a comprehensive Purpose Profile with ≥90% confidence.

Current conversation with user:
User: {user_input}

Please respond empathetically and ask insightful questions to understand:
1. Their core values and what drives them
2. Their passions and what they love doing
3. Their skills (technical, soft, leadership)
4. Their work style preferences
5. How they want to add value to people they care about

Keep the conversation natural and engaging. If you have enough information, provide a confidence score and summary."""

            response = self.bedrock.invoke_model(
                modelId=self.aws_config.bedrock_model_id,
                body=json.dumps({
                    'anthropic_version': 'bedrock-2023-05-31',
                    'max_tokens': 1000,
                    'messages': [
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ]
                })
            )
            
            response_body = json.loads(response['body'].read())
            agent_response = response_body['content'][0]['text']
            
            # Extract confidence score if mentioned
            confidence_score = self._extract_confidence_score(agent_response)
            
            return {
                'response': agent_response,
                'confidence_score': confidence_score,
                'session_id': session_id,
                'agent': 'onboarding'
            }
            
        except Exception as e:
            logger.error(f"Error invoking onboarding agent: {str(e)}")
            return {
                'response': "I'm having trouble processing your request right now. Let's try again.",
                'confidence_score': 0,
                'session_id': session_id,
                'agent': 'onboarding',
                'error': str(e)
            }
    
    def _extract_confidence_score(self, response: str) -> int:
        """Extract confidence score from agent response"""
        # Simple pattern matching for demo
        import re
        
        patterns = [
            r'confidence[:\s]+(\d+)%',
            r'(\d+)%\s+confidence',
            r'confidence[:\s]+(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response.lower())
            if match:
                return int(match.group(1))
        
        # Default confidence based on response length and content
        if len(response) > 200 and any(word in response.lower() for word in ['values', 'skills', 'passion']):
            return 75
        elif len(response) > 100:
            return 50
        else:
            return 25

class DataService:
    """Service for managing user and team data"""
    
    def __init__(self, aws_config: AWSConfig):
        self.aws_config = aws_config
    
    def save_user_profile(self, user_profile: Dict[str, Any]) -> bool:
        """Save user profile to DynamoDB"""
        try:
            if self.aws_config.demo_mode:
                logger.info(f"Demo mode: Would save user profile for {user_profile.get('userId')}")
                return True
                
            self.aws_config.user_profiles_table_ref.put_item(Item=user_profile)
            logger.info(f"Saved user profile for {user_profile.get('userId')}")
            return True
        except Exception as e:
            logger.error(f"Error saving user profile: {str(e)}")
            return False
    
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile from DynamoDB"""
        try:
            if self.aws_config.demo_mode:
                logger.info(f"Demo mode: Would get user profile for {user_id}")
                return None
                
            response = self.aws_config.user_profiles_table_ref.get_item(
                Key={'userId': user_id}
            )
            return response.get('Item')
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            return None

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-key-change-in-production')

# Initialize services
aws_config = AWSConfig()
bedrock_service = BedrockAgentService(aws_config)
data_service = DataService(aws_config)

# Initialize communication system
communication_manager = setup_communication(app)

# Initialize enhanced P2P chat system
if P2P_CHAT_AVAILABLE and communication_manager and hasattr(communication_manager, 'socketio'):
    p2p_chat = SimpleP2PChatIntegration(app, communication_manager.socketio)
    p2p_chat.register_routes()
    
    # Replace with enhanced engine for local storage and bandwidth management
    if hasattr(p2p_chat, 'chat_engine'):
        p2p_chat.chat_engine = EnhancedP2PChatEngine(communication_manager.socketio, user_id="system_user")
        logger.info("Enhanced P2P Chat Engine with local storage and bandwidth management initialized")
        
        # Add enhanced socket handler for user registration
        @communication_manager.socketio.on('user_register')
        def handle_enhanced_user_register(data):
            """Enhanced user registration handler"""
            from flask import request
            success = p2p_chat.chat_engine.handle_user_registration(
                communication_manager.socketio, 
                data, 
                request.sid
            )
            if success:
                logger.info(f"Enhanced user registration successful for {data.get('display_name')}")
            else:
                logger.error(f"Enhanced user registration failed for {data.get('display_name')}")
    
    logger.info("Enhanced P2P Chat system initialized successfully")
else:
    p2p_chat = None
    logger.warning("Enhanced P2P Chat system not available - requires SocketIO")

# Store conversation sessions in memory (use Redis in production)
conversation_sessions = {}

@app.route('/')
def index():
    """Main landing page or dashboard based on auth status"""
    # In a real app, you'd check for valid session/token
    # For demo, we'll check if there's user data in the request
    return render_template('find_your_team.html')

@app.route('/dashboard')
def dashboard():
    """Authenticated user dashboard"""
    return render_template('dashboard.html')

@app.route('/lan-chat')
def lan_chat():
    """LAN Chat interface for low bandwidth and offline scenarios"""
    # For demo purposes, we'll allow access but could add session checking here
    return render_template('lan_chat.html')

@app.route('/p2p-chat')
def p2p_chat_page():
    """Advanced P2P Chat interface with WhatsApp-like features"""
    # For demo purposes, we'll allow access but could add session checking here
    return render_template('p2p_chat.html')

@app.route('/login')
def login():
    """Login page"""
    return render_template('login.html')

@app.route('/signup') 
def signup():
    """Signup page"""
    return render_template('signup.html')

@app.route('/profile')
def profile():
    """User profile page"""
    return render_template('profile.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    """Handle login requests"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
            
        # For demo purposes - in production, verify against database
        if email == 'demo@findyourteam.com' and password == 'demo123':
            return jsonify({
                'success': True,
                'user': {
                    'id': 'demo-user-123',
                    'email': email,
                    'name': 'Demo User'
                },
                'token': 'demo-jwt-token'
            })
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/signup', methods=['POST']) 
def api_signup():
    """Handle signup requests"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        name = data.get('name', '').strip()
        
        if not email or not password or not name:
            return jsonify({'error': 'Name, email and password are required'}), 400
            
        # For demo purposes - in production, create user in database
        return jsonify({
            'success': True,
            'user': {
                'id': f'user-{uuid.uuid4()}',
                'email': email,
                'name': name
            },
            'message': 'Account created successfully!'
        })
        
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/chat', methods=['POST'])
def handle_chat():
    """Handle chat messages from the frontend with conversation history"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        agent = data.get('agent', 'onboarding')
        user_id = data.get('user_id', 'anonymous')
        include_history = data.get('include_history', True)
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Get conversation history if requested
        conversation_history = []
        if include_history:
            try:
                # Create demo conversation history for enhanced agent insights
                conversation_history = [
                    {
                        'timestamp': '2025-01-18T10:00:00Z',
                        'message': message,
                        'type': 'user_message',
                        'confidence_extracted': 0.8
                    }
                ]
                # Add previous messages from session if available
                if 'conversation_history' in session:
                    conversation_history = session['conversation_history'] + conversation_history
                    # Keep only last 10 messages for context
                    conversation_history = conversation_history[-10:]
            except Exception as e:
                logger.warning(f"Failed to fetch conversation history: {e}")
                conversation_history = []
        
        # Use enhanced Bedrock service with conversation history
        result = bedrock_service.invoke_onboarding_agent(message, user_id, conversation_history)
        
        # Store this conversation in session
        if 'conversation_history' not in session:
            session['conversation_history'] = []
        session['conversation_history'].append({
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'response': result['response'],
            'type': 'chat_exchange',
            'confidence_extracted': result['confidence_score'] / 100.0
        })
        
        return jsonify({
            'message': result['response'],
            'confidence': result['confidence_score'] / 100.0,  # Convert to 0-1 scale
            'user_id': user_id,
            'agent': agent,
            'history_used': len(conversation_history)
        })
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/chat/bandwidth/update', methods=['POST'])
def update_chat_bandwidth():
    """Update bandwidth information for chat mode selection"""
    try:
        data = request.get_json()
        bandwidth_quality = data.get('bandwidth_quality', 'unknown')
        network_type = data.get('network_type', 'unknown')
        connection_speed = data.get('connection_speed', 0)
        
        # Store bandwidth info (in production, save to database)
        session['bandwidth_quality'] = bandwidth_quality
        session['network_type'] = network_type
        session['connection_speed'] = connection_speed
        
        # Update P2P chat engine if available
        if p2p_chat and hasattr(p2p_chat, 'chat_engine'):
            try:
                p2p_chat.chat_engine.update_bandwidth_info(bandwidth_quality, network_type)
            except Exception as e:
                logger.warning(f"Could not update P2P bandwidth: {e}")
        
        return jsonify({
            'status': 'success',
            'bandwidth_quality': bandwidth_quality,
            'network_type': network_type,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Bandwidth update error: {e}")
        return jsonify({'error': 'Failed to update bandwidth'}), 500

@app.route('/api/profile', methods=['GET'])
def get_profile():
    """Get user profile information with extracted insights"""
    try:
        # Get extracted insights from session
        extracted_insights = session.get('extracted_insights', {})
        
        # Demo profile data (in production, get from database)
        profile_data = {
            'user_id': session.get('user_id', 'demo_user'),
            'username': session.get('username', 'Demo User'),
            'display_name': session.get('display_name', 'Demo User'),
            'email': session.get('email', 'demo@example.com'),
            'avatar_url': '/static/images/default-avatar.png',
            'preferences': {
                'chat_mode': 'auto',
                'notifications': True,
                'dark_mode': False
            },
            'stats': {
                'messages_sent': 142,
                'files_shared': 23,
                'teams_joined': 5,
                'active_since': '2025-01-15',
                'insights_extracted': len(extracted_insights.get('extracted_values', []) + extracted_insights.get('skills_identified', [])),
                'confidence_score': extracted_insights.get('confidence_score', 75)
            },
            'extracted_insights': extracted_insights
        }
        return jsonify(profile_data)
    except Exception as e:
        logger.error(f"Profile fetch error: {e}")
        return jsonify({'error': 'Failed to fetch profile'}), 500

@app.route('/api/profile', methods=['PUT'])
def update_profile():
    """Update user profile information"""
    try:
        data = request.get_json()
        
        # Update session data (in production, update database)
        if 'display_name' in data:
            session['display_name'] = data['display_name']
        if 'email' in data:
            session['email'] = data['email']
        if 'preferences' in data:
            session['preferences'] = data['preferences']
            
        return jsonify({
            'status': 'success',
            'message': 'Profile updated successfully',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        return jsonify({'error': 'Failed to update profile'}), 500

@app.route('/api/chat/register', methods=['POST'])
def register_chat_user():
    """Register user for P2P chat"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        username = data.get('username')
        display_name = data.get('display_name')
        
        if not all([user_id, username, display_name]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Store user in session (in production, use database)
        session['chat_user_id'] = user_id
        session['chat_username'] = username
        session['chat_display_name'] = display_name
        session['chat_avatar_url'] = data.get('avatar_url')
        
        # Return user data and empty chats for now
        user_data = {
            'user_id': user_id,
            'username': username,
            'display_name': display_name,
            'avatar_url': data.get('avatar_url'),
            'status': 'online'
        }
        
        return jsonify({
            'status': 'success',
            'user': user_data,
            'chats': [],  # Start with empty chats
            'users': []   # Start with empty user list
        })
        
    except Exception as e:
        logger.error(f"Chat registration error: {e}")
        return jsonify({'error': 'Failed to register user'}), 500

@app.route('/api/chat/history/<user_id>', methods=['GET'])
def get_chat_history(user_id):
    """Get chat history for onboarding agent insights"""
    try:
        # For now, return demo conversation data
        # In production, this would fetch from local storage or database
        demo_history = [
            {
                'timestamp': '2025-09-28T10:00:00Z',
                'message': 'I\'m passionate about helping communities through technology.',
                'type': 'user_message',
                'confidence_extracted': 0.8
            },
            {
                'timestamp': '2025-09-28T10:05:00Z', 
                'message': 'I have experience in full-stack development and project management.',
                'type': 'user_message',
                'confidence_extracted': 0.9
            },
            {
                'timestamp': '2025-09-28T10:10:00Z',
                'message': 'I want to build solutions that make a real difference in people\'s lives.',
                'type': 'user_message',
                'confidence_extracted': 0.85
            }
        ]
        
        return jsonify({
            'user_id': user_id,
            'total_messages': len(demo_history),
            'conversation_history': demo_history,
            'insights_extracted': {
                'key_values': ['community impact', 'technology for good'],
                'skills_identified': ['full-stack development', 'project management'],
                'passion_areas': ['community service', 'meaningful technology'],
                'confidence_score': 85
            }
        })
        
    except Exception as e:
        logger.error(f"Chat history error: {e}")
        return jsonify({'error': 'Failed to fetch chat history'}), 500

@app.route('/api/chat/extract-insights', methods=['POST'])
def extract_conversation_insights():
    """Extract insights from previous conversations for profile enhancement"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', session.get('user_id', 'anonymous'))
        conversation_text = data.get('conversation_text', '')
        
        # Get conversation history from session and any provided text
        all_conversations = []
        
        # Add session conversation history
        if 'conversation_history' in session:
            for conv in session['conversation_history']:
                all_conversations.append(conv.get('message', ''))
                all_conversations.append(conv.get('response', ''))
        
        # Add any additional conversation text provided
        if conversation_text:
            all_conversations.append(conversation_text)
        
        # Extract insights using enhanced analysis
        insights = {
            'extracted_values': [],
            'skills_identified': [],
            'passion_areas': [],
            'work_preferences': [],
            'personality_traits': [],
            'confidence_score': 0
        }
        
        if all_conversations:
            # Basic keyword analysis (in production, use NLP/ML)
            text_combined = ' '.join(all_conversations).lower()
            
            # Extract values
            value_keywords = ['community', 'impact', 'helping', 'innovation', 'teamwork', 'leadership', 'creativity', 'problem-solving']
            insights['extracted_values'] = [kw for kw in value_keywords if kw in text_combined]
            
            # Extract skills
            skill_keywords = ['programming', 'development', 'design', 'management', 'communication', 'analytics', 'marketing', 'research']
            insights['skills_identified'] = [kw for kw in skill_keywords if kw in text_combined]
            
            # Extract passions
            passion_keywords = ['technology', 'education', 'healthcare', 'environment', 'social justice', 'entrepreneurship']
            insights['passion_areas'] = [kw for kw in passion_keywords if kw in text_combined]
            
            # Calculate confidence based on content richness
            insights['confidence_score'] = min(95, len(text_combined.split()) * 2)
        
        # Store insights in session for profile
        session['extracted_insights'] = insights
        
        return jsonify({
            'status': 'success',
            'insights': insights,
            'conversations_analyzed': len(all_conversations),
            'total_text_length': sum(len(conv) for conv in all_conversations)
        })
        
    except Exception as e:
        logger.error(f"Insight extraction error: {e}")
        return jsonify({'error': 'Failed to extract insights'}), 500

@app.route('/api/team/<team_id>/performance', methods=['GET'])
def get_team_performance(team_id):
    """Get team performance metrics"""
    days = request.args.get('days', 30, type=int)
    
    # Demo data for team performance
    demo_performance = {
        'team_id': team_id,
        'period_days': days,
        'metrics': {
            'productivity_score': 85.2,
            'collaboration_index': 78.5,
            'innovation_factor': 92.1,
            'satisfaction_rating': 4.3,
            'goal_completion': 87.8
        },
        'trends': {
            'productivity': '+5.2%',
            'collaboration': '+2.1%',
            'innovation': '-1.5%',
            'satisfaction': '+0.8%'
        },
        'timestamp': datetime.now().isoformat()
    }
    
    return jsonify(demo_performance)

@app.route('/api/team/actions', methods=['POST'])
def team_actions():
    """Handle team action requests"""
    data = request.get_json()
    action_type = data.get('action_type')
    
    # Demo response
    response = {
        'status': 'success',
        'action': action_type,
        'message': f'Team action {action_type} completed successfully',
        'timestamp': datetime.now().isoformat()
    }
    
    return jsonify(response)

@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'platform': 'Find Your Team - AWS Hackathon Demo',
        'demo_mode': aws_config.demo_mode if aws_config else True,
        'services': {
            'p2p_chat': p2p_chat is not None,
            'socketio': hasattr(app, 'socketio') or communication_manager is not None
        }
    })

if __name__ == '__main__':
    # Ensure required directories exist
    Path("audio").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)
    
    # Run the application with proper LAN configuration
    host = "0.0.0.0"  # Listen on all interfaces for LAN access
    port = int(os.getenv('PORT', 5002))  # Use standard port
    debug_mode = True
    
    # Configure for LAN broadcasting
    logger.info(f"Starting server on {host}:{port} for LAN access")
    logger.info("Server will be accessible from other devices on the network")

    socketio = getattr(app, 'socketio', None)
    if socketio is not None:
        # When using eventlet/async drivers, socketio.run will start the correct WSGI server
        # Disable the reloader to avoid double-starting in some environments
        socketio.run(app, host=host, port=port, debug=debug_mode, use_reloader=False)
    else:
        # Fallback for environments where SocketIO wasn't configured
        # Use Flask's development server (threading mode). In production use a proper
        # WSGI server and consider enabling eventlet/gevent if you need WebSocket support.
        app.run(host=host, port=port, debug=debug_mode)