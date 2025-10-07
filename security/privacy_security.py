"""
Task 12 - Privacy and Security Controls

This module implements comprehensive privacy and security controls for the Find Your Team platform.

Requirements:
1. Client-side encryption for sensitive profile data
2. Granular privacy setting controls with real-time updates
3. Anonymous mode with secure key management
4. Data sharing consent mechanisms
5. Audit trails for all data access and modifications
6. Security tests for data protection and privacy enforcement

Features:
- End-to-end encryption for sensitive user data
- Fine-grained privacy controls per data type
- Anonymous operation mode with cryptographic anonymity
- Consent management with granular permissions
- Comprehensive audit logging and compliance reporting
- Security testing framework for privacy enforcement
"""

import os
import json
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import asyncio
import sqlite3
from pathlib import Path

# Cryptographic imports
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    import base64
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)


class PrivacyLevel(Enum):
    """Privacy levels for different types of data"""
    PUBLIC = "public"
    PRIVATE = "private"
    CONFIDENTIAL = "confidential"
    TOP_SECRET = "top_secret"


class DataType(Enum):
    """Types of data in the system"""
    PROFILE_BASIC = "profile_basic"
    PROFILE_DETAILED = "profile_detailed"
    PURPOSE_PROFILE = "purpose_profile"
    SKILLS_DATA = "skills_data"
    TEAM_PERFORMANCE = "team_performance"
    CHAT_HISTORY = "chat_history"
    GAMIFICATION_DATA = "gamification_data"
    LOCATION_DATA = "location_data"
    CONTACT_INFO = "contact_info"
    PREFERENCES = "preferences"


class ConsentType(Enum):
    """Types of consent for data processing"""
    DATA_PROCESSING = "data_processing"
    AI_ANALYSIS = "ai_analysis"
    TEAM_MATCHING = "team_matching"
    PERFORMANCE_TRACKING = "performance_tracking"
    MARKETING = "marketing"
    ANALYTICS = "analytics"
    THIRD_PARTY_SHARING = "third_party_sharing"


class AuditAction(Enum):
    """Types of audit actions"""
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"
    PRIVACY_SETTING_CHANGE = "privacy_setting_change"
    CONSENT_GIVEN = "consent_given"
    CONSENT_WITHDRAWN = "consent_withdrawn"
    ENCRYPTION_KEY_GENERATED = "encryption_key_generated"
    ANONYMOUS_MODE_ACTIVATED = "anonymous_mode_activated"
    DATA_EXPORT = "data_export"
    SECURITY_BREACH_DETECTED = "security_breach_detected"


