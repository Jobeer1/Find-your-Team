"""
Local Storage Manager for Robust P2P Chat System
Handles local storage of chat history, user data, and agent insights
Minimizes AWS database usage by storing data locally first
"""

import json
import sqlite3
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class StoragePriority(Enum):
    """Data storage priority levels"""
    LOCAL_ONLY = "local_only"          # Never sync to cloud
    LOCAL_FIRST = "local_first"        # Store locally, sync when possible
    CLOUD_BACKUP = "cloud_backup"      # Store locally + backup to cloud
    CLOUD_REQUIRED = "cloud_required"  # Must be in cloud database

class ChatMode(Enum):
    """Chat operation modes with bandwidth awareness"""
    HIGH_BANDWIDTH_GLOBAL = "high_global"
    LOW_BANDWIDTH_GLOBAL = "low_global" 
    LAN_HIGH_BANDWIDTH = "lan_high"
    LAN_LOW_BANDWIDTH = "lan_low"
    OFFLINE_MODE = "offline"

class LocalStorageManager:
    """
    Manages local data storage with intelligent cloud synchronization
    Prioritizes user device storage to minimize AWS costs and improve performance
    """
    
    def __init__(self, user_id: str, storage_path: str = None):
        self.user_id = user_id
        self.storage_path = storage_path or os.path.join(os.getcwd(), "user_data")
        self.db_path = os.path.join(self.storage_path, f"user_{user_id}.db")
        
        # Ensure storage directory exists
        Path(self.storage_path).mkdir(parents=True, exist_ok=True)
        
        # Initialize local database
        self._init_local_database()
        
        # Background sync thread
        self.sync_thread = None
        self.sync_enabled = False
        
        # Chat mode tracking
        self.current_mode = ChatMode.OFFLINE_MODE
        self.bandwidth_quality = "unknown"
        
        logger.info(f"LocalStorageManager initialized for user {user_id}")
    
    def _init_local_database(self):
        """Initialize local SQLite database schema"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Chat messages table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id TEXT PRIMARY KEY,
                        chat_id TEXT NOT NULL,
                        sender_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        message_type TEXT DEFAULT 'text',
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        sync_status TEXT DEFAULT 'pending',
                        storage_priority TEXT DEFAULT 'local_first',
                        file_path TEXT,
                        read_status TEXT DEFAULT 'unread'
                    )
                """)
                
                # Chat rooms table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS chat_rooms (
                        chat_id TEXT PRIMARY KEY,
                        chat_name TEXT NOT NULL,
                        participants TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        chat_mode TEXT DEFAULT 'high_global',
                        last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                        sync_status TEXT DEFAULT 'pending'
                    )
                """)
                
                # Agent insights table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS agent_insights (
                        id TEXT PRIMARY KEY,
                        agent_type TEXT NOT NULL,
                        insight_data TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        relevance_score REAL DEFAULT 1.0,
                        storage_priority TEXT DEFAULT 'local_only',
                        sync_status TEXT DEFAULT 'local_only'
                    )
                """)
                
                # User preferences table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        sync_status TEXT DEFAULT 'local_first'
                    )
                """)
                
                # Connection history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS connection_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_mode TEXT NOT NULL,
                        bandwidth_quality TEXT NOT NULL,
                        connection_start DATETIME DEFAULT CURRENT_TIMESTAMP,
                        connection_end DATETIME,
                        messages_sent INTEGER DEFAULT 0,
                        bytes_transferred INTEGER DEFAULT 0
                    )
                """)
                
                conn.commit()
                logger.info("Local database schema initialized")
                
        except Exception as e:
            logger.error(f"Failed to initialize local database: {e}")
            raise
    
    def store_message(self, message_data: Dict[str, Any], priority: StoragePriority = StoragePriority.LOCAL_FIRST):
        """Store chat message with specified storage priority"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO chat_messages 
                    (id, chat_id, sender_id, content, message_type, timestamp, 
                     storage_priority, file_path, sync_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message_data.get('id'),
                    message_data.get('chat_id'),
                    message_data.get('sender_id'),
                    message_data.get('content'),
                    message_data.get('message_type', 'text'),
                    message_data.get('timestamp', datetime.now().isoformat()),
                    priority.value,
                    message_data.get('file_path'),
                    'pending' if priority != StoragePriority.LOCAL_ONLY else 'local_only'
                ))
                
                conn.commit()
                logger.debug(f"Message stored locally with priority {priority.value}")
                
                # Schedule cloud sync if needed
                if priority in [StoragePriority.LOCAL_FIRST, StoragePriority.CLOUD_BACKUP, StoragePriority.CLOUD_REQUIRED]:
                    self._schedule_sync()
                
        except Exception as e:
            logger.error(f"Failed to store message locally: {e}")
            raise
    
    def get_chat_history(self, chat_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve chat history from local storage"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM chat_messages 
                    WHERE chat_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ? OFFSET ?
                """, (chat_id, limit, offset))
                
                messages = []
                for row in cursor.fetchall():
                    message = dict(row)
                    message['timestamp'] = datetime.fromisoformat(message['timestamp'])
                    messages.append(message)
                
                return list(reversed(messages))  # Return in chronological order
                
        except Exception as e:
            logger.error(f"Failed to retrieve chat history: {e}")
            return []
    
    def store_agent_insight(self, agent_type: str, insight_data: Dict[str, Any], 
                          relevance_score: float = 1.0, priority: StoragePriority = StoragePriority.LOCAL_ONLY):
        """Store agent insights with local-first approach"""
        try:
            insight_id = f"{agent_type}_{int(time.time() * 1000)}"
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO agent_insights 
                    (id, agent_type, insight_data, relevance_score, storage_priority, sync_status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    insight_id,
                    agent_type,
                    json.dumps(insight_data),
                    relevance_score,
                    priority.value,
                    'local_only' if priority == StoragePriority.LOCAL_ONLY else 'pending'
                ))
                
                conn.commit()
                logger.debug(f"Agent insight stored: {agent_type}")
                
                # Only sync critical insights to cloud
                if priority == StoragePriority.CLOUD_REQUIRED:
                    self._schedule_sync()
                
        except Exception as e:
            logger.error(f"Failed to store agent insight: {e}")
            raise
    
    def get_agent_insights(self, agent_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve agent insights from local storage"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if agent_type:
                    cursor.execute("""
                        SELECT * FROM agent_insights 
                        WHERE agent_type = ? 
                        ORDER BY relevance_score DESC, timestamp DESC 
                        LIMIT ?
                    """, (agent_type, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM agent_insights 
                        ORDER BY relevance_score DESC, timestamp DESC 
                        LIMIT ?
                    """, (limit,))
                
                insights = []
                for row in cursor.fetchall():
                    insight = dict(row)
                    insight['insight_data'] = json.loads(insight['insight_data'])
                    insight['timestamp'] = datetime.fromisoformat(insight['timestamp'])
                    insights.append(insight)
                
                return insights
                
        except Exception as e:
            logger.error(f"Failed to retrieve agent insights: {e}")
            return []
    
    def store_user_data(self, user_id: str, user_data: Dict[str, Any], priority: StoragePriority = StoragePriority.LOCAL_FIRST):
        """Store user profile and registration data"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Create user_profiles table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        profile_data TEXT NOT NULL,
                        storage_priority TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        last_updated TEXT NOT NULL,
                        UNIQUE(user_id)
                    )
                """)
                
                # Store user data as JSON
                profile_json = json.dumps(user_data)
                timestamp = datetime.now().isoformat()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO user_profiles 
                    (user_id, profile_data, storage_priority, timestamp, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, profile_json, priority.value, timestamp, timestamp))
                
                conn.commit()
                logger.info(f"User profile stored for user {user_id} with priority {priority.value}")
                
                # Store in session data for quick access
                if not hasattr(self, '_session_user_data'):
                    self._session_user_data = {}
                self._session_user_data[user_id] = user_data
                
        except Exception as e:
            logger.error(f"Failed to store user data for {user_id}: {e}")
            raise
    
    def get_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user profile data"""
        try:
            # Check session cache first
            if hasattr(self, '_session_user_data') and user_id in self._session_user_data:
                return self._session_user_data[user_id]
            
            # Query database
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT profile_data, last_updated 
                    FROM user_profiles 
                    WHERE user_id = ?
                    ORDER BY last_updated DESC
                    LIMIT 1
                """, (user_id,))
                
                row = cursor.fetchone()
                if row:
                    user_data = json.loads(row['profile_data'])
                    
                    # Cache in session
                    if not hasattr(self, '_session_user_data'):
                        self._session_user_data = {}
                    self._session_user_data[user_id] = user_data
                    
                    return user_data
                    
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve user data for {user_id}: {e}")
            return None
    
    def update_chat_mode(self, new_mode: ChatMode, bandwidth_quality: str):
        """Update current chat mode and log connection history"""
        try:
            # End previous connection session
            if self.current_mode != ChatMode.OFFLINE_MODE:
                self._end_connection_session()
            
            # Start new connection session
            self.current_mode = new_mode
            self.bandwidth_quality = bandwidth_quality
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO connection_history 
                    (chat_mode, bandwidth_quality, connection_start)
                    VALUES (?, ?, ?)
                """, (new_mode.value, bandwidth_quality, datetime.now().isoformat()))
                
                conn.commit()
                
            logger.info(f"Chat mode updated to {new_mode.value} with {bandwidth_quality} bandwidth")
            
        except Exception as e:
            logger.error(f"Failed to update chat mode: {e}")
    
    def _end_connection_session(self):
        """End the current connection session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE connection_history 
                    SET connection_end = ? 
                    WHERE connection_end IS NULL 
                    ORDER BY connection_start DESC 
                    LIMIT 1
                """, (datetime.now().isoformat(),))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to end connection session: {e}")
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get local storage statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Message counts by storage priority
                cursor.execute("""
                    SELECT storage_priority, COUNT(*) as count 
                    FROM chat_messages 
                    GROUP BY storage_priority
                """)
                message_stats = dict(cursor.fetchall())
                
                # Agent insights count
                cursor.execute("SELECT COUNT(*) FROM agent_insights")
                insights_count = cursor.fetchone()[0]
                
                # Database size
                db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                
                # Sync pending count
                cursor.execute("""
                    SELECT COUNT(*) FROM chat_messages 
                    WHERE sync_status = 'pending'
                """)
                pending_sync = cursor.fetchone()[0]
                
                return {
                    'database_size_bytes': db_size,
                    'database_size_mb': round(db_size / 1024 / 1024, 2),
                    'message_counts': message_stats,
                    'agent_insights_count': insights_count,
                    'pending_sync_count': pending_sync,
                    'current_mode': self.current_mode.value,
                    'bandwidth_quality': self.bandwidth_quality
                }
                
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {}
    
    def _schedule_sync(self):
        """Schedule background synchronization with cloud"""
        if not self.sync_enabled:
            return
        
        if self.sync_thread and self.sync_thread.is_alive():
            return
        
        self.sync_thread = threading.Thread(target=self._background_sync, daemon=True)
        self.sync_thread.start()
    
    def _background_sync(self):
        """Background synchronization with cloud databases"""
        try:
            # Only sync essential data to minimize AWS costs
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Sync only CLOUD_REQUIRED and CLOUD_BACKUP priority data
                cursor.execute("""
                    SELECT * FROM chat_messages 
                    WHERE sync_status = 'pending' 
                    AND storage_priority IN ('cloud_required', 'cloud_backup')
                    LIMIT 10
                """)
                
                pending_messages = cursor.fetchall()
                
                for message in pending_messages:
                    # TODO: Implement actual AWS sync logic here
                    # For now, just mark as synced
                    cursor.execute("""
                        UPDATE chat_messages 
                        SET sync_status = 'synced' 
                        WHERE id = ?
                    """, (message[0],))
                
                conn.commit()
                logger.debug(f"Synced {len(pending_messages)} messages to cloud")
                
        except Exception as e:
            logger.error(f"Background sync failed: {e}")
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old local data to manage storage space"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete old messages (keep only LOCAL_ONLY and recent data)
                cursor.execute("""
                    DELETE FROM chat_messages 
                    WHERE timestamp < ? 
                    AND storage_priority != 'local_only'
                    AND sync_status = 'synced'
                """, (cutoff_date.isoformat(),))
                
                messages_deleted = cursor.rowcount
                
                # Delete old connection history
                cursor.execute("""
                    DELETE FROM connection_history 
                    WHERE connection_start < ?
                """, (cutoff_date.isoformat(),))
                
                history_deleted = cursor.rowcount
                
                conn.commit()
                
                # Vacuum database to reclaim space
                cursor.execute("VACUUM")
                
                logger.info(f"Cleaned up {messages_deleted} messages and {history_deleted} history entries")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
    
    def export_user_data(self, export_path: str = None) -> str:
        """Export user data for backup or migration"""
        try:
            export_path = export_path or os.path.join(self.storage_path, f"export_{self.user_id}_{int(time.time())}.json")
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Export all user data
                export_data = {
                    'user_id': self.user_id,
                    'export_timestamp': datetime.now().isoformat(),
                    'messages': [],
                    'chats': [],
                    'insights': [],
                    'preferences': [],
                    'connection_history': []
                }
                
                # Export messages
                cursor.execute("SELECT * FROM chat_messages ORDER BY timestamp")
                for row in cursor.fetchall():
                    export_data['messages'].append(dict(row))
                
                # Export chats
                cursor.execute("SELECT * FROM chat_rooms ORDER BY created_at")
                for row in cursor.fetchall():
                    export_data['chats'].append(dict(row))
                
                # Export insights
                cursor.execute("SELECT * FROM agent_insights ORDER BY timestamp")
                for row in cursor.fetchall():
                    insight = dict(row)
                    insight['insight_data'] = json.loads(insight['insight_data'])
                    export_data['insights'].append(insight)
                
                # Save export
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, default=str)
                
                logger.info(f"User data exported to {export_path}")
                return export_path
                
        except Exception as e:
            logger.error(f"Failed to export user data: {e}")
            raise