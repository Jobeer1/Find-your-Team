"""
Network Resilience Module for Find Your Team

Implements network failure detection, recovery mechanisms, and offline-first patterns
for robust operation in poor connectivity environments.

Features:
1. Network connectivity monitoring and quality assessment
2. Offline queue management for failed requests
3. Request retry mechanisms with intelligent backoff
4. Connection quality adaptation
5. Bandwidth-aware operation modes
"""

import asyncio
import json
import logging
import time
import aiohttp
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Tuple
from collections import deque
import hashlib
import pickle
import os

from .error_handling import resilience_manager, ErrorCategory, ErrorSeverity, resilient_operation

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Network connection states"""
    ONLINE = "online"
    OFFLINE = "offline" 
    LIMITED = "limited"       # Poor connectivity
    UNSTABLE = "unstable"     # Intermittent connectivity
    UNKNOWN = "unknown"


class RequestPriority(Enum):
    """Priority levels for queued requests"""
    CRITICAL = 1    # Must be sent immediately when online
    HIGH = 2        # Send as soon as possible
    NORMAL = 3      # Send in normal queue processing
    LOW = 4         # Send when bandwidth allows
    BACKGROUND = 5  # Send only when connection is excellent


@dataclass 
class NetworkRequest:
    """Queued network request with retry information"""
    request_id: str
    url: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    data: Optional[Dict[str, Any]] = None
    priority: RequestPriority = RequestPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    max_retries: int = 3
    timeout: float = 30.0
    callback: Optional[Callable] = None
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence"""
        return {
            'request_id': self.request_id,
            'url': self.url,
            'method': self.method,
            'headers': self.headers,
            'data': self.data,
            'priority': self.priority.value,
            'created_at': self.created_at.isoformat(),
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
            'user_id': self.user_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NetworkRequest':
        """Create from dictionary"""
        return cls(
            request_id=data['request_id'],
            url=data['url'],
            method=data.get('method', 'GET'),
            headers=data.get('headers', {}),
            data=data.get('data'),
            priority=RequestPriority(data.get('priority', 3)),
            created_at=datetime.fromisoformat(data['created_at']),
            retry_count=data.get('retry_count', 0),
            max_retries=data.get('max_retries', 3),
            timeout=data.get('timeout', 30.0),
            user_id=data.get('user_id')
        )


@dataclass
class BandwidthInfo:
    """Network bandwidth information"""
    download_mbps: float = 0.0
    upload_mbps: float = 0.0
    latency_ms: float = 0.0
    jitter_ms: float = 0.0
    last_measured: datetime = field(default_factory=datetime.utcnow)
    measurement_count: int = 0
    
    def get_quality_score(self) -> float:
        """Calculate quality score 0-1 based on network metrics"""
        # Scoring based on typical requirements
        download_score = min(1.0, self.download_mbps / 10)  # 10 Mbps = perfect
        latency_score = max(0, 1 - (self.latency_ms / 1000))  # 1000ms = 0 score
        jitter_score = max(0, 1 - (self.jitter_ms / 100))  # 100ms jitter = 0 score
        
        return (download_score + latency_score + jitter_score) / 3


class NetworkMonitor:
    """Monitor network connectivity and performance"""
    
    def __init__(self):
        self.connection_state = ConnectionState.UNKNOWN
        self.bandwidth_info = BandwidthInfo()
        self.connectivity_history: deque = deque(maxlen=100)
        self.test_endpoints = [
            'https://httpbin.org/get',
            'https://jsonplaceholder.typicode.com/posts/1',
            'https://api.github.com',
        ]
        self.monitoring_active = False
        self.last_check = datetime.utcnow()
        
    async def start_monitoring(self, interval: int = 30):
        """Start continuous network monitoring"""
        self.monitoring_active = True
        while self.monitoring_active:
            try:
                await self.check_connectivity()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Network monitoring error: {e}")
                await asyncio.sleep(interval * 2)  # Back off on error
    
    def stop_monitoring(self):
        """Stop network monitoring"""
        self.monitoring_active = False
    
    async def check_connectivity(self) -> ConnectionState:
        """Check current network connectivity and performance"""
        start_time = time.time()
        successful_tests = 0
        total_latency = 0
        latencies = []
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                for endpoint in self.test_endpoints:
                    try:
                        test_start = time.time()
                        async with session.get(endpoint) as response:
                            if response.status == 200:
                                latency = (time.time() - test_start) * 1000
                                latencies.append(latency)
                                total_latency += latency
                                successful_tests += 1
                    except Exception as e:
                        logger.debug(f"Connectivity test failed for {endpoint}: {e}")
            
            # Calculate metrics
            success_rate = successful_tests / len(self.test_endpoints)
            avg_latency = total_latency / max(1, successful_tests)
            jitter = max(latencies) - min(latencies) if len(latencies) > 1 else 0
            
            # Update bandwidth info
            self.bandwidth_info.latency_ms = avg_latency
            self.bandwidth_info.jitter_ms = jitter
            self.bandwidth_info.last_measured = datetime.utcnow()
            self.bandwidth_info.measurement_count += 1
            
            # Determine connection state
            if success_rate >= 0.8 and avg_latency < 500:
                self.connection_state = ConnectionState.ONLINE
            elif success_rate >= 0.5 and avg_latency < 1000:
                self.connection_state = ConnectionState.LIMITED
            elif success_rate > 0:
                self.connection_state = ConnectionState.UNSTABLE
            else:
                self.connection_state = ConnectionState.OFFLINE
            
            # Record in history
            self.connectivity_history.append({
                'timestamp': datetime.utcnow(),
                'state': self.connection_state,
                'success_rate': success_rate,
                'latency_ms': avg_latency,
                'jitter_ms': jitter
            })
            
            self.last_check = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Connectivity check failed: {e}")
            self.connection_state = ConnectionState.OFFLINE
            
        return self.connection_state
    
    def is_online(self) -> bool:
        """Check if we're currently online"""
        return self.connection_state in [ConnectionState.ONLINE, ConnectionState.LIMITED]
    
    def get_connection_quality(self) -> str:
        """Get human-readable connection quality"""
        quality_map = {
            ConnectionState.ONLINE: "excellent",
            ConnectionState.LIMITED: "good", 
            ConnectionState.UNSTABLE: "poor",
            ConnectionState.OFFLINE: "none",
            ConnectionState.UNKNOWN: "unknown"
        }
        return quality_map.get(self.connection_state, "unknown")
    
    async def estimate_bandwidth(self) -> BandwidthInfo:
        """Estimate current network bandwidth"""
        # Simple bandwidth estimation using file download
        test_url = "https://httpbin.org/bytes/1048576"  # 1MB test file
        
        try:
            start_time = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(test_url) as response:
                    content = await response.read()
                    download_time = time.time() - start_time
                    
                    # Calculate bandwidth
                    bytes_downloaded = len(content)
                    mbps = (bytes_downloaded * 8) / (download_time * 1_000_000)
                    
                    self.bandwidth_info.download_mbps = mbps
                    self.bandwidth_info.last_measured = datetime.utcnow()
                    
        except Exception as e:
            logger.debug(f"Bandwidth estimation failed: {e}")
            
        return self.bandwidth_info


class OfflineQueue:
    """Manage queued requests for offline operation"""
    
    def __init__(self, queue_file: str = "offline_queue.json"):
        self.queue_file = queue_file
        self.request_queue: List[NetworkRequest] = []
        self.processing_active = False
        self.max_queue_size = 1000
        self.load_queue()
        
    def load_queue(self):
        """Load queued requests from disk"""
        try:
            if os.path.exists(self.queue_file):
                with open(self.queue_file, 'r') as f:
                    data = json.load(f)
                    self.request_queue = [
                        NetworkRequest.from_dict(item) for item in data
                    ]
                logger.info(f"Loaded {len(self.request_queue)} queued requests")
        except Exception as e:
            logger.error(f"Failed to load offline queue: {e}")
            self.request_queue = []
    
    def save_queue(self):
        """Save queued requests to disk"""
        try:
            data = [req.to_dict() for req in self.request_queue]
            with open(self.queue_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save offline queue: {e}")
    
    def add_request(self, request: NetworkRequest) -> bool:
        """Add request to offline queue"""
        if len(self.request_queue) >= self.max_queue_size:
            # Remove oldest low-priority requests to make space
            self.request_queue = [
                req for req in self.request_queue 
                if req.priority != RequestPriority.BACKGROUND
            ]
            
            if len(self.request_queue) >= self.max_queue_size:
                logger.warning("Offline queue full, dropping request")
                return False
        
        # Insert by priority
        insert_index = len(self.request_queue)
        for i, queued_req in enumerate(self.request_queue):
            if request.priority.value < queued_req.priority.value:
                insert_index = i
                break
        
        self.request_queue.insert(insert_index, request)
        self.save_queue()
        
        logger.info(f"Added request to offline queue: {request.request_id}")
        return True
    
    def get_next_request(self) -> Optional[NetworkRequest]:
        """Get next request to process based on priority"""
        if not self.request_queue:
            return None
        
        # Find highest priority request that hasn't exceeded retries
        for request in self.request_queue:
            if request.retry_count <= request.max_retries:
                return request
        
        return None
    
    def remove_request(self, request_id: str):
        """Remove request from queue"""
        self.request_queue = [
            req for req in self.request_queue 
            if req.request_id != request_id
        ]
        self.save_queue()
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get status of offline queue"""
        priority_counts = {}
        for priority in RequestPriority:
            count = sum(1 for req in self.request_queue if req.priority == priority)
            priority_counts[priority.name] = count
        
        return {
            'total_requests': len(self.request_queue),
            'priority_breakdown': priority_counts,
            'oldest_request': min(
                (req.created_at for req in self.request_queue), 
                default=None
            ).isoformat() if self.request_queue else None
        }


class NetworkResilience:
    """Main network resilience coordinator"""
    
    def __init__(self):
        self.monitor = NetworkMonitor()
        self.offline_queue = OfflineQueue()
        self.session_pool: Dict[str, aiohttp.ClientSession] = {}
        self.request_history: deque = deque(maxlen=1000)
        self.adaptive_timeouts = {
            ConnectionState.ONLINE: 10.0,
            ConnectionState.LIMITED: 20.0,
            ConnectionState.UNSTABLE: 30.0,
            ConnectionState.OFFLINE: 5.0
        }
        
    async def start(self):
        """Start network resilience services"""
        # Start monitoring
        asyncio.create_task(self.monitor.start_monitoring())
        
        # Start queue processing
        asyncio.create_task(self._process_offline_queue())
        
        logger.info("Network resilience services started")
    
    async def stop(self):
        """Stop network resilience services"""
        self.monitor.stop_monitoring()
        
        # Close session pools
        for session in self.session_pool.values():
            await session.close()
        self.session_pool.clear()
        
        logger.info("Network resilience services stopped")
    
    @resilient_operation(component="network_resilience", category=ErrorCategory.NETWORK)
    async def make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        priority: RequestPriority = RequestPriority.NORMAL,
        user_id: Optional[str] = None,
        retries: int = 3
    ) -> Dict[str, Any]:
        """Make HTTP request with resilience handling"""
        
        request_id = hashlib.md5(f"{method}{url}{time.time()}".encode()).hexdigest()[:12]
        
        # Check if we should attempt request immediately
        if not self.monitor.is_online() and priority != RequestPriority.CRITICAL:
            # Queue for later
            request = NetworkRequest(
                request_id=request_id,
                url=url,
                method=method,
                headers=headers or {},
                data=data,
                priority=priority,
                timeout=timeout or 30.0,
                user_id=user_id,
                max_retries=retries
            )
            
            self.offline_queue.add_request(request)
            
            return {
                'status': 'queued',
                'request_id': request_id,
                'message': 'Request queued for when connectivity is restored',
                'offline': True
            }
        
        # Attempt immediate request with adaptive timeout
        adaptive_timeout = timeout or self.adaptive_timeouts.get(
            self.monitor.connection_state, 30.0
        )
        
        session = await self._get_session()
        
        start_time = time.time()
        last_exception = None
        
        for attempt in range(retries + 1):
            try:
                timeout_config = aiohttp.ClientTimeout(total=adaptive_timeout)
                
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data if data else None,
                    timeout=timeout_config
                ) as response:
                    
                    response_time = time.time() - start_time
                    
                    # Record successful request
                    self.request_history.append({
                        'timestamp': datetime.utcnow(),
                        'request_id': request_id,
                        'method': method,
                        'url': url,
                        'status_code': response.status,
                        'response_time': response_time,
                        'attempt': attempt + 1,
                        'success': True
                    })
                    
                    if response.status < 400:
                        content = await response.text()
                        
                        try:
                            json_content = json.loads(content)
                            return {
                                'status': 'success',
                                'data': json_content,
                                'status_code': response.status,
                                'response_time': response_time,
                                'attempt': attempt + 1
                            }
                        except json.JSONDecodeError:
                            return {
                                'status': 'success',
                                'data': content,
                                'status_code': response.status,
                                'response_time': response_time,
                                'attempt': attempt + 1
                            }
                    else:
                        # HTTP error status
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status
                        )
                        
            except Exception as e:
                last_exception = e
                
                # Record failed request
                self.request_history.append({
                    'timestamp': datetime.utcnow(),
                    'request_id': request_id,
                    'method': method,
                    'url': url,
                    'error': str(e),
                    'response_time': time.time() - start_time,
                    'attempt': attempt + 1,
                    'success': False
                })
                
                if attempt < retries:
                    # Calculate backoff delay
                    delay = min(2 ** attempt, 30)  # Exponential backoff, max 30s
                    logger.warning(f"Request failed (attempt {attempt + 1}/{retries + 1}): {e}. Retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    # All retries exhausted
                    if priority == RequestPriority.CRITICAL:
                        # Critical requests should still be queued if they fail
                        request = NetworkRequest(
                            request_id=request_id,
                            url=url,
                            method=method,
                            headers=headers or {},
                            data=data,
                            priority=priority,
                            timeout=adaptive_timeout,
                            user_id=user_id,
                            retry_count=retries + 1
                        )
                        self.offline_queue.add_request(request)
                        
                        return {
                            'status': 'queued_after_failure',
                            'request_id': request_id,
                            'error': str(last_exception),
                            'message': 'Critical request queued after exhausting retries'
                        }
        
        # All attempts failed
        raise Exception(f"Request failed after {retries + 1} attempts: {last_exception}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session with appropriate configuration"""
        connection_state = self.monitor.connection_state.value
        
        if connection_state not in self.session_pool:
            # Configure session based on connection quality
            connector_kwargs = {}
            
            if self.monitor.connection_state == ConnectionState.LIMITED:
                # Reduce connection limits for poor connections
                connector_kwargs.update({
                    'limit': 10,
                    'limit_per_host': 2,
                    'keepalive_timeout': 30
                })
            elif self.monitor.connection_state == ConnectionState.UNSTABLE:
                # Very conservative settings for unstable connections
                connector_kwargs.update({
                    'limit': 5,
                    'limit_per_host': 1,
                    'keepalive_timeout': 15
                })
            else:
                # Default settings for good connections
                connector_kwargs.update({
                    'limit': 50,
                    'limit_per_host': 10,
                    'keepalive_timeout': 60
                })
            
            connector = aiohttp.TCPConnector(**connector_kwargs)
            
            self.session_pool[connection_state] = aiohttp.ClientSession(
                connector=connector,
                headers={'User-Agent': 'FindYourTeam/1.0 (Resilient Client)'}
            )
        
        return self.session_pool[connection_state]
    
    async def _process_offline_queue(self):
        """Process queued requests when connectivity is available"""
        while True:
            try:
                if self.monitor.is_online():
                    request = self.offline_queue.get_next_request()
                    
                    if request:
                        logger.info(f"Processing queued request: {request.request_id}")
                        
                        try:
                            result = await self.make_request(
                                method=request.method,
                                url=request.url,
                                headers=request.headers,
                                data=request.data,
                                timeout=request.timeout,
                                priority=request.priority,
                                user_id=request.user_id,
                                retries=1  # Reduced retries for queued requests
                            )
                            
                            # Request succeeded, remove from queue
                            self.offline_queue.remove_request(request.request_id)
                            
                            # Call callback if provided
                            if request.callback:
                                try:
                                    if asyncio.iscoroutinefunction(request.callback):
                                        await request.callback(result)
                                    else:
                                        request.callback(result)
                                except Exception as callback_error:
                                    logger.error(f"Callback failed for {request.request_id}: {callback_error}")
                            
                        except Exception as e:
                            # Request failed, increment retry count
                            request.retry_count += 1
                            
                            if request.retry_count > request.max_retries:
                                # Remove from queue after max retries
                                self.offline_queue.remove_request(request.request_id)
                                logger.warning(f"Dropping request {request.request_id} after {request.max_retries} retries")
                            else:
                                # Will be retried in next iteration
                                logger.warning(f"Queued request {request.request_id} failed (attempt {request.retry_count}): {e}")
                    
                    else:
                        # No requests to process, wait longer
                        await asyncio.sleep(10)
                else:
                    # Offline, wait before checking again
                    await asyncio.sleep(30)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing offline queue: {e}")
                await asyncio.sleep(60)  # Back off on error
    
    def get_network_status(self) -> Dict[str, Any]:
        """Get comprehensive network status"""
        return {
            'connection_state': self.monitor.connection_state.value,
            'quality': self.monitor.get_connection_quality(),
            'bandwidth': {
                'download_mbps': self.monitor.bandwidth_info.download_mbps,
                'latency_ms': self.monitor.bandwidth_info.latency_ms,
                'jitter_ms': self.monitor.bandwidth_info.jitter_ms,
                'quality_score': self.monitor.bandwidth_info.get_quality_score()
            },
            'queue': self.offline_queue.get_queue_status(),
            'last_check': self.monitor.last_check.isoformat()
        }
    
    def get_request_statistics(self) -> Dict[str, Any]:
        """Get request performance statistics"""
        if not self.request_history:
            return {'message': 'No requests recorded yet'}
        
        recent_requests = [
            req for req in self.request_history
            if req['timestamp'] > datetime.utcnow() - timedelta(hours=1)
        ]
        
        successful_requests = [req for req in recent_requests if req['success']]
        failed_requests = [req for req in recent_requests if not req['success']]
        
        if successful_requests:
            avg_response_time = sum(req['response_time'] for req in successful_requests) / len(successful_requests)
            max_response_time = max(req['response_time'] for req in successful_requests)
            min_response_time = min(req['response_time'] for req in successful_requests)
        else:
            avg_response_time = max_response_time = min_response_time = 0
        
        return {
            'total_requests_1h': len(recent_requests),
            'successful_requests_1h': len(successful_requests),
            'failed_requests_1h': len(failed_requests),
            'success_rate': len(successful_requests) / len(recent_requests) if recent_requests else 0,
            'avg_response_time': avg_response_time,
            'max_response_time': max_response_time,
            'min_response_time': min_response_time
        }


# Global network resilience instance
network_resilience = NetworkResilience()


async def resilient_http_request(*args, **kwargs) -> Dict[str, Any]:
    """Global function for making resilient HTTP requests"""
    return await network_resilience.make_request(*args, **kwargs)


def get_network_health() -> Dict[str, Any]:
    """Get current network health status"""
    return network_resilience.get_network_status()


# Initialize network resilience
async def initialize_network_resilience():
    """Initialize network resilience system"""
    try:
        await network_resilience.start()
        logger.info("Network resilience system initialized")
    except Exception as e:
        logger.error(f"Failed to initialize network resilience: {e}")