"""
Bedrock AgentCore Orchestration System

This module provides the central orchestration layer for multi-agent workflows,
handling agent registration, handoffs, decision logging, and performance monitoring.
"""

import json
import uuid
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class AgentType(Enum):
    """Agent types supported by the system"""
    ONBOARDING = "onboarding"
    MATCHING = "matching" 
    TEAM = "team"
    INTEGRATION = "integration"

class WorkflowStatus(Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class HandoffTrigger(Enum):
    """Triggers for agent handoffs"""
    CONFIDENCE_THRESHOLD = "confidence_threshold"
    USER_REQUEST = "user_request"
    WORKFLOW_COMPLETION = "workflow_completion"
    ERROR_ESCALATION = "error_escalation"
    TIMEOUT = "timeout"

@dataclass
class AgentConfiguration:
    """Configuration for a Bedrock agent"""
    agent_id: str
    agent_alias: str
    agent_type: AgentType
    model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    max_tokens: int = 1500
    temperature: float = 0.7
    timeout_seconds: int = 30
    retry_count: int = 3
    handoff_threshold: float = 0.9
    
@dataclass
class AgentContext:
    """Context passed between agents during handoffs"""
    session_id: str
    user_id: str
    conversation_history: List[Dict[str, Any]]
    user_profile: Dict[str, Any]
    current_agent: AgentType
    workflow_id: str
    metadata: Dict[str, Any]
    confidence_scores: Dict[str, float]
    created_at: datetime
    updated_at: datetime

@dataclass
class WorkflowDecision:
    """Decision made during workflow execution"""
    decision_id: str
    workflow_id: str
    agent_type: AgentType
    decision_type: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    confidence_score: float
    execution_time_ms: int
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None

@dataclass
class AgentPerformanceMetrics:
    """Performance metrics for agent monitoring"""
    agent_type: AgentType
    total_invocations: int
    successful_invocations: int
    failed_invocations: int
    average_response_time_ms: float
    average_confidence_score: float
    handoff_rate: float
    error_rate: float
    last_updated: datetime

class BedrockAgentCore:
    """Central orchestration system for Bedrock agents"""
    
    def __init__(self, aws_config):
        self.aws_config = aws_config
        
        # Handle demo mode gracefully
        if aws_config.demo_mode or not aws_config.session:
            self.bedrock_agent = None
            self.bedrock = None
        else:
            self.bedrock_agent = aws_config.session.client('bedrock-agent-runtime')
            self.bedrock = aws_config.bedrock
        
        # Agent configurations
        self.agents: Dict[AgentType, AgentConfiguration] = {}
        
        # Active workflows and contexts
        self.active_workflows: Dict[str, AgentContext] = {}
        self.workflow_decisions: Dict[str, List[WorkflowDecision]] = {}
        
        # Performance monitoring
        self.performance_metrics: Dict[AgentType, AgentPerformanceMetrics] = {}
        
        # Handoff rules
        self.handoff_rules: Dict[AgentType, List[Callable]] = {}
        
        self._initialize_agents()
        self._setup_handoff_rules()
        
    def _initialize_agents(self):
        """Initialize agent configurations"""
        # For hackathon demo, we'll configure agents that work with Claude directly
        # In production, these would be actual Bedrock Agent IDs
        
        self.agents[AgentType.ONBOARDING] = AgentConfiguration(
            agent_id="onboarding-agent-demo",
            agent_alias="onboarding-v1", 
            agent_type=AgentType.ONBOARDING,
            handoff_threshold=0.9
        )
        
        self.agents[AgentType.MATCHING] = AgentConfiguration(
            agent_id="matching-agent-demo",
            agent_alias="matching-v1",
            agent_type=AgentType.MATCHING,
            handoff_threshold=0.8
        )
        
        self.agents[AgentType.TEAM] = AgentConfiguration(
            agent_id="team-agent-demo", 
            agent_alias="team-v1",
            agent_type=AgentType.TEAM,
            handoff_threshold=0.85
        )
        
        # Initialize performance metrics
        for agent_type in AgentType:
            self.performance_metrics[agent_type] = AgentPerformanceMetrics(
                agent_type=agent_type,
                total_invocations=0,
                successful_invocations=0,
                failed_invocations=0,
                average_response_time_ms=0.0,
                average_confidence_score=0.0,
                handoff_rate=0.0,
                error_rate=0.0,
                last_updated=datetime.utcnow()
            )
        
    def _setup_handoff_rules(self):
        """Setup handoff rules between agents"""
        self.handoff_rules = {
            AgentType.ONBOARDING: [
                self._should_handoff_to_matching,
                self._should_escalate_to_human
            ],
            AgentType.MATCHING: [
                self._should_handoff_to_team,
                self._should_return_to_onboarding
            ],
            AgentType.TEAM: [
                self._should_handoff_to_integration,
                self._should_return_to_matching
            ]
        }
    
    async def start_workflow(self, user_input: str, user_id: str, session_id: str = None) -> AgentContext:
        """Start a new multi-agent workflow"""
        if not session_id:
            session_id = str(uuid.uuid4())
            
        workflow_id = str(uuid.uuid4())
        
        context = AgentContext(
            session_id=session_id,
            user_id=user_id,
            conversation_history=[{
                'role': 'user',
                'content': user_input,
                'timestamp': datetime.utcnow().isoformat()
            }],
            user_profile={},
            current_agent=AgentType.ONBOARDING,
            workflow_id=workflow_id,
            metadata={'initial_input': user_input},
            confidence_scores={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.active_workflows[workflow_id] = context
        
        logger.info(f"Started workflow {workflow_id} for user {user_id}")
        return context
    
    async def invoke_agent(self, agent_type: AgentType, context: AgentContext, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a specific agent with context preservation"""
        start_time = datetime.utcnow()
        decision_id = str(uuid.uuid4())
        
        try:
            # Update metrics
            self.performance_metrics[agent_type].total_invocations += 1
            
            # Get agent configuration
            agent_config = self.agents[agent_type]
            
            # Prepare the invocation based on agent type
            if agent_type == AgentType.ONBOARDING:
                result = await self._invoke_onboarding_agent(agent_config, context, input_data)
            elif agent_type == AgentType.MATCHING:
                result = await self._invoke_matching_agent(agent_config, context, input_data)
            elif agent_type == AgentType.TEAM:
                result = await self._invoke_team_agent(agent_config, context, input_data)
            else:
                raise ValueError(f"Unsupported agent type: {agent_type}")
            
            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Extract confidence score
            confidence_score = result.get('confidence_score', 0.0)
            context.confidence_scores[agent_type.value] = confidence_score
            
            # Log decision
            decision = WorkflowDecision(
                decision_id=decision_id,
                workflow_id=context.workflow_id,
                agent_type=agent_type,
                decision_type='invoke',
                input_data=input_data,
                output_data=result,
                confidence_score=confidence_score,
                execution_time_ms=execution_time,
                timestamp=datetime.utcnow(),
                success=True
            )
            
            await self._log_decision(decision)
            
            # Update performance metrics
            self.performance_metrics[agent_type].successful_invocations += 1
            self._update_performance_metrics(agent_type, execution_time, confidence_score)
            
            # Check for handoff triggers
            handoff_result = await self._check_handoff_triggers(context, result)
            if handoff_result:
                result['handoff'] = handoff_result
            
            return result
            
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Log failed decision
            decision = WorkflowDecision(
                decision_id=decision_id,
                workflow_id=context.workflow_id,
                agent_type=agent_type,
                decision_type='invoke',
                input_data=input_data,
                output_data={},
                confidence_score=0.0,
                execution_time_ms=execution_time,
                timestamp=datetime.utcnow(),
                success=False,
                error_message=str(e)
            )
            
            await self._log_decision(decision)
            
            # Update error metrics
            self.performance_metrics[agent_type].failed_invocations += 1
            self.performance_metrics[agent_type].error_rate = (
                self.performance_metrics[agent_type].failed_invocations / 
                self.performance_metrics[agent_type].total_invocations
            )
            
            logger.error(f"Error invoking {agent_type}: {str(e)}")
            
            # Implement retry mechanism
            retry_count = input_data.get('retry_count', 0)
            if retry_count < agent_config.retry_count:
                logger.info(f"Retrying {agent_type} invocation (attempt {retry_count + 1})")
                input_data['retry_count'] = retry_count + 1
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                return await self.invoke_agent(agent_type, context, input_data)
            
            raise
    
    async def _invoke_onboarding_agent(self, config: AgentConfiguration, context: AgentContext, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the onboarding agent"""
        user_input = input_data.get('user_input', '')
        
        # Build conversation history context
        history_context = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in context.conversation_history[-5:]  # Last 5 messages
        ])
        
        prompt = f"""You are the Onboarding Agent for Find Your Team, a platform that helps people discover their purpose and connect with meaningful teams. Your goal is to build a comprehensive Purpose Profile with ≥90% confidence.

Conversation History:
{history_context}

Current User Input: {user_input}

Based on the conversation, please:
1. Respond empathetically to the user's input
2. Ask insightful questions to understand their core values, passions, skills, and work style
3. If you have sufficient information (≥90% confidence), provide a purpose profile summary
4. Always include a confidence score (0-100) at the end of your response

Keep responses conversational and engaging. Focus on how they can add value to people they care about."""

        # Handle demo mode
        if not self.bedrock or self.aws_config.demo_mode:
            # Demo response
            agent_response = f"That's wonderful to hear! I can sense your passion for {user_input}. Could you tell me more about what specifically drives you in this area? I'm building your purpose profile with 75% confidence so far."
        else:
            response = self.bedrock.invoke_model(
                modelId=config.model_id,
                body=json.dumps({
                    'anthropic_version': 'bedrock-2023-05-31',
                    'max_tokens': config.max_tokens,
                    'temperature': config.temperature,
                    'messages': [{'role': 'user', 'content': prompt}]
                })
            )
            
            response_body = json.loads(response['body'].read())
            agent_response = response_body['content'][0]['text']
        
        # Extract confidence score
        confidence_score = self._extract_confidence_score(agent_response)
        
        # Update conversation history
        context.conversation_history.append({
            'role': 'assistant',
            'content': agent_response,
            'timestamp': datetime.utcnow().isoformat(),
            'agent': 'onboarding',
            'confidence': confidence_score
        })
        
        return {
            'response': agent_response,
            'confidence_score': confidence_score,
            'agent': 'onboarding',
            'session_id': context.session_id
        }
    
    async def _invoke_matching_agent(self, config: AgentConfiguration, context: AgentContext, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the matching agent"""
        user_profile = input_data.get('user_profile', context.user_profile)
        
        prompt = f"""You are the Matching Agent for Find Your Team. Based on this user profile, find the best team matches:

User Profile:
{json.dumps(user_profile, indent=2)}

Provide 3 team/opportunity matches with:
1. Alignment score (0-1) 
2. Gap score (skills they need to develop)
3. Clear explanation of why it's a good match
4. How they can add value to people they love through this opportunity

Focus on opportunities that help poor communities and maximize human potential."""
        
        # Handle demo mode
        if not self.bedrock or self.aws_config.demo_mode:
            # Demo response
            matches = "Demo Mode: Here are 3 purpose-driven team opportunities:\n\n1. Community Education Initiative - Help develop learning programs for underserved communities\n2. Social Impact Startup - Join a team building technology solutions for poverty alleviation\n3. Local NGO Partnership - Collaborate on sustainable development projects"
        else:
            response = self.bedrock.invoke_model(
                modelId=config.model_id,
                body=json.dumps({
                    'anthropic_version': 'bedrock-2023-05-31',
                    'max_tokens': config.max_tokens,
                    'temperature': config.temperature,
                    'messages': [{'role': 'user', 'content': prompt}]
                })
            )
            
            response_body = json.loads(response['body'].read())
            matches = response_body['content'][0]['text']
        
        return {
            'matches': matches,
            'agent': 'matching',
            'confidence_score': 0.85,  # Default for matching
            'user_id': context.user_id
        }
    
    async def _invoke_team_agent(self, config: AgentConfiguration, context: AgentContext, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the team agent"""
        team_id = input_data.get('team_id')
        action = input_data.get('action', 'analyze_performance')
        parameters = input_data.get('parameters', {})
        
        # For demo, simulate team agent response
        if action == 'analyze_performance':
            return {
                'team_health': 0.85,
                'performance_metrics': {
                    'productivity': 0.78,
                    'collaboration': 0.82,
                    'satisfaction': 0.89
                },
                'agent': 'team',
                'confidence_score': 0.88
            }
        
        return {
            'result': f"Team agent action '{action}' completed",
            'agent': 'team',
            'confidence_score': 0.75
        }
    
    def _extract_confidence_score(self, response: str) -> float:
        """Extract confidence score from agent response"""
        import re
        
        patterns = [
            r'confidence[:\s]+(\d+)%',
            r'(\d+)%\s+confidence',
            r'confidence[:\s]+(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response.lower())
            if match:
                return float(match.group(1)) / 100.0
        
        # Default confidence based on response analysis
        if len(response) > 300 and any(word in response.lower() for word in ['values', 'skills', 'passion', 'purpose']):
            return 0.85
        elif len(response) > 150:
            return 0.65
        else:
            return 0.45
    
    async def _check_handoff_triggers(self, context: AgentContext, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if agent handoff should occur"""
        current_agent = context.current_agent
        confidence_score = result.get('confidence_score', 0.0)
        
        # Check confidence threshold
        agent_config = self.agents[current_agent]
        if confidence_score >= agent_config.handoff_threshold:
            next_agent = self._determine_next_agent(current_agent, context)
            if next_agent:
                return {
                    'trigger': HandoffTrigger.CONFIDENCE_THRESHOLD.value,
                    'from_agent': current_agent.value,
                    'to_agent': next_agent.value,
                    'confidence_score': confidence_score
                }
        
        return None
    
    def _determine_next_agent(self, current_agent: AgentType, context: AgentContext) -> Optional[AgentType]:
        """Determine the next agent in the workflow"""
        if current_agent == AgentType.ONBOARDING:
            return AgentType.MATCHING
        elif current_agent == AgentType.MATCHING:
            return AgentType.TEAM
        return None
    
    async def _log_decision(self, decision: WorkflowDecision):
        """Log workflow decision for observability"""
        workflow_id = decision.workflow_id
        
        if workflow_id not in self.workflow_decisions:
            self.workflow_decisions[workflow_id] = []
        
        self.workflow_decisions[workflow_id].append(decision)
        
        # In production, this would write to CloudWatch or other logging service
        logger.info(f"Decision logged: {decision.decision_id} for workflow {workflow_id}")
    
    def _update_performance_metrics(self, agent_type: AgentType, execution_time: float, confidence_score: float):
        """Update agent performance metrics"""
        metrics = self.performance_metrics[agent_type]
        
        # Update average response time
        total_time = metrics.average_response_time_ms * (metrics.successful_invocations - 1)
        metrics.average_response_time_ms = (total_time + execution_time) / metrics.successful_invocations
        
        # Update average confidence score
        total_confidence = metrics.average_confidence_score * (metrics.successful_invocations - 1)
        metrics.average_confidence_score = (total_confidence + confidence_score) / metrics.successful_invocations
        
        metrics.last_updated = datetime.utcnow()
    
    # Handoff rule implementations
    def _should_handoff_to_matching(self, context: AgentContext, result: Dict[str, Any]) -> bool:
        """Check if onboarding should handoff to matching"""
        return result.get('confidence_score', 0) >= 0.9
    
    def _should_escalate_to_human(self, context: AgentContext, result: Dict[str, Any]) -> bool:
        """Check if escalation to human is needed"""
        return len(context.conversation_history) > 10 and result.get('confidence_score', 0) < 0.5
    
    def _should_handoff_to_team(self, context: AgentContext, result: Dict[str, Any]) -> bool:
        """Check if matching should handoff to team"""
        return 'matches' in result and result.get('confidence_score', 0) >= 0.8
    
    def _should_return_to_onboarding(self, context: AgentContext, result: Dict[str, Any]) -> bool:
        """Check if should return to onboarding for more info"""
        return result.get('confidence_score', 0) < 0.6
    
    def _should_handoff_to_integration(self, context: AgentContext, result: Dict[str, Any]) -> bool:
        """Check if team should handoff to integration"""
        return result.get('team_health', 0) >= 0.8
    
    def _should_return_to_matching(self, context: AgentContext, result: Dict[str, Any]) -> bool:
        """Check if should return to matching"""
        return result.get('team_health', 0) < 0.5
    
    async def get_workflow_status(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get current workflow status and decisions"""
        if workflow_id not in self.active_workflows:
            return None
        
        context = self.active_workflows[workflow_id]
        decisions = self.workflow_decisions.get(workflow_id, [])
        
        return {
            'workflow_id': workflow_id,
            'status': 'active',
            'current_agent': context.current_agent.value,
            'confidence_scores': context.confidence_scores,
            'decision_count': len(decisions),
            'created_at': context.created_at.isoformat(),
            'updated_at': context.updated_at.isoformat()
        }
    
    def get_agent_performance_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get performance metrics for all agents"""
        return {
            agent_type.value: asdict(metrics)
            for agent_type, metrics in self.performance_metrics.items()
        }
    
    async def execute_handoff(self, context: AgentContext, from_agent: AgentType, to_agent: AgentType, handoff_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent handoff with context preservation"""
        logger.info(f"Executing handoff from {from_agent.value} to {to_agent.value}")
        
        # Update context
        context.current_agent = to_agent
        context.updated_at = datetime.utcnow()
        
        # Prepare handoff input data
        handoff_input = {
            'handoff_context': handoff_data,
            'previous_agent': from_agent.value,
            'user_profile': context.user_profile,
            'conversation_history': context.conversation_history[-3:]  # Last 3 exchanges
        }
        
        # Update handoff rate metrics
        from_metrics = self.performance_metrics[from_agent]
        if from_metrics.total_invocations > 0:
            from_metrics.handoff_rate = (from_metrics.handoff_rate * (from_metrics.total_invocations - 1) + 1) / from_metrics.total_invocations
        
        # Invoke the target agent
        return await self.invoke_agent(to_agent, context, handoff_input)