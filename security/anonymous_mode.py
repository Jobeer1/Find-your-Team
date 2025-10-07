"""
Anonymous Mode System

This module provides anonymous operation capabilities with secure key management,
allowing users to interact with the platform without revealing their identity.
"""

import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
import sqlite3
import json
from .privacy_security import AnonymousProfile, EncryptionManager, DataType

logger = logging.getLogger(__name__)


class AnonymousSession:
    """Manages anonymous user sessions"""
    
    def __init__(self, anonymous_id: str, session_key: bytes, user_hash: Optional[str] = None):
        self.anonymous_id = anonymous_id
        self.session_key = session_key
        self.user_hash = user_hash
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.allowed_operations: Set[str] = set()
        self.temporary_data: Dict[str, Any] = {}
        
    def is_expired(self, session_timeout_minutes: int = 30) -> bool:
        """Check if session is expired"""
        expiry_time = self.last_activity + timedelta(minutes=session_timeout_minutes)
        return datetime.utcnow() > expiry_time
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()
    
    def add_allowed_operation(self, operation: str):
        """Add allowed operation to session"""
        self.allowed_operations.add(operation)
    
    def can_perform_operation(self, operation: str) -> bool:
        """Check if operation is allowed in this session"""
        return operation in self.allowed_operations
    
    def store_temporary_data(self, key: str, data: Any):
        """Store temporary data in session"""
        self.temporary_data[key] = data
    
    def get_temporary_data(self, key: str) -> Any:
        """Retrieve temporary data from session"""
        return self.temporary_data.get(key)


