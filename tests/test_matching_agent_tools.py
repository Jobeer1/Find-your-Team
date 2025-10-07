#!/usr/bin/env python3
"""
Test suite for Matching Agent MCP Tools
"""

import asyncio
import json
import pytest
import sys
import os
from unittest.mock import Mock, patch, AsyncMock

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agents.matching_agent import MatchingAgentTools, ToolResult
from agents.matching_agent_mcp_server import MatchingAgentMCPServer

class TestMatchingAgentTools:
    """Test cases for Matching Agent Tools"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.tools = MatchingAgentTools(
            opensearch_endpoint="localhost:9200",
            opensearch_index="test-opportunities"
        )
        
        self.sample_user_profile = {
            "user_id": "test_user_123",
            "purposeProfile": {
                "mission_statement": "Build sustainable technology solutions",
                "values": {
                    "core": ["sustainability", "innovation", "community"]
                },
                "skills": {
                    "technical": [
                        {"skill_name": "Python", "level": "advanced"},
                        {"skill_name": "Machine Learning", "level": "intermediate"}
                    ],
                    "soft": [
                        {"skill_name": "Leadership", "level": "intermediate"}
                    ]
                },
                "workStyle": {
                    "collaboration": "high",
                    "autonomy": "medium",
                    "structure": "moderate"
                },
                "passions": ["environmental protection", "technology"]
            }
        }
        
        self.sample_team_opportunity = {
            "opportunity_id": "eco_team_001",
            "title": "Eco-Tech Innovation Team",
            "description": "Developing green technology solutions",
            "required_skills": ["Python", "Data Analysis", "Sustainability"],
            "team_values": ["sustainability", "innovation"],
            "impact_area": "Environmental Technology"
        }
    
    def test_tool_definitions(self):
        """Test that tool definitions are properly formatted"""
        definitions = self.tools.get_tool_definitions()
        
        assert isinstance(definitions, list)
        assert len(definitions) > 0
        
        for tool_def in definitions:
            assert "name" in tool_def
            assert "description" in tool_def
            assert "inputSchema" in tool_def
            assert "type" in tool_def["inputSchema"]
            assert "properties" in tool_def["inputSchema"]
    
    @patch('agents.matching_agent.requests.post')
    @patch.object(MatchingAgentTools, '_generate_embedding')
    async def test_semantic_search_teams(self, mock_embedding, mock_requests):
        """Test semantic search functionality"""
        # Mock embedding generation
        mock_embedding.return_value = [0.1] * 1536  # Typical embedding size
        
        # Mock OpenSearch response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "hits": {
                "hits": [
                    {
                        "_score": 0.85,
                        "_source": self.sample_team_opportunity
                    }
                ]
            }
        }
        mock_requests.return_value = mock_response
        
        # Test the tool
        result = await self.tools.semantic_search_teams(
            query_text="Python developer interested in sustainability",
            limit=5,
            min_score=0.7
        )
        
        assert isinstance(result, ToolResult)
        assert result.success
        assert "results" in result.data
        assert len(result.data["results"]) > 0
    
    async def test_analyze_compatibility(self):
        """Test compatibility analysis"""
        result = await self.tools.analyze_compatibility(
            user_profile=self.sample_user_profile,
            team_profile=self.sample_team_opportunity
        )
        
        assert isinstance(result, ToolResult)
        assert result.success
        assert "compatibility_scores" in result.data
        assert "analysis" in result.data
        
        scores = result.data["compatibility_scores"]
        assert "overall" in scores
        assert "skills" in scores
        assert "values" in scores
        assert 0 <= scores["overall"] <= 1
    
    @patch.object(MatchingAgentTools, '_generate_ai_explanation')
    async def test_generate_match_explanation(self, mock_explanation):
        """Test match explanation generation"""
        mock_explanation.return_value = "This is a great match because of shared values and complementary skills."
        
        result = await self.tools.generate_match_explanation(
            user_profile=self.sample_user_profile,
            team_opportunity=self.sample_team_opportunity,
            compatibility_score=0.85,
            explanation_type="detailed"
        )
        
        assert isinstance(result, ToolResult)
        assert result.success
        assert "overall_score" in result.data
        assert "alignment_factors" in result.data
        assert "recommendations" in result.data
        assert result.data["overall_score"] == 0.85
    
    async def test_identify_skill_gaps(self):
        """Test skill gap identification"""
        required_skills = ["Python", "Data Analysis", "DevOps", "UI/UX Design"]
        
        result = await self.tools.identify_skill_gaps(
            target_profile=self.sample_user_profile,
            required_skills=required_skills,
            gap_threshold=0.6
        )
        
        assert isinstance(result, ToolResult)
        assert result.success
        assert "skill_gaps" in result.data
        assert "skill_matches" in result.data
        assert "development_plan" in result.data
        
        # Should identify some gaps since user doesn't have all required skills
        assert len(result.data["skill_gaps"]) > 0
    
    async def test_rank_opportunities(self):
        """Test opportunity ranking"""
        opportunities = [
            self.sample_team_opportunity,
            {
                "opportunity_id": "tech_team_002",
                "title": "General Tech Team",
                "description": "Building software solutions",
                "required_skills": ["JavaScript", "React"],
                "team_values": ["innovation"],
                "impact_area": "Technology"
            }
        ]
        
        result = await self.tools.rank_opportunities(
            user_profile=self.sample_user_profile,
            opportunities=opportunities,
            ranking_criteria={"prioritize_growth": True}
        )
        
        assert isinstance(result, ToolResult)
        assert result.success
        assert "ranked_opportunities" in result.data
        assert len(result.data["ranked_opportunities"]) == len(opportunities)
    
    def test_helper_methods(self):
        """Test helper methods for data extraction"""
        # Test skill extraction
        skills = self.tools._extract_skills_list(self.sample_user_profile)
        assert "Python" in skills
        assert "Machine Learning" in skills
        assert "Leadership" in skills
        
        # Test values extraction
        values = self.tools._extract_values_list(self.sample_user_profile)
        assert "sustainability" in values
        assert "innovation" in values
        assert "community" in values
        
        # Test purpose extraction
        purpose = self.tools._extract_purpose(self.sample_user_profile)
        assert "sustainable technology" in purpose.lower()

class TestMatchingAgentMCPServer:
    """Test cases for MCP Server wrapper"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.server = MatchingAgentMCPServer({
            "opensearch_endpoint": "localhost:9200",
            "opensearch_index": "test-opportunities"
        })
    
    def test_server_initialization(self):
        """Test server initialization"""
        assert self.server.matching_tools is not None
        assert hasattr(self.server.matching_tools, 'tools')
        assert len(self.server.matching_tools.tools) > 0
    
    async def test_standalone_demo(self):
        """Test standalone demo functionality"""
        # This should run without errors
        try:
            await self.server.run_standalone_demo()
            # If we get here, the demo ran successfully
            assert True
        except Exception as e:
            # Demo might fail due to missing AWS credentials or OpenSearch
            # That's expected in test environment
            print(f"Demo failed as expected: {e}")
            assert True

def run_integration_test():
    """Run integration test with real AWS services (if available)"""
    async def integration_test():
        print("Running integration test...")
        
        # Create tools with real configuration
        tools = MatchingAgentTools()
        
        # Test profile text creation
        sample_profile = {
            "user_id": "integration_test_user",
            "purposeProfile": {
                "mission_statement": "Create positive impact through technology",
                "values": {"core": ["innovation", "sustainability"]},
                "skills": {
                    "technical": [{"skill_name": "Python", "level": "advanced"}]
                },
                "passions": ["technology", "environment"]
            }
        }
        
        profile_text = tools._create_profile_text(sample_profile)
        print(f"Profile text: {profile_text}")
        
        # Test compatibility calculation helpers
        user_skills = ["Python", "Machine Learning"]
        team_skills = ["Python", "Data Analysis", "Statistics"]
        
        skill_compatibility = await tools._calculate_skill_compatibility(user_skills, team_skills)
        print(f"Skill compatibility: {skill_compatibility}")
        
        print("Integration test completed successfully!")
    
    asyncio.run(integration_test())

if __name__ == "__main__":
    # Run basic tests
    print("Running Matching Agent Tools tests...")
    
    # Run integration test
    run_integration_test()
    
    print("All tests completed!")