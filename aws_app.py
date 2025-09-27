"""
Find Your Team - AWS-Powered Flask Application
Transformed from existing app.py to use AWS services for hackathon demo
"""

import os
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import boto3
from flask import Flask, request, jsonify, render_template, send_from_directory
from botocore.exceptions import ClientError
import requests
from dotenv import load_dotenv
from communication.flask_integration import setup_communication

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
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self.user_profiles_table = os.getenv('USER_PROFILES_TABLE', 'FindYourTeam-UserProfiles')
        self.team_performance_table = os.getenv('TEAM_PERFORMANCE_TABLE', 'FindYourTeam-TeamPerformance')
        self.opensearch_endpoint = os.getenv('OPENSEARCH_ENDPOINT', '')
        self.iot_endpoint = os.getenv('IOT_ENDPOINT', '')
        
        # Initialize AWS clients
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.bedrock = boto3.client('bedrock-runtime', region_name=self.region)
        self.iot_data = boto3.client('iot-data', region_name=self.region)
        self.lambda_client = boto3.client('lambda', region_name=self.region)
        
        # Get table references
        self.user_profiles_table_ref = self.dynamodb.Table(self.user_profiles_table)
        self.team_performance_table_ref = self.dynamodb.Table(self.team_performance_table)

class BedrockAgentService:
    """Service for interacting with Amazon Bedrock agents"""
    
    def __init__(self, aws_config: AWSConfig):
        self.aws_config = aws_config
        self.bedrock = aws_config.bedrock
        
    def invoke_onboarding_agent(self, user_input: str, session_id: str) -> Dict[str, Any]:
        """Invoke the Onboarding Agent using Bedrock"""
        try:
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
                modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
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
    
    def invoke_matching_agent(self, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the Matching Agent for team recommendations"""
        try:
            # Simulate matching logic for hackathon demo
            # In production, this would use OpenSearch vector search
            
            prompt = f"""You are the Matching Agent for Find Your Team. Based on this user profile, find the best team matches:

User Profile:
{json.dumps(user_profile, indent=2)}

Provide 3 team/opportunity matches with:
1. Alignment score (0-1)
2. Gap score (skills they need to develop)
3. Clear explanation of why it's a good match
4. How they can add value to people they love through this opportunity

Focus on opportunities that help poor communities and maximize human potential."""

            response = self.bedrock.invoke_model(
                modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
                body=json.dumps({
                    'anthropic_version': 'bedrock-2023-05-31',
                    'max_tokens': 1500,
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
            
            return {
                'matches': agent_response,
                'agent': 'matching',
                'user_id': user_profile.get('userId')
            }
            
        except Exception as e:
            logger.error(f"Error invoking matching agent: {str(e)}")
            return {
                'matches': "Unable to find matches at this time. Please try again later.",
                'agent': 'matching',
                'error': str(e)
            }
    
    def invoke_team_agent(self, team_id: str, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the Team Agent via Lambda function"""
        try:
            payload = {
                'action': action,
                'parameters': {
                    'team_id': team_id,
                    **parameters
                }
            }
            
            response = self.aws_config.lambda_client.invoke(
                FunctionName='FindYourTeam-TeamAgentTools',
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            result = json.loads(response['Payload'].read())
            return json.loads(result['body'])
            
        except Exception as e:
            logger.error(f"Error invoking team agent: {str(e)}")
            return {'error': str(e)}
    
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
            self.aws_config.user_profiles_table_ref.put_item(Item=user_profile)
            logger.info(f"Saved user profile for {user_profile.get('userId')}")
            return True
        except Exception as e:
            logger.error(f"Error saving user profile: {str(e)}")
            return False
    
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile from DynamoDB"""
        try:
            response = self.aws_config.user_profiles_table_ref.get_item(
                Key={'userId': user_id}
            )
            return response.get('Item')
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            return None
    
    def save_team_performance(self, team_performance: Dict[str, Any]) -> bool:
        """Save team performance data"""
        try:
            self.aws_config.team_performance_table_ref.put_item(Item=team_performance)
            logger.info(f"Saved team performance for {team_performance.get('teamId')}")
            return True
        except Exception as e:
            logger.error(f"Error saving team performance: {str(e)}")
            return False

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-key-change-in-production')

# Initialize services
aws_config = AWSConfig()
bedrock_service = BedrockAgentService(aws_config)
data_service = DataService(aws_config)

# Initialize communication system
communication_manager = setup_communication(app)

# Store conversation sessions in memory (use Redis in production)
conversation_sessions = {}

@app.route('/')
def index():
    """Main landing page"""
    return render_template('find_your_team.html')

@app.route('/api/onboard', methods=['POST'])
def onboard_user():
    """Handle onboarding conversation with the Onboarding Agent"""
    try:
        data = request.get_json()
        user_input = data.get('message', '')
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        if not user_input:
            return jsonify({'error': 'Message is required'}), 400
        
        # Invoke Onboarding Agent
        result = bedrock_service.invoke_onboarding_agent(user_input, session_id)
        
        # Store conversation history
        if session_id not in conversation_sessions:
            conversation_sessions[session_id] = {
                'messages': [],
                'user_profile': {},
                'confidence_score': 0
            }
        
        conversation_sessions[session_id]['messages'].append({
            'user': user_input,
            'agent': result['response'],
            'timestamp': datetime.now().isoformat(),
            'confidence_score': result['confidence_score']
        })
        
        conversation_sessions[session_id]['confidence_score'] = result['confidence_score']
        
        # If confidence is high enough, save profile and trigger matching
        if result['confidence_score'] >= 90:
            user_profile = {
                'userId': session_id,
                'purposeProfile': extract_purpose_profile(conversation_sessions[session_id]['messages']),
                'confidenceScore': result['confidence_score'],
                'createdAt': datetime.now().isoformat(),
                'status': 'ready_for_matching'
            }
            
            data_service.save_user_profile(user_profile)
            
            return jsonify({
                'response': result['response'],
                'confidence_score': result['confidence_score'],
                'session_id': session_id,
                'ready_for_matching': True,
                'user_profile': user_profile
            })
        
        return jsonify({
            'response': result['response'],
            'confidence_score': result['confidence_score'],
            'session_id': session_id,
            'ready_for_matching': False
        })
        
    except Exception as e:
        logger.error(f"Error in onboarding: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/match', methods=['POST'])
def find_matches():
    """Find team matches using the Matching Agent"""
    try:
        data = request.get_json()
        user_id = data.get('user_id') or data.get('session_id')
        
        if not user_id:
            return jsonify({'error': 'User ID is required'}), 400
        
        # Get user profile
        user_profile = data_service.get_user_profile(user_id)
        if not user_profile:
            return jsonify({'error': 'User profile not found'}), 404
        
        # Invoke Matching Agent
        result = bedrock_service.invoke_matching_agent(user_profile)
        
        return jsonify({
            'matches': result['matches'],
            'user_id': user_id,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error finding matches: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/team/<team_id>/status', methods=['GET'])
def get_team_status(team_id):
    """Get team status using Team Agent"""
    try:
        result = bedrock_service.invoke_team_agent(
            team_id=team_id,
            action='check_project_status',
            parameters={}
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting team status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/team/<team_id>/retrospective', methods=['POST'])
def generate_team_retrospective(team_id):
    """Generate team retrospective using Team Agent"""
    try:
        data = request.get_json()
        period = data.get('period', '30')
        
        result = bedrock_service.invoke_team_agent(
            team_id=team_id,
            action='generate_retrospective',
            parameters={'period': period}
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error generating retrospective: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/team/<team_id>/performance', methods=['POST'])
def update_team_performance(team_id):
    """Update team performance metrics using Team Agent"""
    try:
        data = request.get_json()
        metrics = data.get('metrics', {})
        
        result = bedrock_service.invoke_team_agent(
            team_id=team_id,
            action='update_performance_metrics',
            parameters={
                'metrics': metrics,
                'members': data.get('members', []),
                'agent_insights': data.get('agent_insights', []),
                'improvement_suggestions': data.get('improvement_suggestions', [])
            }
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error updating team performance: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/<user_id>/coaching', methods=['POST'])
def get_coaching_insight(user_id):
    """Get personalized coaching insight using Team Agent"""
    try:
        data = request.get_json()
        context = data.get('context', {})
        
        result = bedrock_service.invoke_team_agent(
            team_id='',  # Not needed for coaching
            action='provide_coaching_insight',
            parameters={
                'user_id': user_id,
                'context': context
            }
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting coaching insight: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'platform': 'Find Your Team - AWS Hackathon Demo'
    })

def extract_purpose_profile(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract purpose profile from conversation messages"""
    # Simple extraction for demo - in production, use NLP
    profile = {
        'values': {'core': [], 'secondary': [], 'weights': {}},
        'workStyle': {
            'collaboration': 'medium',
            'autonomy': 'medium',
            'structure': 'moderate',
            'communication': 'diplomatic'
        },
        'skills': {'technical': [], 'soft': [], 'leadership': []},
        'passions': []
    }
    
    # Analyze conversation content
    all_text = ' '.join([msg.get('user', '') + ' ' + msg.get('agent', '') for msg in messages])
    
    # Simple keyword extraction (enhance with NLP in production)
    if 'help' in all_text.lower() or 'community' in all_text.lower():
        profile['values']['core'].append('Community Service')
        profile['passions'].append('Helping Others')
    
    if 'technology' in all_text.lower() or 'coding' in all_text.lower():
        profile['skills']['technical'].append({'name': 'Technology', 'level': 'intermediate'})
        profile['passions'].append('Technology')
    
    if 'leadership' in all_text.lower() or 'manage' in all_text.lower():
        profile['skills']['leadership'].append({'name': 'Leadership', 'level': 'intermediate'})
    
    return profile

if __name__ == '__main__':
    # Ensure required directories exist
    Path("audio").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)
    
    # Run the application
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )