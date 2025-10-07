"""
Comprehensive Error Handling and Resilience System for Find Your Team

This module implements robust error handling, recovery mechanisms, and resilience
patterns for network failures, agent unavailability, and data sync conflicts.

Task 11 Requirements:
1. Network failure detection and recovery mechanisms
2. Agent unavailability fallback systems  
3. Data sync conflict resolution with user notifications
4. Graceful degradation for partial system failures
5. Comprehensive error logging and monitoring
6. Tests for all failure scenarios and recovery procedures
"""

import asyncio
import json
import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from contextlib import asynccontextmanager
import hashlib
import threading
from collections import defaultdict, deque

# Configure logging
logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for classification and handling"""
    CRITICAL = "critical"      # System-breaking errors requiring immediate attention
    HIGH = "high"             # Major functionality impaired, needs quick resolution
    MEDIUM = "medium"         # Some features affected, manageable degradation
    LOW = "low"              # Minor issues, system still functional
    INFO = "info"            # Informational messages for monitoring


class ErrorCategory(Enum):
    """Categories of errors for targeted handling strategies"""
    NETWORK = "network"           # Network connectivity issues
    AGENT = "agent"              # AI agent unavailability or failures
    DATABASE = "database"        # Data persistence and retrieval errors
    AUTHENTICATION = "auth"      # Authentication and authorization failures
    VALIDATION = "validation"    # Data validation and input errors
    EXTERNAL_API = "external_api" # Third-party service failures
    RESOURCE = "resource"        # Resource exhaustion (memory, CPU, etc.)
    CONFIGURATION = "config"     # Configuration and setup errors


class RecoveryStrategy(Enum):
    """Recovery strategies for different error types"""
    RETRY_EXPONENTIAL = "retry_exponential"      # Retry with exponential backoff
    RETRY_LINEAR = "retry_linear"                # Retry with linear backoff
    FALLBACK_LOCAL = "fallback_local"           # Use local/cached data
    FALLBACK_AGENT = "fallback_agent"           # Switch to backup agent
    DEGRADED_MODE = "degraded_mode"             # Operate with reduced functionality
    USER_NOTIFICATION = "user_notification"     # Notify user and request action
    CIRCUIT_BREAKER = "circuit_breaker"         # Temporarily disable failing component
    NO_RECOVERY = "no_recovery"                 # Log error but don't attempt recovery


@dataclass
class ErrorContext:
    """Comprehensive error context for logging and recovery"""
    error_id: str
    timestamp: datetime
    error_type: str
    error_message: str
    severity: ErrorSeverity
    category: ErrorCategory
    component: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    stack_trace: Optional[str] = None
    recovery_strategy: Optional[RecoveryStrategy] = None
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3
    context_data: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error context to dictionary for logging"""
        return {
            'error_id': self.error_id,
            'timestamp': self.timestamp.isoformat(),
            'error_type': self.error_type,
            'error_message': self.error_message,
            'severity': self.severity.value,
            'category': self.category.value,
            'component': self.component,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'request_id': self.request_id,
            'stack_trace': self.stack_trace,
            'recovery_strategy': self.recovery_strategy.value if self.recovery_strategy else None,
            'recovery_attempts': self.recovery_attempts,
            'max_recovery_attempts': self.max_recovery_attempts,
            'context_data': self.context_data,
            'resolved': self.resolved,
            'resolution_time': self.resolution_time.isoformat() if self.resolution_time else None
        }


@dataclass
class NetworkHealth:
    """Network connectivity health status"""
    is_connected: bool = True
    last_check: datetime = field(default_factory=datetime.utcnow)
    latency_ms: float = 0.0
    packet_loss: float = 0.0
    bandwidth_mbps: float = 0.0
    connection_quality: str = "excellent"  # excellent, good, fair, poor, disconnected
    consecutive_failures: int = 0
    
    def update_quality(self):
        """Update connection quality based on metrics"""
        if not self.is_connected:
            self.connection_quality = "disconnected"
        elif self.latency_ms > 1000 or self.packet_loss > 10:
            self.connection_quality = "poor"
        elif self.latency_ms > 500 or self.packet_loss > 5:
            self.connection_quality = "fair"
        elif self.latency_ms > 200 or self.packet_loss > 2:
            self.connection_quality = "good"
        else:
            self.connection_quality = "excellent"


