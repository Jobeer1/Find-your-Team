"""
Tests for Integration Agent - Cross-platform integration and API orchestration
"""

import pytest
import json
import aiohttp
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

from agents.integration_agent import (
    IntegrationAgent, IntegrationConfig, IntegrationType, IntegrationStatus,
    HttpMethod, ApiCall, ApiResponse, WebhookEvent
)
from config import Config


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    config = MagicMock(spec=Config)
    config.aws_region = "us-east-1"
    config.integrations_table_name = "integrations"
    config.api_calls_table_name = "api-calls"
    config.api_responses_table_name = "api-responses"
    return config


@pytest.fixture
def integration_agent(mock_config):
    """Integration Agent instance for testing."""
    return IntegrationAgent(mock_config)


@pytest.fixture
def sample_integration_config():
    """Sample integration configuration for testing."""
    return IntegrationConfig(
        integration_id="int-123",
        type=IntegrationType.GITHUB,
        name="Test GitHub Integration",
        base_url="https://api.github.com",
        auth_type="bearer_token",
        auth_config={"token": "test-token"},
        settings={"rate_limit": 5000},
        status=IntegrationStatus.ACTIVE,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


@pytest.fixture
def mock_aiohttp_response():
    """Mock aiohttp response."""
    response = MagicMock()
    response.status = 200
    response.headers = {"Content-Type": "application/json"}
    response.json = AsyncMock(return_value={"test": "data"})
    response.text = AsyncMock(return_value='{"test": "data"}')
    return response


class TestIntegrationAgent:
    """Test suite for IntegrationAgent class."""

    @pytest.mark.asyncio
    async def test_register_integration_success(self, integration_agent, sample_integration_config):
        """Test successful integration registration."""
        with patch.object(integration_agent, '_store_integration_config'), \
             patch.object(integration_agent, '_test_integration', return_value=True):

            config = await integration_agent.register_integration(
                integration_type=IntegrationType.GITHUB,
                name="Test GitHub",
                base_url="https://api.github.com",
                auth_type="bearer_token",
                auth_config={"token": "test-token"}
            )

            assert isinstance(config, IntegrationConfig)
            assert config.type == IntegrationType.GITHUB
            assert config.name == "Test GitHub"
            assert config.status == IntegrationStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_execute_api_call_success(self, integration_agent, sample_integration_config, mock_aiohttp_response):
        """Test successful API call execution."""
        # Mock the session
        mock_session = MagicMock()
        integration_agent.session = mock_session

        # Create a proper context manager mock
        mock_context = MagicMock()
        mock_context.__aenter__.return_value = mock_aiohttp_response
        mock_context.__aexit__.return_value = None
        mock_session.request.return_value = mock_context

        with patch.object(integration_agent, '_get_integration_config', return_value=sample_integration_config), \
             patch.object(integration_agent, '_store_api_call'), \
             patch.object(integration_agent, '_store_api_response'), \
             patch.object(integration_agent, '_update_integration_health'):

            response = await integration_agent.execute_api_call(
                integration_id="int-123",
                method=HttpMethod.GET,
                endpoint="/user"
            )

            print(f"Response: {response}")
            print(f"Response type: {type(response)}")

            assert isinstance(response, ApiResponse)
            assert response.status_code == 200
            assert response.success is True
            assert response.data == {"test": "data"}

    @pytest.mark.asyncio
    async def test_execute_api_call_integration_not_found(self, integration_agent):
        """Test API call with non-existent integration."""
        with patch.object(integration_agent, '_get_integration_config', return_value=None):
            with pytest.raises(ValueError, match="Integration int-123 not found"):
                await integration_agent.execute_api_call(
                    integration_id="int-123",
                    method=HttpMethod.GET,
                    endpoint="/test"
                )

    @pytest.mark.asyncio
    async def test_execute_api_call_integration_inactive(self, integration_agent, sample_integration_config):
        """Test API call with inactive integration."""
        sample_integration_config.status = IntegrationStatus.INACTIVE

        with patch.object(integration_agent, '_get_integration_config', return_value=sample_integration_config):
            with pytest.raises(ValueError, match="Integration int-123 is not active"):
                await integration_agent.execute_api_call(
                    integration_id="int-123",
                    method=HttpMethod.GET,
                    endpoint="/test"
                )

    @pytest.mark.asyncio
    async def test_sync_data_success(self, integration_agent, sample_integration_config):
        """Test successful data synchronization."""
        sync_config = {
            'type': 'full',
            'endpoints': [
                {
                    'endpoint': '/users',
                    'method': 'GET'
                }
            ]
        }

        mock_response = ApiResponse(
            call_id="call-123",
            status_code=200,
            headers={},
            data=[{"id": 1, "name": "User 1"}],
            response_time=1.0,
            success=True
        )

        with patch.object(integration_agent, '_get_integration_config', return_value=sample_integration_config), \
             patch.object(integration_agent, 'execute_api_call', return_value=mock_response), \
             patch.object(integration_agent, '_process_sync_data', return_value=[{"id": 1, "name": "User 1"}]), \
             patch.object(integration_agent, '_store_integration_config'):

            result = await integration_agent.sync_data("int-123", sync_config)

            assert result['integration_id'] == "int-123"
            assert result['success'] is True
            assert len(result['endpoints_synced']) == 1
            assert result['total_records'] == 1

    @pytest.mark.asyncio
    async def test_handle_webhook_event_success(self, integration_agent):
        """Test successful webhook event handling."""
        with patch.object(integration_agent, '_store_webhook_event'), \
             patch.object(integration_agent, '_default_webhook_handler', return_value={"status": "processed"}):

            result = await integration_agent.handle_webhook_event(
                integration_id="int-123",
                event_type="push",
                payload={"ref": "refs/heads/main"},
                headers={"X-GitHub-Event": "push"}
            )

            assert result['processed'] is True
            assert 'event_id' in result
            assert result['result']['status'] == "processed"

    def test_register_webhook_handler(self, integration_agent):
        """Test webhook handler registration."""
        async def test_handler(event):
            return {"handled": True}

        integration_agent.register_webhook_handler("int-123", "push", test_handler)

        handler_key = "int-123:push"
        assert handler_key in integration_agent.webhook_handlers
        assert integration_agent.webhook_handlers[handler_key] == test_handler

    @pytest.mark.asyncio
    async def test_monitor_integration_health_success(self, integration_agent, sample_integration_config):
        """Test successful integration health monitoring."""
        integration_agent._integration_cache = {"int-123": sample_integration_config}

        with patch.object(integration_agent, '_check_integration_health', return_value={"score": 0.9, "issues": []}):
            health_report = await integration_agent.monitor_integration_health()

            assert 'timestamp' in health_report
            assert 'integrations' in health_report
            assert 'overall_health' in health_report
            assert health_report['overall_health'] == 'healthy'
            assert "int-123" in health_report['integrations']

    @pytest.mark.asyncio
    async def test_orchestrate_workflow_success(self, integration_agent):
        """Test successful workflow orchestration."""
        workflow_config = {
            'workflow_id': 'wf-123',
            'steps': [
                {
                    'name': 'step1',
                    'type': 'api_call',
                    'config': {
                        'integration_id': 'int-123',
                        'method': 'GET',
                        'endpoint': '/test'
                    }
                }
            ]
        }

        mock_response = ApiResponse(
            call_id="call-123",
            status_code=200,
            headers={},
            data={"result": "success"},
            response_time=1.0,
            success=True
        )

        with patch.object(integration_agent, 'execute_api_call', return_value=mock_response), \
             patch.object(integration_agent, '_execute_workflow_step') as mock_step:

            mock_step.return_value = {
                'name': 'step1',
                'type': 'api_call',
                'success': True,
                'result': {'status_code': 200}
            }

            result = await integration_agent.orchestrate_workflow(workflow_config)

            assert result['workflow_id'] == 'wf-123'
            assert result['success'] is True
            assert len(result['steps']) == 1

    @pytest.mark.asyncio
    async def test_get_integration_config_from_cache(self, integration_agent, sample_integration_config):
        """Test getting integration config from cache."""
        integration_agent._integration_cache["int-123"] = sample_integration_config

        config = await integration_agent._get_integration_config("int-123")

        assert config == sample_integration_config

    @pytest.mark.asyncio
    async def test_get_integration_config_from_db(self, integration_agent, sample_integration_config):
        """Test getting integration config from database."""
        with patch.object(integration_agent.integrations_table, 'get_item') as mock_get:
            mock_get.return_value = {"Item": asdict(sample_integration_config)}

            config = await integration_agent._get_integration_config("int-123")

            assert config.integration_id == "int-123"
            assert config in integration_agent._integration_cache

    @pytest.mark.asyncio
    async def test_store_integration_config(self, integration_agent, sample_integration_config):
        """Test storing integration configuration."""
        with patch.object(integration_agent.integrations_table, 'put_item') as mock_put:
            await integration_agent._store_integration_config(sample_integration_config)

            # Verify put_item was called
            assert mock_put.called
            call_args = mock_put.call_args[1]['Item']
            assert call_args['integration_id'] == "int-123"
            assert call_args['type'] == "github"

    @pytest.mark.asyncio
    async def test_test_integration_success(self, integration_agent, sample_integration_config):
        """Test successful integration testing."""
        mock_response = ApiResponse(
            call_id="call-123",
            status_code=200,
            headers={},
            data={"user": "test"},
            response_time=1.0,
            success=True
        )

        with patch.object(integration_agent, 'execute_api_call', return_value=mock_response):
            result = await integration_agent._test_integration(sample_integration_config)

            assert result is True

    @pytest.mark.asyncio
    async def test_test_integration_failure(self, integration_agent, sample_integration_config):
        """Test failed integration testing."""
        with patch.object(integration_agent, 'execute_api_call', side_effect=Exception("Connection failed")):
            result = await integration_agent._test_integration(sample_integration_config)

            assert result is False

    def test_get_test_endpoint(self, integration_agent):
        """Test getting test endpoints for different integration types."""
        assert integration_agent._get_test_endpoint(IntegrationType.GITHUB) == '/user'
        assert integration_agent._get_test_endpoint(IntegrationType.SLACK) == '/auth.test'
        assert integration_agent._get_test_endpoint(IntegrationType.JIRA) == '/rest/api/2/myself'
        assert integration_agent._get_test_endpoint(IntegrationType.CUSTOM_API) == '/'

    @pytest.mark.asyncio
    async def test_prepare_headers_bearer_token(self, integration_agent, sample_integration_config):
        """Test preparing headers with bearer token auth."""
        headers = await integration_agent._prepare_headers(sample_integration_config, {"X-Custom": "value"})

        assert headers['Authorization'] == "Bearer test-token"
        assert headers['X-Custom'] == "value"

    @pytest.mark.asyncio
    async def test_prepare_headers_api_key(self, integration_agent):
        """Test preparing headers with API key auth."""
        config = IntegrationConfig(
            integration_id="int-123",
            type=IntegrationType.CUSTOM_API,
            name="Test API",
            base_url="https://api.example.com",
            auth_type="api_key",
            auth_config={"key": "test-key", "key_name": "X-API-Key"},
            settings={},
            status=IntegrationStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        headers = await integration_agent._prepare_headers(config, {})

        assert headers['X-API-Key'] == "test-key"

    @pytest.mark.asyncio
    async def test_parse_response_data_json(self, integration_agent, mock_aiohttp_response):
        """Test parsing JSON response data."""
        mock_aiohttp_response.headers = {"Content-Type": "application/json"}

        data = await integration_agent._parse_response_data(mock_aiohttp_response)

        assert data == {"test": "data"}

    @pytest.mark.asyncio
    async def test_parse_response_data_text(self, integration_agent, mock_aiohttp_response):
        """Test parsing text response data."""
        mock_aiohttp_response.headers = {"Content-Type": "text/plain"}

        data = await integration_agent._parse_response_data(mock_aiohttp_response)

        assert data == '{"test": "data"}'

    @pytest.mark.asyncio
    async def test_update_integration_health_success(self, integration_agent, sample_integration_config):
        """Test updating integration health on success."""
        integration_agent._integration_cache["int-123"] = sample_integration_config
        sample_integration_config.error_count = 5

        with patch.object(integration_agent, '_store_integration_config'):
            await integration_agent._update_integration_health("int-123", True)

            assert sample_integration_config.error_count == 4
            assert sample_integration_config.last_error is None

    @pytest.mark.asyncio
    async def test_update_integration_health_failure(self, integration_agent, sample_integration_config):
        """Test updating integration health on failure."""
        integration_agent._integration_cache["int-123"] = sample_integration_config
        sample_integration_config.error_count = 0

        with patch.object(integration_agent, '_store_integration_config'):
            await integration_agent._update_integration_health("int-123", False)

            assert sample_integration_config.error_count == 1

    @pytest.mark.asyncio
    async def test_check_integration_health_good(self, integration_agent, sample_integration_config):
        """Test checking health of a healthy integration."""
        health = await integration_agent._check_integration_health(sample_integration_config)

        assert health['score'] == 1.0
        assert len(health['issues']) == 0

    @pytest.mark.asyncio
    async def test_check_integration_health_issues(self, integration_agent, sample_integration_config):
        """Test checking health of an integration with issues."""
        sample_integration_config.error_count = 15
        sample_integration_config.last_sync_at = datetime.now() - timedelta(hours=48)
        sample_integration_config.status = IntegrationStatus.ERROR

        health = await integration_agent._check_integration_health(sample_integration_config)

        assert health['score'] < 1.0
        assert len(health['issues']) >= 2  # Should have multiple issues

    @pytest.mark.asyncio
    async def test_execute_workflow_step_api_call(self, integration_agent):
        """Test executing workflow step of type api_call."""
        step_config = {
            'name': 'test_step',
            'type': 'api_call',
            'config': {
                'integration_id': 'int-123',
                'method': 'GET',
                'endpoint': '/test'
            }
        }

        mock_response = ApiResponse(
            call_id="call-123",
            status_code=200,
            headers={},
            data={"result": "success"},
            response_time=1.0,
            success=True
        )

        with patch.object(integration_agent, 'execute_api_call', return_value=mock_response):
            result = await integration_agent._execute_workflow_step(step_config)

            assert result['name'] == 'test_step'
            assert result['type'] == 'api_call'
            assert result['success'] is True

    @pytest.mark.asyncio
    async def test_execute_workflow_step_unknown_type(self, integration_agent):
        """Test executing workflow step with unknown type."""
        step_config = {
            'name': 'test_step',
            'type': 'unknown_type'
        }

        result = await integration_agent._execute_workflow_step(step_config)

        assert result['name'] == 'test_step'
        assert result['type'] == 'unknown_type'
        assert result['success'] is False
        assert 'error' in result


class TestIntegrationConfig:
    """Test IntegrationConfig dataclass."""

    def test_integration_config_creation(self):
        """Test creating an IntegrationConfig instance."""
        config = IntegrationConfig(
            integration_id="int-123",
            type=IntegrationType.GITHUB,
            name="Test Integration",
            base_url="https://api.github.com",
            auth_type="bearer_token",
            auth_config={"token": "test-token"},
            settings={"rate_limit": 5000},
            status=IntegrationStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        assert config.integration_id == "int-123"
        assert config.type == IntegrationType.GITHUB
        assert config.name == "Test Integration"
        assert config.auth_type == "bearer_token"
        assert config.status == IntegrationStatus.ACTIVE


class TestApiCall:
    """Test ApiCall dataclass."""

    def test_api_call_creation(self):
        """Test creating an ApiCall instance."""
        call = ApiCall(
            call_id="call-123",
            integration_id="int-123",
            method=HttpMethod.GET,
            endpoint="/users",
            headers={"Authorization": "Bearer token"},
            params={"page": 1},
            data=None,
            timeout=30,
            retries=3
        )

        assert call.call_id == "call-123"
        assert call.method == HttpMethod.GET
        assert call.endpoint == "/users"
        assert call.timeout == 30
        assert call.retries == 3


class TestApiResponse:
    """Test ApiResponse dataclass."""

    def test_api_response_creation(self):
        """Test creating an ApiResponse instance."""
        response = ApiResponse(
            call_id="call-123",
            status_code=200,
            headers={"Content-Type": "application/json"},
            data={"users": []},
            response_time=1.5,
            success=True
        )

        assert response.call_id == "call-123"
        assert response.status_code == 200
        assert response.success is True
        assert response.response_time == 1.5


class TestWebhookEvent:
    """Test WebhookEvent dataclass."""

    def test_webhook_event_creation(self):
        """Test creating a WebhookEvent instance."""
        event = WebhookEvent(
            event_id="event-123",
            integration_id="int-123",
            event_type="push",
            payload={"ref": "main"},
            headers={"X-GitHub-Event": "push"},
            received_at=datetime.now()
        )

        assert event.event_id == "event-123"
        assert event.event_type == "push"
        assert event.processed is False


class TestIntegrationType:
    """Test IntegrationType enum."""

    def test_integration_types(self):
        """Test all integration type values."""
        assert IntegrationType.GITHUB.value == "github"
        assert IntegrationType.SLACK.value == "slack"
        assert IntegrationType.JIRA.value == "jira"
        assert IntegrationType.ZOOM.value == "zoom"
        assert IntegrationType.CUSTOM_API.value == "custom_api"


class TestIntegrationStatus:
    """Test IntegrationStatus enum."""

    def test_integration_statuses(self):
        """Test all integration status values."""
        assert IntegrationStatus.ACTIVE.value == "active"
        assert IntegrationStatus.INACTIVE.value == "inactive"
        assert IntegrationStatus.ERROR.value == "error"
        assert IntegrationStatus.PENDING.value == "pending"


class TestHttpMethod:
    """Test HttpMethod enum."""

    def test_http_methods(self):
        """Test all HTTP method values."""
        assert HttpMethod.GET.value == "GET"
        assert HttpMethod.POST.value == "POST"
        assert HttpMethod.PUT.value == "PUT"
        assert HttpMethod.DELETE.value == "DELETE"