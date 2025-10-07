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
import hashlib
from datetime import datetime, timedelta
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
import configparser

import boto3
from flask import Flask, request, jsonify, render_template, send_from_directory
from botocore.exceptions import ClientError
import requests
from dotenv import load_dotenv

from communication.flask_integration import setup_communication
from agents.onboarding_agent import OnboardingAgent
from agents.team_agent import TeamAgent
from agents.agent_core import BedrockAgentCore, AgentType
from gamification.engine import GamificationEngine

# Import team agent tools (commented out for now to avoid import issues)
# from lambda.team_agent.team_agent_tools import (
#     check_project_status, generate_retrospective, 
#     update_performance_metrics, provide_coaching_insight
# )

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

# Import resilience modules after logger is defined
try:
    from resilience.error_handling import (
        resilience_manager, resilient_operation, resilient_context,
        ErrorCategory, ErrorSeverity, start_resilience_monitoring
    )
    from resilience.network_resilience import (
        network_resilience, resilient_http_request, get_network_health
    )
    from resilience.agent_resilience import (
        agent_resilience, resilient_agent_call, get_agent_health, AgentType as ResAgentType
    )
    from resilience.data_sync_resilience import (
        data_sync_resilience, resilient_save_data, resilient_load_data,
        get_sync_status, DataOperation
    )
    RESILIENCE_AVAILABLE = True
    logger.info("Resilience modules loaded successfully")
except ImportError as e:
    logger.warning(f"Resilience modules not available: {e}")
    RESILIENCE_AVAILABLE = False

# Import security modules for Task 12 - Privacy and Security Controls
try:
    from security import (
        security_controller, privacy_manager, consent_manager, anonymous_manager,
        audit_trail, DataType, ConsentType, PrivacyLevel, AuditAction
    )
    SECURITY_AVAILABLE = True
    logger.info("Security modules loaded successfully")
except ImportError as e:
    logger.warning(f"Security modules not available: {e}")
    SECURITY_AVAILABLE = False