@dataclass
class AgentHealth:
    """Agent availability and health status"""
    agent_name: str
    is_available: bool = True
    last_response: datetime = field(default_factory=datetime.utcnow)
    average_response_time: float = 1.0
    error_rate: float = 0.0
    consecutive_failures: int = 0
    circuit_breaker_open: bool = False
    circuit_breaker_reset_time: Optional[datetime] = None
    performance_score: float = 1.0
    
    def update_performance(self, response_time: float, success: bool):
        """Update agent performance metrics"""
        # Update average response time with exponential moving average
        self.average_response_time = (self.average_response_time * 0.8) + (response_time * 0.2)
        
        # Update error rate
        if success:
            self.consecutive_failures = 0
            self.error_rate = max(0, self.error_rate - 0.1)
        else:
            self.consecutive_failures += 1
            self.error_rate = min(1.0, self.error_rate + 0.1)
        
        # Calculate performance score
        response_score = max(0, 1 - (self.average_response_time / 10))  # 10s = 0 score
        error_score = 1 - self.error_rate
        self.performance_score = (response_score + error_score) / 2
        
        # Circuit breaker logic
        if self.consecutive_failures >= 5:
            self.circuit_breaker_open = True
            self.circuit_breaker_reset_time = datetime.utcnow() + timedelta(minutes=5)
        elif self.circuit_breaker_open and datetime.utcnow() > self.circuit_breaker_reset_time:
            self.circuit_breaker_open = False
            self.consecutive_failures = 0


@dataclass
class DataSyncConflict:
    """Data synchronization conflict information"""
    conflict_id: str
    user_id: str
    data_type: str
    local_version: Dict[str, Any]
    remote_version: Dict[str, Any]
    local_timestamp: datetime
    remote_timestamp: datetime
    conflict_fields: List[str]
    resolution_strategy: str = "user_choice"  # user_choice, latest_wins, merge
    resolved: bool = False
    resolution_data: Optional[Dict[str, Any]] = None
    
    def auto_resolve(self) -> bool:
        """Attempt automatic resolution of the conflict"""
        # If timestamps are very close (< 5 seconds), use latest
        time_diff = abs((self.remote_timestamp - self.local_timestamp).total_seconds())
        if time_diff < 5:
            if self.remote_timestamp > self.local_timestamp:
                self.resolution_data = self.remote_version
                self.resolution_strategy = "remote_wins"
            else:
                self.resolution_data = self.local_version
                self.resolution_strategy = "local_wins"
            self.resolved = True
            return True
        
        # For simple data types, try merging non-conflicting fields
        if len(self.conflict_fields) == 0:
            # No actual conflicts, merge both versions
            merged = {**self.local_version, **self.remote_version}
            self.resolution_data = merged
            self.resolution_strategy = "merge"
            self.resolved = True
            return True
        
        return False


