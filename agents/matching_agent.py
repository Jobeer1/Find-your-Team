"""
Find Your Team - Matching Agent
AI-powered team matching using vector embeddings and semantic search
"""

import json
import boto3
import logging
import requests
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from models.core_models import (
    UserProfile, PurposeProfile, TeamMatch, TeamOpportunity,
    MatchScore, MatchReason, TeamMember, TeamPerformance
)
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class MatchingAgent:
    """
    AI-powered agent that matches users with teams using vector embeddings and semantic search
    """

    def __init__(self,
                 bedrock_client=None,
                 opensearch_endpoint: str = None,
                 opensearch_index: str = "team-opportunities",
                 bedrock_model_id: str = "amazon.titan-embed-text-v1"):
        """
        Initialize the Matching Agent

        Args:
            bedrock_client: Optional boto3 Bedrock client for testing
            opensearch_endpoint: OpenSearch cluster endpoint
            opensearch_index: Name of the team opportunities index
            bedrock_model_id: Model ID for embeddings
        """
        self.bedrock = bedrock_client or boto3.client('bedrock-runtime')
        self.opensearch_endpoint = opensearch_endpoint
        self.opensearch_index = opensearch_index
        self.embedding_model_id = bedrock_model_id

        # Initialize OpenSearch client
        if opensearch_endpoint:
            self.opensearch_url = f"https://{opensearch_endpoint}"
        else:
            # Use default local endpoint for testing
            self.opensearch_url = "http://localhost:9200"

    def find_team_matches(self, user_profile: UserProfile, limit: int = 5) -> List[TeamMatch]:
        """
        Find the best team matches for a user profile

        Args:
            user_profile: Complete user profile with purpose information
            limit: Maximum number of matches to return

        Returns:
            List of team matches with scores and explanations
        """
        try:
            # Generate embedding for user profile
            user_embedding = self._generate_profile_embedding(user_profile)

            # Search for similar team opportunities
            search_results = self._search_similar_teams(user_embedding, limit)

            # Generate detailed matches with explanations
            matches = []
            for result in search_results:
                team_opportunity = result['_source']
                score = result['_score']

                # Generate AI-powered explanation
                explanation = self._generate_match_explanation(user_profile, team_opportunity, score)

                match = TeamMatch(
                    team_id=team_opportunity['opportunity_id'],
                    user_id=user_profile.user_id,
                    match_score=MatchScore(
                        overall_score=min(score / 10.0, 1.0),  # Normalize to 0-1
                        skill_alignment=score / 10.0,
                        value_alignment=score / 10.0,
                        work_style_compatibility=score / 10.0,
                        purpose_alignment=score / 10.0
                    ),
                    match_reasons=[
                        MatchReason(
                            reason_type="skills",
                            description=f"Strong alignment with required skills: {', '.join(team_opportunity.get('required_skills', []))}",
                            weight=0.3
                        ),
                        MatchReason(
                            reason_type="values",
                            description=f"Shared values and mission alignment",
                            weight=0.3
                        ),
                        MatchReason(
                            reason_type="purpose",
                            description=explanation,
                            weight=0.4
                        )
                    ],
                    recommended_actions=[
                        "Review team details and connect with team lead",
                        "Prepare portfolio showcasing relevant experience",
                        "Schedule introductory call to discuss fit"
                    ],
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow().replace(hour=23, minute=59, second=59)  # Expires end of day
                )
                matches.append(match)

            return matches

        except Exception as e:
            logger.error(f"Error finding team matches: {e}")
            return []

    def _generate_profile_embedding(self, user_profile: UserProfile) -> List[float]:
        """
        Generate vector embedding for user profile

        Args:
            user_profile: User profile to embed

        Returns:
            Vector embedding as list of floats
        """
        try:
            # Create comprehensive text representation of user profile
            profile_text = self._create_profile_text(user_profile)

            # Generate embedding using Bedrock
            body = {
                "inputText": profile_text
            }

            response = self.bedrock.invoke_model(
                modelId=self.embedding_model_id,
                body=json.dumps(body)
            )

            response_body = json.loads(response['body'].read())
            return response_body['embedding']

        except Exception as e:
            logger.error(f"Error generating profile embedding: {e}")
            return []

    def _create_profile_text(self, user_profile: UserProfile) -> str:
        """
        Create comprehensive text representation of user profile for embedding

        Args:
            user_profile: User profile

        Returns:
            Text representation for embedding
        """
        if not user_profile.purpose_profile:
            return f"User {user_profile.user_id} seeking team opportunities"

        profile = user_profile.purpose_profile

        text_parts = [
            f"Purpose: {profile.personal_purpose or 'Not specified'}",
            f"Professional Goal: {profile.professional_goal or 'Not specified'}",
            f"Community Impact: {profile.community_impact or 'Not specified'}",
            f"Values: {', '.join([v.value_name for v in profile.values]) if profile.values else 'Not specified'}",
            f"Skills: {', '.join([f'{s.skill_name} ({s.level.value})' for s in profile.skills]) if profile.skills else 'Not specified'}",
            f"Work Style: {profile.work_style.communication_style.value if profile.work_style else 'Not specified'}",
            f"Structure Preference: {profile.work_style.structure_preference.value if profile.work_style else 'Not specified'}"
        ]

        return ". ".join(text_parts)

    def _search_similar_teams(self, user_embedding: List[float], limit: int) -> List[Dict]:
        """
        Search for similar team opportunities using vector similarity

        Args:
            user_embedding: User's profile embedding
            limit: Maximum results to return

        Returns:
            List of search results from OpenSearch
        """
        try:
            search_query = {
                "size": limit,
                "query": {
                    "knn": {
                        "vector": {
                            "vector": user_embedding,
                            "k": limit
                        }
                    }
                },
                "_source": ["opportunity_id", "title", "description", "required_skills", "impact_area", "community_served", "expected_impact"]
            }

            response = requests.post(
                f"{self.opensearch_url}/{self.opensearch_index}/_search",
                json=search_query,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                results = response.json()
                return results.get('hits', {}).get('hits', [])
            else:
                logger.error(f"OpenSearch search failed: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            logger.error(f"Error searching teams: {e}")
            return []

    def _generate_match_explanation(self, user_profile: UserProfile, team_opportunity: Dict, score: float) -> str:
        """
        Generate AI-powered explanation for why this team matches the user

        Args:
            user_profile: User's profile
            team_opportunity: Team opportunity data
            score: Similarity score

        Returns:
            Human-readable explanation
        """
        try:
            prompt = f"""
            Based on the user's profile and team opportunity, explain why they would be a good match.
            Keep the explanation concise but meaningful.

            User Profile:
            {self._create_profile_text(user_profile)}

            Team Opportunity:
            Name: {team_opportunity.get('team_name', 'Unknown')}
            Mission: {team_opportunity.get('mission', 'Not specified')}
            Description: {team_opportunity.get('description', 'Not specified')}
            Required Skills: {', '.join(team_opportunity.get('required_skills', []))}
            Team Values: {', '.join(team_opportunity.get('team_values', []))}

            Similarity Score: {score:.2f}/10

            Provide a 2-3 sentence explanation of why this user would thrive on this team:
            """

            response = self._call_claude(prompt, max_tokens=200)
            return response.strip()

        except Exception as e:
            logger.error(f"Error generating match explanation: {e}")
            return "This team aligns well with your skills and interests."

    def _call_claude(self, prompt: str, max_tokens: int = 200) -> str:
        """
        Call Claude for explanation generation

        Args:
            prompt: Prompt for Claude
            max_tokens: Maximum tokens to generate

        Returns:
            Generated response
        """
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7
            }

            response = self.bedrock.invoke_model(
                modelId="anthropic.claude-3-5-sonnet-20240620",
                body=json.dumps(body)
            )

            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']

        except Exception as e:
            logger.error(f"Error calling Claude: {e}")
            return "Unable to generate detailed explanation at this time."

    def index_team_opportunity(self, team_opportunity: TeamOpportunity) -> bool:
        """
        Index a new team opportunity in OpenSearch

        Args:
            team_opportunity: Team opportunity to index

        Returns:
            Success status
        """
        try:
            # Generate embedding for team opportunity
            team_text = f"""
            Team: {team_opportunity.title}
            Description: {team_opportunity.description}
            Required Skills: {', '.join(team_opportunity.required_skills)}
            Impact Area: {team_opportunity.impact_area}
            Community Served: {team_opportunity.community_served}
            """

            body = {
                "inputText": team_text
            }

            response = self.bedrock.invoke_model(
                modelId=self.embedding_model_id,
                body=json.dumps(body)
            )

            response_body = json.loads(response['body'].read())
            team_embedding = response_body['embedding']

            # Index in OpenSearch
            doc = {
                "opportunity_id": str(team_opportunity.opportunity_id),
                "title": team_opportunity.title,
                "description": team_opportunity.description,
                "required_skills": team_opportunity.required_skills,
                "impact_area": team_opportunity.impact_area,
                "community_served": team_opportunity.community_served,
                "expected_impact": team_opportunity.expected_impact,
                "vector": team_embedding,
                "created_at": datetime.utcnow().isoformat()
            }

            index_response = requests.post(
                f"{self.opensearch_url}/{self.opensearch_index}/_doc/{team_opportunity.opportunity_id}",
                json=doc,
                headers={"Content-Type": "application/json"}
            )

            return index_response.status_code in [200, 201]

        except Exception as e:
            logger.error(f"Error indexing team opportunity: {e}")
            return False