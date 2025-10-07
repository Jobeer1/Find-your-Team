"""
Data Sync Resilience Module for Find Your Team

Implements data synchronization conflict resolution, offline-first data management,
and graceful handling of database connectivity issues.

Features:
1. Data sync conflict detection and resolution
2. Offline data storage and queuing
3. Database failure recovery mechanisms
4. User notification system for sync issues
5. Data integrity validation
6. Automatic retry and reconciliation
"""

import asyncio
import json
import logging
import time
import sqlite3
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from collections import defaultdict, deque
import os
import pickle

from .error_handling import (
    resilience_manager, ErrorCategory, ErrorSeverity, resilient_operation,
    DataSyncConflict, RetryManager, RecoveryStrategy
)

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Status of data synchronization"""
    SYNCED = "synced"               # Data is synchronized
    PENDING = "pending"             # Changes waiting to sync
    CONFLICT = "conflict"           # Conflict requires resolution
    ERROR = "error"                 # Sync failed with error
    OFFLINE = "offline"             # Offline, will sync later


class ConflictResolution(Enum):
    """Strategies for resolving sync conflicts"""
    USER_CHOICE = "user_choice"         # Let user decide
    LOCAL_WINS = "local_wins"           # Prefer local version
    REMOTE_WINS = "remote_wins"         # Prefer remote version
    MERGE = "merge"                     # Attempt automatic merge
    LATEST_TIMESTAMP = "latest_timestamp" # Use most recent version
    MANUAL_REVIEW = "manual_review"     # Queue for manual review


class DataOperation(Enum):
    """Types of data operations"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    READ = "read"


