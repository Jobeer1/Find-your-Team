"""
Find Your Team - Matching Agent with RAG capabilities
AI-powered team matching using vector embeddings and semantic search
"""

import json
import logging
import requests
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
from models.core_models import (
    UserProfile, TeamOpportunity, TeamMatch, MatchScore, MatchReason,
    MatchExplanation, SkillLevel, WorkStylePreference
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MatchingAgent:
    """
    Intelligent team matching agent with RAG capabilities using Amazon OpenSearch
    and Bedrock for semantic search and explainable AI summaries.
    """
    
    def __init__(self, 
                 bedrock_client=None,
                 opensearch_endpoint: str = "localhost:9200",
                 opensearch_index: str = "team-opportunities",
                 embedding_model_id: str = "amazon.titan-embed-text-v1",
                 claude_model_id: str = "anthropic.claude-3-5-sonnet-20240620",
                 aws_region: str = "us-east-1"):
        """
        Initialize the Matching Agent with AWS services
        
        Args:
            bedrock_client: Boto3 Bedrock client (optional, will create if None)
            opensearch_endpoint: OpenSearch cluster endpoint
            opensearch_index: Index name for team opportunities
            embedding_model_id: Bedrock model for embeddings
            claude_model_id: Claude model for explanations
            aws_region: AWS region
        """
        self.opensearch_endpoint = opensearch_endpoint
        self.opensearch_index = opensearch_index
        self.embedding_model_id = embedding_model_id
        self.claude_model_id = claude_model_id
        self.aws_region = aws_region
        
        # Initialize Bedrock client
        if bedrock_client is None:
            self.bedrock = boto3.client('bedrock-runtime', region_name=aws_region)
        else:
            self.bedrock = bedrock_client
            
        # Configuration for matching algorithms
        self.config = {
            "compatibility_weights": {
                "skills": 0.3,
                "values": 0.3,
                "work_style": 0.2,
                "purpose": 0.2
            },
            "min_match_threshold": 0.6,
            "max_results": 10,
            "explanation_max_tokens": 300
        }
        
        logger.info(f"Matching Agent initialized with OpenSearch at {opensearch_endpoint}")

    def find_team_matches(self, user_profile: UserProfile, limit: int = 5) -> List[TeamMatch]:
        """
        Find team matches for a user using RAG-powered semantic search
        
        Args:
            user_profile: Complete user profile with purpose profile
            limit: Maximum number of matches to return
            
        Returns:
            List of TeamMatch objects with scores and explanations
        """
        try:
            logger.info(f"Finding team matches for user {user_profile.user_id}")
            
            # Generate embedding for user profile
            profile_embedding = self._generate_profile_embedding(user_profile)
            if not profile_embedding:
                logger.error("Failed to generate profile embedding")
                return []
            
            # Search for similar teams using vector similarity
            search_results = self._search_similar_teams(profile_embedding, limit * 2)  # Get more for filtering
            if not search_results:
                logger.warning("No search results found")
                return []
            
            # Process and score matches
            matches = []
            for result in search_results[:limit]:
                team_data = result['_source']
                similarity_score = result['_score']
                
                # Calculate detailed compatibility scores
                match_score = self._calculate_compatibility_score(user_profile, team_data, similarity_score)
                
                # Generate explainable AI summary
                explanation = self._generate_match_explanation(user_profile, team_data, similarity_score)
                
                # Create match reasons
                match_reasons = self._generate_match_reasons(user_profile, team_data, match_score)
                
                # Generate recommended actions
                recommended_actions = self._generate_recommended_actions(user_profile, team_data)
                
                # Create TeamMatch object
                team_match = TeamMatch(
                    teamId=team_data.get('team_id', f"team-{len(matches)}"),
                    userId=user_profile.user_id,
                    matchScore=match_score,
                    matchReasons=match_reasons,
                    recommendedActions=recommended_actions,
                    expiresAt=datetime.now() + timedelta(days=30)
                )
                
                matches.append(team_match)
            
            # Sort by overall score
            matches.sort(key=lambda x: x.match_score.overall_score, reverse=True)
            
            logger.info(f"Found {len(matches)} team matches for user {user_profile.user_id}")
            return matches
            
        except Exception as e:
            logger.error(f"Error finding team matches: {str(e)}")
            return []

    def _generate_profile_embedding(self, user_profile: UserProfile) -> List[float]:
        """
        Generate vector embedding for user profile using Amazon Bedrock
        
        Args:
            user_profile: User profile to embed
            
        Returns:
            Vector embedding as list of floats
        """
        try:
            # Create comprehensive text representation of profile
            profile_text = self._create_profile_text(user_profile)
            
            # Call Bedrock embedding model
            response = self.bedrock.invoke_model(
                modelId=self.embedding_model_id,
                body=json.dumps({
                    "inputText": profile_text
                })
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            embedding = response_body.get('embedding', [])
            
            logger.debug(f"Generated embedding of length {len(embedding)} for user {user_profile.user_id}")
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating profile embedding: {str(e)}")
            return []

    def _create_profile_text(self, user_profile: UserProfile) -> str:
        """
        Create comprehensive text representation of user profile for embedding
        
        Args:
            user_profile: User profile to convert to text
            
        Returns:
            Text representation of profile
        """
        try:
            purpose = user_profile.purpose_profile
            
            # Build comprehensive profile text
            text_parts = [
                f"User {user_profile.user_id} seeking team opportunities.",
                f"Mission: {purpose.mission_statement or 'Seeking meaningful collaboration'}",
                f"Core values: {', '.join(purpose.values.core)}",
                f"Passions: {', '.join(purpose.passions)}",
                f"Work style: {purpose.work_style.collaboration.value.upper()} collaboration, "
                f"{purpose.work_style.autonomy.value.upper()} autonomy, "
                f"{purpose.work_style.communication.value.upper()} communication",
            ]
            
            # Add skills
            all_skills = purpose.skills.all_skills
            if all_skills:
                skill_text = ", ".join([f"{skill.name} ({skill.level.value})" for skill in all_skills])
                text_parts.append(f"Skills: {skill_text}")
            
            # Add impact areas
            if purpose.impact_areas:
                text_parts.append(f"Impact areas: {', '.join(purpose.impact_areas)}")
            
            return " ".join(text_parts)
            
        except Exception as e:
            logger.error(f"Error creating profile text: {str(e)}")
            return f"User {user_profile.user_id} seeking team opportunities"

    def _search_similar_teams(self, embedding: List[float], limit: int) -> List[Dict]:
        """
        Search for similar teams using OpenSearch vector similarity
        
        Args:
            embedding: User profile embedding
            limit: Maximum results to return
            
        Returns:
            List of search results from OpenSearch
        """
        try:
            # Construct OpenSearch query
            query = {
                "size": limit,
                "query": {
                    "script_score": {
                        "query": {"match_all": {}},
                        "script": {
                            "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                            "params": {"query_vector": embedding}
                        }
                    }
                },
                "_source": {
                    "excludes": ["embedding"]  # Don't return the embedding in results
                }
            }
            
            # Make request to OpenSearch
            url = f"http://{self.opensearch_endpoint}/{self.opensearch_index}/_search"
            headers = {"Content-Type": "application/json"}
            
            response = requests.post(url, headers=headers, json=query, timeout=30)
            
            if response.status_code == 200:
                results = response.json()
                hits = results.get('hits', {}).get('hits', [])
                logger.debug(f"Found {len(hits)} similar teams")
                return hits
            else:
                logger.error(f"OpenSearch query failed: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching similar teams: {str(e)}")
            return []

    def _calculate_compatibility_score(self, user_profile: UserProfile, team_data: Dict, 
                                     similarity_score: float) -> MatchScore:
        """
        Calculate detailed compatibility scores between user and team
        
        Args:
            user_profile: User profile
            team_data: Team opportunity data
            similarity_score: Vector similarity score from OpenSearch
            
        Returns:
            MatchScore with detailed compatibility metrics
        """
        try:
            purpose = user_profile.purpose_profile
            
            # Skill alignment calculation
            user_skills = {skill.name.lower() for skill in purpose.skills.all_skills}
            required_skills = {skill.lower() for skill in team_data.get('required_skills', [])}
            
            if required_skills:
                skill_overlap = len(user_skills.intersection(required_skills))
                skill_alignment = skill_overlap / len(required_skills)
            else:
                skill_alignment = 0.5  # Neutral if no requirements specified
            
            # Value alignment calculation
            user_values = {value.lower() for value in purpose.values.core}
            team_values = {value.lower() for value in team_data.get('team_values', [])}
            
            if team_values:
                value_overlap = len(user_values.intersection(team_values))
                value_alignment = value_overlap / max(len(team_values), len(user_values))
            else:
                value_alignment = 0.5  # Neutral if no team values specified
            
            # Work style compatibility (simplified)
            work_style_compatibility = 0.8  # Default high compatibility
            
            # Purpose alignment based on impact areas
            user_impact = {area.lower() for area in purpose.impact_areas}
            team_impact = {team_data.get('impact_area', '').lower()}
            
            if user_impact and team_impact:
                purpose_overlap = len(user_impact.intersection(team_impact))
                purpose_alignment = purpose_overlap / max(len(user_impact), len(team_impact))
            else:
                purpose_alignment = 0.6  # Default moderate alignment
            
            # Calculate weighted overall score
            weights = self.config["compatibility_weights"]
            overall_score = (
                skill_alignment * weights["skills"] +
                value_alignment * weights["values"] +
                work_style_compatibility * weights["work_style"] +
                purpose_alignment * weights["purpose"]
            )
            
            # Boost with vector similarity
            overall_score = (overall_score * 0.7) + (min(similarity_score / 10.0, 1.0) * 0.3)
            overall_score = min(1.0, overall_score)  # Cap at 1.0
            
            return MatchScore(
                overallScore=overall_score,
                skillAlignment=skill_alignment,
                valueAlignment=value_alignment,
                workStyleCompatibility=work_style_compatibility,
                purposeAlignment=purpose_alignment
            )
            
        except Exception as e:
            logger.error(f"Error calculating compatibility score: {str(e)}")
            return MatchScore(
                overallScore=0.5,
                skillAlignment=0.5,
                valueAlignment=0.5,
                workStyleCompatibility=0.5,
                purposeAlignment=0.5
            )

    def _generate_match_explanation(self, user_profile: UserProfile, team_data: Dict, 
                                  similarity_score: float) -> str:
        """
        Generate explainable AI (XAI) summary for match using Claude
        
        Args:
            user_profile: User profile
            team_data: Team opportunity data
            similarity_score: Vector similarity score
            
        Returns:
            Human-readable explanation of the match
        """
        try:
            purpose = user_profile.purpose_profile
            
            # Create context for Claude
            prompt = f"""
            Explain why this team opportunity is a good match for this user. Be specific and encouraging.
            
            User Profile:
            - Values: {', '.join(purpose.values.core)}
            - Skills: {', '.join([skill.name for skill in purpose.skills.all_skills[:5]])}
            - Passions: {', '.join(purpose.passions)}
            - Mission: {purpose.mission_statement or 'Seeking meaningful work'}
            
            Team Opportunity:
            - Name: {team_data.get('team_name', 'Team Opportunity')}
            - Mission: {team_data.get('mission', 'Making positive impact')}
            - Description: {team_data.get('description', 'Collaborative project')}
            - Required Skills: {', '.join(team_data.get('required_skills', []))}
            - Values: {', '.join(team_data.get('team_values', []))}
            
            Similarity Score: {similarity_score:.2f}/10
            
            Provide a 2-3 sentence explanation focusing on alignment and growth opportunities.
            """
            
            explanation = self._call_claude(prompt)
            return explanation
            
        except Exception as e:
            logger.error(f"Error generating match explanation: {str(e)}")
            return f"This team opportunity aligns well with your skills and values, offering a {similarity_score:.1f}/10 compatibility match."

    def _call_claude(self, prompt: str) -> str:
        """
        Call Claude model for text generation
        
        Args:
            prompt: Input prompt for Claude
            
        Returns:
            Generated text response
        """
        try:
            response = self.bedrock.invoke_model(
                modelId=self.claude_model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.config["explanation_max_tokens"],
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )
            
            response_body = json.loads(response['body'].read())
            content = response_body.get('content', [])
            
            if content and len(content) > 0:
                return content[0].get('text', 'Unable to generate explanation.')
            else:
                return 'Unable to generate detailed explanation at this time.'
                
        except Exception as e:
            logger.error(f"Error calling Claude: {str(e)}")
            return 'Unable to generate detailed explanation due to service unavailability.'

    def _generate_match_reasons(self, user_profile: UserProfile, team_data: Dict, 
                              match_score: MatchScore) -> List[MatchReason]:
        """
        Generate specific reasons for the match recommendation
        
        Args:
            user_profile: User profile
            team_data: Team opportunity data
            match_score: Calculated match scores
            
        Returns:
            List of MatchReason objects
        """
        reasons = []
        
        try:
            # Skill-based reason
            if match_score.skill_alignment > 0.6:
                reasons.append(MatchReason(
                    reasonType="skills",
                    description=f"Your skills align well with {len(team_data.get('required_skills', []))} required competencies",
                    weight=match_score.skill_alignment
                ))
            
            # Value-based reason
            if match_score.value_alignment > 0.5:
                reasons.append(MatchReason(
                    reasonType="values",
                    description=f"Shared values create strong cultural fit with this team",
                    weight=match_score.value_alignment
                ))
            
            # Purpose-based reason
            if match_score.purpose_alignment > 0.5:
                reasons.append(MatchReason(
                    reasonType="purpose",
                    description=f"Mission alignment with {team_data.get('impact_area', 'team goals')}",
                    weight=match_score.purpose_alignment
                ))
            
            # Ensure at least one reason
            if not reasons:
                reasons.append(MatchReason(
                    reasonType="general",
                    description="Good overall compatibility based on profile analysis",
                    weight=match_score.overall_score
                ))
                
        except Exception as e:
            logger.error(f"Error generating match reasons: {str(e)}")
            reasons = [MatchReason(
                reasonType="general",
                description="Compatibility identified through AI analysis",
                weight=0.7
            )]
        
        return reasons

    def _generate_recommended_actions(self, user_profile: UserProfile, team_data: Dict) -> List[str]:
        """
        Generate recommended next steps for the user
        
        Args:
            user_profile: User profile
            team_data: Team opportunity data
            
        Returns:
            List of recommended action strings
        """
        actions = []
        
        try:
            # Always include basic actions
            actions.extend([
                f"Review the {team_data.get('team_name', 'team')} mission and project details",
                "Connect with current team members to learn more about the culture",
                "Prepare questions about role expectations and growth opportunities"
            ])
            
            # Add skill-specific actions
            required_skills = team_data.get('required_skills', [])
            user_skills = {skill.name.lower() for skill in user_profile.purpose_profile.skills.all_skills}
            
            missing_skills = [skill for skill in required_skills 
                            if skill.lower() not in user_skills]
            
            if missing_skills:
                actions.append(f"Consider developing skills in: {', '.join(missing_skills[:2])}")
            
        except Exception as e:
            logger.error(f"Error generating recommended actions: {str(e)}")
            actions = [
                "Review team details and mission alignment",
                "Connect with team members",
                "Prepare for initial conversation"
            ]
        
        return actions

    def index_team_opportunity(self, team_opportunity: TeamOpportunity) -> bool:
        """
        Index a team opportunity in OpenSearch with vector embedding
        
        Args:
            team_opportunity: Team opportunity to index
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create text representation for embedding
            opportunity_text = self._create_opportunity_text(team_opportunity)
            
            # Generate embedding
            embedding = self._generate_text_embedding(opportunity_text)
            if not embedding:
                logger.error("Failed to generate embedding for team opportunity")
                return False
            
            # Prepare document for indexing
            doc = {
                "team_id": team_opportunity.opportunity_id,
                "team_name": team_opportunity.title,
                "description": team_opportunity.description,
                "required_skills": team_opportunity.required_skills,
                "preferred_skills": team_opportunity.preferred_skills,
                "team_size": team_opportunity.team_size,
                "commitment_hours": team_opportunity.commitment_hours,
                "impact_area": team_opportunity.impact_area,
                "community_served": team_opportunity.community_served,
                "expected_impact": team_opportunity.expected_impact,
                "created_at": team_opportunity.created_at.isoformat(),
                "is_active": team_opportunity.is_active,
                "embedding": embedding,
                "indexed_at": datetime.now().isoformat()
            }
            
            # Index in OpenSearch
            url = f"http://{self.opensearch_endpoint}/{self.opensearch_index}/_doc/{team_opportunity.opportunity_id}"
            headers = {"Content-Type": "application/json"}
            
            response = requests.put(url, headers=headers, json=doc, timeout=30)
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully indexed team opportunity {team_opportunity.opportunity_id}")
                return True
            else:
                logger.error(f"Failed to index team opportunity: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error indexing team opportunity: {str(e)}")
            return False

    def _create_opportunity_text(self, team_opportunity: TeamOpportunity) -> str:
        """
        Create text representation of team opportunity for embedding
        
        Args:
            team_opportunity: Team opportunity to convert to text
            
        Returns:
            Text representation
        """
        text_parts = [
            f"Team: {team_opportunity.title}",
            f"Description: {team_opportunity.description}",
            f"Impact area: {team_opportunity.impact_area}",
            f"Community served: {team_opportunity.community_served}",
            f"Expected impact: {team_opportunity.expected_impact}",
            f"Required skills: {', '.join(team_opportunity.required_skills)}",
            f"Team size: {team_opportunity.team_size} members",
            f"Commitment: {team_opportunity.commitment_hours} hours per week"
        ]
        
        if team_opportunity.preferred_skills:
            text_parts.append(f"Preferred skills: {', '.join(team_opportunity.preferred_skills)}")
        
        return " ".join(text_parts)

    def _generate_text_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for arbitrary text
        
        Args:
            text: Text to embed
            
        Returns:
            Vector embedding
        """
        try:
            response = self.bedrock.invoke_model(
                modelId=self.embedding_model_id,
                body=json.dumps({
                    "inputText": text
                })
            )
            
            response_body = json.loads(response['body'].read())
            return response_body.get('embedding', [])
            
        except Exception as e:
            logger.error(f"Error generating text embedding: {str(e)}")
            return []

    def get_match_analytics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get analytics on matching performance for a user
        
        Args:
            user_id: User ID to analyze
            days: Number of days to look back
            
        Returns:
            Analytics dictionary
        """
        # This would typically query a database of past matches
        # For now, return mock analytics
        return {
            "user_id": user_id,
            "period_days": days,
            "total_matches_found": 15,
            "high_quality_matches": 8,
            "average_match_score": 0.78,
            "top_match_categories": ["Technology", "Education", "Environment"],
            "recommendation_accuracy": 0.85,
            "user_engagement_rate": 0.72
        }