class AWSConfig:
    """AWS Configuration Manager"""
    
    def __init__(self):
        # Load config from config.ini
        self.config = configparser.ConfigParser()
        config_file = Path('config.ini')
        
        if config_file.exists():
            self.config.read(config_file)
        
        # AWS settings
        self.region = self._get_config_value('AWS', 'aws_region', 'us-east-1')
        self.access_key = self._get_config_value('AWS', 'aws_access_key_id')
        self.secret_key = self._get_config_value('AWS', 'aws_secret_access_key')
        
        # Table names
        self.user_profiles_table = self._get_config_value('AWS', 'dynamodb_table_users', 'find-your-team-users')
        self.team_performance_table = self._get_config_value('AWS', 'dynamodb_table_teams', 'find-your-team-teams')
        self.integrations_table = self._get_config_value('AWS', 'dynamodb_table_integrations', 'find-your-team-integrations')
        
        # Bedrock settings
        self.bedrock_model_id = self._get_config_value('AWS', 'bedrock_model_id', 'anthropic.claude-3-5-sonnet-20240620-v1:0')
        self.bedrock_region = self._get_config_value('AWS', 'bedrock_region', 'us-east-1')
        
        # OpenSearch settings
        self.opensearch_domain = self._get_config_value('AWS', 'opensearch_domain_name', 'find-your-team-search')
        self.opensearch_region = self._get_config_value('AWS', 'opensearch_region', 'us-east-1')
        
        # IoT settings
        self.iot_endpoint = self._get_config_value('AWS', 'iot_endpoint')
        self.iot_topic_prefix = self._get_config_value('AWS', 'iot_topic_prefix', 'find-your-team/')
        
        # App settings
        self.debug = self._get_config_value('APP', 'debug', 'false').lower() == 'true'
        self.host = self._get_config_value('APP', 'host', '0.0.0.0')
        self.port = int(self._get_config_value('APP', 'port', '5000'))
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
            # Do not return early — continue to set client attributes to None
            # so the rest of the application can run in demo/local mode
            # without AttributeError when accessing aws_config.bedrock, etc.
        
        # Initialize AWS clients (skip in demo mode)
        if not self.demo_mode:
            # Create boto3 session
            self.session = boto3.Session(
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            
            self.dynamodb = self.session.resource('dynamodb', region_name=self.region)
            self.bedrock = self.session.client('bedrock-runtime', region_name=self.bedrock_region)
            self.iot_data = None
            # Only initialize IoT client if endpoint is properly configured
            iot_endpoint = self._get_config_value('AWS', 'iot_endpoint')
            if iot_endpoint and not iot_endpoint.startswith('YOUR_'):
                self.iot_data = self.session.client(
                    'iot-data',
                    region_name=self.region,
                    endpoint_url=f"https://{iot_endpoint}"
                )
            self.lambda_client = self.session.client('lambda', region_name=self.region)
            
            # Get table references
            self.user_profiles_table_ref = self.dynamodb.Table(self.user_profiles_table)
            self.team_performance_table_ref = self.dynamodb.Table(self.team_performance_table)
            self.integrations_table_ref = self.dynamodb.Table(self.integrations_table)
        else:
            # Demo mode - set clients to None
            self.session = None
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
    """Service for interacting with Amazon Bedrock agents via AgentCore orchestration"""
    
    def __init__(self, aws_config: AWSConfig):
        self.aws_config = aws_config
        self.bedrock = aws_config.bedrock
        self.agent_core = None  # Will be set after initialization
        
    async def invoke_onboarding_agent(self, user_input: str, session_id: str, user_id: str = None) -> Dict[str, Any]:
        """Invoke the Onboarding Agent using AgentCore orchestration"""
        try:
            if not self.agent_core:
                raise ValueError("AgentCore not initialized")
            
            # Start or continue workflow
            if session_id not in self.agent_core.active_workflows:
                context = await self.agent_core.start_workflow(user_input, user_id or "anonymous", session_id)
            else:
                context = self.agent_core.active_workflows[session_id]
            
            # Invoke onboarding agent through AgentCore
            input_data = {'user_input': user_input}
            result = await self.agent_core.invoke_agent(AgentType.ONBOARDING, context, input_data)
            
            # Check for handoff
            if 'handoff' in result:
                handoff = result['handoff']
                logger.info(f"Handoff triggered: {handoff}")
                
                # Execute handoff to next agent
                if handoff['to_agent'] == AgentType.MATCHING.value:
                    handoff_result = await self.agent_core.execute_handoff(
                        context, 
                        AgentType.ONBOARDING,
                        AgentType.MATCHING,
                        {'confidence_threshold_met': True, 'user_profile': context.user_profile}
                    )
                    result['next_step'] = handoff_result
            
            return result
            
        except Exception as e:
            logger.error(f"Error invoking onboarding agent: {str(e)}")
            # Fallback to direct Bedrock call
            return await self._fallback_onboarding_agent(user_input, session_id)
    
    async def _fallback_onboarding_agent(self, user_input: str, session_id: str) -> Dict[str, Any]:
        """Fallback onboarding agent implementation"""
        try:
            prompt = f"""You are the Onboarding Agent for Find Your Team. Respond to: {user_input}
            
Please ask insightful questions to understand their purpose and provide a confidence score (0-100)."""

            response = self.bedrock.invoke_model(
                modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
                body=json.dumps({
                    'anthropic_version': 'bedrock-2023-05-31',
                    'max_tokens': 1000,
                    'messages': [{'role': 'user', 'content': prompt}]
                })
            )
            
            response_body = json.loads(response['body'].read())
            agent_response = response_body['content'][0]['text']
            
            return {
                'response': agent_response,
                'confidence_score': self._extract_confidence_score(agent_response),
                'session_id': session_id,
                'agent': 'onboarding'
            }
            
        except Exception as e:
            logger.error(f"Fallback onboarding agent error: {str(e)}")
            return {
                'response': "I'm having trouble processing your request right now. Let's try again.",
                'confidence_score': 0,
                'session_id': session_id,
                'agent': 'onboarding',
                'error': str(e)
            }
    
    async def invoke_matching_agent(self, user_profile: Dict[str, Any], session_id: str = None) -> Dict[str, Any]:
        """Invoke the Matching Agent using AgentCore orchestration"""
        try:
            if not self.agent_core:
                raise ValueError("AgentCore not initialized")
            
            # Find existing workflow or create new one
            workflow_id = None
            context = None
            
            if session_id:
                for wf_id, wf_context in self.agent_core.active_workflows.items():
                    if wf_context.session_id == session_id:
                        workflow_id = wf_id
                        context = wf_context
                        break
            
            if not context:
                context = await self.agent_core.start_workflow(
                    "Find team matches", 
                    user_profile.get('userId', 'anonymous'),
                    session_id
                )
                context.user_profile = user_profile
            
            # Invoke matching agent through AgentCore
            input_data = {'user_profile': user_profile}
            result = await self.agent_core.invoke_agent(AgentType.MATCHING, context, input_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error invoking matching agent: {str(e)}")
            # Fallback to direct Bedrock call
            return await self._fallback_matching_agent(user_profile)
    
    async def _fallback_matching_agent(self, user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback matching agent implementation"""
        try:
            prompt = f"""You are the Matching Agent. Find team matches for:
{json.dumps(user_profile, indent=2)}

Provide 3 opportunities focused on helping poor communities."""

            response = self.bedrock.invoke_model(
                modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
                body=json.dumps({
                    'anthropic_version': 'bedrock-2023-05-31',
                    'max_tokens': 1500,
                    'messages': [{'role': 'user', 'content': prompt}]
                })
            )
            
            response_body = json.loads(response['body'].read())
            agent_response = response_body['content'][0]['text']
            
            return {
                'matches': agent_response,
                'agent': 'matching',
                'confidence_score': 0.8,
                'user_id': user_profile.get('userId')
            }
            
        except Exception as e:
            logger.error(f"Fallback matching agent error: {str(e)}")
            return {
                'matches': "Unable to find matches at this time. Please try again later.",
                'agent': 'matching',
                'error': str(e)
            }
    
    async def invoke_team_agent(self, team_id: str, action: str, parameters: Dict[str, Any], session_id: str = None) -> Dict[str, Any]:
        """Invoke the Team Agent using AgentCore orchestration"""
        try:
            if not self.agent_core:
                raise ValueError("AgentCore not initialized")
            
            # Find or create workflow context
            context = None
            if session_id:
                for wf_context in self.agent_core.active_workflows.values():
                    if wf_context.session_id == session_id:
                        context = wf_context
                        break
            
            if not context:
                context = await self.agent_core.start_workflow(
                    f"Team action: {action}", 
                    parameters.get('user_id', 'system'),
                    session_id
                )
            
            # Invoke team agent through AgentCore
            input_data = {
                'team_id': team_id,
                'action': action,
                'parameters': parameters
            }
            
            result = await self.agent_core.invoke_agent(AgentType.TEAM, context, input_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error invoking team agent: {str(e)}")
            # Fallback to Lambda or demo mode
            return await self._fallback_team_agent(team_id, action, parameters)
    
    async def _fallback_team_agent(self, team_id: str, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback team agent implementation"""
        try:
            # Try Lambda first
            payload = {
                'action': action,
                'parameters': {'team_id': team_id, **parameters}
            }
            
            response = self.aws_config.lambda_client.invoke(
                FunctionName='FindYourTeam-TeamAgentTools',
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            result = json.loads(response['Payload'].read())
            return json.loads(result['body'])
            
        except Exception as lambda_error:
            logger.warning(f"Lambda fallback failed: {lambda_error}")
            
            # Demo mode fallback
            if action == 'analyze_performance':
                return {
                    'team_health': 0.85,
                    'performance_metrics': {
                        'productivity': 0.78,
                        'collaboration': 0.82,
                        'satisfaction': 0.89
                    },
                    'agent': 'team',
                    'confidence_score': 0.75,
                    'mode': 'demo'
                }
            
            return {
                'result': f"Team action '{action}' simulated in demo mode",
                'agent': 'team',
                'confidence_score': 0.7,
                'mode': 'demo'
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

# Initialize AgentCore orchestration system
agent_core = BedrockAgentCore(aws_config)

# Link AgentCore to BedrockAgentService
bedrock_service.agent_core = agent_core

# Initialize Gamification Engine
gamification_engine = GamificationEngine(aws_config)

# Initialize resilience systems
if RESILIENCE_AVAILABLE:
    try:
        start_resilience_monitoring()
        logger.info("Resilience monitoring started")
    except Exception as e:
        logger.warning(f"Could not start resilience monitoring: {e}")
else:
    logger.warning("Resilience systems not available - running without resilience features")

# Initialize security systems
if SECURITY_AVAILABLE:
    try:
        # Security system is auto-initialized via imports
        logger.info("Security and privacy controls initialized")
    except Exception as e:
        logger.warning(f"Could not initialize security systems: {e}")
else:
    logger.warning("Security systems not available - running without privacy and security features")

# Initialize Team Agent (if not in demo mode)
team_agent_service = None
if not aws_config.demo_mode:
    try:
        from config import Config
        team_config = Config()
        team_agent_service = TeamAgent(team_config)
    except Exception as e:
        logger.warning(f"Could not initialize Team Agent: {e}")

# Team Agent Lambda-like functions for demo
def check_project_status(parameters):
    """Simulate project status check"""
    team_id = parameters.get('team_id', 'demo-team')
    return {
        'statusCode': 200,
        'body': json.dumps({
            'team_id': team_id,
            'status': 'Active',
            'current_metrics': {
                'productivity': 0.85,
                'collaboration': 0.78,
                'communication': 0.82,
                'engagement': 0.88
            },
            'trends': {
                'productivity': 'improving',
                'collaboration': 'stable'
            },
            'last_updated': datetime.now().isoformat()
        })
    }

def generate_retrospective(parameters):
    """Simulate retrospective generation"""
    team_id = parameters.get('team_id', 'demo-team')
    return {
        'statusCode': 200,
        'body': json.dumps({
            'team_id': team_id,
            'successes': [
                'Successfully delivered three major features ahead of schedule',
                'Improved team communication through daily check-ins',
                'Achieved 95% code coverage on recent projects'
            ],
            'challenges': [
                'Meeting efficiency could be improved - some run over time',
                'Knowledge sharing between team members needs enhancement'
            ],
            'action_items': [
                'Implement timeboxing for all meetings starting next week',
                'Set up weekly knowledge sharing sessions',
                'Create code review guidelines and SLA'
            ],
            'generated_at': datetime.now().isoformat()
        })
    }

def update_performance_metrics(parameters):
    """Simulate performance metrics update"""
    team_id = parameters.get('team_id', 'demo-team')
    metrics = parameters.get('metrics', {})
    return {
        'statusCode': 200,
        'body': json.dumps({
            'team_id': team_id,
            'updated_metrics': metrics,
            'success': True,
            'timestamp': datetime.now().isoformat()
        })
    }

def provide_coaching_insight(parameters):
    """Simulate coaching insight generation"""
    team_id = parameters.get('team_id', 'demo-team')
    focus_area = parameters.get('focus_area', 'team_dynamics')
    
    insights = {
        'team_dynamics': {
            'title': 'Enhance Team Communication Flow',
            'insight': 'Your team demonstrates excellent technical skills and collaboration. However, there is an opportunity to improve information flow between team members, particularly during handoffs and knowledge transfer.',
            'priority': 'medium',
            'recommendations': [
                'Implement structured handoff documentation templates',
                'Schedule bi-weekly knowledge sharing sessions',
                'Create a team wiki for important project information'
            ]
        },
        'productivity': {
            'title': 'Optimize Sprint Planning Process',
            'insight': 'The team shows strong execution capabilities but could benefit from more accurate story estimation and sprint commitment.',
            'priority': 'high',
            'recommendations': [
                'Conduct story estimation workshops',
                'Track velocity trends over multiple sprints',
                'Implement capacity planning tools'
            ]
        }
    }
    
    selected_insight = insights.get(focus_area, insights['team_dynamics'])
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'team_id': team_id,
            'focus_area': focus_area,
            **selected_insight,
            'generated_at': datetime.now().isoformat()
        })
    }

@app.route('/api/profile/<conversation_id>', methods=['GET'])
def get_user_profile(conversation_id: str):
    """Get the generated user profile from a conversation"""
    try:
        if aws_config.demo_mode:
            # Return demo profile
            return jsonify({
                'profile': {
                    'userId': conversation_id.split('_')[1] if '_' in conversation_id else 'demo_user',
                    'confidenceScore': 85,
                    'status': 'ready_for_matching',
                    'purposeProfile': {
                        'values': {
                            'core': ['Impact', 'Collaboration', 'Growth'],
                            'secondary': ['Innovation', 'Sustainability']
                        },
                        'passions': ['Community Development', 'Technology for Good'],
                        'skills': {
                            'technical': ['Python', 'Web Development'],
                            'soft': ['Communication', 'Problem Solving'],
                            'leadership': ['Team Building']
                        }
                    }
                },
                'demo_mode': True
            })
        
        onboarding_agent = OnboardingAgent(bedrock_client=aws_config.bedrock)
        user_profile = onboarding_agent.get_purpose_profile(conversation_id)
        
        if user_profile:
            return jsonify({
                'profile': user_profile.model_dump(by_alias=True),
                'success': True
            })
        else:
            return jsonify({
                'error': 'Profile not ready or conversation not found',
                'profile_complete': False
            }), 404
            
    except Exception as e:
        logger.error(f"Error getting profile for conversation {conversation_id}: {str(e)}")
        return jsonify({'error': 'Failed to retrieve profile'}), 500

@app.route('/api/team/<team_id>/performance', methods=['GET'])
def get_team_performance(team_id: str):
    """Get team performance analytics and insights"""
    try:
        days_back = int(request.args.get('days', 30))
        
        if aws_config.demo_mode or not team_agent_service:
            # Return demo performance data
            return jsonify({
                'team_id': team_id,
                'overall_score': 0.82,
                'metrics': {
                    'productivity': 0.85,
                    'collaboration': 0.78,
                    'communication': 0.80,
                    'engagement': 0.88,
                    'quality': 0.83
                },
                'insights': [
                    {
                        'category': 'communication',
                        'priority': 'medium',
                        'title': 'Improve Daily Standup Efficiency',
                        'description': 'Daily standups are running 20% longer than optimal',
                        'recommendations': ['Use timeboxing', 'Focus on blockers', 'Async updates for details']
                    }
                ],
                'recommendations': ['Schedule regular team retrospectives', 'Implement pair programming sessions'],
                'demo_mode': True
            })
        
        # Use actual Team Agent in production
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            report = loop.run_until_complete(
                team_agent_service.analyze_team_performance(team_id, days_back)
            )
            return jsonify({
                'team_id': report.team_id,
                'overall_score': report.overall_score,
                'metrics': report.metrics,
                'insights': [{
                    'category': insight.category.value,
                    'priority': insight.priority,
                    'title': insight.title,
                    'description': insight.description,
                    'recommendations': insight.recommendations
                } for insight in report.insights],
                'recommendations': report.recommendations,
                'period_start': report.period_start.isoformat(),
                'period_end': report.period_end.isoformat()
            })
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error getting team performance for {team_id}: {str(e)}")
        return jsonify({'error': 'Failed to get team performance'}), 500

@app.route('/api/team/<team_id>/health', methods=['GET'])
def get_team_health(team_id: str):
    """Get real-time team health monitoring"""
    try:
        if aws_config.demo_mode or not team_agent_service:
            # Return demo health data
            return jsonify({
                'team_id': team_id,
                'health_score': 0.79,
                'indicators': {
                    'overall_health': 0.79,
                    'communication_health': 0.82,
                    'productivity_health': 0.75,
                    'morale_health': 0.88,
                    'workload_balance': 0.71
                },
                'alerts': [
                    {'type': 'warning', 'message': 'Workload imbalance detected - consider redistributing tasks'}
                ],
                'demo_mode': True
            })
        
        # Use actual Team Agent in production
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            health_data = loop.run_until_complete(
                team_agent_service.monitor_team_health(team_id)
            )
            return jsonify(health_data)
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error getting team health for {team_id}: {str(e)}")
        return jsonify({'error': 'Failed to get team health'}), 500

@app.route('/api/team/<team_id>/coaching', methods=['POST'])
def generate_coaching_session(team_id: str):
    """Generate personalized coaching session for a team"""
    try:
        data = request.get_json() or {}
        focus_areas = data.get('focus_areas', [])
        
        if aws_config.demo_mode or not team_agent_service:
            # Return demo coaching session
            return jsonify({
                'team_id': team_id,
                'session_title': 'Team Communication & Collaboration Workshop',
                'objectives': [
                    'Improve daily standup efficiency',
                    'Enhance cross-functional collaboration',
                    'Strengthen feedback culture'
                ],
                'activities': [
                    {
                        'name': 'Communication Styles Assessment',
                        'duration': 15,
                        'description': 'Identify individual communication preferences'
                    },
                    {
                        'name': 'Feedback Circle',
                        'duration': 20,
                        'description': 'Practice giving and receiving constructive feedback'
                    }
                ],
                'discussion_points': [
                    'What are our current communication challenges?',
                    'How can we make meetings more effective?',
                    'What tools or processes could help us collaborate better?'
                ],
                'materials_needed': ['Whiteboard', 'Sticky notes', 'Timer'],
                'duration_minutes': 90,
                'demo_mode': True
            })
        
        # Use actual Team Agent in production
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            coaching_session = loop.run_until_complete(
                team_agent_service.provide_coaching_session(team_id, focus_areas)
            )
            return jsonify(coaching_session)
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Error generating coaching session for {team_id}: {str(e)}")
        return jsonify({'error': 'Failed to generate coaching session'}), 500

@app.route('/api/team/actions', methods=['POST'])
def handle_team_actions():
    """Handle team management actions via Lambda tools"""
    try:
        data = request.get_json()
        action = data.get('action')
        parameters = data.get('parameters', {})
        
        if not action:
            return jsonify({'error': 'Action is required'}), 400
        
        # Route to appropriate Lambda function simulation
        if action == 'check_project_status':
            result = check_project_status(parameters)
        elif action == 'generate_retrospective':
            result = generate_retrospective(parameters)
        elif action == 'update_performance_metrics':
            result = update_performance_metrics(parameters)
        elif action == 'provide_coaching_insight':
            result = provide_coaching_insight(parameters)
        else:
            return jsonify({'error': f'Unknown action: {action}'}), 400
        
        # Return the result from the Lambda function
        if result.get('statusCode') == 200:
            return jsonify(json.loads(result['body']))
        else:
            return jsonify(json.loads(result['body'])), result.get('statusCode', 500)
            
    except Exception as e:
        logger.error(f"Error handling team action: {str(e)}")
        return jsonify({'error': 'Failed to handle team action'}), 500

# Initialize communication system
communication_manager = setup_communication(app)

# Store conversation sessions in memory (use Redis in production)
conversation_sessions = {}

@app.route('/')
def index():
    """Main landing page or dashboard based on auth status"""
    # In a real app, you'd check for valid session/token
    # For demo, we'll check if there's user data in the request
    return render_template('find_your_team.html')

@app.route('/agent-core-dashboard')
def agent_core_dashboard():
    """Serve the AgentCore orchestration dashboard"""
    return send_from_directory('static', 'agent_core_dashboard.html')

@app.route('/gamification-dashboard')
def gamification_dashboard():
    """Serve the Gamification dashboard"""
    return send_from_directory('static', 'gamification_dashboard.html')

# ===== RESILIENCE AND ERROR HANDLING ENDPOINTS =====

@app.route('/api/resilience/health', methods=['GET'])
def get_system_health():
    """Get comprehensive system health status"""
    if not RESILIENCE_AVAILABLE:
        return jsonify({
            'error': 'Resilience system not available',
            'health': 'degraded'
        }), 503
    
    try:
        health_status = {
            'system': resilience_manager.get_system_health(),
            'network': get_network_health(),
            'agents': get_agent_health(),
            'timestamp': datetime.utcnow().isoformat()
        }
        return jsonify(health_status)
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/resilience/sync-status/<user_id>', methods=['GET'])
def get_user_sync_status(user_id):
    """Get data synchronization status for a user"""
    if not RESILIENCE_AVAILABLE:
        return jsonify({
            'error': 'Resilience system not available',
            'sync_status': 'unknown'
        }), 503
    
    try:
        sync_status = get_sync_status(user_id)
        return jsonify(sync_status)
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/resilience/resolve-conflict', methods=['POST'])
def resolve_sync_conflict():
    """Handle user's conflict resolution choice"""
    if not RESILIENCE_AVAILABLE:
        return jsonify({
            'error': 'Resilience system not available'
        }), 503
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        notification_id = data.get('notification_id')
        resolution_choice = data.get('resolution_choice')
        
        if not all([user_id, notification_id, resolution_choice]):
            return jsonify({
                'error': 'Missing required parameters'
            }), 400
        
        # Use asyncio to handle the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                data_sync_resilience.resolve_user_conflict(
                    user_id, notification_id, resolution_choice
                )
            )
        finally:
            loop.close()
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error resolving sync conflict: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/resilience/network-status', methods=['GET'])
def get_network_status():
    """Get current network connectivity status"""
    if not RESILIENCE_AVAILABLE:
        return jsonify({
            'error': 'Resilience system not available'
        }), 503
    
    try:
        network_status = get_network_health()
        return jsonify(network_status)
    except Exception as e:
        logger.error(f"Error getting network status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/resilience/error-history', methods=['GET'])
def get_error_history():
    """Get recent error history for monitoring"""
    if not RESILIENCE_AVAILABLE:
        return jsonify({
            'error': 'Resilience system not available'
        }), 503
    
    try:
        limit = request.args.get('limit', 50, type=int)
        hours = request.args.get('hours', 24, type=int)
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_errors = [
            error.to_dict() for error in resilience_manager.error_history
            if error.timestamp > cutoff_time
        ][-limit:]
        
        return jsonify({
            'errors': recent_errors,
            'total_count': len(recent_errors),
            'time_range_hours': hours
        })
    except Exception as e:
        logger.error(f"Error getting error history: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/resilience/test-resilience', methods=['POST'])
def test_resilience():
    """Test resilience features (for development/testing)"""
    if not RESILIENCE_AVAILABLE:
        return jsonify({
            'error': 'Resilience system not available'
        }), 503
    
    try:
        test_type = request.json.get('test_type', 'network')
        
        if test_type == 'network':
            # Test network resilience
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    resilient_http_request(
                        method='GET',
                        url='https://httpbin.org/get',
                        timeout=5
                    )
                )
            finally:
                loop.close()
            
            return jsonify({
                'test_type': 'network',
                'result': result,
                'status': 'success'
            })
            
        elif test_type == 'agent':
            # Test agent resilience
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    resilient_agent_call(
                        agent_type=ResAgentType.ONBOARDING,
                        action='health_check',
                        parameters={},
                        user_id='test_user'
                    )
                )
            finally:
                loop.close()
            
            return jsonify({
                'test_type': 'agent',
                'result': result,
                'status': 'success'
            })
            
        else:
            return jsonify({
                'error': f'Unknown test type: {test_type}'
            }), 400
            
    except Exception as e:
        logger.error(f"Resilience test failed: {e}")
        return jsonify({
            'error': str(e),
            'status': 'failed'
        }), 500

