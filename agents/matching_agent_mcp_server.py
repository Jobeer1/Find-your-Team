#!/usr/bin/env python3
"""
MCP Server for Find Your Team Matching Agent
Provides MCP-compatible interface for team matching tools
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        CallToolRequest,
        CallToolResult,
        ListToolsRequest,
        ListToolsResult,
        Tool,
        TextContent,
        ImageContent,
        EmbeddedResource
    )
except ImportError:
    # Fallback for when MCP is not available
    print("MCP not available, running in standalone mode")
    Server = None

try:
    from .matching_agent import MatchingAgentTools, ToolResult
except ImportError:
    # Handle running as script
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from agents.matching_agent import MatchingAgentTools, ToolResult

logger = logging.getLogger(__name__)

class MatchingAgentMCPServer:
    """
    MCP Server wrapper for Matching Agent Tools
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the MCP server
        
        Args:
            config: Configuration dictionary for the matching agent
        """
        self.config = config or {}
        
        # For demo mode, use mock clients
        if self.config.get('demo_mode', False):
            from unittest.mock import Mock
            mock_bedrock = Mock()
            self.matching_tools = MatchingAgentTools(
                bedrock_client=mock_bedrock,
                opensearch_endpoint=self.config.get('opensearch_endpoint'),
                opensearch_index=self.config.get('opensearch_index', 'team-opportunities'),
                bedrock_model_id=self.config.get('bedrock_model_id', 'amazon.titan-embed-text-v1')
            )
        else:
            self.matching_tools = MatchingAgentTools(
                opensearch_endpoint=self.config.get('opensearch_endpoint'),
                opensearch_index=self.config.get('opensearch_index', 'team-opportunities'),
                bedrock_model_id=self.config.get('bedrock_model_id', 'amazon.titan-embed-text-v1')
            )
        
        if Server:
            self.server = Server("find-your-team-matching")
        else:
            self.server = None
            
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup MCP server handlers"""
        if not self.server:
            return
            
        @self.server.list_tools()
        async def handle_list_tools() -> ListToolsResult:
            """List available tools"""
            try:
                tool_definitions = self.matching_tools.get_tool_definitions()
                
                tools = []
                for tool_def in tool_definitions:
                    tools.append(Tool(
                        name=tool_def["name"],
                        description=tool_def["description"],
                        inputSchema=tool_def["inputSchema"]
                    ))
                
                return ListToolsResult(tools=tools)
                
            except Exception as e:
                logger.error(f"Error listing tools: {e}")
                return ListToolsResult(tools=[])
        
        @self.server.call_tool()
        async def handle_call_tool(request: CallToolRequest) -> CallToolResult:
            """Handle tool calls"""
            try:
                tool_name = request.params.name
                arguments = request.params.arguments or {}
                
                logger.info(f"Calling tool: {tool_name} with args: {arguments}")
                
                # Get the tool function
                if tool_name not in self.matching_tools.tools:
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=f"Unknown tool: {tool_name}"
                        )],
                        isError=True
                    )
                
                tool_function = self.matching_tools.tools[tool_name]
                
                # Call the tool
                result = await tool_function(**arguments)
                
                # Format the result
                if result.success:
                    content = [TextContent(
                        type="text",
                        text=json.dumps(result.to_dict(), indent=2, default=str)
                    )]
                    
                    return CallToolResult(
                        content=content,
                        isError=False
                    )
                else:
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=f"Tool error: {result.error}"
                        )],
                        isError=True
                    )
                    
            except Exception as e:
                logger.error(f"Error calling tool {request.params.name}: {e}")
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=f"Internal error: {str(e)}"
                    )],
                    isError=True
                )
    
    async def run_stdio(self):
        """Run the server using stdio transport"""
        if not self.server:
            logger.error("MCP Server not available")
            return
            
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="find-your-team-matching",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=None,
                        experimental_capabilities=None
                    )
                )
            )
    
    async def run_standalone_demo(self):
        """Run a standalone demo without MCP"""
        logger.info("Running standalone demo of Matching Agent tools")
        
        # Demo user profile
        demo_user_profile = {
            "user_id": "demo_user_123",
            "purposeProfile": {
                "mission_statement": "Help communities become more sustainable through technology",
                "values": {
                    "core": ["sustainability", "community", "innovation"]
                },
                "skills": {
                    "technical": [
                        {"skill_name": "Python", "level": "advanced"},
                        {"skill_name": "Machine Learning", "level": "intermediate"}
                    ],
                    "soft": [
                        {"skill_name": "Leadership", "level": "intermediate"},
                        {"skill_name": "Communication", "level": "advanced"}
                    ]
                },
                "workStyle": {
                    "collaboration": "high",
                    "autonomy": "medium",
                    "structure": "moderate"
                },
                "passions": ["environmental protection", "community development", "technology for good"]
            }
        }
        
        # Demo team opportunity
        demo_team_opportunity = {
            "opportunity_id": "green_tech_team_001",
            "title": "Green Technology Innovation Team",
            "description": "Developing sustainable technology solutions for local communities",
            "required_skills": ["Python", "Data Analysis", "Project Management"],
            "team_values": ["sustainability", "innovation", "collaboration"],
            "impact_area": "Environmental Technology",
            "community_served": "Local environmental groups"
        }
        
        print("\n=== Find Your Team - Matching Agent Demo ===\n")
        
        # Test semantic search
        print("1. Testing Semantic Search...")
        search_result = await self.matching_tools.semantic_search_teams(
            query_text="Sustainable technology developer with Python skills and community focus",
            limit=3,
            min_score=0.5
        )
        print(f"Search Result: {json.dumps(search_result.to_dict(), indent=2, default=str)}\n")
        
        # Test compatibility analysis
        print("2. Testing Compatibility Analysis...")
        compatibility_result = await self.matching_tools.analyze_compatibility(
            user_profile=demo_user_profile,
            team_profile=demo_team_opportunity
        )
        print(f"Compatibility Result: {json.dumps(compatibility_result.to_dict(), indent=2, default=str)}\n")
        
        # Test match explanation
        print("3. Testing Match Explanation...")
        explanation_result = await self.matching_tools.generate_match_explanation(
            user_profile=demo_user_profile,
            team_opportunity=demo_team_opportunity,
            compatibility_score=0.85,
            explanation_type="detailed"
        )
        print(f"Explanation Result: {json.dumps(explanation_result.to_dict(), indent=2, default=str)}\n")
        
        # Test skill gap analysis
        print("4. Testing Skill Gap Analysis...")
        gap_result = await self.matching_tools.identify_skill_gaps(
            target_profile=demo_user_profile,
            required_skills=["Python", "Data Analysis", "Project Management", "DevOps", "UI/UX Design"],
            gap_threshold=0.6
        )
        print(f"Skill Gap Result: {json.dumps(gap_result.to_dict(), indent=2, default=str)}\n")
        
        print("=== Demo Complete ===")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Find Your Team Matching Agent MCP Server")
    parser.add_argument("--demo", action="store_true", help="Run standalone demo")
    parser.add_argument("--config", type=str, help="Configuration file path")
    
    args = parser.parse_args()
    
    # Load configuration
    config = {}
    if args.config:
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    
    # Create server
    if args.demo or not Server:
        config['demo_mode'] = True
    
    server = MatchingAgentMCPServer(config)
    
    if args.demo or not Server:
        # Run standalone demo
        asyncio.run(server.run_standalone_demo())
    else:
        # Run MCP server
        asyncio.run(server.run_stdio())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()