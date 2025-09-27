"""
AWS Lambda functions for Team Agent tools
These functions will be called by Bedrock AgentCore as action groups
"""

import json
import boto3
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
opensearch_client = boto3.client('opensearchserverless')

# Get table names from environment
USER_PROFILES_TABLE = os.environ['USER_PROFILES_TABLE']
TEAM_PERFORMANCE_TABLE = os.environ['TEAM_PERFORMANCE_TABLE']
OPENSEARCH_ENDPOINT = os.environ['OPENSEARCH_ENDPOINT']

def handler(event, context):
    """Main Lambda handler for Team Agent tools"""
    try:
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Parse the action from the event
        action = event.get('action', '')
        parameters = event.get('parameters', {})
        
        # Route to appropriate function based on action
        if action == 'check_project_status':
            return check_project_status(parameters)
        elif action == 'generate_retrospective':
            return generate_retrospective(parameters)
        elif action == 'update_performance_metrics':
            return update_performance_metrics(parameters)
        elif action == 'provide_coaching_insight':
            return provide_coaching_insight(parameters)
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Unknown action: {action}'})
            }
            
    except Exception as e:
        logger.error(f"Error in handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def check_project_status(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve current project metrics and status for a team"""
    try:
        team_id = parameters.get('team_id')
        if not team_id:
            raise ValueError("team_id is required")
        
        # Get team performance table
        table = dynamodb.Table(TEAM_PERFORMANCE_TABLE)
        
        # Query recent performance data
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('teamId').eq(team_id),
            ScanIndexForward=False,  # Get most recent first
            Limit=10
        )
        
        items = response.get('Items', [])
        
        if not items:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'team_id': team_id,
                    'status': 'No performance data found',
                    'metrics': {},
                    'last_updated': None
                })
            }
        
        # Get the most recent metrics
        latest_metrics = items[0]
        
        # Calculate trends from recent data
        productivity_trend = calculate_trend([item.get('metrics', {}).get('productivity', 0) for item in items])
        collaboration_trend = calculate_trend([item.get('metrics', {}).get('collaboration', 0) for item in items])
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'team_id': team_id,
                'status': 'Active',
                'current_metrics': latest_metrics.get('metrics', {}),
                'trends': {
                    'productivity': productivity_trend,
                    'collaboration': collaboration_trend
                },
                'last_updated': latest_metrics.get('timestamp'),
                'member_count': len(latest_metrics.get('members', []))
            })
        }
        
    except Exception as e:
        logger.error(f"Error checking project status: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def generate_retrospective(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Create customized team retrospective report"""
    try:
        team_id = parameters.get('team_id')
        period = parameters.get('period', '30')  # days
        
        if not team_id:
            raise ValueError("team_id is required")
        
        # Get team performance data for the specified period
        table = dynamodb.Table(TEAM_PERFORMANCE_TABLE)
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(period))
        
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('teamId').eq(team_id),
            FilterExpression=boto3.dynamodb.conditions.Attr('timestamp').between(
                start_date.isoformat(),
                end_date.isoformat()
            )
        )
        
        items = response.get('Items', [])
        
        if not items:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'team_id': team_id,
                    'period': f"{period} days",
                    'retrospective': {
                        'summary': 'No data available for this period',
                        'achievements': [],
                        'challenges': [],
                        'recommendations': ['Start tracking team performance metrics']
                    }
                })
            }
        
        # Analyze the data
        achievements = []
        challenges = []
        recommendations = []
        
        # Calculate average metrics
        avg_productivity = sum(item.get('metrics', {}).get('productivity', 0) for item in items) / len(items)
        avg_collaboration = sum(item.get('metrics', {}).get('collaboration', 0) for item in items) / len(items)
        avg_satisfaction = sum(item.get('metrics', {}).get('satisfaction', 0) for item in items) / len(items)
        
        # Generate insights based on metrics
        if avg_productivity > 0.8:
            achievements.append("High productivity maintained throughout the period")
        elif avg_productivity < 0.6:
            challenges.append("Productivity below target levels")
            recommendations.append("Consider reviewing workload distribution and removing blockers")
        
        if avg_collaboration > 0.8:
            achievements.append("Excellent team collaboration and communication")
        elif avg_collaboration < 0.6:
            challenges.append("Team collaboration needs improvement")
            recommendations.append("Schedule more team building activities and improve communication channels")
        
        if avg_satisfaction > 0.8:
            achievements.append("High team satisfaction and morale")
        elif avg_satisfaction < 0.6:
            challenges.append("Team satisfaction is concerning")
            recommendations.append("Conduct individual check-ins to understand satisfaction drivers")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'team_id': team_id,
                'period': f"{period} days",
                'retrospective': {
                    'summary': f"Team performance analysis for {len(items)} data points over {period} days",
                    'average_metrics': {
                        'productivity': round(avg_productivity, 2),
                        'collaboration': round(avg_collaboration, 2),
                        'satisfaction': round(avg_satisfaction, 2)
                    },
                    'achievements': achievements,
                    'challenges': challenges,
                    'recommendations': recommendations
                },
                'data_points': len(items)
            })
        }
        
    except Exception as e:
        logger.error(f"Error generating retrospective: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def update_performance_metrics(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Update team performance data in the database"""
    try:
        team_id = parameters.get('team_id')
        metrics = parameters.get('metrics', {})
        
        if not team_id or not metrics:
            raise ValueError("team_id and metrics are required")
        
        # Get team performance table
        table = dynamodb.Table(TEAM_PERFORMANCE_TABLE)
        
        # Create timestamp
        timestamp = datetime.now().isoformat()
        
        # Prepare item for insertion
        item = {
            'teamId': team_id,
            'timestamp': timestamp,
            'metrics': metrics,
            'agentInsights': parameters.get('agent_insights', []),
            'improvementSuggestions': parameters.get('improvement_suggestions', [])
        }
        
        # Add members if provided
        if 'members' in parameters:
            item['members'] = parameters['members']
        
        # Insert into DynamoDB
        table.put_item(Item=item)
        
        logger.info(f"Updated performance metrics for team {team_id}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'team_id': team_id,
                'timestamp': timestamp,
                'message': 'Performance metrics updated successfully'
            })
        }
        
    except Exception as e:
        logger.error(f"Error updating performance metrics: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def provide_coaching_insight(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Generate personalized coaching recommendation"""
    try:
        user_id = parameters.get('user_id')
        context = parameters.get('context', {})
        
        if not user_id:
            raise ValueError("user_id is required")
        
        # Get user profile
        user_table = dynamodb.Table(USER_PROFILES_TABLE)
        user_response = user_table.get_item(Key={'userId': user_id})
        
        if 'Item' not in user_response:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'User not found'})
            }
        
        user_profile = user_response['Item']
        
        # Generate coaching insights based on profile and context
        insights = []
        
        # Analyze skills and suggest improvements
        skills = user_profile.get('purposeProfile', {}).get('skills', {})
        technical_skills = skills.get('technical', [])
        soft_skills = skills.get('soft', [])
        
        # Find areas for improvement
        if len(technical_skills) < 3:
            insights.append("Consider developing more technical skills to increase your value to teams")
        
        if len(soft_skills) < 3:
            insights.append("Focus on developing soft skills like communication and leadership")
        
        # Analyze work style and provide recommendations
        work_style = user_profile.get('purposeProfile', {}).get('workStyle', {})
        
        if work_style.get('collaboration') == 'low':
            insights.append("Consider joining collaborative projects to improve teamwork skills")
        
        if work_style.get('autonomy') == 'high' and context.get('team_size', 1) > 1:
            insights.append("Balance your preference for autonomy with team collaboration needs")
        
        # Performance-based insights
        if context.get('recent_performance'):
            performance = context['recent_performance']
            if performance.get('productivity', 0) < 0.7:
                insights.append("Focus on time management and prioritization to boost productivity")
            if performance.get('collaboration', 0) < 0.7:
                insights.append("Engage more actively in team discussions and knowledge sharing")
        
        # Default insight if no specific recommendations
        if not insights:
            insights.append("Continue leveraging your strengths while staying open to new learning opportunities")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'user_id': user_id,
                'coaching_insights': insights,
                'focus_areas': extract_focus_areas(user_profile, context),
                'next_steps': generate_next_steps(insights),
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"Error providing coaching insight: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def calculate_trend(values: List[float]) -> str:
    """Calculate trend direction from a list of values"""
    if len(values) < 2:
        return "insufficient_data"
    
    # Simple trend calculation
    recent_avg = sum(values[:3]) / min(3, len(values))
    older_avg = sum(values[-3:]) / min(3, len(values))
    
    if recent_avg > older_avg * 1.1:
        return "improving"
    elif recent_avg < older_avg * 0.9:
        return "declining"
    else:
        return "stable"