# === Task 12 Security API Endpoints ===

@app.route('/api/security/privacy-settings/<user_id>', methods=['GET', 'POST'])
def manage_privacy_settings(user_id):
    """Manage user privacy settings"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        if request.method == 'GET':
            # Get current privacy settings
            dashboard = security_controller.get_privacy_dashboard(user_id)
            return jsonify(dashboard)
        
        elif request.method == 'POST':
            # Update privacy settings
            data = request.get_json()
            settings_data = data.get('settings', {})
            
            # Convert string keys back to DataType enums
            settings = {}
            for data_type_str, setting_data in settings_data.items():
                try:
                    data_type = DataType(data_type_str)
                    settings[data_type] = setting_data
                except ValueError:
                    continue
            
            result = security_controller.update_privacy_settings(
                user_id=user_id,
                settings=settings,
                ip_address=request.remote_addr
            )
            
            return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error managing privacy settings: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/security/consent/<user_id>', methods=['GET', 'POST', 'DELETE'])
def manage_consent(user_id):
    """Manage user consent for data processing"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        if request.method == 'GET':
            # Get consent summary
            consent_summary = consent_manager.get_consent_summary(user_id)
            return jsonify(consent_summary)
        
        elif request.method == 'POST':
            # Grant consent
            data = request.get_json()
            consent_type = ConsentType(data.get('consent_type'))
            purpose = data.get('purpose', '')
            data_types = [DataType(dt) for dt in data.get('data_types', [])]
            expires_in_days = data.get('expires_in_days')
            
            result = security_controller.grant_user_consent(
                user_id=user_id,
                consent_type=consent_type,
                purpose=purpose,
                data_types=data_types,
                expires_in_days=expires_in_days,
                ip_address=request.remote_addr
            )
            
            return jsonify(result)
        
        elif request.method == 'DELETE':
            # Withdraw consent
            data = request.get_json()
            consent_type = ConsentType(data.get('consent_type'))
            
            result = security_controller.withdraw_user_consent(
                user_id=user_id,
                consent_type=consent_type,
                ip_address=request.remote_addr
            )
            
            return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error managing consent: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/security/anonymous/create', methods=['POST'])