class AnonymousManager:
    """Manager for anonymous mode operations"""
    
    def __init__(self, storage_path: str = "security/anonymous.db"):
        self.storage_path = storage_path
        self.active_sessions: Dict[str, AnonymousSession] = {}
        self.encryption_manager = EncryptionManager()
        self.session_timeout_minutes = 30
        self._init_storage()
    
    def _init_storage(self):
        """Initialize anonymous mode storage"""
        import os
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        
        conn = sqlite3.connect(self.storage_path)
        
        # Anonymous profiles table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS anonymous_profiles (
                anonymous_id TEXT PRIMARY KEY,
                user_hash TEXT,
                session_key TEXT,
                created_at TEXT,
                expires_at TEXT,
                allowed_operations TEXT,
                temporary_data TEXT,
                last_activity TEXT
            )
        ''')
        
        # Anonymous operations log
        conn.execute('''
            CREATE TABLE IF NOT EXISTS anonymous_operations (
                operation_id TEXT PRIMARY KEY,
                anonymous_id TEXT,
                operation_type TEXT,
                timestamp TEXT,
                success BOOLEAN,
                details TEXT
            )
        ''')
        
        # Create indexes
        conn.execute('CREATE INDEX IF NOT EXISTS idx_anonymous_hash ON anonymous_profiles (user_hash)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_anonymous_operations ON anonymous_operations (anonymous_id)')
        
        conn.commit()
        conn.close()
    
    def create_anonymous_session(self, user_data: Optional[Dict] = None) -> str:
        """Create a new anonymous session"""
        # Generate anonymous ID and session key
        anonymous_id = secrets.token_urlsafe(24)
        session_key = secrets.token_bytes(32)
        
        # Create user hash if user data provided (for matching purposes)
        user_hash = None
        if user_data:
            # Create deterministic hash of user data for anonymous matching
            user_str = json.dumps(user_data, sort_keys=True)
            user_hash = hashlib.sha256(user_str.encode()).hexdigest()
        
        # Create session
        session = AnonymousSession(anonymous_id, session_key, user_hash)
        
        # Set default allowed operations for anonymous mode
        default_operations = {
            'profile_creation',
            'basic_matching',
            'skill_assessment',
            'team_exploration',
            'chat_interaction'
        }
        
        for op in default_operations:
            session.add_allowed_operation(op)
        
        # Store session
        self.active_sessions[anonymous_id] = session
        self._persist_session(session)
        
        logger.info(f"Anonymous session created: {anonymous_id}")
        return anonymous_id
    
    def get_session(self, anonymous_id: str) -> Optional[AnonymousSession]:
        """Get anonymous session by ID"""
        # Check active sessions first
        if anonymous_id in self.active_sessions:
            session = self.active_sessions[anonymous_id]
            if not session.is_expired(self.session_timeout_minutes):
                session.update_activity()
                return session
            else:
                # Remove expired session
                del self.active_sessions[anonymous_id]
                self._remove_session(anonymous_id)
        
        # Try to load from database
        session = self._load_session(anonymous_id)
        if session and not session.is_expired(self.session_timeout_minutes):
            session.update_activity()
            self.active_sessions[anonymous_id] = session
            return session
        
        return None
    
    def extend_session(self, anonymous_id: str, additional_operations: List[str] = None) -> bool:
        """Extend anonymous session with additional operations"""
        session = self.get_session(anonymous_id)
        if not session:
            return False
        
        # Add additional operations if specified
        if additional_operations:
            for op in additional_operations:
                session.add_allowed_operation(op)
        
        # Update activity and persist
        session.update_activity()
        self._persist_session(session)
        
        return True
    
    def perform_anonymous_operation(
        self, 
        anonymous_id: str, 
        operation_type: str, 
        operation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform operation in anonymous mode"""
        session = self.get_session(anonymous_id)
        if not session:
            return {'success': False, 'error': 'Invalid or expired anonymous session'}
        
        if not session.can_perform_operation(operation_type):
            return {'success': False, 'error': f'Operation {operation_type} not allowed in anonymous mode'}
        
        # Log operation
        self._log_anonymous_operation(anonymous_id, operation_type, True, operation_data)
        
        # Perform the operation based on type
        try:
            if operation_type == 'profile_creation':
                result = self._handle_anonymous_profile_creation(session, operation_data)
            elif operation_type == 'basic_matching':
                result = self._handle_anonymous_matching(session, operation_data)
            elif operation_type == 'skill_assessment':
                result = self._handle_anonymous_skill_assessment(session, operation_data)
            elif operation_type == 'team_exploration':
                result = self._handle_anonymous_team_exploration(session, operation_data)
            elif operation_type == 'chat_interaction':
                result = self._handle_anonymous_chat(session, operation_data)
            else:
                result = {'success': False, 'error': f'Unknown operation type: {operation_type}'}
            
            session.update_activity()
            self._persist_session(session)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in anonymous operation {operation_type}: {e}")
            self._log_anonymous_operation(anonymous_id, operation_type, False, {'error': str(e)})
            return {'success': False, 'error': 'Internal error during anonymous operation'}
    
    def _handle_anonymous_profile_creation(self, session: AnonymousSession, data: Dict) -> Dict:
        """Handle anonymous profile creation"""
        # Store profile data temporarily in session (encrypted)
        profile_data = {
            'skills': data.get('skills', []),
            'interests': data.get('interests', []),
            'values': data.get('values', []),
            'experience_level': data.get('experience_level', 'beginner'),
            'availability': data.get('availability', {})
        }
        
        # Encrypt sensitive data
        encrypted_data, key_id = self.encryption_manager.encrypt_data(profile_data)
        session.store_temporary_data('encrypted_profile', {
            'data': encrypted_data.hex(),
            'key_id': key_id
        })
        
        return {
            'success': True,
            'message': 'Anonymous profile created',
            'profile_id': f"anon_{session.anonymous_id[:8]}"
        }
    
    def _handle_anonymous_matching(self, session: AnonymousSession, data: Dict) -> Dict:
        """Handle anonymous team matching"""
        # Simple matching based on stored profile data
        encrypted_profile = session.get_temporary_data('encrypted_profile')
        if not encrypted_profile:
            return {'success': False, 'error': 'No profile data available for matching'}
        
        # For demo purposes, return mock matches
        matches = [
            {
                'team_id': f"team_anon_{i}",
                'compatibility_score': 85 - (i * 5),
                'focus_areas': ['innovation', 'technology', 'impact'],
                'description': f"Anonymous team #{i+1} focused on making positive impact"
            }
            for i in range(3)
        ]
        
        return {
            'success': True,
            'matches': matches,
            'matching_criteria': 'anonymous_algorithm'
        }
    
    def _handle_anonymous_skill_assessment(self, session: AnonymousSession, data: Dict) -> Dict:
        """Handle anonymous skill assessment"""
        skills = data.get('skills', [])
        
        # Generate anonymous skill assessment
        assessment = {
            'assessed_skills': len(skills),
            'confidence_score': 0.7,  # Lower confidence for anonymous assessment
            'recommendations': [
                'Continue developing your technical skills',
                'Consider joining collaborative projects',
                'Explore leadership opportunities'
            ],
            'anonymous_id': session.anonymous_id[:8]  # Partial ID for reference
        }
        
        session.store_temporary_data('skill_assessment', assessment)
        
        return {
            'success': True,
            'assessment': assessment
        }
    
    def _handle_anonymous_team_exploration(self, session: AnonymousSession, data: Dict) -> Dict:
        """Handle anonymous team exploration"""
        preferences = data.get('preferences', {})
        
        # Generate team exploration results
        teams = [
            {
                'team_name': f"Project Team {i+1}",
                'description': f"Working on innovative project in {area}",
                'open_roles': ['developer', 'designer', 'analyst'],
                'commitment_level': 'part-time',
                'anonymous_friendly': True
            }
            for i, area in enumerate(['AI/ML', 'Web Development', 'Data Science'])
        ]
        
        return {
            'success': True,
            'available_teams': teams,
            'exploration_mode': 'anonymous'
        }
    
    def _handle_anonymous_chat(self, session: AnonymousSession, data: Dict) -> Dict:
        """Handle anonymous chat interaction"""
        message = data.get('message', '')
        
        # Process anonymous chat (limited functionality)
        responses = [
            "I understand you're exploring anonymously. How can I help you discover teams?",
            "In anonymous mode, I can help you understand team opportunities without revealing your identity.",
            "Would you like to learn more about team matching while staying anonymous?",
            "I can provide general guidance about skills and team dynamics in anonymous mode."
        ]
        
        # Select response based on message content
        response = responses[0]  # Default response
        
        if 'team' in message.lower():
            response = responses[1]
        elif 'match' in message.lower():
            response = responses[2]
        elif 'skill' in message.lower():
            response = responses[3]
        
        return {
            'success': True,
            'response': response,
            'mode': 'anonymous',
            'limitations': 'Full AI analysis not available in anonymous mode'
        }
    
    def convert_to_registered_user(self, anonymous_id: str, user_id: str) -> Dict[str, Any]:
        """Convert anonymous session to registered user"""
        session = self.get_session(anonymous_id)
        if not session:
            return {'success': False, 'error': 'Anonymous session not found'}
        
        # Retrieve temporary data from anonymous session
        profile_data = session.get_temporary_data('encrypted_profile')
        skill_assessment = session.get_temporary_data('skill_assessment')
        
        # Prepare data transfer
        transferred_data = {}
        if profile_data:
            # Decrypt profile data
            try:
                encrypted_bytes = bytes.fromhex(profile_data['data'])
                decrypted_data = self.encryption_manager.decrypt_data(
                    encrypted_bytes, 
                    profile_data['key_id']
                )
                transferred_data['profile'] = json.loads(decrypted_data.decode())
            except Exception as e:
                logger.error(f"Error decrypting anonymous profile: {e}")
        
        if skill_assessment:
            transferred_data['skill_assessment'] = skill_assessment
        
        # Clean up anonymous session
        self.terminate_session(anonymous_id)
        
        logger.info(f"Anonymous session converted to user: {anonymous_id} -> {user_id}")
        
        return {
            'success': True,
            'transferred_data': transferred_data,
            'message': 'Anonymous data successfully transferred to your account'
        }
    
    def terminate_session(self, anonymous_id: str) -> bool:
        """Terminate anonymous session"""
        # Remove from active sessions
        if anonymous_id in self.active_sessions:
            del self.active_sessions[anonymous_id]
        
        # Remove from database
        self._remove_session(anonymous_id)
        
        logger.info(f"Anonymous session terminated: {anonymous_id}")
        return True
    
    def cleanup_expired_sessions(self):
        """Clean up expired anonymous sessions"""
        expired_sessions = []
        
        for anonymous_id, session in self.active_sessions.items():
            if session.is_expired(self.session_timeout_minutes):
                expired_sessions.append(anonymous_id)
        
        for anonymous_id in expired_sessions:
            self.terminate_session(anonymous_id)
        
        # Also clean up database
        expiry_time = datetime.utcnow() - timedelta(minutes=self.session_timeout_minutes)
        
        conn = sqlite3.connect(self.storage_path)
        conn.execute(
            'DELETE FROM anonymous_profiles WHERE last_activity < ?',
            (expiry_time.isoformat(),)
        )
        conn.commit()
        conn.close()
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired anonymous sessions")
    
    def get_anonymous_statistics(self) -> Dict[str, Any]:
        """Get statistics about anonymous usage"""
        conn = sqlite3.connect(self.storage_path)
        
        # Active sessions
        cursor = conn.execute('SELECT COUNT(*) FROM anonymous_profiles')
        total_profiles = cursor.fetchone()[0]
        
        # Recent operations
        recent_time = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        cursor = conn.execute(
            'SELECT COUNT(*) FROM anonymous_operations WHERE timestamp > ?',
            (recent_time,)
        )
        recent_operations = cursor.fetchone()[0]
        
        # Operations by type
        cursor = conn.execute('''
            SELECT operation_type, COUNT(*) 
            FROM anonymous_operations 
            WHERE timestamp > ?
            GROUP BY operation_type
        ''', (recent_time,))
        operations_by_type = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            'active_sessions': len(self.active_sessions),
            'total_profiles': total_profiles,
            'recent_operations_24h': recent_operations,
            'operations_by_type': operations_by_type,
            'session_timeout_minutes': self.session_timeout_minutes
        }
    
    def _persist_session(self, session: AnonymousSession):
        """Persist session to database"""
        conn = sqlite3.connect(self.storage_path)
        conn.execute('''
            INSERT OR REPLACE INTO anonymous_profiles 
            (anonymous_id, user_hash, session_key, created_at, expires_at, 
             allowed_operations, temporary_data, last_activity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session.anonymous_id,
            session.user_hash,
            session.session_key.hex(),
            session.created_at.isoformat(),
            (session.created_at + timedelta(hours=24)).isoformat(),  # 24h expiry
            json.dumps(list(session.allowed_operations)),
            json.dumps(session.temporary_data),
            session.last_activity.isoformat()
        ))
        conn.commit()
        conn.close()
    
    def _load_session(self, anonymous_id: str) -> Optional[AnonymousSession]:
        """Load session from database"""
        conn = sqlite3.connect(self.storage_path)
        cursor = conn.execute(
            'SELECT * FROM anonymous_profiles WHERE anonymous_id = ?',
            (anonymous_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        session = AnonymousSession(
            anonymous_id=row[0],
            session_key=bytes.fromhex(row[2]),
            user_hash=row[1]
        )
        
        session.created_at = datetime.fromisoformat(row[3])
        session.last_activity = datetime.fromisoformat(row[7])
        
        # Load allowed operations
        try:
            session.allowed_operations = set(json.loads(row[5]))
        except (json.JSONDecodeError, TypeError):
            session.allowed_operations = set()
        
        # Load temporary data
        try:
            session.temporary_data = json.loads(row[6])
        except (json.JSONDecodeError, TypeError):
            session.temporary_data = {}
        
        return session
    
    def _remove_session(self, anonymous_id: str):
        """Remove session from database"""
        conn = sqlite3.connect(self.storage_path)
        conn.execute('DELETE FROM anonymous_profiles WHERE anonymous_id = ?', (anonymous_id,))
        conn.commit()
        conn.close()
    
    def _log_anonymous_operation(self, anonymous_id: str, operation_type: str, success: bool, details: Dict):
        """Log anonymous operation"""
        operation_id = secrets.token_urlsafe(16)
        
        conn = sqlite3.connect(self.storage_path)
        conn.execute('''
            INSERT INTO anonymous_operations 
            (operation_id, anonymous_id, operation_type, timestamp, success, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            operation_id,
            anonymous_id,
            operation_type,
            datetime.utcnow().isoformat(),
            success,
            json.dumps(details)
        ))
        conn.commit()
        conn.close()


# Initialize global anonymous manager
anonymous_manager = AnonymousManager()

logger.info("Anonymous mode system initialized")