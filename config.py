"""
Configuration management for Find Your Team platform
"""

import os
from typing import Optional


class Config:
    """Configuration class for the Find Your Team platform"""

    def __init__(self):
        # AWS Configuration
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')
        self.aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')

        # AWS Service Configuration
        self.bedrock_model_id = os.getenv('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20240620-v1:0')
        self.opensearch_domain_endpoint = os.getenv('OPENSEARCH_DOMAIN_ENDPOINT')
        self.opensearch_index_name = os.getenv('OPENSEARCH_INDEX_NAME', 'team-profiles')

        # DynamoDB Table Names
        self.teams_table_name = os.getenv('TEAMS_TABLE_NAME', 'teams')
        self.users_table_name = os.getenv('USERS_TABLE_NAME', 'users')
        self.metrics_table_name = os.getenv('METRICS_TABLE_NAME', 'team-metrics')
        self.performance_reports_table_name = os.getenv('PERFORMANCE_REPORTS_TABLE_NAME', 'performance-reports')
        self.integrations_table_name = os.getenv('INTEGRATIONS_TABLE_NAME', 'integrations')
        self.api_calls_table_name = os.getenv('API_CALLS_TABLE_NAME', 'api-calls')
        self.api_responses_table_name = os.getenv('API_RESPONSES_TABLE_NAME', 'api-responses')

        # Chat System Configuration
        self.mqtt_broker_host = os.getenv('MQTT_BROKER_HOST', 'localhost')
        self.mqtt_broker_port = int(os.getenv('MQTT_BROKER_PORT', '1883'))
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', '6379'))

        # Application Settings
        self.debug = os.getenv('DEBUG', 'False').lower() == 'true'
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')

        # OpenSearch Configuration
        self.opensearch_region = os.getenv('OPENSEARCH_REGION', self.aws_region)

        # WebRTC Configuration
        self.turn_server_url = os.getenv('TURN_SERVER_URL')
        self.turn_server_username = os.getenv('TURN_SERVER_USERNAME')
        self.turn_server_password = os.getenv('TURN_SERVER_PASSWORD')

        # File Upload Configuration
        self.upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        self.max_file_size = int(os.getenv('MAX_FILE_SIZE', '16'))  # MB

        # Security Configuration
        self.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
        self.session_timeout = int(os.getenv('SESSION_TIMEOUT', '3600'))  # seconds

        # API Configuration
        self.api_host = os.getenv('API_HOST', '0.0.0.0')
        self.api_port = int(os.getenv('API_PORT', '5000'))
        self.api_debug = self.debug

        # Database Configuration (if using SQL database)
        self.database_url = os.getenv('DATABASE_URL')

        # Email Configuration (for notifications)
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')

        # PWA Configuration
        self.pwa_name = os.getenv('PWA_NAME', 'Find Your Team')
        self.pwa_short_name = os.getenv('PWA_SHORT_NAME', 'FYT')
        self.pwa_description = os.getenv('PWA_DESCRIPTION', 'AI-powered team matching platform')
        self.pwa_theme_color = os.getenv('PWA_THEME_COLOR', '#007bff')

        # AI Agent Configuration
        self.max_tokens_per_request = int(os.getenv('MAX_TOKENS_PER_REQUEST', '4000'))
        self.temperature = float(os.getenv('TEMPERATURE', '0.7'))
        self.embedding_model_id = os.getenv('EMBEDDING_MODEL_ID', 'amazon.titan-embed-text-v1')

        # Performance Monitoring
        self.enable_performance_monitoring = os.getenv('ENABLE_PERFORMANCE_MONITORING', 'True').lower() == 'true'
        self.metrics_collection_interval = int(os.getenv('METRICS_COLLECTION_INTERVAL', '300'))  # seconds

        # Feature Flags
        self.enable_chat_system = os.getenv('ENABLE_CHAT_SYSTEM', 'True').lower() == 'true'
        self.enable_video_calls = os.getenv('ENABLE_VIDEO_CALLS', 'True').lower() == 'true'
        self.enable_file_sharing = os.getenv('ENABLE_FILE_SHARING', 'True').lower() == 'true'


# Global config instance
config = Config()