def create_anonymous_session():
    """Create anonymous session"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        data = request.get_json() or {}
        user_data = data.get('user_data')
        
        result = security_controller.create_anonymous_session(
            user_data=user_data,
            ip_address=request.remote_addr
        )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error creating anonymous session: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/security/anonymous/<anonymous_id>/operate', methods=['POST'])
def perform_anonymous_operation(anonymous_id):
    """Perform operation in anonymous mode"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        data = request.get_json()
        operation_type = data.get('operation_type')
        operation_data = data.get('operation_data', {})
        
        result = security_controller.perform_anonymous_operation(
            anonymous_id=anonymous_id,
            operation_type=operation_type,
            operation_data=operation_data,
            ip_address=request.remote_addr
        )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error performing anonymous operation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/security/anonymous/<anonymous_id>/convert', methods=['POST'])
def convert_anonymous_to_user(anonymous_id):
    """Convert anonymous session to registered user"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'user_id required'}), 400
        
        result = anonymous_manager.convert_to_registered_user(anonymous_id, user_id)
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error converting anonymous session: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/security/audit/<user_id>', methods=['GET'])
def get_user_audit_trail(user_id):
    """Get user audit trail"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        # Parse query parameters
        limit = request.args.get('limit', 50, type=int)
        hours = request.args.get('hours', 24 * 7, type=int)  # Default: 1 week
        action_filter = request.args.getlist('actions')
        
        start_date = datetime.utcnow() - timedelta(hours=hours)
        
        # Convert action filter to enum
        actions = []
        for action_str in action_filter:
            try:
                actions.append(AuditAction(action_str))
            except ValueError:
                pass
        
        audit_records = audit_trail.get_user_audit_trail(
            user_id=user_id,
            start_date=start_date,
            action_filter=actions if actions else None,
            limit=limit
        )
        
        return jsonify({
            'audit_trail': audit_records,
            'total_records': len(audit_records),
            'time_range_hours': hours,
            'filters': action_filter
        })
    
    except Exception as e:
        logger.error(f"Error getting audit trail: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/security/export/<user_id>', methods=['POST'])
def export_user_data(user_id):
    """Export user data with proper consent validation"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        data = request.get_json() or {}
        data_types = []
        
        # Parse requested data types
        for dt_str in data.get('data_types', []):
            try:
                data_types.append(DataType(dt_str))
            except ValueError:
                pass
        
        result = security_controller.export_user_data(
            user_id=user_id,
            data_types=data_types if data_types else None,
            ip_address=request.remote_addr
        )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error exporting user data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/security/status', methods=['GET'])
def get_security_status():
    """Get comprehensive security status"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        user_id = request.args.get('user_id')
        status = security_controller.get_security_status(user_id)
        return jsonify(status)
    
    except Exception as e:
        logger.error(f"Error getting security status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/security/compliance-report', methods=['GET'])
def generate_compliance_report():
    """Generate compliance report for audit purposes"""
    if not SECURITY_AVAILABLE:
        return jsonify({'error': 'Security features not available'}), 503
    
    try:
        # Parse query parameters
        days = request.args.get('days', 30, type=int)
        include_details = request.args.get('include_details', 'false').lower() == 'true'
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        report = audit_trail.generate_compliance_report(
            start_date=start_date,
            end_date=end_date,
            include_details=include_details
        )
        
        return jsonify(report)
    
    except Exception as e:
        logger.error(f"Error generating compliance report: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/dashboard')
def dashboard():
    """Authenticated user dashboard"""
    return render_template('dashboard.html')

@app.route('/lan-chat')
def lan_chat():
    """LAN Chat interface for low bandwidth and offline scenarios"""
    return render_template('lan_chat.html')

@app.route('/login')
def login():
    """Login page"""
    return render_template('login.html')

@app.route('/signup') 
def signup():
    """Signup page"""
    return render_template('signup.html')

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
    """Handle chat messages from the frontend using AgentCore orchestration"""
    import asyncio
    
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        user_id = data.get('user_id', f'user_{uuid.uuid4().hex[:8]}')
        conversation_id = data.get('conversation_id')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Generate conversation ID if not provided
        if not conversation_id:
            conversation_id = f'conv_{user_id}_{int(datetime.now().timestamp())}'
        
        # Check if we're in demo mode
        if aws_config.demo_mode:
            # Use simulated responses for demo mode
            return handle_demo_chat(message, user_id, conversation_id)
        
        # Use AgentCore orchestration for production mode
        try:
            # Run async function in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(
                bedrock_service.invoke_onboarding_agent(message, conversation_id, user_id)
            )
            
            loop.close()
            
            # Convert confidence score to percentage
            confidence_score = result.get('confidence_score', 0)
            if isinstance(confidence_score, float) and confidence_score <= 1.0:
                confidence_score = int(confidence_score * 100)
            
            response_data = {
                'message': result.get('response', 'I apologize, but I had trouble processing that.'),
                'confidence': confidence_score,
                'conversation_id': conversation_id,
                'user_id': user_id,
                'agent': result.get('agent', 'onboarding')
            }
            
            # Add handoff information if present
            if 'handoff' in result:
                response_data['handoff'] = result['handoff']
            
            # Add next step information if present  
            if 'next_step' in result:
                response_data['next_step'] = result['next_step']
            
            # Gamification integration - run in background
            try:
                # Award points for conversation
                asyncio.create_task(
                    gamification_engine.award_points(user_id, 10, "Chat interaction")
                )
                
                # Calculate purpose alignment if confidence is high
                if confidence_score >= 50:
                    conversation_data = {
                        'message': message,
                        'response': result.get('response', ''),
                        'confidence_score': confidence_score / 100.0
                    }
                    
                    asyncio.create_task(
                        gamification_engine.calculate_purpose_alignment(user_id, conversation_data)
                    )
                
                # Check for achievements
                asyncio.create_task(
                    gamification_engine.check_achievements(user_id, {
                        'conversation_count': 1,
                        'confidence_score': confidence_score / 100.0
                    })
                )
                
            except Exception as gamification_error:
                logger.warning(f"Gamification error: {gamification_error}")
            
            return jsonify(response_data)
            
        except Exception as agent_error:
            logger.error(f"AgentCore error: {str(agent_error)}")
            # Fallback to demo mode if agent fails
            return handle_demo_chat(message, user_id, conversation_id)
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def handle_demo_chat(message: str, user_id: str, conversation_id: str = None):
    """Handle chat in demo mode with simulated onboarding responses"""
    
    # Generate or use existing conversation ID
    if not conversation_id:
        conversation_id = f'demo_{user_id}_{int(datetime.now().timestamp())}'
    
    # Smart demo responses based on conversation stage
    demo_responses = [
        "That's wonderful! I can sense your passion. Tell me more about what specifically drives you in this area?",
        "I love hearing about what motivates people! What values are most important to you when choosing work or projects?",
        "Fascinating! It sounds like you have a clear sense of purpose. What skills do you feel strongest in?",
        "That's really meaningful work. How do you prefer to collaborate with others - do you like structured teams or flexible partnerships?",
        "Excellent insights! Based on what you've shared, I'm building a strong sense of your purpose profile. What kind of impact do you want to make?",
        "I'm getting a clear picture of your values and passions! What would your ideal team environment look like?",
        "This is great - I can see you have strong alignment around making a difference. Are there any specific skills you'd like to develop?",
        "Perfect! I feel confident about your profile now. You seem driven by meaningful impact and collaborative excellence."
    ]
    
    # Simulate conversation progression
    import hashlib
    message_hash = hashlib.md5((conversation_id + message).encode()).hexdigest()
    response_index = int(message_hash[:2], 16) % len(demo_responses)
    
    # Simulate confidence progression
    confidence = min(95, 30 + (response_index * 10) + len(message) // 10)
    
    return jsonify({
        'message': demo_responses[response_index],
        'confidence': confidence,
        'conversation_id': conversation_id,
        'current_stage': 'demo_progression',
        'profile_complete': confidence >= 85,
        'user_id': user_id,
        'agent': 'onboarding_demo',
        'demo_mode': True
    })

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
    """Find team matches using AgentCore orchestration"""
    import asyncio
    
    try:
        data = request.get_json()
        user_id = data.get('user_id') or data.get('session_id')
        session_id = data.get('conversation_id')
        
        if not user_id:
            return jsonify({'error': 'User ID is required'}), 400
        
        # Get user profile
        user_profile = data_service.get_user_profile(user_id)
        if not user_profile:
            return jsonify({'error': 'User profile not found'}), 404
        
        # Use AgentCore orchestration for matching
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(
                bedrock_service.invoke_matching_agent(user_profile, session_id)
            )
            
            loop.close()
            
            return jsonify({
                'matches': result.get('matches', result.get('response', '')),
                'confidence_score': result.get('confidence_score', 0.8),
                'agent': result.get('agent', 'matching'),
                'user_id': user_id,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as agent_error:
            logger.error(f"AgentCore matching error: {str(agent_error)}")
            # Fallback to demo matches
            return jsonify({
                'matches': "Demo mode: Here are 3 purpose-driven opportunities focused on community impact...",
                'confidence_score': 0.75,
                'agent': 'matching',
                'user_id': user_id,
                'timestamp': datetime.now().isoformat(),
                'mode': 'demo'
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
    """Update team performance metrics using AgentCore orchestration"""
    import asyncio
    
    try:
        data = request.get_json()
        metrics = data.get('metrics', {})
        
        # Use AgentCore orchestration
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            result = loop.run_until_complete(
                bedrock_service.invoke_team_agent(
                    team_id=team_id,
                    action='update_performance_metrics',
                    parameters={
                        'metrics': metrics,
                        'members': data.get('members', []),
                        'agent_insights': data.get('agent_insights', []),
                        'improvement_suggestions': data.get('improvement_suggestions', [])
                    },
                    session_id=data.get('session_id')
                )
            )
            
            loop.close()
            
            return jsonify(result)
            
        except Exception as agent_error:
            logger.error(f"AgentCore team error: {str(agent_error)}")
            # Fallback response
            return jsonify({
                'result': 'Team performance updated (demo mode)',
                'team_id': team_id,
                'agent': 'team',
                'mode': 'demo'
            })
        
    except Exception as e:
        logger.error(f"Error updating team performance: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/agent-core/status', methods=['GET'])
def get_agent_core_status():
    """Get AgentCore orchestration status and performance metrics"""
    try:
        if not agent_core:
            return jsonify({'error': 'AgentCore not initialized'}), 500
        
        # Get performance metrics
        performance_metrics = agent_core.get_agent_performance_metrics()
        
        # Get active workflows
        active_workflows = {
            wf_id: {
                'workflow_id': wf_id,
                'current_agent': context.current_agent.value,
                'user_id': context.user_id,
                'session_id': context.session_id,
                'confidence_scores': context.confidence_scores,
                'created_at': context.created_at.isoformat(),
                'updated_at': context.updated_at.isoformat()
            }
            for wf_id, context in agent_core.active_workflows.items()
        }
        
        return jsonify({
            'status': 'active',
            'performance_metrics': performance_metrics,
            'active_workflows': active_workflows,
            'workflow_count': len(active_workflows),
            'agent_count': len(agent_core.agents),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting AgentCore status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/agent-core/workflow/<workflow_id>', methods=['GET'])
def get_workflow_status(workflow_id):
    """Get detailed workflow status and decision history"""
    import asyncio
    
    try:
        if not agent_core:
            return jsonify({'error': 'AgentCore not initialized'}), 500
        
        # Get workflow status
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        workflow_status = loop.run_until_complete(
            agent_core.get_workflow_status(workflow_id)
        )
        
        loop.close()
        
        if not workflow_status:
            return jsonify({'error': 'Workflow not found'}), 404
        
        # Get decision history
        decisions = agent_core.workflow_decisions.get(workflow_id, [])
        decision_history = [
            {
                'decision_id': d.decision_id,
                'agent_type': d.agent_type.value,
                'decision_type': d.decision_type,
                'confidence_score': d.confidence_score,
                'execution_time_ms': d.execution_time_ms,
                'timestamp': d.timestamp.isoformat(),
                'success': d.success,
                'error_message': d.error_message
            }
            for d in decisions
        ]
        
        return jsonify({
            'workflow_status': workflow_status,
            'decision_history': decision_history,
            'decision_count': len(decision_history)
        })
        
    except Exception as e:
        logger.error(f"Error getting workflow status: {str(e)}")
        return jsonify({'error': str(e)}), 500

# =============================================================================
# GAMIFICATION API ENDPOINTS
# =============================================================================

@app.route('/api/gamification/profile/<user_id>', methods=['GET'])
def get_gamification_profile(user_id):
    """Get comprehensive gamification profile for user"""
    import asyncio
    
    try:
        # Run async function in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        profile = loop.run_until_complete(
            gamification_engine.get_user_profile(user_id)
        )
        
        loop.close()
        
        return jsonify({
            'user_id': profile.user_id,
            'level': profile.level,
            'total_points': profile.total_points,
            'experience_points': profile.experience_points,
            'engagement_streak_days': profile.engagement_streak_days,
            'purpose_alignment': {
                'overall_score': profile.purpose_alignment.get_percentage(),
                'grade': profile.purpose_alignment.get_grade(),
                'values_alignment': int(profile.purpose_alignment.values_alignment * 100),
                'passion_alignment': int(profile.purpose_alignment.passion_alignment * 100),
                'skills_match': int(profile.purpose_alignment.skills_match * 100),
                'impact_potential': int(profile.purpose_alignment.impact_potential * 100),
                'confidence_level': int(profile.purpose_alignment.confidence_level * 100),
                'last_updated': profile.purpose_alignment.last_updated.isoformat()
            },
            'talent_gap_analysis': {
                'overall_readiness': profile.talent_gap_analysis.get_readiness_percentage(),
                'critical_gaps_count': len(profile.talent_gap_analysis.critical_gaps),
                'improvement_gaps_count': len(profile.talent_gap_analysis.improvement_gaps),
                'strength_areas': profile.talent_gap_analysis.strength_areas,
                'recommended_focus': profile.talent_gap_analysis.recommended_focus,
                'estimated_development_time': profile.talent_gap_analysis.estimated_development_time
            },
            'achievements_count': len([ach for ach in profile.achievements if ach.is_unlocked]),
            'active_challenges_count': len(profile.active_challenges),
            'completed_milestones_count': len([m for m in profile.milestones if m.is_completed]),
            'last_activity': profile.last_activity.isoformat(),
            'created_at': profile.created_at.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting gamification profile: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/gamification/progress/<user_id>', methods=['GET'])
def get_progress_summary(user_id):
    """Get progress summary for dashboard display"""
    import asyncio
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        progress = loop.run_until_complete(
            gamification_engine.get_progress_summary(user_id)
        )
        
        loop.close()
        
        return jsonify(progress)
        
    except Exception as e:
        logger.error(f"Error getting progress summary: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/gamification/purpose-alignment/<user_id>', methods=['POST'])
def calculate_purpose_alignment(user_id):
    """Calculate purpose alignment based on conversation data"""
    import asyncio
    
    try:
        data = request.get_json()
        conversation_data = data.get('conversation_data', {})
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        alignment = loop.run_until_complete(
            gamification_engine.calculate_purpose_alignment(user_id, conversation_data)
        )
        
        loop.close()
        
        return jsonify({
            'overall_score': alignment.get_percentage(),
            'grade': alignment.get_grade(),
            'breakdown': {
                'values_alignment': int(alignment.values_alignment * 100),
                'passion_alignment': int(alignment.passion_alignment * 100),
                'skills_match': int(alignment.skills_match * 100),
                'impact_potential': int(alignment.impact_potential * 100),
                'confidence_level': int(alignment.confidence_level * 100)
            },
            'last_updated': alignment.last_updated.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error calculating purpose alignment: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/gamification/talent-gaps/<user_id>', methods=['POST'])
def analyze_talent_gaps(user_id):
    """Analyze talent gaps and provide improvement suggestions"""
    import asyncio
    
    try:
        data = request.get_json()
        user_profile = data.get('user_profile', {})
        team_requirements = data.get('team_requirements')
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        analysis = loop.run_until_complete(
            gamification_engine.analyze_talent_gaps(user_id, user_profile, team_requirements)
        )
        
        loop.close()
        
        return jsonify({
            'overall_readiness': analysis.get_readiness_percentage(),
            'critical_gaps': [
                {
                    'skill_name': gap.skill_name,
                    'current_level': int(gap.current_level * 100),
                    'target_level': int(gap.target_level * 100),
                    'gap_percentage': gap.gap_percentage,
                    'importance': gap.importance,
                    'improvement_suggestions': gap.improvement_suggestions,
                    'resources': gap.resources,
                    'estimated_time_weeks': gap.estimated_time_weeks,
                    'priority_score': gap.priority_score
                }
                for gap in analysis.critical_gaps
            ],
            'improvement_gaps': [
                {
                    'skill_name': gap.skill_name,
                    'current_level': int(gap.current_level * 100),
                    'target_level': int(gap.target_level * 100),
                    'gap_percentage': gap.gap_percentage,
                    'improvement_suggestions': gap.improvement_suggestions[:2],  # Limit for display
                    'estimated_time_weeks': gap.estimated_time_weeks
                }
                for gap in analysis.improvement_gaps
            ],
            'strength_areas': analysis.strength_areas,
            'recommended_focus': analysis.recommended_focus,
            'estimated_development_time': analysis.estimated_development_time,
            'last_updated': analysis.last_updated.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error analyzing talent gaps: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/gamification/achievements/<user_id>', methods=['GET'])
def get_user_achievements(user_id):
    """Get user achievements"""
    import asyncio
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        profile = loop.run_until_complete(
            gamification_engine.get_user_profile(user_id)
        )
        
        loop.close()
        
        achievements = [
            {
                'achievement_id': ach.achievement_id,
                'title': ach.title,
                'description': ach.description,
                'icon': ach.icon,
                'points': ach.points,
                'unlocked': ach.is_unlocked,
                'progress_percentage': ach.progress_percentage,
                'unlocked_at': ach.unlocked_at.isoformat() if ach.unlocked_at else None,
                'achievement_type': ach.achievement_type.value
            }
            for ach in profile.achievements
        ]
        
        return jsonify({
            'achievements': achievements,
            'total_unlocked': len([ach for ach in achievements if ach['unlocked']]),
            'total_points_from_achievements': sum(ach['points'] for ach in achievements if ach['unlocked'])
        })
        
    except Exception as e:
        logger.error(f"Error getting achievements: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/gamification/achievements/<user_id>/check', methods=['POST'])
def check_achievements(user_id):
    """Check and award new achievements"""
    import asyncio
    
    try:
        data = request.get_json()
        action_data = data.get('action_data', {})
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        new_achievements = loop.run_until_complete(
            gamification_engine.check_achievements(user_id, action_data)
        )
        
        loop.close()
        
        return jsonify({
            'new_achievements': [
                {
                    'title': ach.title,
                    'description': ach.description,
                    'icon': ach.icon,
                    'points': ach.points,
                    'unlocked_at': ach.unlocked_at.isoformat()
                }
                for ach in new_achievements
            ],
            'achievement_count': len(new_achievements)
        })
        
    except Exception as e:
        logger.error(f"Error checking achievements: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/gamification/challenges/<user_id>', methods=['GET'])
def get_user_challenges(user_id):
    """Get personalized challenges for user"""
    import asyncio
    
    try:
        count = request.args.get('count', 3, type=int)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        challenges = loop.run_until_complete(
            gamification_engine.generate_personalized_challenges(user_id, count)
        )
        
        loop.close()
        
        return jsonify({
            'challenges': [
                {
                    'challenge_id': ch.challenge_id,
                    'title': ch.title,
                    'description': ch.description,
                    'difficulty': ch.difficulty.value,
                    'category': ch.category,
                    'points_reward': ch.points_reward,
                    'estimated_duration_days': ch.estimated_duration_days,
                    'status': ch.status.value,
                    'progress_percentage': int(ch.progress * 100),
                    'success_criteria': ch.success_criteria,
                    'created_at': ch.created_at.isoformat()
                }
                for ch in challenges
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting challenges: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/gamification/points/<user_id>', methods=['POST'])
def award_points(user_id):
    """Award points to user"""
    import asyncio
    
    try:
        data = request.get_json()
        points = data.get('points', 0)
        reason = data.get('reason', '')
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        total_points = loop.run_until_complete(
            gamification_engine.award_points(user_id, points, reason)
        )
        
        loop.close()
        
        return jsonify({
            'points_awarded': points,
            'total_points': total_points,
            'reason': reason
        })
        
    except Exception as e:
        logger.error(f"Error awarding points: {str(e)}")
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
    # Prefer running via the Flask-SocketIO server if it's been initialized
    host = '0.0.0.0'
    port = int(os.getenv('PORT', 5000))
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

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