def extract_focus_areas(user_profile: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
    """Extract key focus areas for the user"""
    focus_areas = []
    
    purpose_profile = user_profile.get('purposeProfile', {})
    passions = purpose_profile.get('passions', [])
    
    # Add passion-based focus areas
    focus_areas.extend(passions[:3])  # Top 3 passions
    
    # Add skill-based focus areas
    skills = purpose_profile.get('skills', {})
    technical_skills = skills.get('technical', [])
    if technical_skills:
        focus_areas.append(f"Technical: {technical_skills[0].get('name', 'Unknown')}")
    
    return focus_areas[:5]  # Limit to 5 focus areas

def generate_next_steps(insights: List[str]) -> List[str]:
    """Generate actionable next steps from insights"""
    next_steps = []
    
    for insight in insights:
        if "technical skills" in insight.lower():
            next_steps.append("Identify 1-2 technical skills to develop this month")
        elif "soft skills" in insight.lower():
            next_steps.append("Practice active listening and communication in team meetings")
        elif "collaboration" in insight.lower():
            next_steps.append("Volunteer for a collaborative project or cross-functional team")
        elif "productivity" in insight.lower():
            next_steps.append("Implement time-blocking and prioritization techniques")
    
    # Add default next step if none generated
    if not next_steps:
        next_steps.append("Schedule a follow-up coaching session in 2 weeks")
    
    return next_steps[:3]  # Limit to 3 next steps