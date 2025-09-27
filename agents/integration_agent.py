"""
Integration Agent - Cross-platform integration and API orchestration
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import boto3
from botocore.exceptions import ClientError

from models.core_models import UserProfile, TeamOpportunity, TeamMember
from config import Config

logger = logging.getLogger(__name__)


class IntegrationType(Enum):
    """Supported integration types"""
    GITHUB = "github"
    SLACK = "slack"
    JIRA = "jira"
    TRELLO = "trello"
    ZOOM = "zoom"
    GOOGLE_WORKSPACE = "google_workspace"
    MICROSOFT_TEAMS = "microsoft_teams"
    WEBEX = "webex"
    CUSTOM_API = "custom_api"


class IntegrationStatus(Enum):
    """Integration status states"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"
    SUSPENDED = "suspended"


class HttpMethod(Enum):
    """HTTP methods for API calls"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class IntegrationConfig:
    """Configuration for an integration"""
    integration_id: str
    type: IntegrationType
    name: str
    base_url: str
    auth_type: str  # "oauth2", "api_key", "basic_auth", "bearer_token"
    auth_config: Dict[str, Any]
    settings: Dict[str, Any]
    status: IntegrationStatus
    created_at: datetime
    updated_at: datetime
    last_sync_at: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None


@dataclass
class ApiCall:
    """Represents an API call to be executed"""
    call_id: str
    integration_id: str
    method: HttpMethod
    endpoint: str
    headers: Dict[str, str]
    params: Optional[Dict[str, Any]] = None
    data: Optional[Union[Dict[str, Any], str]] = None
    timeout: int = 30
    retries: int = 3
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class ApiResponse:
    """Response from an API call"""
    call_id: str
    status_code: int
    headers: Dict[str, str]
    data: Any
    response_time: float
    success: bool
    error: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class WebhookEvent:
    """Webhook event data"""
    event_id: str
    integration_id: str
    event_type: str
    payload: Dict[str, Any]
    headers: Dict[str, str]
    received_at: datetime
    processed: bool = False
    processing_result: Optional[Dict[str, Any]] = None


class IntegrationAgent:
    """
    AI-powered integration agent for cross-platform API orchestration.
    Manages integrations, executes API calls, and handles webhook events.
    """

    def __init__(self, config: Config):
        self.config = config
        self.dynamodb = boto3.resource('dynamodb', region_name=config.aws_region)
        self.integrations_table = self.dynamodb.Table(config.integrations_table_name)
        self.api_calls_table = self.dynamodb.Table(config.api_calls_table_name)

        # HTTP session for API calls
        self.session = None

        # Webhook handlers registry
        self.webhook_handlers: Dict[str, Callable] = {}

        # Integration configurations cache
        self._integration_cache: Dict[str, IntegrationConfig] = {}

    async def _ensure_session(self):
        """Ensure HTTP session is created."""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60)
            )

    async def initialize(self):
        """Initialize the integration agent"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60)
        )
        await self._load_integrations()

    async def close(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()

    async def register_integration(
        self,
        integration_type: IntegrationType,
        name: str,
        base_url: str,
        auth_type: str,
        auth_config: Dict[str, Any],
        settings: Optional[Dict[str, Any]] = None
    ) -> IntegrationConfig:
        """
        Register a new integration.

        Args:
            integration_type: Type of integration
            name: Human-readable name
            base_url: Base URL for the API
            auth_type: Authentication type
            auth_config: Authentication configuration
            settings: Additional settings

        Returns:
            Created integration configuration
        """
        try:
            integration_id = str(uuid.uuid4())
            now = datetime.now()

            config = IntegrationConfig(
                integration_id=integration_id,
                type=integration_type,
                name=name,
                base_url=base_url.rstrip('/'),
                auth_type=auth_type,
                auth_config=auth_config,
                settings=settings or {},
                status=IntegrationStatus.PENDING,
                created_at=now,
                updated_at=now
            )

            # Store in DynamoDB
            await self._store_integration_config(config)

            # Test the integration
            test_success = await self._test_integration(config)
            if test_success:
                config.status = IntegrationStatus.ACTIVE
                config.updated_at = datetime.now()
                await self._store_integration_config(config)

            # Cache the configuration
            self._integration_cache[integration_id] = config

            return config

        except Exception as e:
            logger.error(f"Error registering integration: {str(e)}")
            raise

    async def execute_api_call(
        self,
        integration_id: str,
        method: HttpMethod,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str]] = None,
        timeout: int = 30,
        retries: int = 3
    ) -> ApiResponse:
        """
        Execute an API call for a registered integration.

        Args:
            integration_id: ID of the integration to use
            method: HTTP method
            endpoint: API endpoint (relative to base URL)
            headers: Additional headers
            params: Query parameters
            data: Request body data
            timeout: Request timeout in seconds
            retries: Number of retries on failure

        Returns:
            API response
        """
        await self._ensure_session()
        # ... rest of the method

    async def sync_data(
        self,
        integration_id: str,
        sync_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Synchronize data from an external integration.

        Args:
            integration_id: Integration to sync from
            sync_config: Synchronization configuration

        Returns:
            Sync results
        """
        try:
            integration = await self._get_integration_config(integration_id)
            if not integration:
                raise ValueError(f"Integration {integration_id} not found")

            sync_type = sync_config.get('type', 'full')
            endpoints = sync_config.get('endpoints', [])

            results = {
                'integration_id': integration_id,
                'sync_type': sync_type,
                'start_time': datetime.now().isoformat(),
                'endpoints_synced': [],
                'total_records': 0,
                'errors': []
            }

            for endpoint_config in endpoints:
                try:
                    endpoint = endpoint_config['endpoint']
                    method = HttpMethod(endpoint_config.get('method', 'GET'))
                    params = endpoint_config.get('params', {})

                    response = await self.execute_api_call(
                        integration_id=integration_id,
                        method=method,
                        endpoint=endpoint,
                        params=params
                    )

                    if response.success:
                        # Process the data (this would be integration-specific)
                        processed_data = await self._process_sync_data(
                            integration, endpoint, response.data
                        )

                        results['endpoints_synced'].append({
                            'endpoint': endpoint,
                            'records': len(processed_data) if isinstance(processed_data, list) else 1,
                            'status': 'success'
                        })

                        results['total_records'] += len(processed_data) if isinstance(processed_data, list) else 1
                    else:
                        results['errors'].append({
                            'endpoint': endpoint,
                            'error': response.error
                        })

                except Exception as e:
                    results['errors'].append({
                        'endpoint': endpoint_config.get('endpoint', 'unknown'),
                        'error': str(e)
                    })

            results['end_time'] = datetime.now().isoformat()
            results['success'] = len(results['errors']) == 0

            # Update last sync time
            integration.last_sync_at = datetime.now()
            await self._store_integration_config(integration)

            return results

        except Exception as e:
            logger.error(f"Error syncing data for integration {integration_id}: {str(e)}")
            raise

    async def handle_webhook_event(
        self,
        integration_id: str,
        event_type: str,
        payload: Dict[str, Any],
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Handle incoming webhook event from an integration.

        Args:
            integration_id: Integration that sent the webhook
            event_type: Type of event
            payload: Event payload
            headers: Request headers

        Returns:
            Processing result
        """
        try:
            event_id = str(uuid.uuid4())

            # Create webhook event record
            event = WebhookEvent(
                event_id=event_id,
                integration_id=integration_id,
                event_type=event_type,
                payload=payload,
                headers=headers,
                received_at=datetime.now()
            )

            # Store the event
            await self._store_webhook_event(event)

            # Find and execute handler
            handler_key = f"{integration_id}:{event_type}"
            if handler_key in self.webhook_handlers:
                handler = self.webhook_handlers[handler_key]
                result = await handler(event)
                event.processing_result = result
                event.processed = True
            else:
                # Use default handler
                result = await self._default_webhook_handler(event)
                event.processing_result = result
                event.processed = True

            # Update event record
            await self._store_webhook_event(event)

            return {
                'event_id': event_id,
                'processed': True,
                'result': result
            }

        except Exception as e:
            logger.error(f"Error handling webhook event: {str(e)}")
            return {
                'event_id': event_id if 'event_id' in locals() else None,
                'processed': False,
                'error': str(e)
            }

    def register_webhook_handler(
        self,
        integration_id: str,
        event_type: str,
        handler: Callable[[WebhookEvent], Any]
    ):
        """
        Register a webhook event handler.

        Args:
            integration_id: Integration ID
            event_type: Event type to handle
            handler: Async handler function
        """
        handler_key = f"{integration_id}:{event_type}"
        self.webhook_handlers[handler_key] = handler

    async def monitor_integration_health(self) -> Dict[str, Any]:
        """
        Monitor health of all integrations.

        Returns:
            Health status for all integrations
        """
        try:
            health_report = {
                'timestamp': datetime.now().isoformat(),
                'integrations': {},
                'overall_health': 'healthy',
                'issues': []
            }

            for integration_id, config in self._integration_cache.items():
                health = await self._check_integration_health(config)

                health_report['integrations'][integration_id] = {
                    'name': config.name,
                    'type': config.type.value,
                    'status': config.status.value,
                    'last_sync': config.last_sync_at.isoformat() if config.last_sync_at else None,
                    'error_count': config.error_count,
                    'last_error': config.last_error,
                    'health_score': health['score'],
                    'issues': health['issues']
                }

                if health['score'] < 0.8:
                    health_report['issues'].append({
                        'integration_id': integration_id,
                        'issues': health['issues']
                    })

            # Determine overall health
            if health_report['issues']:
                health_report['overall_health'] = 'degraded'
            if any(h['health_score'] < 0.5 for h in health_report['integrations'].values()):
                health_report['overall_health'] = 'unhealthy'

            return health_report

        except Exception as e:
            logger.error(f"Error monitoring integration health: {str(e)}")
            raise

    async def orchestrate_workflow(
        self,
        workflow_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Orchestrate a multi-step workflow across integrations.

        Args:
            workflow_config: Workflow configuration

        Returns:
            Workflow execution results
        """
        try:
            workflow_id = workflow_config.get('workflow_id', str(uuid.uuid4()))
            steps = workflow_config.get('steps', [])

            results = {
                'workflow_id': workflow_id,
                'start_time': datetime.now().isoformat(),
                'steps': [],
                'success': True,
                'errors': []
            }

            # Execute steps in sequence
            for step_config in steps:
                step_result = await self._execute_workflow_step(step_config)

                results['steps'].append(step_result)

                if not step_result['success']:
                    results['success'] = False
                    results['errors'].append({
                        'step': step_config.get('name', 'unknown'),
                        'error': step_result.get('error')
                    })

                    # Check if we should continue on failure
                    if not step_config.get('continue_on_failure', False):
                        break

            results['end_time'] = datetime.now().isoformat()
            return results

        except Exception as e:
            logger.error(f"Error orchestrating workflow: {str(e)}")
            raise

    async def _load_integrations(self):
        """Load all integration configurations from DynamoDB"""
        try:
            response = self.integrations_table.scan()
            items = response.get('Items', [])

            for item in items:
                config = IntegrationConfig(**item)
                self._integration_cache[config.integration_id] = config

        except ClientError as e:
            logger.error(f"Error loading integrations: {str(e)}")

    async def _get_integration_config(self, integration_id: str) -> Optional[IntegrationConfig]:
        """Get integration configuration by ID"""
        # Check cache first
        if integration_id in self._integration_cache:
            return self._integration_cache[integration_id]

        # Load from DynamoDB
        try:
            response = self.integrations_table.get_item(Key={'integration_id': integration_id})
            item = response.get('Item')
            if item:
                config = IntegrationConfig(**item)
                self._integration_cache[integration_id] = config
                return config
        except ClientError as e:
            logger.error(f"Error getting integration config: {str(e)}")

        return None

    async def _store_integration_config(self, config: IntegrationConfig):
        """Store integration configuration in DynamoDB"""
        try:
            item = asdict(config)
            # Convert enums to values
            item['type'] = config.type.value
            item['status'] = config.status.value
            # Convert datetime to ISO string
            item['created_at'] = config.created_at.isoformat()
            item['updated_at'] = config.updated_at.isoformat()
            if config.last_sync_at:
                item['last_sync_at'] = config.last_sync_at.isoformat()

            await self.integrations_table.put_item(Item=item)
        except ClientError as e:
            logger.error(f"Error storing integration config: {str(e)}")
            raise

    async def _test_integration(self, config: IntegrationConfig) -> bool:
        """Test if an integration is working"""
        try:
            # Simple test call - adjust based on integration type
            test_endpoint = self._get_test_endpoint(config.type)

            response = await self.execute_api_call(
                integration_id=config.integration_id,
                method=HttpMethod.GET,
                endpoint=test_endpoint,
                timeout=10,
                retries=1
            )

            return response.success

        except Exception as e:
            logger.error(f"Integration test failed: {str(e)}")
            return False

    def _get_test_endpoint(self, integration_type: IntegrationType) -> str:
        """Get test endpoint for integration type"""
        test_endpoints = {
            IntegrationType.GITHUB: '/user',
            IntegrationType.SLACK: '/auth.test',
            IntegrationType.JIRA: '/rest/api/2/myself',
            IntegrationType.TRELLO: '/members/me',
        }
        return test_endpoints.get(integration_type, '/')

    async def _execute_with_retries(
        self,
        api_call: ApiCall,
        integration: IntegrationConfig
    ) -> aiohttp.ClientResponse:
        """Execute API call with retry logic"""
        last_error = None

        for attempt in range(api_call.retries + 1):
            try:
                # Prepare request
                url = f"{integration.base_url}{api_call.endpoint}"
                headers = await self._prepare_headers(integration, api_call.headers)

                # Prepare request data
                request_data = None
                if api_call.data:
                    if isinstance(api_call.data, dict):
                        request_data = json.dumps(api_call.data)
                        headers['Content-Type'] = 'application/json'
                    else:
                        request_data = api_call.data

                # Make request
                async with self.session.request(
                    method=api_call.method.value,
                    url=url,
                    headers=headers,
                    params=api_call.params,
                    data=request_data,
                    timeout=aiohttp.ClientTimeout(total=api_call.timeout)
                ) as response:
                    # Clone response for return (since it will be closed)
                    return response

            except Exception as e:
                last_error = e
                if attempt < api_call.retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise last_error

        raise last_error

    async def _prepare_headers(
        self,
        integration: IntegrationConfig,
        additional_headers: Dict[str, str]
    ) -> Dict[str, str]:
        """Prepare headers for API request including authentication"""
        headers = dict(additional_headers)

        if integration.auth_type == 'bearer_token':
            headers['Authorization'] = f"Bearer {integration.auth_config['token']}"
        elif integration.auth_type == 'api_key':
            key_name = integration.auth_config.get('key_name', 'X-API-Key')
            headers[key_name] = integration.auth_config['key']
        elif integration.auth_type == 'basic_auth':
            import base64
            auth_string = f"{integration.auth_config['username']}:{integration.auth_config['password']}"
            encoded = base64.b64encode(auth_string.encode()).decode()
            headers['Authorization'] = f"Basic {encoded}"

        return headers

    async def _parse_response_data(self, response: aiohttp.ClientResponse) -> Any:
        """Parse response data based on content type"""
        content_type = response.headers.get('Content-Type', '')

        if 'application/json' in content_type:
            return await response.json()
        else:
            return await response.text()

    async def _store_api_call(self, api_call: ApiCall):
        """Store API call record"""
        try:
            item = asdict(api_call)
            item['method'] = api_call.method.value
            item['created_at'] = api_call.created_at.isoformat()

            await self.api_calls_table.put_item(Item=item)
        except ClientError as e:
            logger.error(f"Error storing API call: {str(e)}")

    async def _store_api_response(self, response: ApiResponse):
        """Store API response record"""
        try:
            item = asdict(response)
            item['timestamp'] = response.timestamp.isoformat()

            # Store in responses table (would need to create this table)
            responses_table = self.dynamodb.Table(self.config.api_responses_table_name)
            await responses_table.put_item(Item=item)
        except ClientError as e:
            logger.error(f"Error storing API response: {str(e)}")

    async def _update_integration_health(self, integration_id: str, success: bool):
        """Update integration health based on API call result"""
        try:
            integration = self._integration_cache.get(integration_id)
            if integration:
                if success:
                    integration.error_count = max(0, integration.error_count - 1)
                    integration.last_error = None
                else:
                    integration.error_count += 1

                integration.updated_at = datetime.now()
                await self._store_integration_config(integration)

        except Exception as e:
            logger.error(f"Error updating integration health: {str(e)}")

    async def _process_sync_data(
        self,
        integration: IntegrationConfig,
        endpoint: str,
        data: Any
    ) -> Any:
        """Process synchronized data (integration-specific logic)"""
        # This would contain integration-specific processing logic
        # For now, just return the data as-is
        return data

    async def _store_webhook_event(self, event: WebhookEvent):
        """Store webhook event record"""
        try:
            # Would need a webhooks table
            pass
        except Exception as e:
            logger.error(f"Error storing webhook event: {str(e)}")

    async def _default_webhook_handler(self, event: WebhookEvent) -> Dict[str, Any]:
        """Default webhook event handler"""
        # Log the event and acknowledge receipt
        logger.info(f"Received webhook event: {event.event_type} from {event.integration_id}")
        return {'status': 'acknowledged', 'event_id': event.event_id}

    async def _check_integration_health(self, config: IntegrationConfig) -> Dict[str, Any]:
        """Check health of a specific integration"""
        issues = []

        # Check error rate
        if config.error_count > 10:
            issues.append("High error rate")

        # Check last sync time
        if config.last_sync_at:
            hours_since_sync = (datetime.now() - config.last_sync_at).total_seconds() / 3600
            if hours_since_sync > 24:
                issues.append("No recent sync")

        # Check status
        if config.status != IntegrationStatus.ACTIVE:
            issues.append(f"Integration status: {config.status.value}")

        # Calculate health score
        score = 1.0
        if issues:
            score -= len(issues) * 0.2
        score = max(0.0, min(1.0, score))

        return {
            'score': score,
            'issues': issues
        }

    async def _execute_workflow_step(self, step_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single workflow step"""
        try:
            step_type = step_config.get('type')
            step_name = step_config.get('name', 'unnamed_step')

            if step_type == 'api_call':
                response = await self.execute_api_call(**step_config.get('config', {}))
                return {
                    'name': step_name,
                    'type': step_type,
                    'success': response.success,
                    'result': {
                        'status_code': response.status_code,
                        'response_time': response.response_time
                    }
                }
            elif step_type == 'sync':
                result = await self.sync_data(**step_config.get('config', {}))
                return {
                    'name': step_name,
                    'type': step_type,
                    'success': result.get('success', False),
                    'result': result
                }
            else:
                return {
                    'name': step_name,
                    'type': step_type,
                    'success': False,
                    'error': f"Unknown step type: {step_type}"
                }

        except Exception as e:
            return {
                'name': step_config.get('name', 'unnamed_step'),
                'type': step_config.get('type', 'unknown'),
                'success': False,
                'error': str(e)
            }