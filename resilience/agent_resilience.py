"""
Agent Resilience Module for Find Your Team

Implements agent unavailability fallback systems, load balancing, and graceful degradation
for AI agents (Onboarding, Matching, Team agents).

Features:
1. Agent health monitoring and failure detection
2. Automatic failover to backup agents or demo mode
3. Load balancing across multiple agent instances
4. Graceful degradation strategies
5. Agent performance optimization
6. Context preservation during agent handoffs
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from collections import deque, defaultdict
import hashlib

from .error_handling import (
    resilience_manager, ErrorCategory, ErrorSeverity, resilient_operation,
    CircuitBreaker, RetryManager, RecoveryStrategy
)

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Types of agents in the system"""
    ONBOARDING = "onboarding"
    MATCHING = "matching"
    TEAM = "team"
    GAMIFICATION = "gamification"


class AgentMode(Enum):
    """Agent operation modes"""
    FULL_AI = "full_ai"           # Full AI capability with AWS Bedrock
    FALLBACK_AI = "fallback_ai"   # Backup AI service or local model
    RULE_BASED = "rule_based"     # Rule-based logic without AI
    DEMO_MODE = "demo_mode"       # Demo responses with static data
    OFFLINE_MODE = "offline_mode" # Cached responses only


class FallbackStrategy(Enum):
    """Strategies for handling agent failures"""
    BACKUP_AGENT = "backup_agent"         # Switch to backup agent instance
    DEGRADED_AI = "degraded_ai"          # Use simpler AI model
    RULE_ENGINE = "rule_engine"          # Use rule-based responses
    CACHED_RESPONSES = "cached_responses" # Use cached/templated responses
    USER_SELF_SERVICE = "user_self_service" # Guide user through manual process
    DEFER_TO_HUMAN = "defer_to_human"    # Queue for human intervention


@dataclass
class AgentInstance:
    """Information about a specific agent instance"""
    agent_id: str
    agent_type: AgentType
    mode: AgentMode
    endpoint: Optional[str] = None
    is_primary: bool = False
    is_available: bool = True
    last_response_time: float = 1.0
    error_rate: float = 0.0
    request_count: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_health_check: datetime = field(default_factory=datetime.utcnow)
    circuit_breaker: Optional[CircuitBreaker] = None
    load_score: float = 0.0  # Current load (0.0 = idle, 1.0 = max capacity)
    
    def __post_init__(self):
        if self.circuit_breaker is None:
            self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=300)
    
    def update_metrics(self, response_time: float, success: bool):
        """Update agent performance metrics"""
        self.request_count += 1
        
        if success:
            self.successful_requests += 1
            # Exponential moving average for response time
            self.last_response_time = (self.last_response_time * 0.8) + (response_time * 0.2)
        else:
            self.failed_requests += 1
        
        # Update error rate
        self.error_rate = self.failed_requests / self.request_count if self.request_count > 0 else 0
        
        # Update availability based on recent performance
        self.is_available = self.error_rate < 0.5 and not self.circuit_breaker.state == 'OPEN'
    
    def get_health_score(self) -> float:
        """Calculate overall health score (0.0 to 1.0)"""
        if not self.is_available:
            return 0.0
        
        # Factors: error rate, response time, load
        error_score = max(0, 1 - (self.error_rate * 2))  # 50% error rate = 0 score
        response_score = max(0, 1 - (self.last_response_time / 10))  # 10s response = 0 score
        load_score = max(0, 1 - self.load_score)  # Full load = 0 score
        
        return (error_score + response_score + load_score) / 3


@dataclass
class AgentRequest:
    """Request to be processed by an agent"""
    request_id: str
    agent_type: AgentType
    user_id: str
    action: str
    parameters: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1 = highest, 10 = lowest
    created_at: datetime = field(default_factory=datetime.utcnow)
    timeout_seconds: int = 60
    fallback_strategy: FallbackStrategy = FallbackStrategy.BACKUP_AGENT
    max_retries: int = 2
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'request_id': self.request_id,
            'agent_type': self.agent_type.value,
            'user_id': self.user_id,
            'action': self.action,
            'parameters': self.parameters,
            'context': self.context,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'timeout_seconds': self.timeout_seconds,
            'fallback_strategy': self.fallback_strategy.value,
            'max_retries': self.max_retries,
            'retry_count': self.retry_count
        }