@dataclass
class EncryptionKey:
    """Encryption key with metadata"""
    key_id: str
    key_data: bytes
    algorithm: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    key_type: str = "symmetric"  # symmetric, asymmetric_public, asymmetric_private
    
    def is_expired(self) -> bool:
        """Check if the key is expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


@dataclass
class PrivacySetting:
    """Privacy setting for a specific data type"""
    data_type: DataType
    privacy_level: PrivacyLevel
    allow_ai_processing: bool = True
    allow_team_matching: bool = True
    allow_analytics: bool = False
    allow_third_party: bool = False
    retention_days: Optional[int] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'data_type': self.data_type.value,
            'privacy_level': self.privacy_level.value,
            'allow_ai_processing': self.allow_ai_processing,
            'allow_team_matching': self.allow_team_matching,
            'allow_analytics': self.allow_analytics,
            'allow_third_party': self.allow_third_party,
            'retention_days': self.retention_days,
            'last_updated': self.last_updated.isoformat()
        }


@dataclass
class ConsentRecord:
    """Record of user consent for data processing"""
    consent_id: str
    user_id: str
    consent_type: ConsentType
    granted: bool
    granted_at: datetime
    expires_at: Optional[datetime] = None
    purpose: str = ""
    data_types: List[DataType] = field(default_factory=list)
    third_parties: List[str] = field(default_factory=list)
    
    def is_expired(self) -> bool:
        """Check if consent is expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if consent is valid (granted and not expired)"""
        return self.granted and not self.is_expired()


@dataclass
class AuditLog:
    """Audit log entry"""
    log_id: str
    user_id: str
    action: AuditAction
    data_type: Optional[DataType] = None
    resource_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'log_id': self.log_id,
            'user_id': self.user_id,
            'action': self.action.value,
            'data_type': self.data_type.value if self.data_type else None,
            'resource_id': self.resource_id,
            'timestamp': self.timestamp.isoformat(),
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'details': self.details,
            'success': self.success
        }


@dataclass
class AnonymousProfile:
    """Anonymous user profile for anonymous mode"""
    anonymous_id: str
    session_key: bytes
    created_at: datetime
    expires_at: datetime
    allowed_operations: List[str] = field(default_factory=list)
    data_hash: Optional[str] = None  # Hash of original user data for matching
    
    def is_expired(self) -> bool:
        """Check if anonymous profile is expired"""
        return datetime.utcnow() > self.expires_at


class EncryptionManager:
    """Manager for encryption operations"""
    
    def __init__(self, master_key: Optional[bytes] = None):
        self.master_key = master_key or self._generate_master_key()
        self.keys: Dict[str, EncryptionKey] = {}
        self._fernet = None
        
        if CRYPTO_AVAILABLE:
            self._fernet = Fernet(base64.urlsafe_b64encode(self.master_key[:32]))
    
    def _generate_master_key(self) -> bytes:
        """Generate a master encryption key"""
        return secrets.token_bytes(32)
    
    def generate_key(self, key_type: str = "symmetric", expires_in_days: Optional[int] = None) -> str:
        """Generate a new encryption key"""
        key_id = secrets.token_urlsafe(16)
        
        if key_type == "symmetric":
            key_data = Fernet.generate_key()
        elif key_type == "asymmetric":
            # Generate RSA key pair
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            key_data = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
        else:
            raise ValueError(f"Unsupported key type: {key_type}")
        
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        encryption_key = EncryptionKey(
            key_id=key_id,
            key_data=key_data,
            algorithm="Fernet" if key_type == "symmetric" else "RSA",
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            key_type=key_type
        )
        
        self.keys[key_id] = encryption_key
        return key_id
    
    def encrypt_data(self, data: Union[str, Dict, bytes], key_id: Optional[str] = None) -> Tuple[bytes, str]:
        """Encrypt data with specified or default key"""
        if not CRYPTO_AVAILABLE:
            logger.warning("Cryptography not available - data not encrypted")
            return json.dumps(data).encode() if isinstance(data, (dict, str)) else data, "none"
        
        # Convert data to bytes
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        elif isinstance(data, dict):
            data_bytes = json.dumps(data).encode('utf-8')
        else:
            data_bytes = data
        
        if key_id and key_id in self.keys:
            key = self.keys[key_id]
            if key.is_expired():
                raise ValueError(f"Encryption key {key_id} is expired")
            
            if key.algorithm == "Fernet":
                fernet = Fernet(key.key_data)
                encrypted = fernet.encrypt(data_bytes)
            else:
                raise ValueError(f"Unsupported encryption algorithm: {key.algorithm}")
        else:
            # Use master key
            if self._fernet is None:
                raise ValueError("No encryption available")
            encrypted = self._fernet.encrypt(data_bytes)
            key_id = "master"
        
        return encrypted, key_id
    
    def decrypt_data(self, encrypted_data: bytes, key_id: str) -> bytes:
        """Decrypt data with specified key"""
        if not CRYPTO_AVAILABLE:
            logger.warning("Cryptography not available - returning data as-is")
            return encrypted_data
        
        if key_id == "master":
            if self._fernet is None:
                raise ValueError("No master key available")
            return self._fernet.decrypt(encrypted_data)
        
        if key_id not in self.keys:
            raise ValueError(f"Encryption key {key_id} not found")
        
        key = self.keys[key_id]
        if key.is_expired():
            raise ValueError(f"Encryption key {key_id} is expired")
        
        if key.algorithm == "Fernet":
            fernet = Fernet(key.key_data)
            return fernet.decrypt(encrypted_data)
        else:
            raise ValueError(f"Unsupported decryption algorithm: {key.algorithm}")
    
    def rotate_key(self, key_id: str) -> str:
        """Rotate an encryption key"""
        if key_id not in self.keys:
            raise ValueError(f"Key {key_id} not found")
        
        old_key = self.keys[key_id]
        new_key_id = self.generate_key(
            key_type=old_key.key_type,
            expires_in_days=365 if old_key.expires_at else None
        )
        
        return new_key_id


class PrivacyManager:
    """Manager for privacy settings and controls"""
    
    def __init__(self, storage_path: str = "security/privacy_settings.db"):
        self.storage_path = storage_path
        self.settings_cache: Dict[str, Dict[DataType, PrivacySetting]] = {}
        self._init_storage()
    
    def _init_storage(self):
        """Initialize privacy settings storage"""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        
        conn = sqlite3.connect(self.storage_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS privacy_settings (
                user_id TEXT,
                data_type TEXT,
                privacy_level TEXT,
                allow_ai_processing BOOLEAN,
                allow_team_matching BOOLEAN,
                allow_analytics BOOLEAN,
                allow_third_party BOOLEAN,
                retention_days INTEGER,
                last_updated TEXT,
                PRIMARY KEY (user_id, data_type)
            )
        ''')
        conn.commit()
        conn.close()
    
    def set_privacy_setting(self, user_id: str, setting: PrivacySetting):
        """Set privacy setting for user and data type"""
        # Update cache
        if user_id not in self.settings_cache:
            self.settings_cache[user_id] = {}
        self.settings_cache[user_id][setting.data_type] = setting
        
        # Update database
        conn = sqlite3.connect(self.storage_path)
        conn.execute('''
            INSERT OR REPLACE INTO privacy_settings 
            (user_id, data_type, privacy_level, allow_ai_processing, 
             allow_team_matching, allow_analytics, allow_third_party, 
             retention_days, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, setting.data_type.value, setting.privacy_level.value,
            setting.allow_ai_processing, setting.allow_team_matching,
            setting.allow_analytics, setting.allow_third_party,
            setting.retention_days, setting.last_updated.isoformat()
        ))
        conn.commit()
        conn.close()
    
    def get_privacy_setting(self, user_id: str, data_type: DataType) -> PrivacySetting:
        """Get privacy setting for user and data type"""
        # Check cache first
        if user_id in self.settings_cache and data_type in self.settings_cache[user_id]:
            return self.settings_cache[user_id][data_type]
        
        # Load from database
        conn = sqlite3.connect(self.storage_path)
        cursor = conn.execute(
            'SELECT * FROM privacy_settings WHERE user_id = ? AND data_type = ?',
            (user_id, data_type.value)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            setting = PrivacySetting(
                data_type=DataType(row[1]),
                privacy_level=PrivacyLevel(row[2]),
                allow_ai_processing=row[3],
                allow_team_matching=row[4],
                allow_analytics=row[5],
                allow_third_party=row[6],
                retention_days=row[7],
                last_updated=datetime.fromisoformat(row[8])
            )
        else:
            # Default setting
            setting = PrivacySetting(
                data_type=data_type,
                privacy_level=PrivacyLevel.PRIVATE,
                allow_ai_processing=True,
                allow_team_matching=True,
                allow_analytics=False,
                allow_third_party=False
            )
            self.set_privacy_setting(user_id, setting)
        
        # Update cache
        if user_id not in self.settings_cache:
            self.settings_cache[user_id] = {}
        self.settings_cache[user_id][data_type] = setting
        
        return setting
    
    def get_all_privacy_settings(self, user_id: str) -> Dict[DataType, PrivacySetting]:
        """Get all privacy settings for a user"""
        settings = {}
        
        # Load from database
        conn = sqlite3.connect(self.storage_path)
        cursor = conn.execute(
            'SELECT * FROM privacy_settings WHERE user_id = ?',
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        for row in rows:
            data_type = DataType(row[1])
            setting = PrivacySetting(
                data_type=data_type,
                privacy_level=PrivacyLevel(row[2]),
                allow_ai_processing=row[3],
                allow_team_matching=row[4],
                allow_analytics=row[5],
                allow_third_party=row[6],
                retention_days=row[7],
                last_updated=datetime.fromisoformat(row[8])
            )
            settings[data_type] = setting
        
        # Update cache
        self.settings_cache[user_id] = settings
        
        return settings
    
    def bulk_update_settings(self, user_id: str, settings: Dict[DataType, PrivacySetting]):
        """Bulk update privacy settings for a user"""
        for data_type, setting in settings.items():
            self.set_privacy_setting(user_id, setting)
    
    def check_permission(self, user_id: str, data_type: DataType, operation: str) -> bool:
        """Check if user has permission for specific operation on data type"""
        setting = self.get_privacy_setting(user_id, data_type)
        
        if operation == "ai_processing":
            return setting.allow_ai_processing
        elif operation == "team_matching":
            return setting.allow_team_matching
        elif operation == "analytics":
            return setting.allow_analytics
        elif operation == "third_party":
            return setting.allow_third_party
        elif operation == "read":
            return setting.privacy_level in [PrivacyLevel.PUBLIC, PrivacyLevel.PRIVATE]
        elif operation == "write":
            return setting.privacy_level != PrivacyLevel.TOP_SECRET
        else:
            return False


# Initialize global instances
encryption_manager = EncryptionManager()
privacy_manager = PrivacyManager()

logger.info("Privacy and security controls initialized")