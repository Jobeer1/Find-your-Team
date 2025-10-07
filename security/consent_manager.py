"""
Consent Management System

This module handles user consent for data processing, tracking consent history,
and managing consent validation throughout the application.
"""

import sqlite3
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from .privacy_security import (
    ConsentRecord, ConsentType, DataType, AuditAction, AuditLog
)

logger = logging.getLogger(__name__)


class ConsentManager:
    """Manager for user consent and data processing permissions"""
    
    def __init__(self, storage_path: str = "security/consent.db"):
        self.storage_path = storage_path
        self.consent_cache: Dict[str, Dict[ConsentType, ConsentRecord]] = {}
        self._init_storage()
    
    def _init_storage(self):
        """Initialize consent storage"""
        import os
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        
        conn = sqlite3.connect(self.storage_path)
        
        # Consent records table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS consent_records (
                consent_id TEXT PRIMARY KEY,
                user_id TEXT,
                consent_type TEXT,
                granted BOOLEAN,
                granted_at TEXT,
                expires_at TEXT,
                purpose TEXT,
                data_types TEXT,  -- JSON array of data types
                third_parties TEXT,  -- JSON array of third party names
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Consent history table for audit purposes
        conn.execute('''
            CREATE TABLE IF NOT EXISTS consent_history (
                history_id TEXT PRIMARY KEY,
                user_id TEXT,
                consent_id TEXT,
                action TEXT,  -- granted, withdrawn, expired
                timestamp TEXT,
                details TEXT  -- JSON details
            )
        ''')
        
        # Create indexes for performance
        conn.execute('CREATE INDEX IF NOT EXISTS idx_consent_user_type ON consent_records (user_id, consent_type)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_consent_history_user ON consent_history (user_id)')
        
        conn.commit()
        conn.close()
    
    def grant_consent(
        self, 
        user_id: str, 
        consent_type: ConsentType, 
        purpose: str,
        data_types: List[DataType] = None,
        third_parties: List[str] = None,
        expires_in_days: Optional[int] = None
    ) -> str:
        """Grant consent for specific data processing"""
        consent_id = secrets.token_urlsafe(16)
        granted_at = datetime.utcnow()
        expires_at = None
        
        if expires_in_days:
            expires_at = granted_at + timedelta(days=expires_in_days)
        
        # Create consent record
        consent = ConsentRecord(
            consent_id=consent_id,
            user_id=user_id,
            consent_type=consent_type,
            granted=True,
            granted_at=granted_at,
            expires_at=expires_at,
            purpose=purpose,
            data_types=data_types or [],
            third_parties=third_parties or []
        )
        
        # Store in database
        self._store_consent(consent)
        
        # Update cache
        if user_id not in self.consent_cache:
            self.consent_cache[user_id] = {}
        self.consent_cache[user_id][consent_type] = consent
        
        # Log consent action
        self._log_consent_action(user_id, consent_id, "granted", {
            'consent_type': consent_type.value,
            'purpose': purpose,
            'expires_at': expires_at.isoformat() if expires_at else None
        })
        
        logger.info(f"Consent granted: {user_id} -> {consent_type.value}")
        return consent_id
    
    def withdraw_consent(self, user_id: str, consent_type: ConsentType) -> bool:
        """Withdraw consent for specific data processing"""
        # Get existing consent
        consent = self.get_consent(user_id, consent_type)
        if not consent or not consent.granted:
            return False
        
        # Mark as withdrawn
        consent.granted = False
        self._store_consent(consent)
        
        # Update cache
        if user_id in self.consent_cache and consent_type in self.consent_cache[user_id]:
            self.consent_cache[user_id][consent_type].granted = False
        
        # Log withdrawal
        self._log_consent_action(user_id, consent.consent_id, "withdrawn", {
            'consent_type': consent_type.value,
            'withdrawn_at': datetime.utcnow().isoformat()
        })
        
        logger.info(f"Consent withdrawn: {user_id} -> {consent_type.value}")
        return True
    
    def get_consent(self, user_id: str, consent_type: ConsentType) -> Optional[ConsentRecord]:
        """Get consent record for user and type"""
        # Check cache first
        if user_id in self.consent_cache and consent_type in self.consent_cache[user_id]:
            consent = self.consent_cache[user_id][consent_type]
            # Check if still valid
            if not consent.is_expired():
                return consent
            else:
                # Mark as expired and log
                self._log_consent_action(user_id, consent.consent_id, "expired", {
                    'consent_type': consent_type.value,
                    'expired_at': datetime.utcnow().isoformat()
                })
        
        # Load from database
        conn = sqlite3.connect(self.storage_path)
        cursor = conn.execute('''
            SELECT consent_id, user_id, consent_type, granted, granted_at, 
                   expires_at, purpose, data_types, third_parties
            FROM consent_records 
            WHERE user_id = ? AND consent_type = ? AND granted = 1
            ORDER BY granted_at DESC LIMIT 1
        ''', (user_id, consent_type.value))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        # Parse data types and third parties from JSON
        import json
        data_types = []
        if row[7]:
            try:
                data_types = [DataType(dt) for dt in json.loads(row[7])]
            except (json.JSONDecodeError, ValueError):
                pass
        
        third_parties = []
        if row[8]:
            try:
                third_parties = json.loads(row[8])
            except json.JSONDecodeError:
                pass
        
        consent = ConsentRecord(
            consent_id=row[0],
            user_id=row[1],
            consent_type=ConsentType(row[2]),
            granted=bool(row[3]),
            granted_at=datetime.fromisoformat(row[4]),
            expires_at=datetime.fromisoformat(row[5]) if row[5] else None,
            purpose=row[6] or "",
            data_types=data_types,
            third_parties=third_parties
        )
        
        # Update cache
        if user_id not in self.consent_cache:
            self.consent_cache[user_id] = {}
        self.consent_cache[user_id][consent_type] = consent
        
        return consent
    
    def has_valid_consent(self, user_id: str, consent_type: ConsentType) -> bool:
        """Check if user has valid consent for specific processing"""
        consent = self.get_consent(user_id, consent_type)
        return consent is not None and consent.is_valid()
    
    def get_all_consents(self, user_id: str) -> Dict[ConsentType, ConsentRecord]:
        """Get all consent records for a user"""
        consents = {}
        
        conn = sqlite3.connect(self.storage_path)
        cursor = conn.execute('''
            SELECT consent_id, user_id, consent_type, granted, granted_at, 
                   expires_at, purpose, data_types, third_parties
            FROM consent_records 
            WHERE user_id = ?
            ORDER BY granted_at DESC
        ''', (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        import json
        for row in rows:
            consent_type = ConsentType(row[2])
            
            # Skip if we already have a more recent record for this type
            if consent_type in consents:
                continue
            
            # Parse data types and third parties
            data_types = []
            if row[7]:
                try:
                    data_types = [DataType(dt) for dt in json.loads(row[7])]
                except (json.JSONDecodeError, ValueError):
                    pass
            
            third_parties = []
            if row[8]:
                try:
                    third_parties = json.loads(row[8])
                except json.JSONDecodeError:
                    pass
            
            consent = ConsentRecord(
                consent_id=row[0],
                user_id=row[1],
                consent_type=consent_type,
                granted=bool(row[3]),
                granted_at=datetime.fromisoformat(row[4]),
                expires_at=datetime.fromisoformat(row[5]) if row[5] else None,
                purpose=row[6] or "",
                data_types=data_types,
                third_parties=third_parties
            )
            
            consents[consent_type] = consent
        
        return consents
    
    def get_consent_summary(self, user_id: str) -> Dict[str, any]:
        """Get summary of user's consent status"""
        consents = self.get_all_consents(user_id)
        
        summary = {
            'total_consents': len(consents),
            'active_consents': 0,
            'expired_consents': 0,
            'withdrawn_consents': 0,
            'consent_details': []
        }
        
        for consent_type, consent in consents.items():
            status = "active"
            if not consent.granted:
                status = "withdrawn"
                summary['withdrawn_consents'] += 1
            elif consent.is_expired():
                status = "expired"
                summary['expired_consents'] += 1
            else:
                summary['active_consents'] += 1
            
            summary['consent_details'].append({
                'type': consent_type.value,
                'status': status,
                'granted_at': consent.granted_at.isoformat(),
                'expires_at': consent.expires_at.isoformat() if consent.expires_at else None,
                'purpose': consent.purpose
            })
        
        return summary
    
    def check_data_processing_allowed(
        self, 
        user_id: str, 
        data_type: DataType, 
        processing_purpose: str
    ) -> bool:
        """Check if data processing is allowed for specific purpose"""
        # Map processing purpose to consent type
        purpose_to_consent = {
            'ai_analysis': ConsentType.AI_ANALYSIS,
            'team_matching': ConsentType.TEAM_MATCHING,
            'performance_tracking': ConsentType.PERFORMANCE_TRACKING,
            'analytics': ConsentType.ANALYTICS,
            'marketing': ConsentType.MARKETING,
            'third_party_sharing': ConsentType.THIRD_PARTY_SHARING
        }
        
        consent_type = purpose_to_consent.get(processing_purpose, ConsentType.DATA_PROCESSING)
        
        # Check if user has valid consent
        if not self.has_valid_consent(user_id, consent_type):
            return False
        
        # Get consent record to check data types
        consent = self.get_consent(user_id, consent_type)
        if consent and consent.data_types:
            # If specific data types are listed, check if this one is included
            return data_type in consent.data_types
        
        # If no specific data types listed, assume general consent covers all
        return True
    
    def _store_consent(self, consent: ConsentRecord):
        """Store consent record in database"""
        import json
        
        conn = sqlite3.connect(self.storage_path)
        conn.execute('''
            INSERT OR REPLACE INTO consent_records 
            (consent_id, user_id, consent_type, granted, granted_at, expires_at, 
             purpose, data_types, third_parties)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            consent.consent_id,
            consent.user_id,
            consent.consent_type.value,
            consent.granted,
            consent.granted_at.isoformat(),
            consent.expires_at.isoformat() if consent.expires_at else None,
            consent.purpose,
            json.dumps([dt.value for dt in consent.data_types]),
            json.dumps(consent.third_parties)
        ))
        conn.commit()
        conn.close()
    
    def _log_consent_action(self, user_id: str, consent_id: str, action: str, details: Dict):
        """Log consent action for audit trail"""
        import json
        
        history_id = secrets.token_urlsafe(16)
        
        conn = sqlite3.connect(self.storage_path)
        conn.execute('''
            INSERT INTO consent_history 
            (history_id, user_id, consent_id, action, timestamp, details)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            history_id,
            user_id,
            consent_id,
            action,
            datetime.utcnow().isoformat(),
            json.dumps(details)
        ))
        conn.commit()
        conn.close()
    
    def get_consent_history(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get consent history for a user"""
        conn = sqlite3.connect(self.storage_path)
        cursor = conn.execute('''
            SELECT history_id, consent_id, action, timestamp, details
            FROM consent_history 
            WHERE user_id = ?
            ORDER BY timestamp DESC LIMIT ?
        ''', (user_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        import json
        history = []
        for row in rows:
            try:
                details = json.loads(row[4]) if row[4] else {}
            except json.JSONDecodeError:
                details = {}
            
            history.append({
                'history_id': row[0],
                'consent_id': row[1],
                'action': row[2],
                'timestamp': row[3],
                'details': details
            })
        
        return history


# Initialize global consent manager
consent_manager = ConsentManager()

logger.info("Consent management system initialized")