class AgentLoadBalancer:
    """Load balancer for distributing requests across agent instances"""
    
    def __init__(self):
        self.instances: Dict[AgentType, List[AgentInstance]] = defaultdict(list)
        self.request_history: deque = deque(maxlen=1000)
        
    def register_agent(self, instance: AgentInstance):
        """Register an agent instance"""
        self.instances[instance.agent_type].append(instance)
        logger.info(f"Registered {instance.agent_type.value} agent: {instance.agent_id}")
    
    def get_best_agent(self, agent_type: AgentType) -> Optional[AgentInstance]:
        """Select the best available agent for a request"""
        available_agents = [
            agent for agent in self.instances[agent_type]
            if agent.is_available and agent.circuit_breaker.state != 'OPEN'
        ]
        
        if not available_agents:
            return None
        
        # Sort by health score and load
        available_agents.sort(key=lambda a: (a.get_health_score(), -a.load_score), reverse=True)
        
        return available_agents[0]
    
    def get_backup_agent(self, agent_type: AgentType, exclude_id: str = None) -> Optional[AgentInstance]:
        """Get a backup agent instance"""
        backup_agents = [
            agent for agent in self.instances[agent_type]
            if agent.is_available and agent.agent_id != exclude_id
        ]
        
        if backup_agents:
            # Prefer agents in degraded modes as backups
            degraded_agents = [a for a in backup_agents if a.mode != AgentMode.FULL_AI]
            if degraded_agents:
                return min(degraded_agents, key=lambda a: a.load_score)
            else:
                return min(backup_agents, key=lambda a: a.load_score)
        
        return None
    
    def update_load(self, agent_id: str, load_delta: float):
        """Update agent load score"""
        for agent_type, agents in self.instances.items():
            for agent in agents:
                if agent.agent_id == agent_id:
                    agent.load_score = max(0, min(1, agent.load_score + load_delta))
                    break


