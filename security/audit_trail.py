"""
Audit Trail System

This module provides comprehensive audit logging for all data access and modifications,
ensuring compliance with privacy regulations and security requirements.
"""

import sqlite3
import secrets
import logging
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from .privacy_security import AuditLog, AuditAction, DataType

logger = logging.getLogger(__name__)


class AuditTrail:
    """Comprehensive audit trail system for security and compliance"""
    
    def __init__(self, storage_path: str = "security/audit.db"):
        self.storage_path = storage_path
        self._init_storage()
    
    def _init_storage(self):
        """Initialize audit trail storage"""
        import os
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        
        conn = sqlite3.connect(self.storage_path)
        
        # Main audit log table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id TEXT PRIMARY KEY,
                user_id TEXT,
                action TEXT,
                data_type TEXT,
                resource_id TEXT,
                timestamp TEXT,
                ip_address TEXT,
                user_agent TEXT,
                session_id TEXT,
                details TEXT,
                success BOOLEAN,
                risk_score INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Data access patterns table for anomaly detection
        conn.execute('''
            CREATE TABLE IF NOT EXISTS access_patterns (
                pattern_id TEXT PRIMARY KEY,
                user_id TEXT,
                data_type TEXT,
                access_frequency INTEGER DEFAULT 1,
                last_access TEXT,
                typical_times TEXT,  -- JSON array of typical access times
                risk_indicators TEXT,  -- JSON array of risk indicators
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Security events table for breach detection
        conn.execute('''
            CREATE TABLE IF NOT EXISTS security_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT,
                severity TEXT,
                user_id TEXT,
                timestamp TEXT,
                source_ip TEXT,
                description TEXT,
                indicators TEXT,  -- JSON array of security indicators
                resolved BOOLEAN DEFAULT FALSE,
                resolution_notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Data lineage table for tracking data flow
        conn.execute('''
            CREATE TABLE IF NOT EXISTS data_lineage (
                lineage_id TEXT PRIMARY KEY,
                source_data_id TEXT,
                target_data_id TEXT,
                transformation_type TEXT,
                user_id TEXT,
                timestamp TEXT,
                process_details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for performance
        conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_user_time ON audit_logs (user_id, timestamp)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs (action)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_data_type ON audit_logs (data_type)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_security_events_severity ON security_events (severity, timestamp)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_access_patterns_user ON access_patterns (user_id)')
        
        conn.commit()
        conn.close()
        
        logger.info("Audit trail storage initialized")
    
    def log_action(
        self,
        user_id: str,
        action: AuditAction,
        data_type: Optional[DataType] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True
    ) -> str:
        """Log an audit action"""
        log_id = secrets.token_urlsafe(16)
        timestamp = datetime.utcnow()
        
        # Calculate risk score based on action and context
        risk_score = self._calculate_risk_score(action, data_type, details, timestamp)
        
        # Create audit log entry
        audit_log = AuditLog(
            log_id=log_id,
            user_id=user_id,
            action=action,
            data_type=data_type,
            resource_id=resource_id,
            timestamp=timestamp,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            success=success
        )
        
        # Store in database
        conn = sqlite3.connect(self.storage_path)
        conn.execute('''
            INSERT INTO audit_logs 
            (log_id, user_id, action, data_type, resource_id, timestamp, 
             ip_address, user_agent, session_id, details, success, risk_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            log_id,
            user_id,
            action.value,
            data_type.value if data_type else None,
            resource_id,
            timestamp.isoformat(),
            ip_address,
            user_agent,
            session_id,
            json.dumps(details or {}),
            success,
            risk_score
        ))
        conn.commit()
        conn.close()
        
        # Update access patterns
        if data_type:
            self._update_access_patterns(user_id, data_type, timestamp)
        
        # Check for security anomalies
        if risk_score > 50:  # High risk threshold
            self._check_security_anomalies(user_id, action, risk_score, timestamp, details)
        
        logger.debug(f"Audit action logged: {user_id} -> {action.value} (risk: {risk_score})")
        return log_id
    
    def get_user_audit_trail(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action_filter: Optional[List[AuditAction]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit trail for a specific user"""
        conn = sqlite3.connect(self.storage_path)
        
        # Build query
        query = 'SELECT * FROM audit_logs WHERE user_id = ?'
        params = [user_id]
        
        if start_date:
            query += ' AND timestamp >= ?'
            params.append(start_date.isoformat())
        
        if end_date:
            query += ' AND timestamp <= ?'
            params.append(end_date.isoformat())
        
        if action_filter:
            action_values = [action.value for action in action_filter]
            placeholders = ','.join(['?' for _ in action_values])
            query += f' AND action IN ({placeholders})'
            params.extend(action_values)
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        columns = [
            'log_id', 'user_id', 'action', 'data_type', 'resource_id',
            'timestamp', 'ip_address', 'user_agent', 'session_id', 
            'details', 'success', 'risk_score', 'created_at'
        ]
        
        audit_trail = []
        for row in rows:
            entry = dict(zip(columns, row))
            try:
                entry['details'] = json.loads(entry['details']) if entry['details'] else {}
            except json.JSONDecodeError:
                entry['details'] = {}
            audit_trail.append(entry)
        
        return audit_trail
    
    def get_data_access_history(
        self,
        data_type: DataType,
        resource_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get access history for specific data type or resource"""
        conn = sqlite3.connect(self.storage_path)
        
        query = 'SELECT * FROM audit_logs WHERE data_type = ?'
        params = [data_type.value]
        
        if resource_id:
            query += ' AND resource_id = ?'
            params.append(resource_id)
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        columns = [
            'log_id', 'user_id', 'action', 'data_type', 'resource_id',
            'timestamp', 'ip_address', 'user_agent', 'session_id', 
            'details', 'success', 'risk_score', 'created_at'
        ]
        
        history = []
        for row in rows:
            entry = dict(zip(columns, row))
            try:
                entry['details'] = json.loads(entry['details']) if entry['details'] else {}
            except json.JSONDecodeError:
                entry['details'] = {}
            history.append(entry)
        
        return history
    
    def detect_anomalous_access(self, user_id: str) -> List[Dict[str, Any]]:
        """Detect anomalous access patterns for a user"""
        anomalies = []
        
        # Get recent access patterns
        conn = sqlite3.connect(self.storage_path)
        
        # Check for unusual access volumes
        recent_time = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        cursor = conn.execute('''
            SELECT action, COUNT(*) as count
            FROM audit_logs 
            WHERE user_id = ? AND timestamp > ?
            GROUP BY action
        ''', (user_id, recent_time))
        
        action_counts = cursor.fetchall()
        
        for action, count in action_counts:
            if count > 100:  # Threshold for unusual activity
                anomalies.append({
                    'type': 'high_volume_access',
                    'action': action,
                    'count': count,
                    'timeframe': '24h',
                    'risk_level': 'medium' if count < 500 else 'high'
                })
        
        # Check for unusual time patterns
        cursor = conn.execute('''
            SELECT timestamp, action
            FROM audit_logs 
            WHERE user_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
        ''', (user_id, recent_time))
        
        time_accesses = cursor.fetchall()
        
        # Detect access during unusual hours (e.g., 2-6 AM)
        unusual_hours = 0
        for timestamp_str, action in time_accesses:
            timestamp = datetime.fromisoformat(timestamp_str)
            if 2 <= timestamp.hour <= 6:  # Unusual hours
                unusual_hours += 1
        
        if unusual_hours > 5:
            anomalies.append({
                'type': 'unusual_time_access',
                'count': unusual_hours,
                'timeframe': '24h',
                'risk_level': 'medium'
            })
        
        # Check for rapid sequential access
        cursor = conn.execute('''
            SELECT timestamp
            FROM audit_logs 
            WHERE user_id = ? AND timestamp > ?
            ORDER BY timestamp DESC LIMIT 20
        ''', (user_id, recent_time))
        
        timestamps = [datetime.fromisoformat(row[0]) for row in cursor.fetchall()]
        
        rapid_access_count = 0
        for i in range(1, len(timestamps)):
            time_diff = (timestamps[i-1] - timestamps[i]).total_seconds()
            if time_diff < 1:  # Less than 1 second between actions
                rapid_access_count += 1
        
        if rapid_access_count > 10:
            anomalies.append({
                'type': 'rapid_sequential_access',
                'count': rapid_access_count,
                'risk_level': 'high'
            })
        
        conn.close()
        return anomalies
    
    def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime,
        include_details: bool = False
    ) -> Dict[str, Any]:
        """Generate compliance report for audit purposes"""
        conn = sqlite3.connect(self.storage_path)
        
        # Summary statistics
        cursor = conn.execute('''
            SELECT 
                COUNT(*) as total_actions,
                COUNT(DISTINCT user_id) as unique_users,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_actions,
                AVG(risk_score) as avg_risk_score
            FROM audit_logs 
            WHERE timestamp BETWEEN ? AND ?
        ''', (start_date.isoformat(), end_date.isoformat()))
        
        summary = cursor.fetchone()
        
        # Actions by type
        cursor = conn.execute('''
            SELECT action, COUNT(*) as count
            FROM audit_logs 
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY action
            ORDER BY count DESC
        ''', (start_date.isoformat(), end_date.isoformat()))
        
        actions_by_type = dict(cursor.fetchall())
        
        # Data types accessed
        cursor = conn.execute('''
            SELECT data_type, COUNT(*) as count
            FROM audit_logs 
            WHERE timestamp BETWEEN ? AND ? AND data_type IS NOT NULL
            GROUP BY data_type
            ORDER BY count DESC
        ''', (start_date.isoformat(), end_date.isoformat()))
        
        data_types_accessed = dict(cursor.fetchall())
        
        # High-risk activities
        cursor = conn.execute('''
            SELECT user_id, action, timestamp, risk_score
            FROM audit_logs 
            WHERE timestamp BETWEEN ? AND ? AND risk_score > 70
            ORDER BY risk_score DESC
        ''', (start_date.isoformat(), end_date.isoformat()))
        
        high_risk_activities = cursor.fetchall()
        
        # Security events
        cursor = conn.execute('''
            SELECT event_type, severity, COUNT(*) as count
            FROM security_events 
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY event_type, severity
        ''', (start_date.isoformat(), end_date.isoformat()))
        
        security_events = cursor.fetchall()
        
        conn.close()
        
        report = {
            'report_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_actions': summary[0] or 0,
                'unique_users': summary[1] or 0,
                'failed_actions': summary[2] or 0,
                'success_rate': ((summary[0] - summary[2]) / summary[0] * 100) if summary[0] > 0 else 0,
                'average_risk_score': round(summary[3] or 0, 2)
            },
            'actions_by_type': actions_by_type,
            'data_types_accessed': data_types_accessed,
            'security_summary': {
                'high_risk_activities': len(high_risk_activities),
                'security_events': len(security_events)
            }
        }
        
        if include_details:
            report['high_risk_details'] = [
                {
                    'user_id': row[0],
                    'action': row[1],
                    'timestamp': row[2],
                    'risk_score': row[3]
                }
                for row in high_risk_activities
            ]
            
            report['security_events_details'] = [
                {
                    'event_type': row[0],
                    'severity': row[1],
                    'count': row[2]
                }
                for row in security_events
            ]
        
        return report
    
    def _calculate_risk_score(
        self,
        action: AuditAction,
        data_type: Optional[DataType],
        details: Optional[Dict],
        timestamp: datetime
    ) -> int:
        """Calculate risk score for an audit action"""
        risk_score = 0
        
        # Base risk by action type
        action_risks = {
            AuditAction.DATA_ACCESS: 10,
            AuditAction.DATA_MODIFICATION: 30,
            AuditAction.DATA_DELETION: 50,
            AuditAction.PRIVACY_SETTING_CHANGE: 20,
            AuditAction.CONSENT_WITHDRAWN: 15,
            AuditAction.ENCRYPTION_KEY_GENERATED: 25,
            AuditAction.ANONYMOUS_MODE_ACTIVATED: 5,
            AuditAction.DATA_EXPORT: 40,
            AuditAction.SECURITY_BREACH_DETECTED: 100
        }
        
        risk_score += action_risks.get(action, 10)
        
        # Risk by data type sensitivity
        if data_type:
            data_type_risks = {
                DataType.PROFILE_BASIC: 5,
                DataType.PROFILE_DETAILED: 15,
                DataType.PURPOSE_PROFILE: 10,
                DataType.SKILLS_DATA: 8,
                DataType.TEAM_PERFORMANCE: 12,
                DataType.CHAT_HISTORY: 20,
                DataType.LOCATION_DATA: 25,
                DataType.CONTACT_INFO: 30,
                DataType.PREFERENCES: 5
            }
            risk_score += data_type_risks.get(data_type, 10)
        
        # Time-based risk (unusual hours)
        if 2 <= timestamp.hour <= 6:  # 2-6 AM
            risk_score += 15
        
        # Volume-based risk (from details)
        if details:
            if 'bulk_operation' in details and details['bulk_operation']:
                risk_score += 20
            if 'export_size' in details:
                export_size = details.get('export_size', 0)
                if export_size > 1000:  # Large export
                    risk_score += 25
        
        return min(risk_score, 100)  # Cap at 100
    
    def _update_access_patterns(self, user_id: str, data_type: DataType, timestamp: datetime):
        """Update access patterns for anomaly detection"""
        conn = sqlite3.connect(self.storage_path)
        
        # Check if pattern exists
        cursor = conn.execute(
            'SELECT pattern_id, access_frequency, typical_times FROM access_patterns WHERE user_id = ? AND data_type = ?',
            (user_id, data_type.value)
        )
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing pattern
            pattern_id, frequency, typical_times_str = existing
            
            try:
                typical_times = json.loads(typical_times_str) if typical_times_str else []
            except json.JSONDecodeError:
                typical_times = []
            
            # Add current hour to typical times
            current_hour = timestamp.hour
            typical_times.append(current_hour)
            
            # Keep only recent patterns (last 50 accesses)
            if len(typical_times) > 50:
                typical_times = typical_times[-50:]
            
            conn.execute('''
                UPDATE access_patterns 
                SET access_frequency = ?, last_access = ?, typical_times = ?, updated_at = ?
                WHERE pattern_id = ?
            ''', (
                frequency + 1,
                timestamp.isoformat(),
                json.dumps(typical_times),
                datetime.utcnow().isoformat(),
                pattern_id
            ))
        else:
            # Create new pattern
            pattern_id = secrets.token_urlsafe(16)
            typical_times = [timestamp.hour]
            
            conn.execute('''
                INSERT INTO access_patterns 
                (pattern_id, user_id, data_type, access_frequency, last_access, typical_times)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                pattern_id,
                user_id,
                data_type.value,
                1,
                timestamp.isoformat(),
                json.dumps(typical_times)
            ))
        
        conn.commit()
        conn.close()
    
    def _check_security_anomalies(
        self,
        user_id: str,
        action: AuditAction,
        risk_score: int,
        timestamp: datetime,
        details: Optional[Dict]
    ):
        """Check for security anomalies and create security events"""
        event_id = secrets.token_urlsafe(16)
        
        # Determine event type and severity
        if risk_score >= 80:
            severity = "critical"
            event_type = "high_risk_action"
        elif risk_score >= 60:
            severity = "high"
            event_type = "suspicious_activity"
        else:
            severity = "medium"
            event_type = "elevated_risk"
        
        description = f"User {user_id} performed {action.value} with risk score {risk_score}"
        
        indicators = [
            f"risk_score:{risk_score}",
            f"action:{action.value}",
            f"timestamp:{timestamp.isoformat()}"
        ]
        
        if details:
            indicators.extend([f"{k}:{v}" for k, v in details.items()])
        
        # Store security event
        conn = sqlite3.connect(self.storage_path)
        conn.execute('''
            INSERT INTO security_events 
            (event_id, event_type, severity, user_id, timestamp, description, indicators)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            event_id,
            event_type,
            severity,
            user_id,
            timestamp.isoformat(),
            description,
            json.dumps(indicators)
        ))
        conn.commit()
        conn.close()
        
        logger.warning(f"Security event created: {event_type} ({severity}) for user {user_id}")


# Initialize global audit trail
audit_trail = AuditTrail()

logger.info("Audit trail system initialized")