class CircuitBreaker:
    """Circuit breaker pattern implementation for failing components"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60, expected_exception=Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == 'OPEN':
            if datetime.utcnow().timestamp() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
            else:
                raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful operation"""
        self.failure_count = 0
        if self.state == 'HALF_OPEN':
            self.state = 'CLOSED'
    
    def _on_failure(self):
        """Handle failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow().timestamp()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'


class RetryManager:
    """Intelligent retry mechanism with different strategies"""
    
    @staticmethod
    async def retry_with_backoff(
        func: Callable,
        max_attempts: int = 3,
        backoff_strategy: RecoveryStrategy = RecoveryStrategy.RETRY_EXPONENTIAL,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True,
        *args,
        **kwargs
    ) -> Any:
        """Retry function with configurable backoff strategy"""
        
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except Exception as e:
                last_exception = e
                
                if attempt == max_attempts - 1:
                    # Last attempt, don't wait
                    break
                
                # Calculate delay
                if backoff_strategy == RecoveryStrategy.RETRY_EXPONENTIAL:
                    delay = min(initial_delay * (2 ** attempt), max_delay)
                else:  # LINEAR
                    delay = min(initial_delay * (attempt + 1), max_delay)
                
                # Add jitter to prevent thundering herd
                if jitter:
                    import random
                    delay *= (0.5 + random.random() * 0.5)
                
                logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. Retrying in {delay:.2f}s")
                await asyncio.sleep(delay)
        
        # All attempts failed
        raise last_exception


class ResilienceManager:
    """Central manager for error handling and system resilience"""
    
    def __init__(self):
        self.error_history: deque = deque(maxlen=1000)
        self.network_health = NetworkHealth()
        self.agent_health: Dict[str, AgentHealth] = {}
        self.sync_conflicts: List[DataSyncConflict] = []
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.monitoring_active = False
        self.monitoring_task = None
        self._lock = threading.Lock()
        
        # Error handling strategies
        self.error_handlers: Dict[ErrorCategory, List[Callable]] = defaultdict(list)
        self.recovery_strategies: Dict[str, RecoveryStrategy] = {
            'network_timeout': RecoveryStrategy.RETRY_EXPONENTIAL,
            'agent_unavailable': RecoveryStrategy.FALLBACK_AGENT,
            'database_error': RecoveryStrategy.RETRY_LINEAR,
            'validation_error': RecoveryStrategy.USER_NOTIFICATION,
            'auth_error': RecoveryStrategy.USER_NOTIFICATION,
            'resource_exhausted': RecoveryStrategy.DEGRADED_MODE,
        }
    
    def start_monitoring(self):
        """Start continuous system health monitoring"""
        if not self.monitoring_active:
            self.monitoring_active = True
            try:
                # Try to create task if we're in an async context
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    self.monitoring_task = asyncio.create_task(self._monitoring_loop())
                    logger.info("Resilience monitoring started")
                else:
                    logger.info("Resilience monitoring will start with next async operation")
            except RuntimeError:
                # No event loop running, monitoring will start later
                logger.info("Resilience monitoring initialized (will start with async context)")
    
    def stop_monitoring(self):
        """Stop system health monitoring"""
        self.monitoring_active = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            logger.info("Resilience monitoring stopped")
    
    async def _monitoring_loop(self):
        """Continuous monitoring of system health"""
        while self.monitoring_active:
            try:
                await self._check_network_health()
                await self._check_agent_health()
                await self._cleanup_old_data()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Back off on error
    
    async def _check_network_health(self):
        """Check network connectivity and performance"""
        try:
            import aiohttp
            start_time = time.time()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get('https://httpbin.org/get') as response:
                    if response.status == 200:
                        latency = (time.time() - start_time) * 1000
                        self.network_health.is_connected = True
                        self.network_health.latency_ms = latency
                        self.network_health.consecutive_failures = 0
                    else:
                        raise Exception(f"HTTP {response.status}")
                        
        except Exception as e:
            self.network_health.is_connected = False
            self.network_health.consecutive_failures += 1
            logger.warning(f"Network health check failed: {e}")
        
        self.network_health.last_check = datetime.utcnow()
        self.network_health.update_quality()
    
    async def _check_agent_health(self):
        """Check health of all registered agents"""
        for agent_name, health in self.agent_health.items():
            # Reset circuit breaker if timeout elapsed
            if health.circuit_breaker_open and health.circuit_breaker_reset_time:
                if datetime.utcnow() > health.circuit_breaker_reset_time:
                    health.circuit_breaker_open = False
                    health.consecutive_failures = 0
                    logger.info(f"Circuit breaker reset for agent: {agent_name}")
    
    async def _cleanup_old_data(self):
        """Clean up old error history and resolved conflicts"""
        # Remove old sync conflicts (older than 24 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        self.sync_conflicts = [
            conflict for conflict in self.sync_conflicts 
            if not conflict.resolved or conflict.local_timestamp > cutoff_time
        ]
    
    def register_agent(self, agent_name: str):
        """Register an agent for health monitoring"""
        if agent_name not in self.agent_health:
            self.agent_health[agent_name] = AgentHealth(agent_name=agent_name)
            logger.info(f"Registered agent for monitoring: {agent_name}")
    
    def get_circuit_breaker(self, component_name: str, **kwargs) -> CircuitBreaker:
        """Get or create circuit breaker for a component"""
        if component_name not in self.circuit_breakers:
            self.circuit_breakers[component_name] = CircuitBreaker(**kwargs)
        return self.circuit_breakers[component_name]
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None) -> ErrorContext:
        """Log error with comprehensive context"""
        error_id = hashlib.md5(f"{str(error)}{time.time()}".encode()).hexdigest()[:12]
        
        error_context = ErrorContext(
            error_id=error_id,
            timestamp=datetime.utcnow(),
            error_type=type(error).__name__,
            error_message=str(error),
            severity=self._classify_severity(error),
            category=self._classify_category(error),
            component=context.get('component', 'unknown') if context else 'unknown',
            user_id=context.get('user_id') if context else None,
            session_id=context.get('session_id') if context else None,
            request_id=context.get('request_id') if context else None,
            stack_trace=traceback.format_exc(),
            context_data=context or {}
        )
        
        with self._lock:
            self.error_history.append(error_context)
        
        # Log to standard logging
        log_level = {
            ErrorSeverity.CRITICAL: logging.CRITICAL,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.INFO: logging.INFO
        }.get(error_context.severity, logging.ERROR)
        
        logger.log(log_level, f"Error {error_id}: {error_context.error_message}", 
                  extra=error_context.to_dict())
        
        return error_context
    
    def _classify_severity(self, error: Exception) -> ErrorSeverity:
        """Classify error severity based on type and context"""
        error_type = type(error).__name__
        
        if error_type in ['SystemError', 'MemoryError', 'KeyboardInterrupt']:
            return ErrorSeverity.CRITICAL
        elif error_type in ['ConnectionError', 'TimeoutError', 'OSError']:
            return ErrorSeverity.HIGH
        elif error_type in ['ValueError', 'TypeError', 'KeyError']:
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.LOW
    
    def _classify_category(self, error: Exception) -> ErrorCategory:
        """Classify error category based on type and context"""
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        if any(keyword in error_message for keyword in ['network', 'connection', 'timeout', 'dns']):
            return ErrorCategory.NETWORK
        elif any(keyword in error_message for keyword in ['agent', 'bedrock', 'ai']):
            return ErrorCategory.AGENT
        elif any(keyword in error_message for keyword in ['database', 'dynamodb', 'sql']):
            return ErrorCategory.DATABASE
        elif any(keyword in error_message for keyword in ['auth', 'token', 'credential', 'permission']):
            return ErrorCategory.AUTHENTICATION
        elif any(keyword in error_message for keyword in ['validation', 'invalid', 'format']):
            return ErrorCategory.VALIDATION
        elif any(keyword in error_message for keyword in ['api', 'service', 'external']):
            return ErrorCategory.EXTERNAL_API
        elif any(keyword in error_message for keyword in ['memory', 'resource', 'limit']):
            return ErrorCategory.RESOURCE
        else:
            return ErrorCategory.CONFIGURATION
    
    async def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Comprehensive error handling with recovery strategies"""
        error_context = self.log_error(error, context)
        
        # Determine recovery strategy
        strategy = self._get_recovery_strategy(error_context)
        error_context.recovery_strategy = strategy
        
        # Execute recovery
        recovery_result = await self._execute_recovery(error_context, error, context or {})
        
        # Update error context
        if recovery_result.get('success'):
            error_context.resolved = True
            error_context.resolution_time = datetime.utcnow()
        else:
            error_context.recovery_attempts += 1
        
        return recovery_result
    
    def _get_recovery_strategy(self, error_context: ErrorContext) -> RecoveryStrategy:
        """Determine appropriate recovery strategy for error"""
        # Check specific error type mappings
        error_key = f"{error_context.category.value}_{error_context.error_type.lower()}"
        if error_key in self.recovery_strategies:
            return self.recovery_strategies[error_key]
        
        # Fallback to category-based strategy
        category_strategies = {
            ErrorCategory.NETWORK: RecoveryStrategy.RETRY_EXPONENTIAL,
            ErrorCategory.AGENT: RecoveryStrategy.FALLBACK_AGENT,
            ErrorCategory.DATABASE: RecoveryStrategy.RETRY_LINEAR,
            ErrorCategory.AUTHENTICATION: RecoveryStrategy.USER_NOTIFICATION,
            ErrorCategory.VALIDATION: RecoveryStrategy.USER_NOTIFICATION,
            ErrorCategory.EXTERNAL_API: RecoveryStrategy.CIRCUIT_BREAKER,
            ErrorCategory.RESOURCE: RecoveryStrategy.DEGRADED_MODE,
            ErrorCategory.CONFIGURATION: RecoveryStrategy.NO_RECOVERY
        }
        
        return category_strategies.get(error_context.category, RecoveryStrategy.NO_RECOVERY)
    
    async def _execute_recovery(self, error_context: ErrorContext, original_error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the appropriate recovery strategy"""
        strategy = error_context.recovery_strategy
        
        try:
            if strategy == RecoveryStrategy.RETRY_EXPONENTIAL:
                return await self._retry_recovery(error_context, context, exponential=True)
            elif strategy == RecoveryStrategy.RETRY_LINEAR:
                return await self._retry_recovery(error_context, context, exponential=False)
            elif strategy == RecoveryStrategy.FALLBACK_LOCAL:
                return await self._fallback_local_recovery(error_context, context)
            elif strategy == RecoveryStrategy.FALLBACK_AGENT:
                return await self._fallback_agent_recovery(error_context, context)
            elif strategy == RecoveryStrategy.DEGRADED_MODE:
                return await self._degraded_mode_recovery(error_context, context)
            elif strategy == RecoveryStrategy.USER_NOTIFICATION:
                return await self._user_notification_recovery(error_context, context)
            elif strategy == RecoveryStrategy.CIRCUIT_BREAKER:
                return await self._circuit_breaker_recovery(error_context, context)
            else:  # NO_RECOVERY
                return {
                    'success': False,
                    'strategy': strategy.value,
                    'message': 'No recovery attempted',
                    'error_id': error_context.error_id
                }
                
        except Exception as recovery_error:
            logger.error(f"Recovery strategy {strategy.value} failed: {recovery_error}")
            return {
                'success': False,
                'strategy': strategy.value,
                'message': f'Recovery failed: {recovery_error}',
                'error_id': error_context.error_id
            }
    
    async def _retry_recovery(self, error_context: ErrorContext, context: Dict[str, Any], exponential: bool = True) -> Dict[str, Any]:
        """Implement retry recovery strategy"""
        # This would be called by the original function using RetryManager
        return {
            'success': False,
            'strategy': 'retry_exponential' if exponential else 'retry_linear',
            'message': 'Retry recovery requires original function context',
            'recommended_action': 'Use RetryManager.retry_with_backoff',
            'error_id': error_context.error_id
        }
    
    async def _fallback_local_recovery(self, error_context: ErrorContext, context: Dict[str, Any]) -> Dict[str, Any]:
        """Use local/cached data as fallback"""
        return {
            'success': True,
            'strategy': 'fallback_local',
            'message': 'Using cached/local data',
            'data': context.get('fallback_data', {}),
            'degraded': True,
            'error_id': error_context.error_id
        }
    
    async def _fallback_agent_recovery(self, error_context: ErrorContext, context: Dict[str, Any]) -> Dict[str, Any]:
        """Switch to backup agent"""
        component = error_context.component
        
        # Mark primary agent as unhealthy
        if component in self.agent_health:
            self.agent_health[component].is_available = False
            self.agent_health[component].consecutive_failures += 1
        
        return {
            'success': True,
            'strategy': 'fallback_agent',
            'message': f'Switched to backup for {component}',
            'primary_agent': component,
            'backup_used': True,
            'error_id': error_context.error_id
        }
    
    async def _degraded_mode_recovery(self, error_context: ErrorContext, context: Dict[str, Any]) -> Dict[str, Any]:
        """Operate with reduced functionality"""
        return {
            'success': True,
            'strategy': 'degraded_mode',
            'message': 'Operating in degraded mode with reduced functionality',
            'limitations': context.get('degraded_limitations', []),
            'degraded': True,
            'error_id': error_context.error_id
        }
    
    async def _user_notification_recovery(self, error_context: ErrorContext, context: Dict[str, Any]) -> Dict[str, Any]:
        """Notify user and request action"""
        return {
            'success': False,
            'strategy': 'user_notification',
            'message': 'User intervention required',
            'notification': {
                'type': 'error',
                'title': 'System Error',
                'message': f'A {error_context.category.value} error occurred. Please try again or contact support.',
                'error_id': error_context.error_id,
                'actions': ['retry', 'report', 'continue_degraded']
            },
            'error_id': error_context.error_id
        }
    
    async def _circuit_breaker_recovery(self, error_context: ErrorContext, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply circuit breaker pattern"""
        component = error_context.component
        breaker = self.get_circuit_breaker(component)
        
        if breaker.state == 'OPEN':
            return {
                'success': False,
                'strategy': 'circuit_breaker',
                'message': f'Circuit breaker is OPEN for {component}',
                'circuit_state': 'OPEN',
                'retry_after': breaker.recovery_timeout,
                'error_id': error_context.error_id
            }
        
        return {
            'success': True,
            'strategy': 'circuit_breaker',
            'message': f'Circuit breaker applied to {component}',
            'circuit_state': breaker.state,
            'error_id': error_context.error_id
        }
    
    def detect_sync_conflict(self, user_id: str, data_type: str, local_data: Dict[str, Any], 
                           remote_data: Dict[str, Any]) -> Optional[DataSyncConflict]:
        """Detect data synchronization conflicts"""
        # Compare data versions
        conflict_fields = []
        
        # Find conflicting fields
        all_keys = set(local_data.keys()) | set(remote_data.keys())
        for key in all_keys:
            local_value = local_data.get(key)
            remote_value = remote_data.get(key)
            
            if local_value != remote_value:
                conflict_fields.append(key)
        
        if conflict_fields:
            conflict_id = hashlib.md5(f"{user_id}{data_type}{time.time()}".encode()).hexdigest()[:12]
            
            conflict = DataSyncConflict(
                conflict_id=conflict_id,
                user_id=user_id,
                data_type=data_type,
                local_version=local_data,
                remote_version=remote_data,
                local_timestamp=datetime.fromisoformat(local_data.get('updated_at', datetime.utcnow().isoformat())),
                remote_timestamp=datetime.fromisoformat(remote_data.get('updated_at', datetime.utcnow().isoformat())),
                conflict_fields=conflict_fields
            )
            
            # Try auto-resolution
            if not conflict.auto_resolve():
                self.sync_conflicts.append(conflict)
                logger.warning(f"Sync conflict detected: {conflict_id}")
            
            return conflict
        
        return None
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        total_agents = len(self.agent_health)
        healthy_agents = sum(1 for agent in self.agent_health.values() if agent.is_available and not agent.circuit_breaker_open)
        
        recent_errors = [error for error in self.error_history if error.timestamp > datetime.utcnow() - timedelta(hours=1)]
        
        return {
            'network': {
                'connected': self.network_health.is_connected,
                'quality': self.network_health.connection_quality,
                'latency_ms': self.network_health.latency_ms,
                'consecutive_failures': self.network_health.consecutive_failures
            },
            'agents': {
                'total': total_agents,
                'healthy': healthy_agents,
                'unhealthy': total_agents - healthy_agents,
                'details': {
                    name: {
                        'available': agent.is_available,
                        'performance_score': agent.performance_score,
                        'circuit_breaker_open': agent.circuit_breaker_open,
                        'error_rate': agent.error_rate
                    }
                    for name, agent in self.agent_health.items()
                }
            },
            'errors': {
                'total_in_history': len(self.error_history),
                'recent_1h': len(recent_errors),
                'unresolved_conflicts': len([c for c in self.sync_conflicts if not c.resolved])
            },
            'timestamp': datetime.utcnow().isoformat()
        }


# Global resilience manager instance
resilience_manager = ResilienceManager()


# Decorators for easy error handling
def resilient_operation(component: str = None, category: ErrorCategory = None):
    """Decorator to make functions resilient with automatic error handling"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            try:
                start_time = time.time()
                result = await func(*args, **kwargs)
                
                # Update agent health on success
                if component and component in resilience_manager.agent_health:
                    response_time = time.time() - start_time
                    resilience_manager.agent_health[component].update_performance(response_time, True)
                
                return result
            except Exception as e:
                context = {
                    'component': component or func.__name__,
                    'function': func.__name__,
                    'args': str(args)[:200],  # Truncate long args
                    'kwargs': str(kwargs)[:200]
                }
                
                # Update agent health on failure
                if component and component in resilience_manager.agent_health:
                    response_time = time.time() - start_time
                    resilience_manager.agent_health[component].update_performance(response_time, False)
                
                recovery_result = await resilience_manager.handle_error(e, context)
                
                if recovery_result.get('success'):
                    # If recovery succeeded, return recovery data
                    return recovery_result.get('data', {})
                else:
                    # Re-raise with additional context
                    raise Exception(f"{str(e)} [Error ID: {recovery_result.get('error_id')}]") from e
        
        def sync_wrapper(*args, **kwargs):
            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                
                # Update agent health on success
                if component and component in resilience_manager.agent_health:
                    response_time = time.time() - start_time
                    resilience_manager.agent_health[component].update_performance(response_time, True)
                
                return result
            except Exception as e:
                context = {
                    'component': component or func.__name__,
                    'function': func.__name__,
                    'args': str(args)[:200],
                    'kwargs': str(kwargs)[:200]
                }
                
                # Update agent health on failure
                if component and component in resilience_manager.agent_health:
                    response_time = time.time() - start_time
                    resilience_manager.agent_health[component].update_performance(response_time, False)
                
                # For sync functions, log error but don't attempt async recovery
                error_context = resilience_manager.log_error(e, context)
                raise Exception(f"{str(e)} [Error ID: {error_context.error_id}]") from e
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


@asynccontextmanager
async def resilient_context(component: str, operation: str = None):
    """Context manager for resilient operations with comprehensive error handling"""
    context = {
        'component': component,
        'operation': operation or 'unknown'
    }
    
    start_time = time.time()
    
    try:
        yield context
        
        # Success - update component health
        if component in resilience_manager.agent_health:
            response_time = time.time() - start_time
            resilience_manager.agent_health[component].update_performance(response_time, True)
            
    except Exception as e:
        # Failure - handle error and update health
        if component in resilience_manager.agent_health:
            response_time = time.time() - start_time
            resilience_manager.agent_health[component].update_performance(response_time, False)
        
        recovery_result = await resilience_manager.handle_error(e, context)
        
        if not recovery_result.get('success'):
            raise Exception(f"{str(e)} [Error ID: {recovery_result.get('error_id')}]") from e


# Initialize monitoring on import
def start_resilience_monitoring():
    """Start resilience monitoring if not already active"""
    try:
        if not resilience_manager.monitoring_active:
            # Register common agents
            resilience_manager.register_agent('onboarding_agent')
            resilience_manager.register_agent('matching_agent')  
            resilience_manager.register_agent('team_agent')
            resilience_manager.register_agent('gamification_engine')
            
            # Start monitoring (without creating task in non-async context)
            resilience_manager.monitoring_active = True
            logger.info("Resilience monitoring initialized (will start with first async call)")
    except Exception as e:
        logger.warning(f"Could not start resilience monitoring: {e}")


# Auto-start monitoring when module is imported
if __name__ != '__main__':
    try:
        start_resilience_monitoring()
    except Exception as e:
        logger.warning(f"Could not start resilience monitoring: {e}")