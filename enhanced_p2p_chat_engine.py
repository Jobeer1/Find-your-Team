"""
Enhanced P2P Chat Engine with Local Storage Integration
Robust chat system with minimal AWS usage and local-first approach
"""

import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import threading
import time
import hashlib

# Import original P2P chat engine components
from p2p_chat_engine import (
    P2PChatEngine as OriginalEngine, 
    MessageType, MessageStatus, UserStatus, ConnectionQuality,
    ChatMessage, ChatUser, FileMetadata
)

# Import local storage components
try:
    from local_storage_manager import LocalStorageManager, StoragePriority, ChatMode
    from chat_mode_manager import ChatModeManager, BandwidthQuality
    LOCAL_STORAGE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Local storage not available: {e}")
    LOCAL_STORAGE_AVAILABLE = False

logger = logging.getLogger(__name__)

class EnhancedP2PChatEngine(OriginalEngine):
    """
    Enhanced P2P Chat Engine with local storage and robust mode management
    Minimizes cloud usage while providing rich chat functionality
    """
    
    def __init__(self, socketio_instance=None, user_id: str = None):
        # Initialize original engine
        super().__init__(socketio_instance)
        
        # Initialize emit rate-limiting attributes first
        self._emit_lock = threading.Lock()
        self._last_emit_hash: Optional[str] = None
        self._last_emit_time: Optional[datetime] = None
        self._min_emit_interval = timedelta(seconds=3)
        
        # Enhanced initialization
        self.user_id = user_id or "anonymous_user"
        self.current_chat_mode = ChatMode.OFFLINE_MODE
        self.bandwidth_quality = BandwidthQuality.UNKNOWN
        
        # Initialize threading locks for safe operations
        self._emit_lock = threading.Lock()
        self._last_emit_hash = None
        
        # Statistics tracking (initialize before other components)
        self.stats = {
            'messages_local': 0,
            'messages_synced': 0,
            'bytes_saved_local': 0,
            'sync_attempts': 0,
            'sync_failures': 0,
            'current_mode': self.current_chat_mode.value if hasattr(self.current_chat_mode, 'value') else str(self.current_chat_mode)
        }
        
        # Initialize local storage
        if LOCAL_STORAGE_AVAILABLE:
            self.storage_manager = LocalStorageManager(self.user_id)
            self.mode_manager = ChatModeManager(self.user_id, self.storage_manager)
            self.mode_manager.add_mode_change_callback(self._on_mode_change)
            
            # Start monitoring
            self.mode_manager.start_monitoring()
            logger.info("Local storage and mode management initialized")
        else:
            self.storage_manager = None
            self.mode_manager = None
            logger.warning("Running without local storage - reduced functionality")
        
        # Message queues for different priorities
        self.local_queue = []  # Local-only messages
        self.sync_queue = []   # Messages waiting for cloud sync
        self.priority_queue = []  # High-priority messages for immediate sync
        
    def _on_mode_change(self, mode_info: Dict[str, Any]):
        """Handle chat mode changes"""
        try:
            old_mode = self.current_chat_mode
            new_mode_str = mode_info.get('current_mode', 'offline')
            
            # Convert string to ChatMode enum
            try:
                if hasattr(ChatMode, new_mode_str.upper()):
                    new_mode = getattr(ChatMode, new_mode_str.upper())
                else:
                    # Try to match by value
                    for mode in ChatMode:
                        if mode.value == new_mode_str:
                            new_mode = mode
                            break
                    else:
                        new_mode = ChatMode.OFFLINE_MODE
            except:
                new_mode = ChatMode.OFFLINE_MODE
            
            self.current_chat_mode = new_mode
            self.bandwidth_quality = BandwidthQuality(mode_info.get('bandwidth_quality', 'unknown'))
            
            # Update statistics
            self.stats['current_mode'] = new_mode.value if hasattr(new_mode, 'value') else str(new_mode)
            
            # Notify connected clients about mode change
            if self.socketio:
                self._emit_mode_change(old_mode, new_mode, mode_info)
            
            # Adjust behavior based on new mode
            self._adjust_for_mode(new_mode)
            
            logger.info(f"Chat mode changed: {old_mode} -> {new_mode}")
            
        except Exception as e:
            logger.error(f"Error handling mode change: {e}")
    
    def _emit_mode_change(self, old_mode, new_mode, mode_info):
        """Emit mode change to connected clients"""
        try:
            if not self.socketio:
                return

            # Build a canonical payload string to hash for deduplication
            payload = json.dumps({
                'old_mode': old_mode.value if hasattr(old_mode, 'value') else str(old_mode),
                'new_mode': new_mode.value if hasattr(new_mode, 'value') else str(new_mode),
                'mode_info': mode_info,
                'bandwidth_quality': self.bandwidth_quality.value if hasattr(self.bandwidth_quality, 'value') else str(self.bandwidth_quality)
            }, sort_keys=True, default=str)

            payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()

            with self._emit_lock:
                now = datetime.now()
                # If same payload recently emitted, skip unless interval passed
                if self._last_emit_hash == payload_hash:
                    if self._last_emit_time and (now - self._last_emit_time) < self._min_emit_interval:
                        logger.debug('Skipping duplicate mode_changed emit (rate-limited)')
                        return

                # Emit and update last emit state
                self.socketio.emit('mode_changed', {
                    'old_mode': old_mode.value if hasattr(old_mode, 'value') else str(old_mode),
                    'new_mode': new_mode.value if hasattr(new_mode, 'value') else str(new_mode),
                    'mode_info': mode_info,
                    'bandwidth_quality': self.bandwidth_quality.value if hasattr(self.bandwidth_quality, 'value') else str(self.bandwidth_quality),
                    'timestamp': now.isoformat()
                })

                self._last_emit_hash = payload_hash
                self._last_emit_time = now
        except Exception as e:
            logger.error(f"Failed to emit mode change: {e}")
    
    def _adjust_for_mode(self, mode):
        """Adjust engine behavior based on chat mode"""
        try:
            if mode == ChatMode.LOW_BANDWIDTH_GLOBAL or mode == ChatMode.LAN_LOW_BANDWIDTH:
                # Reduce chunk size for file transfers
                self._set_low_bandwidth_settings()
            elif mode == ChatMode.HIGH_BANDWIDTH_GLOBAL or mode == ChatMode.LAN_HIGH_BANDWIDTH:
                # Optimize for high bandwidth
                self._set_high_bandwidth_settings()
            elif mode == ChatMode.OFFLINE_MODE:
                # Queue everything locally
                self._set_offline_settings()
            
        except Exception as e:
            logger.error(f"Failed to adjust for mode {mode}: {e}")
    
    def _set_low_bandwidth_settings(self):
        """Configure for low bandwidth operation"""
        # Smaller chunk sizes
        self.chunk_size = 16 * 1024  # 16KB chunks
        self.max_file_size = 5 * 1024 * 1024  # 5MB max
        self.image_quality = 60  # Lower image quality
        self.enable_compression = True
    
    def _set_high_bandwidth_settings(self):
        """Configure for high bandwidth operation"""
        # Larger chunk sizes
        self.chunk_size = 256 * 1024  # 256KB chunks
        self.max_file_size = 100 * 1024 * 1024  # 100MB max
        self.image_quality = 90  # Higher image quality
        self.enable_compression = False
    
    def _set_offline_settings(self):
        """Configure for offline operation"""
        # Queue everything locally
        self.chunk_size = 32 * 1024  # 32KB chunks
        self.max_file_size = 50 * 1024 * 1024  # 50MB max
        self.enable_compression = True
    
    def send_message_enhanced(self, sender_id: str, chat_id: str, content: str, 
                            message_type: MessageType = MessageType.TEXT, 
                            reply_to: str = None, storage_priority: StoragePriority = None) -> ChatMessage:
        """Enhanced message sending with local storage priority"""
        try:
            # Create message
            message = ChatMessage(
                message_id=str(uuid.uuid4()),
                chat_id=chat_id,
                sender_id=sender_id,
                content=content,
                message_type=message_type,
                timestamp=datetime.now(),
                reply_to=reply_to,
                status=MessageStatus.PENDING
            )
            
            # Determine storage priority if not specified
            if storage_priority is None:
                storage_priority = self._get_message_storage_priority(message)
            
            # Store locally first
            if self.storage_manager:
                self.storage_manager.store_message(
                    message_data=message.__dict__,
                    priority=storage_priority
                )
                self.stats['messages_local'] += 1
            
            # Add to local message list
            if chat_id not in self.messages:
                self.messages[chat_id] = []
            self.messages[chat_id].append(message)
            
            # Handle based on current mode and priority
            self._handle_message_by_mode(message, storage_priority)
            
            # Emit to connected clients
            if self.socketio:
                self._emit_message_to_chat(chat_id, message)
            
            logger.debug(f"Enhanced message sent: {sender_id} -> {chat_id} (priority: {storage_priority.value})")
            return message
            
        except Exception as e:
            logger.error(f"Enhanced send message error: {e}")
            raise
    
    def _get_message_storage_priority(self, message: ChatMessage) -> StoragePriority:
        """Determine appropriate storage priority for message"""
        
        # System messages and critical info -> cloud required
        if message.message_type == MessageType.SYSTEM:
            return StoragePriority.CLOUD_REQUIRED
        
        # File transfers -> local first, cloud backup
        if message.message_type in [MessageType.FILE, MessageType.IMAGE, MessageType.VIDEO]:
            return StoragePriority.CLOUD_BACKUP
        
        # Regular text messages -> local first (minimal cloud usage)
        if message.message_type == MessageType.TEXT:
            # Only sync important text messages to cloud
            if len(message.content) > 500 or any(keyword in message.content.lower() 
                                               for keyword in ['important', 'urgent', 'meeting', 'deadline']):
                return StoragePriority.LOCAL_FIRST
            else:
                return StoragePriority.LOCAL_ONLY
        
        # Voice messages -> local only (too much bandwidth)
        if message.message_type == MessageType.VOICE:
            return StoragePriority.LOCAL_ONLY
        
        # Default to local first
        return StoragePriority.LOCAL_FIRST
    
    def _handle_message_by_mode(self, message: ChatMessage, priority: StoragePriority):
        """Handle message based on current chat mode"""
        
        if self.current_chat_mode == ChatMode.OFFLINE_MODE:
            # Queue for later sync
            self.local_queue.append((message, priority))
            
        elif self.current_chat_mode in [ChatMode.LOW_BANDWIDTH_GLOBAL, ChatMode.LAN_LOW_BANDWIDTH]:
            # Minimize cloud usage
            if priority == StoragePriority.CLOUD_REQUIRED:
                self.priority_queue.append((message, priority))
            else:
                self.local_queue.append((message, priority))
                
        elif self.current_chat_mode in [ChatMode.HIGH_BANDWIDTH_GLOBAL, ChatMode.LAN_HIGH_BANDWIDTH]:
            # Normal sync behavior
            if priority in [StoragePriority.CLOUD_REQUIRED, StoragePriority.CLOUD_BACKUP]:
                self.sync_queue.append((message, priority))
            else:
                self.local_queue.append((message, priority))
    
    def _emit_message_to_chat(self, chat_id: str, message: ChatMessage):
        """Emit message to chat participants with mode awareness"""
        try:
            # Prepare message data
            message_data = {
                **message.__dict__,
                'mode': self.current_chat_mode.value if hasattr(self.current_chat_mode, 'value') else str(self.current_chat_mode),
                'bandwidth_quality': self.bandwidth_quality.value if hasattr(self.bandwidth_quality, 'value') else str(self.bandwidth_quality),
                'local_stored': True
            }
            
            # Emit based on current mode
            if self.current_chat_mode in [ChatMode.LOW_BANDWIDTH_GLOBAL, ChatMode.LAN_LOW_BANDWIDTH]:
                # Compress data for low bandwidth
                message_data = self._compress_message_data(message_data)
            
            if self.socketio:
                self.socketio.emit('new_message', message_data, room=f'chat_{chat_id}')
            
        except Exception as e:
            logger.error(f"Failed to emit message to chat {chat_id}: {e}")
    
    def _compress_message_data(self, data: Dict) -> Dict:
        """Compress message data for low bandwidth transmission"""
        # Remove non-essential fields for low bandwidth
        compressed = {
            'id': data.get('message_id'),
            'cid': data.get('chat_id'),
            'sid': data.get('sender_id'),
            'c': data.get('content', '')[:200] if data.get('message_type') == MessageType.TEXT else data.get('content', ''),
            't': data.get('message_type', MessageType.TEXT).value if hasattr(data.get('message_type'), 'value') else data.get('message_type'),
            'ts': data.get('timestamp').isoformat() if isinstance(data.get('timestamp'), datetime) else data.get('timestamp'),
            'compressed': True
        }
        return compressed
    
    def get_chat_history_enhanced(self, chat_id: str, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get chat history prioritizing local storage"""
        try:
            # Try local storage first
            if self.storage_manager:
                local_messages = self.storage_manager.get_chat_history(chat_id, limit, offset)
                if local_messages:
                    logger.debug(f"Retrieved {len(local_messages)} messages from local storage")
                    return local_messages
            
            # Fallback to in-memory storage
            if chat_id in self.messages:
                messages = self.messages[chat_id]
                start_idx = max(0, len(messages) - offset - limit)
                end_idx = len(messages) - offset if offset > 0 else len(messages)
                
                selected_messages = messages[start_idx:end_idx]
                return [msg.__dict__ for msg in selected_messages]
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get chat history: {e}")
            return []
    
    def store_agent_insight(self, agent_type: str, insight_data: Dict[str, Any], 
                          relevance_score: float = 1.0) -> bool:
        """Store agent insights locally (never sync to cloud by default)"""
        try:
            if self.storage_manager:
                self.storage_manager.store_agent_insight(
                    agent_type=agent_type,
                    insight_data=insight_data,
                    relevance_score=relevance_score,
                    priority=StoragePriority.LOCAL_ONLY  # Keep insights local
                )
                
                logger.debug(f"Agent insight stored locally: {agent_type}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to store agent insight: {e}")
            return False
    
    def get_agent_insights(self, agent_type: str = None, limit: int = 10) -> List[Dict]:
        """Retrieve agent insights from local storage"""
        try:
            if self.storage_manager:
                return self.storage_manager.get_agent_insights(agent_type, limit)
            return []
            
        except Exception as e:
            logger.error(f"Failed to get agent insights: {e}")
            return []
    
    def get_mode_info(self) -> Dict[str, Any]:
        """Get comprehensive mode and status information"""
        base_info = {
            'current_mode': self.current_chat_mode.value if hasattr(self.current_chat_mode, 'value') else str(self.current_chat_mode),
            'bandwidth_quality': self.bandwidth_quality.value if hasattr(self.bandwidth_quality, 'value') else str(self.bandwidth_quality),
            'local_storage_available': LOCAL_STORAGE_AVAILABLE,
            'statistics': self.stats.copy()
        }
        
        # Add mode manager info if available
        if self.mode_manager:
            mode_manager_info = self.mode_manager.get_mode_info()
            base_info.update(mode_manager_info)
        
        return base_info
    
    def force_mode_change(self, mode: ChatMode) -> bool:
        """Manually force a mode change"""
        try:
            if self.mode_manager:
                return self.mode_manager.manually_select_mode(mode)
            else:
                # Manual mode change without mode manager
                old_mode = self.current_chat_mode
                self.current_chat_mode = mode
                
                # Emit change
                if self.socketio:
                    self._emit_mode_change(old_mode, mode, {'manual': True})
                
                # Adjust settings
                self._adjust_for_mode(mode)
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to force mode change to {mode}: {e}")
            return False
    
    def get_storage_statistics(self) -> Dict[str, Any]:
        """Get comprehensive storage and usage statistics"""
        stats = self.stats.copy()
        
        if self.storage_manager:
            storage_stats = self.storage_manager.get_storage_stats()
            stats.update(storage_stats)
        
        # Add queue statistics
        stats.update({
            'local_queue_size': len(self.local_queue),
            'sync_queue_size': len(self.sync_queue),
            'priority_queue_size': len(self.priority_queue),
            'total_queued': len(self.local_queue) + len(self.sync_queue) + len(self.priority_queue)
        })
        
        return stats
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old local data to manage storage space"""
        try:
            if self.storage_manager:
                self.storage_manager.cleanup_old_data(days_to_keep)
                logger.info(f"Cleaned up data older than {days_to_keep} days")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
    
    def export_user_data(self, export_path: str = None) -> str:
        """Export all user data for backup"""
        try:
            if self.storage_manager:
                return self.storage_manager.export_user_data(export_path)
            else:
                # Fallback export
                export_data = {
                    'user_id': self.user_id,
                    'messages': {chat_id: [msg.__dict__ for msg in msgs] 
                               for chat_id, msgs in self.messages.items()},
                    'statistics': self.stats,
                    'export_timestamp': datetime.now().isoformat()
                }
                
                if not export_path:
                    export_path = f"chat_export_{self.user_id}_{int(time.time())}.json"
                
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, default=str)
                
                return export_path
                
        except Exception as e:
            logger.error(f"Failed to export user data: {e}")
            raise
    
    def shutdown(self):
        """Gracefully shutdown the enhanced engine"""
        try:
            # Stop mode manager
            if self.mode_manager:
                self.mode_manager.stop_monitoring()
            
            # Save any pending data
            self._process_queues()
            
            # Call parent shutdown if it exists
            if hasattr(super(), 'shutdown'):
                super().shutdown()
            
            logger.info("Enhanced P2P Chat Engine shut down gracefully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def _process_queues(self):
        """Process pending message queues"""
        try:
            # Process priority queue first
            while self.priority_queue:
                message, priority = self.priority_queue.pop(0)
                # Process high-priority messages
                self.stats['sync_attempts'] += 1
            
            # Process regular sync queue if in good connectivity mode
            if self.current_chat_mode in [ChatMode.HIGH_BANDWIDTH_GLOBAL, ChatMode.LAN_HIGH_BANDWIDTH]:
                batch_size = min(10, len(self.sync_queue))
                for _ in range(batch_size):
                    if self.sync_queue:
                        message, priority = self.sync_queue.pop(0)
                        self.stats['sync_attempts'] += 1
        except Exception as e:
            logger.error(f"Error processing message queues: {e}")
    
    def update_bandwidth_info(self, bandwidth_quality, network_type):
        """Update bandwidth information for the enhanced engine"""
        try:
            if hasattr(BandwidthQuality, bandwidth_quality.upper()):
                self.bandwidth_quality = getattr(BandwidthQuality, bandwidth_quality.upper())
            
            # Update mode based on bandwidth (safely check if method exists)
            if self.mode_manager and hasattr(self.mode_manager, 'update_network_conditions'):
                self.mode_manager.update_network_conditions(bandwidth_quality, network_type)
            elif self.mode_manager:
                # Alternative: update bandwidth quality directly
                self.mode_manager.bandwidth_quality = bandwidth_quality
                
            logger.info(f"Updated bandwidth: {bandwidth_quality}, network: {network_type}")
        except Exception as e:
            logger.error(f"Failed to update bandwidth info: {e}")
    
    def handle_user_registration(self, socketio, data, session_id):
        """Handle enhanced user registration with local storage"""
        try:
            user_id = data.get('user_id')
            username = data.get('username')
            display_name = data.get('display_name')
            avatar_url = data.get('avatar_url')
            
            if not all([user_id, username, display_name]):
                socketio.emit('error', {'message': 'Missing required user data'}, room=session_id)
                return False
            
            # Create user data
            user_data = {
                'user_id': user_id,
                'username': username,
                'display_name': display_name,
                'avatar_url': avatar_url,
                'status': 'online',
                'socket_id': session_id,
                'registration_time': datetime.now().isoformat(),
                'chat_mode': self.current_chat_mode.value if hasattr(self.current_chat_mode, 'value') else str(self.current_chat_mode)
            }
            
            # Store user in local storage with LOCAL_FIRST priority
            if self.storage_manager:
                try:
                    # Use proper method name for LocalStorageManager
                    if hasattr(self.storage_manager, 'store_user_data'):
                        self.storage_manager.store_user_data(user_id, user_data)
                    elif hasattr(self.storage_manager, 'store_data'):
                        self.storage_manager.store_data('user_profiles', f"user_{user_id}", user_data)
                    logger.info(f"User {display_name} stored in local storage")
                except Exception as e:
                    logger.warning(f"Could not store user in local storage: {e}")
            
            # Add to parent engine's users if it exists
            if hasattr(self, 'users') and hasattr(self.users, '__setitem__'):
                self.users[session_id] = user_data
            
            # Get user's existing chats (from local storage first)
            user_chats = []
            if self.storage_manager:
                try:
                    chats_data = self.storage_manager.get_data('user_chats', user_id)
                    if chats_data:
                        user_chats = chats_data.get('chats', [])
                except Exception as e:
                    logger.warning(f"Could not load user chats: {e}")
            
            # Emit successful registration
            socketio.emit('user_registered', {
                'user': user_data,
                'chats': user_chats,
                'users': [user_data],  # For now, just return current user
                'mode_info': {
                    'current_mode': self.current_chat_mode.value if hasattr(self.current_chat_mode, 'value') else str(self.current_chat_mode),
                    'bandwidth_quality': self.bandwidth_quality.value if hasattr(self.bandwidth_quality, 'value') else str(self.bandwidth_quality)
                }
            }, room=session_id)
            
            logger.info(f"User registered successfully: {display_name} ({username})")
            return True
            
        except Exception as e:
            logger.error(f"Error in enhanced user registration: {e}")
            socketio.emit('error', {'message': 'Registration failed'}, room=session_id)
            return False
            
            logger.debug(f"Processed queues: {len(self.priority_queue)} priority, {len(self.sync_queue)} sync, {len(self.local_queue)} local")
            
        except Exception as e:
            logger.error(f"Error processing queues: {e}")
            self.stats['sync_failures'] += 1