class ResponseCache:
    """Cache for storing agent responses to enable offline operation"""
    
    def __init__(self, max_size: int = 1000):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, datetime] = {}
        self.max_size = max_size
    
    def _generate_key(self, agent_type: AgentType, action: str, parameters: Dict[str, Any]) -> str:
        """Generate cache key for request"""
        # Create deterministic key from request components
        param_str = json.dumps(parameters, sort_keys=True)
        key_data = f"{agent_type.value}:{action}:{param_str}"
        return hashlib.md5(key_data.encode()).hexdigest()[:16]
    
    def get(self, agent_type: AgentType, action: str, parameters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Retrieve cached response"""
        key = self._generate_key(agent_type, action, parameters)
        
        if key in self.cache:
            self.access_times[key] = datetime.utcnow()
            response = self.cache[key].copy()
            response['cached'] = True
            response['cache_timestamp'] = self.access_times[key].isoformat()
            return response
        
        return None
    
    def set(self, agent_type: AgentType, action: str, parameters: Dict[str, Any], response: Dict[str, Any]):
        """Store response in cache"""
        key = self._generate_key(agent_type, action, parameters)
        
        # Remove cache metadata before storing
        clean_response = response.copy()
        clean_response.pop('cached', None)
        clean_response.pop('cache_timestamp', None)
        clean_response.pop('agent_id', None)
        
        self.cache[key] = clean_response
        self.access_times[key] = datetime.utcnow()
        
        # Evict old entries if cache is full
        if len(self.cache) > self.max_size:
            self._evict_old_entries()
    
    def _evict_old_entries(self):
        """Remove oldest cache entries"""
        # Sort by access time and remove oldest 10%
        sorted_keys = sorted(self.access_times.items(), key=lambda x: x[1])
        evict_count = max(1, len(sorted_keys) // 10)
        
        for key, _ in sorted_keys[:evict_count]:
            self.cache.pop(key, None)
            self.access_times.pop(key, None)


class FallbackEngine:
    """Engine for providing fallback responses when agents are unavailable"""
    
    def __init__(self):
        self.response_templates = {
            AgentType.ONBOARDING: {
                'start_conversation': {
                    'message': "Welcome to Find Your Team! I'm here to help you discover your purpose and connect with like-minded people. Let's start by learning about your values and what matters most to you.",
                    'confidence_score': 0.7,
                    'mode': 'demo'
                },
                'process_response': {
                    'message': "Thank you for sharing that with me. Your insights help me understand your perspective better. What else would you like to explore about your purpose?",
                    'confidence_score': 0.6,
                    'mode': 'demo'
                }
            },
            AgentType.MATCHING: {
                'find_matches': {
                    'matches': [
                        {
                            'team_name': 'Community Education Initiative',
                            'match_score': 0.85,
                            'compatibility_reasons': ['Shared values in education', 'Similar skills in communication'],
                            'team_location': 'Cape Town'
                        },
                        {
                            'team_name': 'Local Sustainability Project',
                            'match_score': 0.78,
                            'compatibility_reasons': ['Environmental passion', 'Problem-solving skills'],
                            'team_location': 'Johannesburg'
                        }
                    ],
                    'confidence_score': 0.75,
                    'mode': 'demo'
                }
            },
            AgentType.TEAM: {
                'analyze_performance': {
                    'team_health': 0.82,
                    'performance_metrics': {
                        'productivity': 0.78,
                        'collaboration': 0.85,
                        'satisfaction': 0.80
                    },
                    'recommendations': [
                        'Increase communication frequency',
                        'Implement regular check-ins',
                        'Celebrate team achievements'
                    ],
                    'confidence_score': 0.7,
                    'mode': 'demo'
                }
            },
            AgentType.GAMIFICATION: {
                'calculate_progress': {
                    'purpose_alignment_score': 0.75,
                    'skill_development': 0.68,
                    'engagement_level': 0.82,
                    'next_milestone': 'Complete 3 more challenges to reach Level 5',
                    'confidence_score': 0.8,
                    'mode': 'demo'
                }
            }
        }
    
    def get_fallback_response(self, agent_type: AgentType, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback response for failed agent request"""
        
        # Try to find specific template
        agent_templates = self.response_templates.get(agent_type, {})
        template = agent_templates.get(action)
        
        if template:
            response = template.copy()
            response['fallback'] = True
            response['timestamp'] = datetime.utcnow().isoformat()
            return response
        
        # Generate generic response
        return {
            'message': f"I'm currently experiencing some technical difficulties. Please try again in a few moments, or continue with basic functionality.",
            'action': action,
            'status': 'fallback_mode',
            'confidence_score': 0.5,
            'fallback': True,
            'timestamp': datetime.utcnow().isoformat(),
            'suggestions': [
                'Refresh the page and try again',
                'Check your internet connection',
                'Contact support if the issue persists'
            ]
        }
    
    def get_rule_based_response(self, agent_type: AgentType, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate rule-based response without AI"""
        
        if agent_type == AgentType.ONBOARDING:
            return self._rule_based_onboarding(action, parameters)
        elif agent_type == AgentType.MATCHING:
            return self._rule_based_matching(action, parameters)
        elif agent_type == AgentType.TEAM:
            return self._rule_based_team_analysis(action, parameters)
        elif agent_type == AgentType.GAMIFICATION:
            return self._rule_based_gamification(action, parameters)
        
        return self.get_fallback_response(agent_type, action, parameters)
    
    def _rule_based_onboarding(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based onboarding responses"""
        if action == 'start_conversation':
            return {
                'message': "Welcome! Let's discover your purpose together. What topics are you most passionate about?",
                'confidence_score': 0.8,
                'mode': 'rule_based',
                'suggested_topics': ['Education', 'Healthcare', 'Environment', 'Community Development', 'Technology']
            }
        
        user_input = parameters.get('user_input', '').lower()
        
        # Simple keyword-based responses
        if any(word in user_input for word in ['help', 'community', 'support']):
            return {
                'message': "It sounds like helping others and community support are important to you. That's wonderful! Can you tell me more about what specific aspects of community work inspire you?",
                'confidence_score': 0.7,
                'mode': 'rule_based'
            }
        elif any(word in user_input for word in ['education', 'teach', 'learn']):
            return {
                'message': "Education is such a powerful way to create positive change! What aspects of education resonate most with you - teaching, curriculum development, or perhaps educational equity?",
                'confidence_score': 0.75,
                'mode': 'rule_based'
            }
        else:
            return {
                'message': "That's interesting! Tell me more about what drives your passion in this area.",
                'confidence_score': 0.6,
                'mode': 'rule_based'
            }
    
    def _rule_based_matching(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based team matching"""
        user_profile = parameters.get('user_profile', {})
        
        # Simple matching based on keywords
        interests = user_profile.get('interests', [])
        location = user_profile.get('location', 'Unknown')
        
        matches = []
        if 'education' in str(interests).lower():
            matches.append({
                'team_name': 'Local Education Support Team',
                'match_score': 0.8,
                'compatibility_reasons': ['Shared interest in education'],
                'team_location': location
            })
        
        if 'community' in str(interests).lower():
            matches.append({
                'team_name': 'Community Development Group',
                'match_score': 0.75,
                'compatibility_reasons': ['Community focus alignment'],
                'team_location': location
            })
        
        return {
            'matches': matches[:3],  # Limit to top 3
            'confidence_score': 0.7,
            'mode': 'rule_based',
            'total_teams_considered': 25
        }
    
    def _rule_based_team_analysis(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based team performance analysis"""
        team_data = parameters.get('team_data', {})
        
        # Simple analysis based on available metrics
        member_count = len(team_data.get('members', []))
        activity_level = team_data.get('recent_activity_count', 0)
        
        # Calculate basic health score
        health_score = min(1.0, (member_count * 0.1 + activity_level * 0.05))
        
        recommendations = []
        if member_count < 3:
            recommendations.append("Consider recruiting more team members")
        if activity_level < 5:
            recommendations.append("Increase team activity and engagement")
        
        return {
            'team_health': health_score,
            'performance_metrics': {
                'team_size': member_count,
                'activity_level': activity_level / 10,  # Normalize
                'estimated_productivity': health_score * 0.8
            },
            'recommendations': recommendations,
            'confidence_score': 0.65,
            'mode': 'rule_based'
        }
    
    def _rule_based_gamification(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based gamification calculations"""
        user_data = parameters.get('user_data', {})
        
        # Simple scoring based on available data
        completed_tasks = len(user_data.get('completed_tasks', []))
        engagement_days = user_data.get('engagement_days', 0)
        
        purpose_score = min(1.0, completed_tasks * 0.1)
        engagement_score = min(1.0, engagement_days * 0.05)
        
        return {
            'purpose_alignment_score': purpose_score,
            'engagement_level': engagement_score,
            'total_points': completed_tasks * 10,
            'next_milestone': f"Complete {5 - (completed_tasks % 5)} more tasks for bonus points",
            'confidence_score': 0.75,
            'mode': 'rule_based'
        }


class AgentResilience:
    """Main agent resilience coordinator"""
    
    def __init__(self):
        self.load_balancer = AgentLoadBalancer()
        self.response_cache = ResponseCache()
        self.fallback_engine = FallbackEngine()
        self.request_queue: deque = deque()
        self.processing_requests: Dict[str, AgentRequest] = {}
        self.request_timeout_tasks: Dict[str, asyncio.Task] = {}
        
        # Initialize default agents
        self._register_default_agents()
    
    def _register_default_agents(self):
        """Register default agent instances"""
        # Primary AI agents
        self.load_balancer.register_agent(AgentInstance(
            agent_id="onboarding_primary",
            agent_type=AgentType.ONBOARDING,
            mode=AgentMode.FULL_AI,
            is_primary=True
        ))
        
        self.load_balancer.register_agent(AgentInstance(
            agent_id="matching_primary", 
            agent_type=AgentType.MATCHING,
            mode=AgentMode.FULL_AI,
            is_primary=True
        ))
        
        self.load_balancer.register_agent(AgentInstance(
            agent_id="team_primary",
            agent_type=AgentType.TEAM,
            mode=AgentMode.FULL_AI,
            is_primary=True
        ))
        
        self.load_balancer.register_agent(AgentInstance(
            agent_id="gamification_primary",
            agent_type=AgentType.GAMIFICATION,
            mode=AgentMode.FULL_AI,
            is_primary=True
        ))
        
        # Fallback agents
        self.load_balancer.register_agent(AgentInstance(
            agent_id="onboarding_fallback",
            agent_type=AgentType.ONBOARDING,
            mode=AgentMode.RULE_BASED,
            is_primary=False
        ))
        
        self.load_balancer.register_agent(AgentInstance(
            agent_id="matching_fallback",
            agent_type=AgentType.MATCHING,
            mode=AgentMode.RULE_BASED,
            is_primary=False
        ))
        
        logger.info("Default agent instances registered")
    
    @resilient_operation(component="agent_resilience")
    async def process_request(self, request: AgentRequest) -> Dict[str, Any]:
        """Process agent request with resilience handling"""
        
        # Try cache first for non-critical requests
        if request.priority > 3:
            cached_response = self.response_cache.get(
                request.agent_type, request.action, request.parameters
            )
            if cached_response:
                logger.info(f"Returning cached response for {request.request_id}")
                return cached_response
        
        # Get best available agent
        agent = self.load_balancer.get_best_agent(request.agent_type)
        
        if not agent:
            # No agents available, use fallback
            logger.warning(f"No agents available for {request.agent_type.value}, using fallback")
            return await self._handle_no_agent_available(request)
        
        # Process request with selected agent
        try:
            # Update agent load
            self.load_balancer.update_load(agent.agent_id, 0.1)
            
            # Set timeout for request
            timeout_task = asyncio.create_task(
                self._request_timeout(request.request_id, request.timeout_seconds)
            )
            self.request_timeout_tasks[request.request_id] = timeout_task
            
            # Process request
            start_time = time.time()
            response = await self._call_agent(agent, request)
            response_time = time.time() - start_time
            
            # Cancel timeout
            timeout_task.cancel()
            self.request_timeout_tasks.pop(request.request_id, None)
            
            # Update agent metrics
            agent.update_metrics(response_time, True)
            self.load_balancer.update_load(agent.agent_id, -0.1)
            
            # Cache successful response
            if response.get('confidence_score', 0) > 0.7:
                self.response_cache.set(
                    request.agent_type, request.action, request.parameters, response
                )
            
            return response
            
        except asyncio.TimeoutError:
            logger.warning(f"Request {request.request_id} timed out")
            agent.update_metrics(request.timeout_seconds, False)
            self.load_balancer.update_load(agent.agent_id, -0.1)
            return await self._handle_agent_failure(request, agent, "timeout")
            
        except Exception as e:
            logger.error(f"Agent {agent.agent_id} failed for request {request.request_id}: {e}")
            agent.update_metrics(time.time() - start_time, False)
            self.load_balancer.update_load(agent.agent_id, -0.1)
            return await self._handle_agent_failure(request, agent, str(e))
    
    async def _call_agent(self, agent: AgentInstance, request: AgentRequest) -> Dict[str, Any]:
        """Call specific agent instance"""
        
        if agent.mode == AgentMode.FULL_AI:
            # Call actual AI agent (would integrate with existing agent infrastructure)
            return await self._call_ai_agent(agent, request)
        elif agent.mode == AgentMode.RULE_BASED:
            # Use rule-based fallback
            response = self.fallback_engine.get_rule_based_response(
                request.agent_type, request.action, request.parameters
            )
            response['agent_id'] = agent.agent_id
            return response
        elif agent.mode == AgentMode.DEMO_MODE:
            # Use demo responses
            response = self.fallback_engine.get_fallback_response(
                request.agent_type, request.action, request.parameters
            )
            response['agent_id'] = agent.agent_id
            return response
        else:
            raise Exception(f"Unsupported agent mode: {agent.mode}")
    
    async def _call_ai_agent(self, agent: AgentInstance, request: AgentRequest) -> Dict[str, Any]:
        """Call AI agent (integration point with existing infrastructure)"""
        
        # This would integrate with the existing agent infrastructure
        # For now, simulate AI response with some processing delay
        await asyncio.sleep(0.5)  # Simulate processing time
        
        # Integration point: Replace this with actual agent calls
        # Example: return await bedrock_agent_runtime.invoke_agent(...)
        
        return {
            'message': f"AI response for {request.action} (simulated)",
            'confidence_score': 0.85,
            'agent_id': agent.agent_id,
            'mode': agent.mode.value,
            'processing_time': 0.5
        }
    
    async def _handle_agent_failure(self, request: AgentRequest, failed_agent: AgentInstance, error: str) -> Dict[str, Any]:
        """Handle agent failure with appropriate fallback strategy"""
        
        if request.retry_count < request.max_retries:
            # Try backup agent
            backup_agent = self.load_balancer.get_backup_agent(
                request.agent_type, exclude_id=failed_agent.agent_id
            )
            
            if backup_agent:
                logger.info(f"Retrying with backup agent {backup_agent.agent_id}")
                request.retry_count += 1
                return await self.process_request(request)
        
        # Apply fallback strategy
        strategy = request.fallback_strategy
        
        if strategy == FallbackStrategy.CACHED_RESPONSES:
            cached_response = self.response_cache.get(
                request.agent_type, request.action, request.parameters
            )
            if cached_response:
                cached_response['fallback_reason'] = f"Agent failure: {error}"
                return cached_response
        
        elif strategy == FallbackStrategy.RULE_ENGINE:
            response = self.fallback_engine.get_rule_based_response(
                request.agent_type, request.action, request.parameters
            )
            response['fallback_reason'] = f"Agent failure: {error}"
            return response
        
        elif strategy == FallbackStrategy.USER_SELF_SERVICE:
            return {
                'status': 'self_service_mode',
                'message': "I'm experiencing some technical difficulties. Here are some things you can try:",
                'self_service_options': self._get_self_service_options(request.agent_type, request.action),
                'fallback_reason': f"Agent failure: {error}",
                'confidence_score': 0.3
            }
        
        # Default fallback
        response = self.fallback_engine.get_fallback_response(
            request.agent_type, request.action, request.parameters
        )
        response['fallback_reason'] = f"Agent failure: {error}"
        return response
    
    async def _handle_no_agent_available(self, request: AgentRequest) -> Dict[str, Any]:
        """Handle case when no agents are available"""
        
        # Try cached response first
        cached_response = self.response_cache.get(
            request.agent_type, request.action, request.parameters
        )
        if cached_response:
            cached_response['fallback_reason'] = "No agents available"
            return cached_response
        
        # Use fallback engine
        response = self.fallback_engine.get_fallback_response(
            request.agent_type, request.action, request.parameters
        )
        response['fallback_reason'] = "No agents available"
        return response
    
    def _get_self_service_options(self, agent_type: AgentType, action: str) -> List[Dict[str, str]]:
        """Get self-service options for specific agent actions"""
        
        options = []
        
        if agent_type == AgentType.ONBOARDING:
            options = [
                {
                    'title': 'Continue with guided questions',
                    'description': 'Answer a series of questions about your interests and values',
                    'action': 'guided_onboarding'
                },
                {
                    'title': 'Browse existing teams',
                    'description': 'Explore teams in your area and see which ones interest you',
                    'action': 'browse_teams'
                }
            ]
        
        elif agent_type == AgentType.MATCHING:
            options = [
                {
                    'title': 'Search teams by location',
                    'description': 'Find teams near you by browsing location-based listings',
                    'action': 'location_search'
                },
                {
                    'title': 'Filter by interests',
                    'description': 'Use interest filters to find relevant teams',
                    'action': 'interest_filter'
                }
            ]
        
        return options
    
    async def _request_timeout(self, request_id: str, timeout_seconds: int):
        """Handle request timeout"""
        try:
            await asyncio.sleep(timeout_seconds)
            # If we reach here, the request timed out
            if request_id in self.processing_requests:
                logger.warning(f"Request {request_id} timed out after {timeout_seconds}s")
                # The actual timeout handling is done in process_request
        except asyncio.CancelledError:
            # Request completed before timeout
            pass
    
    def get_agent_health_status(self) -> Dict[str, Any]:
        """Get comprehensive agent health status"""
        
        health_by_type = {}
        
        for agent_type, agents in self.load_balancer.instances.items():
            type_health = {
                'total_agents': len(agents),
                'healthy_agents': len([a for a in agents if a.is_available]),
                'primary_healthy': any(a.is_primary and a.is_available for a in agents),
                'agents': []
            }
            
            for agent in agents:
                type_health['agents'].append({
                    'agent_id': agent.agent_id,
                    'mode': agent.mode.value,
                    'is_primary': agent.is_primary,
                    'is_available': agent.is_available,
                    'health_score': agent.get_health_score(),
                    'error_rate': agent.error_rate,
                    'load_score': agent.load_score,
                    'last_response_time': agent.last_response_time,
                    'circuit_breaker_state': agent.circuit_breaker.state if agent.circuit_breaker else 'UNKNOWN'
                })
            
            health_by_type[agent_type.value] = type_health
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'agent_types': health_by_type,
            'cache_stats': {
                'cached_responses': len(self.response_cache.cache),
                'cache_hit_rate': getattr(self, '_cache_hit_rate', 0.0)
            }
        }
    
    async def health_check_all_agents(self):
        """Perform health check on all registered agents"""
        
        for agent_type, agents in self.load_balancer.instances.items():
            for agent in agents:
                try:
                    # Simple health check request
                    test_request = AgentRequest(
                        request_id=f"health_check_{agent.agent_id}_{int(time.time())}",
                        agent_type=agent_type,
                        user_id="system",
                        action="health_check",
                        parameters={},
                        timeout_seconds=5,
                        max_retries=0
                    )
                    
                    start_time = time.time()
                    await self._call_agent(agent, test_request)
                    response_time = time.time() - start_time
                    
                    agent.update_metrics(response_time, True)
                    agent.last_health_check = datetime.utcnow()
                    
                except Exception as e:
                    logger.warning(f"Health check failed for {agent.agent_id}: {e}")
                    agent.update_metrics(5.0, False)
                    agent.last_health_check = datetime.utcnow()


# Global agent resilience instance
agent_resilience = AgentResilience()


async def resilient_agent_call(
    agent_type: AgentType, 
    action: str, 
    parameters: Dict[str, Any],
    user_id: str = "anonymous",
    priority: int = 5,
    timeout: int = 60
) -> Dict[str, Any]:
    """Global function for making resilient agent calls"""
    
    request = AgentRequest(
        request_id=hashlib.md5(f"{agent_type.value}{action}{user_id}{time.time()}".encode()).hexdigest()[:12],
        agent_type=agent_type,
        user_id=user_id,
        action=action,
        parameters=parameters,
        priority=priority,
        timeout_seconds=timeout
    )
    
    return await agent_resilience.process_request(request)


def get_agent_health() -> Dict[str, Any]:
    """Get current agent health status"""
    return agent_resilience.get_agent_health_status()


# Auto-start agent health monitoring
async def start_agent_monitoring():
    """Start agent health monitoring"""
    while True:
        try:
            await agent_resilience.health_check_all_agents()
            await asyncio.sleep(300)  # Check every 5 minutes
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Agent monitoring error: {e}")
            await asyncio.sleep(600)  # Back off on error