"""
Find Your Team - Onboarding Agent
Handles user onboarding conversations to build comprehensive Purpose Profiles
"""

import json
import boto3
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from models.core_models import (
    UserProfile, PurposeProfile, Values, WorkStyle, Skills, Skill,
    SkillLevel, WorkStylePreference, CommunicationStyle, StructurePreference,
    UserStatus
)
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class OnboardingAgent:
    """
    AI-powered agent that conducts conversational onboarding to build Purpose Profiles
    """

    def __init__(self, bedrock_client=None, memory_table_name: str = "ConversationMemory"):
        """
        Initialize the Onboarding Agent

        Args:
            bedrock_client: Optional boto3 Bedrock client for testing
            memory_table_name: DynamoDB table name for conversation memory
        """
        self.bedrock = bedrock_client or boto3.client('bedrock-runtime')
        self.memory_table = memory_table_name
        self.dynamodb = boto3.resource('dynamodb')
        self.memory_table_resource = self.dynamodb.Table(self.memory_table)

        # Claude 3.5 Sonnet model ID
        self.model_id = "anthropic.claude-3-5-sonnet-20240620"

    def start_conversation(self, user_id: str, initial_message: str = "") -> Dict[str, Any]:
        """
        Start a new onboarding conversation

        Args:
            user_id: Unique identifier for the user
            initial_message: Optional initial message from user

        Returns:
            Dict containing response message and conversation state
        """
        try:
            # Initialize conversation memory
            conversation_id = f"onboarding-{user_id}-{int(datetime.now().timestamp())}"

            # Create initial memory entry
            initial_memory = {
                'conversation_id': conversation_id,
                'user_id': user_id,
                'messages': [],
                'profile_data': {},
                'confidence_score': 0.0,
                'current_stage': 'greeting',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }

            # Store initial memory
            self._save_memory(initial_memory)

            # Generate initial response
            if initial_message:
                return self.process_message(conversation_id, initial_message)
            else:
                return self._generate_greeting_response(conversation_id)

        except Exception as e:
            logger.error(f"Error starting conversation for user {user_id}: {str(e)}")
            return {
                'response': "I'm sorry, I'm having trouble starting our conversation. Please try again.",
                'conversation_id': conversation_id if 'conversation_id' in locals() else None,
                'error': str(e)
            }

    def process_message(self, conversation_id: str, user_message: str) -> Dict[str, Any]:
        """
        Process a user message and generate appropriate response

        Args:
            conversation_id: Unique conversation identifier
            user_message: User's message

        Returns:
            Dict containing response and updated conversation state
        """
        try:
            # Load conversation memory
            memory = self._load_memory(conversation_id)
            if not memory:
                return {
                    'response': "I can't find our conversation. Let's start over.",
                    'conversation_id': conversation_id,
                    'error': 'conversation_not_found'
                }

            # Add user message to memory
            memory['messages'].append({
                'role': 'user',
                'content': user_message,
                'timestamp': datetime.now().isoformat()
            })

            # Determine next action based on current stage and message
            current_stage = memory.get('current_stage', 'greeting')

            if current_stage == 'greeting':
                response, next_stage = self._handle_greeting_stage(memory, user_message)
            elif current_stage == 'values_discovery':
                response, next_stage = self._handle_values_discovery(memory, user_message)
            elif current_stage == 'passions_exploration':
                response, next_stage = self._handle_passions_exploration(memory, user_message)
            elif current_stage == 'work_style_assessment':
                response, next_stage = self._handle_work_style_assessment(memory, user_message)
            elif current_stage == 'skills_inventory':
                response, next_stage = self._handle_skills_inventory(memory, user_message)
            elif current_stage == 'personality_assessment':
                response, next_stage = self._handle_personality_assessment(memory, user_message)
            elif current_stage == 'profile_completion':
                response, next_stage = self._complete_profile(memory)
            else:
                response, next_stage = self._handle_general_query(memory, user_message)

            # Update memory
            memory['current_stage'] = next_stage
            memory['updated_at'] = datetime.now().isoformat()

            # Add agent response to memory
            memory['messages'].append({
                'role': 'assistant',
                'content': response,
                'timestamp': datetime.now().isoformat()
            })

            # Save updated memory
            self._save_memory(memory)

            # Check if profile is complete
            profile_complete = self._check_profile_completion(memory)

            return {
                'response': response,
                'conversation_id': conversation_id,
                'current_stage': next_stage,
                'profile_complete': profile_complete,
                'confidence_score': memory.get('confidence_score', 0.0)
            }

        except Exception as e:
            logger.error(f"Error processing message for conversation {conversation_id}: {str(e)}")
            return {
                'response': "I'm sorry, I encountered an error processing your message. Please try again.",
                'conversation_id': conversation_id,
                'error': str(e)
            }

    def get_purpose_profile(self, conversation_id: str) -> Optional[UserProfile]:
        """
        Generate a complete UserProfile from conversation data

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            UserProfile object if profile is complete, None otherwise
        """
        try:
            memory = self._load_memory(conversation_id)
            if not memory or not self._check_profile_completion(memory):
                return None

            profile_data = memory.get('profile_data', {})

            # Build PurposeProfile from collected data
            purpose_profile = PurposeProfile(
                values=Values(
                    core=profile_data.get('core_values', []),
                    secondary=profile_data.get('secondary_values', []),
                    weights=profile_data.get('value_weights', {})
                ),
                workStyle=WorkStyle(
                    collaboration=profile_data.get('collaboration_preference', WorkStylePreference.MEDIUM),
                    autonomy=profile_data.get('autonomy_preference', WorkStylePreference.MEDIUM),
                    structure=profile_data.get('structure_preference', StructurePreference.MODERATE),
                    communication=profile_data.get('communication_style', CommunicationStyle.DIPLOMATIC),
                    remote_preference=profile_data.get('remote_preference', 0.5)
                ),
                skills=Skills(
                    technical=profile_data.get('technical_skills', []),
                    soft=profile_data.get('soft_skills', []),
                    leadership=profile_data.get('leadership_skills', [])
                ),
                passions=profile_data.get('passions', []),
                mission_statement=profile_data.get('mission_statement'),
                impact_areas=profile_data.get('impact_areas', [])
            )

            # Create UserProfile
            user_profile = UserProfile(
                userId=memory['user_id'],
                purposeProfile=purpose_profile,
                confidenceScore=int(memory.get('confidence_score', 0) * 100),
                status=UserStatus.READY_FOR_MATCHING if memory.get('confidence_score', 0) >= 0.9 else UserStatus.ONBOARDING
            )

            return user_profile

        except Exception as e:
            logger.error(f"Error generating profile for conversation {conversation_id}: {str(e)}")
            return None

    def _generate_greeting_response(self, conversation_id: str) -> Dict[str, Any]:
        """Generate initial greeting response"""
        response = """Hello! I'm excited to help you discover your perfect team and purpose-driven opportunities.

I'm the Onboarding Agent for Find Your Team, and together we'll build a comprehensive profile of your values, passions, skills, and work style. This will help us find teams and projects that truly align with who you are and what you want to achieve.

To get started, could you tell me a bit about what brings you here? What are you hoping to accomplish by joining or forming a team?"""

        return {
            'response': response,
            'conversation_id': conversation_id,
            'current_stage': 'values_discovery',
            'profile_complete': False,
            'confidence_score': 0.0
        }

    def _handle_greeting_stage(self, memory: Dict, user_message: str) -> Tuple[str, str]:
        """Handle initial greeting and transition to values discovery"""
        # Use Claude to analyze the user's initial motivation
        prompt = f"""Analyze this user's initial message and determine their primary motivation for joining Find Your Team.
        Then provide a natural response that acknowledges their motivation and transitions into values discovery.

        User message: "{user_message}"

        Respond as a friendly onboarding agent who wants to understand their core values."""

        response = self._call_claude(prompt)

        return response, 'values_discovery'

    def _handle_values_discovery(self, memory: Dict, user_message: str) -> Tuple[str, str]:
        """Handle values discovery stage"""
        prompt = f"""Based on the conversation so far, help the user identify and articulate their core values.
        Current profile data: {json.dumps(memory.get('profile_data', {}))}

        User message: "{user_message}"

        Guide them to identify 3-5 core values that drive their decisions and work.
        If they seem ready to move on, transition to passions exploration."""

        response = self._call_claude(prompt)

        # Update profile data with extracted values if possible
        self._extract_values_from_message(memory, user_message)

        next_stage = 'passions_exploration' if self._should_transition_to_passions(memory) else 'values_discovery'
        return response, next_stage

    def _handle_passions_exploration(self, memory: Dict, user_message: str) -> Tuple[str, str]:
        """Handle passions exploration stage"""
        prompt = f"""Help the user explore their passions and what energizes them in their work.
        Current profile data: {json.dumps(memory.get('profile_data', {}))}

        User message: "{user_message}"

        Focus on what they love doing, what problems they want to solve, and what impact they want to make."""

        response = self._call_claude(prompt)

        # Extract passions from message
        self._extract_passions_from_message(memory, user_message)

        next_stage = 'work_style_assessment' if self._should_transition_to_work_style(memory) else 'passions_exploration'
        return response, next_stage

    def _handle_work_style_assessment(self, memory: Dict, user_message: str) -> Tuple[str, str]:
        """Handle work style assessment"""
        prompt = f"""Assess the user's work style preferences including collaboration style, autonomy needs, structure preferences, and communication style.
        Current profile data: {json.dumps(memory.get('profile_data', {}))}

        User message: "{user_message}"

        Ask questions that help determine their preferences for remote vs office work, team vs individual work, structured vs flexible environments."""

        response = self._call_claude(prompt)

        # Extract work style preferences
        self._extract_work_style_from_message(memory, user_message)

        next_stage = 'skills_inventory' if self._should_transition_to_skills(memory) else 'work_style_assessment'
        return response, next_stage

    def _handle_skills_inventory(self, memory: Dict, user_message: str) -> Tuple[str, str]:
        """Handle skills inventory"""
        prompt = f"""Help the user inventory their technical, soft, and leadership skills.
        Current profile data: {json.dumps(memory.get('profile_data', {}))}

        User message: "{user_message}"

        Ask about their experience levels, areas of expertise, and skills they want to develop."""

        response = self._call_claude(prompt)

        # Extract skills from message
        self._extract_skills_from_message(memory, user_message)

        next_stage = 'personality_assessment' if self._should_transition_to_personality(memory) else 'skills_inventory'
        return response, next_stage

    def _handle_personality_assessment(self, memory: Dict, user_message: str) -> Tuple[str, str]:
        """Handle personality assessment"""
        prompt = f"""Assess the user's personality traits that affect team dynamics.
        Current profile data: {json.dumps(memory.get('profile_data', {}))}

        User message: "{user_message}"

        Focus on traits like openness, conscientiousness, extraversion, agreeableness, and neuroticism through natural conversation."""

        response = self._call_claude(prompt)

        # Extract personality traits
        self._extract_personality_from_message(memory, user_message)

        next_stage = 'profile_completion' if self._should_complete_profile(memory) else 'personality_assessment'
        return response, next_stage

    def _complete_profile(self, memory: Dict) -> Tuple[str, str]:
        """Complete the profile and provide summary"""
        # Calculate final confidence score
        confidence = self._calculate_profile_confidence(memory)

        profile_summary = self._generate_profile_summary(memory)

        response = f"""Thank you for sharing so much about yourself! I've compiled your Purpose Profile with a confidence score of {confidence:.1%}.

{profile_summary}

Your profile is now ready for matching! We'll look for teams and opportunities that align with your values, passions, and work style. You can update your profile anytime by chatting with me again.

Would you like to see potential matches now, or would you prefer to refine any aspect of your profile first?"""

        return response, 'completed'

    def _call_claude(self, prompt: str, max_tokens: int = 1000) -> str:
        """Call Claude 3.5 Sonnet via Bedrock"""
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
                "temperature": 0.7,
                "top_p": 0.9
            }

            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )

            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']

        except Exception as e:
            logger.error(f"Error calling Claude: {e}")
            return "I'm sorry, I'm having trouble processing your request right now. Please try again."

    def _save_memory(self, memory: Dict) -> None:
        """Save conversation memory to DynamoDB"""
        try:
            self.memory_table_resource.put_item(Item=memory)
        except Exception as e:
            logger.error(f"Error saving memory: {e}")

    def _load_memory(self, conversation_id: str) -> Optional[Dict]:
        """Load conversation memory from DynamoDB"""
        try:
            response = self.memory_table_resource.get_item(Key={'conversation_id': conversation_id})
            return response.get('Item')
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
            return None

    def _check_profile_completion(self, memory: Dict) -> bool:
        """Check if profile has sufficient data for completion"""
        profile_data = memory.get('profile_data', {})

        required_fields = [
            'core_values', 'passions', 'technical_skills', 'soft_skills'
        ]

        return all(
            len(profile_data.get(field, [])) > 0 for field in required_fields
        ) and memory.get('confidence_score', 0) >= 0.8

    def _calculate_profile_confidence(self, memory: Dict) -> float:
        """Calculate overall profile confidence score"""
        profile_data = memory.get('profile_data', {})

        scores = []

        # Values score (20%)
        values_count = len(profile_data.get('core_values', []))
        scores.append(min(values_count / 5, 1.0) * 0.2)

        # Passions score (20%)
        passions_count = len(profile_data.get('passions', []))
        scores.append(min(passions_count / 5, 1.0) * 0.2)

        # Skills score (30%)
        technical_count = len(profile_data.get('technical_skills', []))
        soft_count = len(profile_data.get('soft_skills', []))
        skills_score = min((technical_count + soft_count) / 10, 1.0)
        scores.append(skills_score * 0.3)

        # Work style score (15%)
        work_style_fields = ['collaboration_preference', 'autonomy_preference', 'structure_preference']
        work_style_complete = sum(1 for field in work_style_fields if profile_data.get(field))
        scores.append((work_style_complete / len(work_style_fields)) * 0.15)

        # Personality score (15%)
        personality_fields = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']
        personality_complete = sum(1 for field in personality_fields if profile_data.get(field) is not None)
        scores.append((personality_complete / len(personality_fields)) * 0.15)

        return sum(scores)

    def _generate_profile_summary(self, memory: Dict) -> str:
        """Generate a human-readable profile summary"""
        profile_data = memory.get('profile_data', {})

        summary_parts = []

        if profile_data.get('core_values'):
            summary_parts.append(f"**Core Values:** {', '.join(profile_data['core_values'])}")

        if profile_data.get('passions'):
            summary_parts.append(f"**Passions:** {', '.join(profile_data['passions'])}")

        if profile_data.get('technical_skills') or profile_data.get('soft_skills'):
            all_skills = profile_data.get('technical_skills', []) + profile_data.get('soft_skills', [])
            if all_skills:
                summary_parts.append(f"**Key Skills:** {', '.join(all_skills[:5])}")

        if profile_data.get('mission_statement'):
            summary_parts.append(f"**Mission:** {profile_data['mission_statement']}")

        return "\n".join(summary_parts)

    # Helper methods for extracting data from messages
    def _extract_values_from_message(self, memory: Dict, message: str) -> None:
        """Extract values from user message using Claude"""
        # This would use Claude to extract structured data from natural language
        pass

    def _extract_passions_from_message(self, memory: Dict, message: str) -> None:
        """Extract passions from user message"""
        pass

    def _extract_work_style_from_message(self, memory: Dict, message: str) -> None:
        """Extract work style preferences from user message"""
        pass

    def _extract_skills_from_message(self, memory: Dict, message: str) -> None:
        """Extract skills from user message"""
        pass

    def _extract_personality_from_message(self, memory: Dict, message: str) -> None:
        """Extract personality traits from user message"""
        pass

    # Transition logic methods
    def _should_transition_to_passions(self, memory: Dict) -> bool:
        """Determine if ready to move to passions exploration"""
        return len(memory.get('profile_data', {}).get('core_values', [])) >= 3

    def _should_transition_to_work_style(self, memory: Dict) -> bool:
        """Determine if ready to move to work style assessment"""
        return len(memory.get('profile_data', {}).get('passions', [])) >= 2

    def _should_transition_to_skills(self, memory: Dict) -> bool:
        """Determine if ready to move to skills inventory"""
        profile_data = memory.get('profile_data', {})
        return (profile_data.get('collaboration_preference') and
                profile_data.get('autonomy_preference'))

    def _should_transition_to_personality(self, memory: Dict) -> bool:
        """Determine if ready to move to personality assessment"""
        profile_data = memory.get('profile_data', {})
        skills_count = (len(profile_data.get('technical_skills', [])) +
                       len(profile_data.get('soft_skills', [])))
        return skills_count >= 3

    def _should_complete_profile(self, memory: Dict) -> bool:
        """Determine if profile is ready for completion"""
        profile_data = memory.get('profile_data', {})
        personality_complete = all(
            profile_data.get(trait) is not None
            for trait in ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']
        )
        return personality_complete and self._calculate_profile_confidence(memory) >= 0.7