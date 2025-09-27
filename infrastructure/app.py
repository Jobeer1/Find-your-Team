#!/usr/bin/env python3
"""
AWS CDK Infrastructure for Find Your Team Platform
Deploys the complete AWS stack needed for the hackathon demo
"""

import aws_cdk as cdk
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_iot as iot,
    aws_lambda as lambda_,
    aws_opensearchservice as opensearch,
    aws_bedrock as bedrock,
    aws_iam as iam,
    aws_apigateway as apigateway,
    aws_s3 as s3,
    aws_cloudwatch as cloudwatch,
    Duration,
    RemovalPolicy
)

class FindYourTeamStack(Stack):
    """Main stack for Find Your Team platform"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDB Tables for user profiles and team performance
        self.user_profiles_table = dynamodb.Table(
            self, "UserProfilesTable",
            table_name="FindYourTeam-UserProfiles",
            partition_key=dynamodb.Attribute(
                name="userId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # For hackathon demo
            point_in_time_recovery=True
        )

        self.team_performance_table = dynamodb.Table(
            self, "TeamPerformanceTable",
            table_name="FindYourTeam-TeamPerformance",
            partition_key=dynamodb.Attribute(
                name="teamId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True
        )

        # Add GSI for user queries
        self.user_profiles_table.add_global_secondary_index(
            index_name="SkillsIndex",
            partition_key=dynamodb.Attribute(
                name="primarySkill",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="confidenceScore",
                type=dynamodb.AttributeType.NUMBER
            )
        )

        # OpenSearch cluster for vector embeddings and semantic search
        self.opensearch_domain = opensearch.Domain(
            self, "FindYourTeamSearch",
            domain_name="findyourteam-search",
            version=opensearch.EngineVersion.OPENSEARCH_2_11,
            capacity=opensearch.CapacityConfig(
                data_nodes=1,
                data_node_instance_type="t3.small.search"
            ),
            ebs=opensearch.EbsOptions(
                volume_size=10
            ),
            removal_policy=RemovalPolicy.DESTROY,
            access_policies=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    principals=[iam.AnyPrincipal()],
                    actions=["es:*"],
                    resources=["*"]
                )
            ],
            # Enable vector search capabilities
            advanced_options={
                "override_main_response_version": "true",
                "rest.action.multi.allow_explicit_index": "true"
            }
        )

        # S3 bucket for static assets and file storage
        self.assets_bucket = s3.Bucket(
            self, "FindYourTeamAssets",
            bucket_name=f"findyourteam-assets-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            website_index_document="index.html",
            block_public_access=s3.BlockPublicAccess.BLOCK_ACLS
        )

        # IoT Core for real-time messaging
        self.iot_policy = iot.CfnPolicy(
            self, "FindYourTeamIoTPolicy",
            policy_name="FindYourTeamIoTPolicy",
            policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "iot:Connect",
                            "iot:Publish",
                            "iot:Subscribe",
                            "iot:Receive"
                        ],
                        "Resource": "*"
                    }
                ]
            }
        )

        # Lambda execution role with necessary permissions
        self.lambda_role = iam.Role(
            self, "FindYourTeamLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "FindYourTeamPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "dynamodb:GetItem",
                                "dynamodb:PutItem",
                                "dynamodb:UpdateItem",
                                "dynamodb:DeleteItem",
                                "dynamodb:Query",
                                "dynamodb:Scan"
                            ],
                            resources=[
                                self.user_profiles_table.table_arn,
                                self.team_performance_table.table_arn,
                                f"{self.user_profiles_table.table_arn}/index/*",
                                f"{self.team_performance_table.table_arn}/index/*"
                            ]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeAgent",
                                "bedrock:GetAgent",
                                "bedrock:ListAgents"
                            ],
                            resources=["*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "es:ESHttpGet",
                                "es:ESHttpPost",
                                "es:ESHttpPut",
                                "es:ESHttpDelete"
                            ],
                            resources=[self.opensearch_domain.domain_arn + "/*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "iot:Publish",
                                "iot:Subscribe"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )

        # Lambda functions for agent tools
        self.team_agent_tools = lambda_.Function(
            self, "TeamAgentTools",
            function_name="FindYourTeam-TeamAgentTools",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="team_agent_tools.handler",
            code=lambda_.Code.from_asset("../lambda/team_agent"),
            role=self.lambda_role,
            timeout=Duration.seconds(30),
            environment={
                "USER_PROFILES_TABLE": self.user_profiles_table.table_name,
                "TEAM_PERFORMANCE_TABLE": self.team_performance_table.table_name,
                "OPENSEARCH_ENDPOINT": self.opensearch_domain.domain_endpoint
            }
        )

        # API Gateway for REST endpoints
        self.api = apigateway.RestApi(
            self, "FindYourTeamAPI",
            rest_api_name="FindYourTeam API",
            description="API for Find Your Team platform",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"]
            )
        )

        # API Gateway integration with Lambda
        team_integration = apigateway.LambdaIntegration(self.team_agent_tools)
        
        team_resource = self.api.root.add_resource("team")
        team_resource.add_method("POST", team_integration)
        team_resource.add_method("GET", team_integration)

        # CloudWatch Dashboard for monitoring
        self.dashboard = cloudwatch.Dashboard(
            self, "FindYourTeamDashboard",
            dashboard_name="FindYourTeam-Metrics"
        )

        # Add widgets for key metrics
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="DynamoDB Operations",
                left=[
                    self.user_profiles_table.metric_consumed_read_capacity_units(),
                    self.user_profiles_table.metric_consumed_write_capacity_units(),
                    self.team_performance_table.metric_consumed_read_capacity_units(),
                    self.team_performance_table.metric_consumed_write_capacity_units()
                ]
            ),
            cloudwatch.GraphWidget(
                title="Lambda Performance",
                left=[
                    self.team_agent_tools.metric_duration(),
                    self.team_agent_tools.metric_errors(),
                    self.team_agent_tools.metric_invocations()
                ]
            )
        )

        # Output important values
        cdk.CfnOutput(self, "UserProfilesTableName", value=self.user_profiles_table.table_name)
        cdk.CfnOutput(self, "TeamPerformanceTableName", value=self.team_performance_table.table_name)
        cdk.CfnOutput(self, "OpenSearchEndpoint", value=self.opensearch_domain.domain_endpoint)
        cdk.CfnOutput(self, "APIEndpoint", value=self.api.url)
        cdk.CfnOutput(self, "AssetsBucket", value=self.assets_bucket.bucket_name)

app = cdk.App()
FindYourTeamStack(app, "FindYourTeamStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1"
    )
)

app.synth()