@dataclass
class DataChange:
    """Represents a data change that needs synchronization"""
    change_id: str
    user_id: str
    data_type: str  # e.g., "user_profile", "team_data", "conversation"
    operation: DataOperation
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sync_status: SyncStatus = SyncStatus.PENDING
    retry_count: int = 0
    max_retries: int = 5
    conflict_resolution: Optional[ConflictResolution] = None
    parent_change_id: Optional[str] = None  # For tracking related changes
    checksum: Optional[str] = None
    
    def __post_init__(self):
        if self.checksum is None:
            self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Calculate checksum for data integrity"""
        data_str = json.dumps(self.data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'change_id': self.change_id,
            'user_id': self.user_id,
            'data_type': self.data_type,
            'operation': self.operation.value,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'sync_status': self.sync_status.value,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'conflict_resolution': self.conflict_resolution.value if self.conflict_resolution else None,
            'parent_change_id': self.parent_change_id,
            'checksum': self.checksum
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataChange':
        """Create from dictionary"""
        return cls(
            change_id=data['change_id'],
            user_id=data['user_id'],
            data_type=data['data_type'],
            operation=DataOperation(data['operation']),
            data=data['data'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            sync_status=SyncStatus(data['sync_status']),
            retry_count=data.get('retry_count', 0),
            max_retries=data.get('max_retries', 5),
            conflict_resolution=ConflictResolution(data['conflict_resolution']) if data.get('conflict_resolution') else None,
            parent_change_id=data.get('parent_change_id'),
            checksum=data.get('checksum')
        )


@dataclass
class SyncConflictNotification:
    """Notification about sync conflict requiring user attention"""
    notification_id: str
    user_id: str
    conflict: DataSyncConflict
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    resolution_deadline: Optional[datetime] = None
    
    def to_user_friendly_dict(self) -> Dict[str, Any]:
        """Convert to user-friendly notification format"""
        return {
            'id': self.notification_id,
            'type': 'sync_conflict',
            'title': f'Data Sync Conflict - {self.conflict.data_type.title()}',
            'message': self._generate_user_message(),
            'priority': 'high',
            'created_at': self.created_at.isoformat(),
            'deadline': self.resolution_deadline.isoformat() if self.resolution_deadline else None,
            'actions': [
                {
                    'id': 'choose_local',
                    'label': 'Keep My Version',
                    'description': 'Use the version on this device'
                },
                {
                    'id': 'choose_remote',
                    'label': 'Use Server Version',
                    'description': 'Use the version from the server'
                },
                {
                    'id': 'review_manually',
                    'label': 'Review Changes',
                    'description': 'See detailed differences and decide'
                }
            ],
            'data': {
                'conflict_id': self.conflict.conflict_id,
                'data_type': self.conflict.data_type,
                'conflicted_fields': self.conflict.conflict_fields
            }
        }
    
    def _generate_user_message(self) -> str:
        """Generate user-friendly conflict message"""
        data_type_friendly = {
            'user_profile': 'Profile Information',
            'team_data': 'Team Information',
            'conversation_history': 'Conversation History',
            'gamification_data': 'Progress and Achievements'
        }.get(self.conflict.data_type, self.conflict.data_type.title())
        
        field_count = len(self.conflict.conflict_fields)
        
        if field_count == 1:
            return f"Your {data_type_friendly} was updated on another device. The '{self.conflict.conflict_fields[0]}' field has different values."
        else:
            return f"Your {data_type_friendly} was updated on another device. {field_count} fields have conflicting changes."


class OfflineDataStore:
    """Local database for offline data storage and sync queue"""
    
    def __init__(self, db_path: str = "offline_data.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database for offline storage"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Table for pending data changes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_changes (
                    change_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    data_type TEXT,
                    operation TEXT,
                    data TEXT,
                    timestamp TEXT,
                    sync_status TEXT,
                    retry_count INTEGER,
                    max_retries INTEGER,
                    conflict_resolution TEXT,
                    parent_change_id TEXT,
                    checksum TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table for cached data
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cached_data (
                    cache_key TEXT PRIMARY KEY,
                    user_id TEXT,
                    data_type TEXT,
                    data TEXT,
                    timestamp TEXT,
                    expiry TEXT,
                    checksum TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table for sync conflicts
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_conflicts (
                    conflict_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    data_type TEXT,
                    local_version TEXT,
                    remote_version TEXT,
                    local_timestamp TEXT,
                    remote_timestamp TEXT,
                    conflict_fields TEXT,
                    resolution_strategy TEXT,
                    resolved BOOLEAN,
                    resolution_data TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_changes_user_status ON data_changes(user_id, sync_status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cache_user_type ON cached_data(user_id, data_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_conflicts_user ON sync_conflicts(user_id, resolved)')
            
            conn.commit()
            conn.close()
            
            logger.info(f"Offline database initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize offline database: {e}")
            raise
    
    def save_change(self, change: DataChange):
        """Save data change to local database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            change_dict = change.to_dict()
            cursor.execute('''
                INSERT OR REPLACE INTO data_changes 
                (change_id, user_id, data_type, operation, data, timestamp, 
                 sync_status, retry_count, max_retries, conflict_resolution, 
                 parent_change_id, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                change_dict['change_id'], change_dict['user_id'], change_dict['data_type'],
                change_dict['operation'], json.dumps(change_dict['data']), change_dict['timestamp'],
                change_dict['sync_status'], change_dict['retry_count'], change_dict['max_retries'],
                change_dict['conflict_resolution'], change_dict['parent_change_id'], change_dict['checksum']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to save data change: {e}")
            raise
    
    def get_pending_changes(self, user_id: Optional[str] = None, limit: int = 100) -> List[DataChange]:
        """Get pending changes for synchronization"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if user_id:
                cursor.execute('''
                    SELECT * FROM data_changes 
                    WHERE user_id = ? AND sync_status = 'pending'
                    ORDER BY timestamp ASC LIMIT ?
                ''', (user_id, limit))
            else:
                cursor.execute('''
                    SELECT * FROM data_changes 
                    WHERE sync_status = 'pending'
                    ORDER BY timestamp ASC LIMIT ?
                ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            changes = []
            for row in rows:
                change_dict = {
                    'change_id': row[0], 'user_id': row[1], 'data_type': row[2],
                    'operation': row[3], 'data': json.loads(row[4]), 'timestamp': row[5],
                    'sync_status': row[6], 'retry_count': row[7], 'max_retries': row[8],
                    'conflict_resolution': row[9], 'parent_change_id': row[10], 'checksum': row[11]
                }
                changes.append(DataChange.from_dict(change_dict))
            
            return changes
            
        except Exception as e:
            logger.error(f"Failed to get pending changes: {e}")
            return []
    
    def update_change_status(self, change_id: str, status: SyncStatus, retry_count: int = None):
        """Update sync status of a change"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if retry_count is not None:
                cursor.execute('''
                    UPDATE data_changes 
                    SET sync_status = ?, retry_count = ?
                    WHERE change_id = ?
                ''', (status.value, retry_count, change_id))
            else:
                cursor.execute('''
                    UPDATE data_changes 
                    SET sync_status = ?
                    WHERE change_id = ?
                ''', (status.value, change_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to update change status: {e}")
    
    def cache_data(self, cache_key: str, user_id: str, data_type: str, data: Dict[str, Any], ttl_hours: int = 24):
        """Cache data for offline access"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            expiry = datetime.utcnow() + timedelta(hours=ttl_hours)
            data_str = json.dumps(data, sort_keys=True)
            checksum = hashlib.sha256(data_str.encode()).hexdigest()[:16]
            
            cursor.execute('''
                INSERT OR REPLACE INTO cached_data
                (cache_key, user_id, data_type, data, timestamp, expiry, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                cache_key, user_id, data_type, data_str,
                datetime.utcnow().isoformat(), expiry.isoformat(), checksum
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to cache data: {e}")
    
    def get_cached_data(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached data if not expired"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT data, timestamp, expiry, checksum FROM cached_data
                WHERE cache_key = ? AND expiry > ?
            ''', (cache_key, datetime.utcnow().isoformat()))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'data': json.loads(row[0]),
                    'timestamp': row[1],
                    'expiry': row[2],
                    'checksum': row[3],
                    'cached': True
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached data: {e}")
            return None


class ConflictResolver:
    """Resolves data synchronization conflicts"""
    
    def __init__(self):
        self.resolution_strategies = {
            ConflictResolution.LATEST_TIMESTAMP: self._resolve_by_timestamp,
            ConflictResolution.MERGE: self._resolve_by_merge,
            ConflictResolution.LOCAL_WINS: self._resolve_local_wins,
            ConflictResolution.REMOTE_WINS: self._resolve_remote_wins
        }
    
    def resolve_conflict(self, conflict: DataSyncConflict, strategy: ConflictResolution) -> Dict[str, Any]:
        """Resolve sync conflict using specified strategy"""
        
        if strategy in self.resolution_strategies:
            try:
                resolution = self.resolution_strategies[strategy](conflict)
                conflict.resolved = True
                conflict.resolution_data = resolution
                return resolution
            except Exception as e:
                logger.error(f"Conflict resolution failed with strategy {strategy}: {e}")
                return self._resolve_local_wins(conflict)  # Safe fallback
        
        logger.warning(f"Unknown resolution strategy: {strategy}")
        return self._resolve_local_wins(conflict)
    
    def _resolve_by_timestamp(self, conflict: DataSyncConflict) -> Dict[str, Any]:
        """Resolve conflict by using the most recent version"""
        if conflict.remote_timestamp > conflict.local_timestamp:
            return conflict.remote_version
        else:
            return conflict.local_version
    
    def _resolve_by_merge(self, conflict: DataSyncConflict) -> Dict[str, Any]:
        """Attempt to merge non-conflicting changes"""
        merged = conflict.local_version.copy()
        
        # For each field in remote version
        for key, remote_value in conflict.remote_version.items():
            local_value = conflict.local_version.get(key)
            
            # If field is not conflicted, take remote value
            if key not in conflict.conflict_fields:
                merged[key] = remote_value
            else:
                # For conflicted fields, apply merge logic based on data type
                if isinstance(local_value, dict) and isinstance(remote_value, dict):
                    # Merge dictionaries recursively
                    merged[key] = self._merge_dicts(local_value, remote_value)
                elif isinstance(local_value, list) and isinstance(remote_value, list):
                    # Merge lists by combining unique items
                    merged[key] = list(set(local_value + remote_value))
                else:
                    # For primitive types, use newer timestamp
                    if conflict.remote_timestamp > conflict.local_timestamp:
                        merged[key] = remote_value
                    else:
                        merged[key] = local_value
        
        return merged
    
    def _merge_dicts(self, local: Dict[str, Any], remote: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge dictionaries"""
        merged = local.copy()
        
        for key, value in remote.items():
            if key not in merged:
                merged[key] = value
            elif isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_dicts(merged[key], value)
            else:
                # Keep local value for conflicts
                pass
        
        return merged
    
    def _resolve_local_wins(self, conflict: DataSyncConflict) -> Dict[str, Any]:
        """Resolve by keeping local version"""
        return conflict.local_version
    
    def _resolve_remote_wins(self, conflict: DataSyncConflict) -> Dict[str, Any]:
        """Resolve by keeping remote version"""
        return conflict.remote_version


class DataSyncResilience:
    """Main data synchronization resilience coordinator"""
    
    def __init__(self):
        self.offline_store = OfflineDataStore()
        self.conflict_resolver = ConflictResolver()
        self.sync_queue: deque = deque()
        self.conflict_notifications: List[SyncConflictNotification] = []
        self.sync_status_by_user: Dict[str, Dict[str, SyncStatus]] = defaultdict(dict)
        self.sync_active = False
        self.sync_task = None
        
        # Configuration
        self.auto_resolve_threshold_minutes = 5  # Auto-resolve conflicts older than 5 minutes
        self.max_conflict_age_hours = 24  # Clean up conflicts older than 24 hours
        
    async def start_sync_service(self):
        """Start background synchronization service"""
        if not self.sync_active:
            self.sync_active = True
            self.sync_task = asyncio.create_task(self._sync_loop())
            logger.info("Data sync service started")
    
    def stop_sync_service(self):
        """Stop synchronization service"""
        self.sync_active = False
        if self.sync_task:
            self.sync_task.cancel()
            logger.info("Data sync service stopped")
    
    async def _sync_loop(self):
        """Background sync processing loop"""
        while self.sync_active:
            try:
                await self._process_pending_changes()
                await self._auto_resolve_old_conflicts()
                await self._cleanup_old_data()
                await asyncio.sleep(30)  # Sync every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync loop error: {e}")
                await asyncio.sleep(60)  # Back off on error
    
    @resilient_operation(component="data_sync")
    async def save_data(self, user_id: str, data_type: str, data: Dict[str, Any], operation: DataOperation = DataOperation.UPDATE) -> Dict[str, Any]:
        """Save data with sync resilience"""
        
        change_id = hashlib.md5(f"{user_id}{data_type}{operation.value}{time.time()}".encode()).hexdigest()[:12]
        
        change = DataChange(
            change_id=change_id,
            user_id=user_id,
            data_type=data_type,
            operation=operation,
            data=data
        )
        
        # Save to local database
        self.offline_store.save_change(change)
        
        # Update user sync status
        self.sync_status_by_user[user_id][data_type] = SyncStatus.PENDING
        
        # Try immediate sync if online
        if await self._is_online():
            try:
                result = await self._sync_change(change)
                return result
            except Exception as e:
                logger.warning(f"Immediate sync failed for {change_id}: {e}")
                return {
                    'status': 'saved_offline',
                    'change_id': change_id,
                    'message': 'Data saved locally, will sync when online',
                    'offline': True
                }
        
        return {
            'status': 'saved_offline',
            'change_id': change_id,
            'message': 'Data saved locally, will sync when online',
            'offline': True
        }
    
    @resilient_operation(component="data_sync")
    async def load_data(self, user_id: str, data_type: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Load data with offline fallback"""
        
        cache_key = f"{user_id}:{data_type}"
        
        # Try remote data first if online and not using cache
        if not force_refresh and await self._is_online():
            try:
                remote_data = await self._fetch_remote_data(user_id, data_type)
                
                if remote_data:
                    # Cache the data
                    self.offline_store.cache_data(cache_key, user_id, data_type, remote_data)
                    
                    # Check for conflicts with local changes
                    await self._check_for_conflicts(user_id, data_type, remote_data)
                    
                    return remote_data
            except Exception as e:
                logger.warning(f"Failed to load remote data for {user_id}:{data_type}: {e}")
        
        # Fallback to cached data
        cached_data = self.offline_store.get_cached_data(cache_key)
        
        if cached_data:
            return cached_data
        
        # No data available
        return None
    
    async def _sync_change(self, change: DataChange) -> Dict[str, Any]:
        """Synchronize a single data change"""
        
        try:
            # Simulate remote sync (would integrate with actual database)
            await asyncio.sleep(0.1)  # Simulate network delay
            
            # For now, mark as synced
            self.offline_store.update_change_status(change.change_id, SyncStatus.SYNCED)
            self.sync_status_by_user[change.user_id][change.data_type] = SyncStatus.SYNCED
            
            return {
                'status': 'synced',
                'change_id': change.change_id,
                'sync_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            # Handle sync failure
            change.retry_count += 1
            
            if change.retry_count >= change.max_retries:
                self.offline_store.update_change_status(change.change_id, SyncStatus.ERROR, change.retry_count)
                self.sync_status_by_user[change.user_id][change.data_type] = SyncStatus.ERROR
                raise Exception(f"Sync failed after {change.max_retries} attempts: {e}")
            else:
                self.offline_store.update_change_status(change.change_id, SyncStatus.PENDING, change.retry_count)
                raise e
    
    async def _fetch_remote_data(self, user_id: str, data_type: str) -> Optional[Dict[str, Any]]:
        """Fetch data from remote database (simulation)"""
        
        # Simulate network delay and potential failure
        await asyncio.sleep(0.1)
        
        # This would integrate with actual database
        # For now, return None to indicate no remote data
        return None
    
    async def _check_for_conflicts(self, user_id: str, data_type: str, remote_data: Dict[str, Any]):
        """Check for conflicts between local and remote data"""
        
        cache_key = f"{user_id}:{data_type}"
        cached_data = self.offline_store.get_cached_data(cache_key)
        
        if cached_data and 'data' in cached_data:
            local_data = cached_data['data']
            
            conflict = resilience_manager.detect_sync_conflict(user_id, data_type, local_data, remote_data)
            
            if conflict:
                logger.warning(f"Sync conflict detected: {conflict.conflict_id}")
                
                # Create notification
                notification = SyncConflictNotification(
                    notification_id=hashlib.md5(f"{conflict.conflict_id}{time.time()}".encode()).hexdigest()[:12],
                    user_id=user_id,
                    conflict=conflict,
                    resolution_deadline=datetime.utcnow() + timedelta(hours=24)
                )
                
                self.conflict_notifications.append(notification)
                self.sync_status_by_user[user_id][data_type] = SyncStatus.CONFLICT
                
                # Try auto-resolution for simple conflicts
                if await self._try_auto_resolve_conflict(conflict):
                    notification.acknowledged = True
    
    async def _try_auto_resolve_conflict(self, conflict: DataSyncConflict) -> bool:
        """Attempt automatic conflict resolution"""
        
        # Simple conflicts can be auto-resolved
        time_diff = abs((conflict.remote_timestamp - conflict.local_timestamp).total_seconds())
        
        if time_diff < 300:  # 5 minutes
            # Use latest timestamp for recent conflicts
            resolution = self.conflict_resolver.resolve_conflict(conflict, ConflictResolution.LATEST_TIMESTAMP)
            
            logger.info(f"Auto-resolved conflict {conflict.conflict_id} using latest timestamp")
            return True
        
        elif len(conflict.conflict_fields) == 0:
            # No actual field conflicts, safe to merge
            resolution = self.conflict_resolver.resolve_conflict(conflict, ConflictResolution.MERGE)
            
            logger.info(f"Auto-resolved conflict {conflict.conflict_id} by merging")
            return True
        
        return False
    
    async def resolve_user_conflict(self, user_id: str, notification_id: str, resolution_choice: str) -> Dict[str, Any]:
        """Handle user's conflict resolution choice"""
        
        # Find the notification
        notification = None
        for notif in self.conflict_notifications:
            if notif.notification_id == notification_id and notif.user_id == user_id:
                notification = notif
                break
        
        if not notification:
            return {'status': 'error', 'message': 'Notification not found'}
        
        conflict = notification.conflict
        
        # Apply user's choice
        if resolution_choice == 'choose_local':
            resolution_data = self.conflict_resolver.resolve_conflict(conflict, ConflictResolution.LOCAL_WINS)
        elif resolution_choice == 'choose_remote':
            resolution_data = self.conflict_resolver.resolve_conflict(conflict, ConflictResolution.REMOTE_WINS)
        elif resolution_choice == 'merge':
            resolution_data = self.conflict_resolver.resolve_conflict(conflict, ConflictResolution.MERGE)
        else:
            return {'status': 'error', 'message': 'Invalid resolution choice'}
        
        # Mark notification as acknowledged
        notification.acknowledged = True
        
        # Update sync status
        self.sync_status_by_user[user_id][conflict.data_type] = SyncStatus.SYNCED
        
        # Save resolved data
        await self.save_data(user_id, conflict.data_type, resolution_data, DataOperation.UPDATE)
        
        return {
            'status': 'resolved',
            'conflict_id': conflict.conflict_id,
            'resolution_data': resolution_data
        }
    
    async def _process_pending_changes(self):
        """Process all pending changes for synchronization"""
        
        if not await self._is_online():
            return
        
        pending_changes = self.offline_store.get_pending_changes(limit=50)
        
        for change in pending_changes:
            try:
                await self._sync_change(change)
                logger.debug(f"Synced change {change.change_id}")
            except Exception as e:
                logger.warning(f"Failed to sync change {change.change_id}: {e}")
    
    async def _auto_resolve_old_conflicts(self):
        """Auto-resolve conflicts that are older than threshold"""
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=self.auto_resolve_threshold_minutes)
        
        for notification in self.conflict_notifications:
            if not notification.acknowledged and notification.created_at < cutoff_time:
                conflict = notification.conflict
                
                # Auto-resolve using merge strategy
                try:
                    resolution_data = self.conflict_resolver.resolve_conflict(conflict, ConflictResolution.MERGE)
                    await self.save_data(notification.user_id, conflict.data_type, resolution_data, DataOperation.UPDATE)
                    
                    notification.acknowledged = True
                    logger.info(f"Auto-resolved old conflict {conflict.conflict_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to auto-resolve conflict {conflict.conflict_id}: {e}")
    
    async def _cleanup_old_data(self):
        """Clean up old conflicts and cached data"""
        
        # Remove old acknowledged notifications
        cutoff_time = datetime.utcnow() - timedelta(hours=self.max_conflict_age_hours)
        
        self.conflict_notifications = [
            notif for notif in self.conflict_notifications
            if not notif.acknowledged or notif.created_at > cutoff_time
        ]
    
    async def _is_online(self) -> bool:
        """Check if we're currently online"""
        # This would integrate with network resilience module
        # For now, simulate being online most of the time
        return True
    
    def get_user_sync_status(self, user_id: str) -> Dict[str, Any]:
        """Get sync status for a specific user"""
        
        user_conflicts = [
            notif.to_user_friendly_dict() 
            for notif in self.conflict_notifications
            if notif.user_id == user_id and not notif.acknowledged
        ]
        
        pending_changes = len(self.offline_store.get_pending_changes(user_id))
        
        data_statuses = self.sync_status_by_user.get(user_id, {})
        
        return {
            'user_id': user_id,
            'overall_status': self._calculate_overall_status(data_statuses),
            'data_types': {
                data_type: status.value
                for data_type, status in data_statuses.items()
            },
            'pending_changes': pending_changes,
            'active_conflicts': len(user_conflicts),
            'conflict_notifications': user_conflicts,
            'last_sync': datetime.utcnow().isoformat()
        }
    
    def _calculate_overall_status(self, data_statuses: Dict[str, SyncStatus]) -> str:
        """Calculate overall sync status from individual data type statuses"""
        if not data_statuses:
            return 'synced'
        
        statuses = list(data_statuses.values())
        
        if SyncStatus.ERROR in statuses:
            return 'error'
        elif SyncStatus.CONFLICT in statuses:
            return 'conflict'
        elif SyncStatus.PENDING in statuses:
            return 'pending'
        elif SyncStatus.OFFLINE in statuses:
            return 'offline'
        else:
            return 'synced'
    
    def get_system_sync_status(self) -> Dict[str, Any]:
        """Get overall system synchronization status"""
        
        total_users = len(self.sync_status_by_user)
        total_conflicts = len([n for n in self.conflict_notifications if not n.acknowledged])
        total_pending = len(self.offline_store.get_pending_changes())
        
        return {
            'sync_active': self.sync_active,
            'total_users': total_users,
            'total_pending_changes': total_pending,
            'total_unresolved_conflicts': total_conflicts,
            'auto_resolve_threshold_minutes': self.auto_resolve_threshold_minutes,
            'last_sync_cycle': datetime.utcnow().isoformat()
        }


# Global data sync resilience instance
data_sync_resilience = DataSyncResilience()


async def resilient_save_data(user_id: str, data_type: str, data: Dict[str, Any], operation: DataOperation = DataOperation.UPDATE) -> Dict[str, Any]:
    """Global function for resilient data saving"""
    return await data_sync_resilience.save_data(user_id, data_type, data, operation)


async def resilient_load_data(user_id: str, data_type: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """Global function for resilient data loading"""
    return await data_sync_resilience.load_data(user_id, data_type, force_refresh)


def get_sync_status(user_id: str) -> Dict[str, Any]:
    """Get sync status for a user"""
    return data_sync_resilience.get_user_sync_status(user_id)


# Initialize data sync service
async def initialize_data_sync_resilience():
    """Initialize data synchronization resilience"""
    try:
        await data_sync_resilience.start_sync_service()
        logger.info("Data sync resilience initialized")
    except Exception as e:
        logger.error(f"Failed to initialize data sync resilience: {e}")