"""
Advanced P2P Chat System
WhatsApp-like functionality with file transfer and bandwidth optimization
"""

import asyncio
import json
import logging
import os
import uuid
import hashlib
import mimetypes
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import base64
import zipfile
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import time

# WebRTC and networking
try:
    import socketio
    from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False

logger = logging.getLogger(__name__)

class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    FOLDER = "folder"
    VOICE = "voice"
    VIDEO = "video"
    SYSTEM = "system"
    TYPING = "typing"
    READ_RECEIPT = "read_receipt"
    DELIVERY_RECEIPT = "delivery_receipt"

class MessageStatus(Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class ConnectionQuality(Enum):
    LOW = "low"          # < 100 kbps
    MEDIUM = "medium"    # 100 kbps - 1 Mbps
    HIGH = "high"        # > 1 Mbps

class UserStatus(Enum):
    ONLINE = "online"
    AWAY = "away"
    BUSY = "busy"
    OFFLINE = "offline"

@dataclass
class ChatUser:
    """Represents a user in the chat system"""
    user_id: str
    username: str
    display_name: str
    avatar_url: Optional[str] = None
    status: UserStatus = UserStatus.OFFLINE
    last_seen: Optional[datetime] = None
    connection_quality: ConnectionQuality = ConnectionQuality.HIGH
    session_id: Optional[str] = None
    public_key: Optional[str] = None  # For E2E encryption

@dataclass
class ChatMessage:
    """Represents a chat message with rich metadata"""
    id: str
    chat_id: str
    sender_id: str
    content: str
    message_type: MessageType
    timestamp: datetime
    status: MessageStatus = MessageStatus.PENDING
    reply_to: Optional[str] = None
    file_metadata: Optional[Dict[str, Any]] = None
    chunk_info: Optional[Dict[str, Any]] = None  # For large file transfers
    encryption_key: Optional[str] = None
    expires_at: Optional[datetime] = None

@dataclass
class FileMetadata:
    """Metadata for file transfers"""
    filename: str
    file_size: int
    mime_type: str
    checksum: str
    chunks_total: int
    chunk_size: int = 64 * 1024  # 64KB default chunks for low bandwidth
    thumbnail: Optional[str] = None  # Base64 encoded thumbnail for images

class P2PChatEngine:
    """Advanced P2P Chat Engine with WhatsApp-like features"""
    
    def __init__(self, socketio_instance: SocketIO = None):
        self.socketio = socketio_instance
        self.users: Dict[str, ChatUser] = {}
        self.messages: Dict[str, List[ChatMessage]] = {}  # chat_id -> messages
        self.active_chats: Dict[str, Set[str]] = {}  # chat_id -> user_ids
        self.user_chats: Dict[str, Set[str]] = {}  # user_id -> chat_ids
        self.file_transfers: Dict[str, Dict] = {}  # transfer_id -> transfer_info
        self.typing_users: Dict[str, Dict[str, datetime]] = {}  # chat_id -> {user_id: last_typing}
        
        # Storage paths
        self.storage_path = Path("chat_storage")
        self.files_path = self.storage_path / "files"
        self.thumbnails_path = self.storage_path / "thumbnails"
        
        # Create storage directories
        self.storage_path.mkdir(exist_ok=True)
        self.files_path.mkdir(exist_ok=True)
        self.thumbnails_path.mkdir(exist_ok=True)
        
        # Thread pool for file operations
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # Load existing data
        self._load_data()
        
        # Start background tasks
        self._start_background_tasks()
    
    def _load_data(self):
        """Load existing chat data from storage"""
        try:
            data_file = self.storage_path / "chat_data.json"
            if data_file.exists():
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Load users
                for user_data in data.get('users', []):
                    user = ChatUser(**user_data)
                    user.last_seen = datetime.fromisoformat(user_data['last_seen']) if user_data.get('last_seen') else None
                    self.users[user.user_id] = user
                
                # Load messages
                for chat_id, messages_data in data.get('messages', {}).items():
                    self.messages[chat_id] = []
                    for msg_data in messages_data:
                        msg = ChatMessage(**msg_data)
                        msg.timestamp = datetime.fromisoformat(msg_data['timestamp'])
                        if msg_data.get('expires_at'):
                            msg.expires_at = datetime.fromisoformat(msg_data['expires_at'])
                        self.messages[chat_id].append(msg)
                
                # Load chat memberships
                self.active_chats = data.get('active_chats', {})
                self.user_chats = data.get('user_chats', {})
                
        except Exception as e:
            logger.error(f"Error loading chat data: {e}")
    
    def _save_data(self):
        """Save chat data to storage"""
        try:
            data = {
                'users': [asdict(user) for user in self.users.values()],
                'messages': {
                    chat_id: [asdict(msg) for msg in messages]
                    for chat_id, messages in self.messages.items()
                },
                'active_chats': {k: list(v) for k, v in self.active_chats.items()},
                'user_chats': {k: list(v) for k, v in self.user_chats.items()}
            }
            
            # Convert datetime objects to ISO format
            for user_data in data['users']:
                if user_data.get('last_seen'):
                    user_data['last_seen'] = user_data['last_seen'].isoformat() if isinstance(user_data['last_seen'], datetime) else user_data['last_seen']
            
            for chat_messages in data['messages'].values():
                for msg_data in chat_messages:
                    msg_data['timestamp'] = msg_data['timestamp'].isoformat() if isinstance(msg_data['timestamp'], datetime) else msg_data['timestamp']
                    if msg_data.get('expires_at'):
                        msg_data['expires_at'] = msg_data['expires_at'].isoformat() if isinstance(msg_data['expires_at'], datetime) else msg_data['expires_at']
            
            data_file = self.storage_path / "chat_data.json"
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Error saving chat data: {e}")
    
    def _start_background_tasks(self):
        """Start background maintenance tasks"""
        def cleanup_expired_messages():
            """Clean up expired messages and typing indicators"""
            while True:
                try:
                    now = datetime.utcnow()
                    
                    # Clean expired messages
                    for chat_id in list(self.messages.keys()):
                        self.messages[chat_id] = [
                            msg for msg in self.messages[chat_id]
                            if not msg.expires_at or msg.expires_at > now
                        ]
                    
                    # Clean old typing indicators
                    for chat_id in list(self.typing_users.keys()):
                        self.typing_users[chat_id] = {
                            user_id: last_typing
                            for user_id, last_typing in self.typing_users[chat_id].items()
                            if now - last_typing < timedelta(seconds=10)
                        }
                        if not self.typing_users[chat_id]:
                            del self.typing_users[chat_id]
                    
                    # Save data periodically
                    self._save_data()
                    
                except Exception as e:
                    logger.error(f"Background cleanup error: {e}")
                
                time.sleep(60)  # Run every minute
        
        # Start cleanup thread
        cleanup_thread = threading.Thread(target=cleanup_expired_messages, daemon=True)
        cleanup_thread.start()
    
    # User Management
    def register_user(self, user_id: str, username: str, display_name: str, 
                     avatar_url: str = None, session_id: str = None) -> ChatUser:
        """Register a new user or update existing user"""
        user = ChatUser(
            user_id=user_id,
            username=username,
            display_name=display_name,
            avatar_url=avatar_url,
            status=UserStatus.ONLINE,
            last_seen=datetime.utcnow(),
            session_id=session_id
        )
        
        self.users[user_id] = user
        
        if user_id not in self.user_chats:
            self.user_chats[user_id] = set()
        
        self._save_data()
        
        # Notify other users about online status
        self._broadcast_user_status_update(user)
        
        return user
    
    def update_user_status(self, user_id: str, status: UserStatus, 
                          connection_quality: ConnectionQuality = None):
        """Update user status and connection quality"""
        if user_id in self.users:
            self.users[user_id].status = status
            self.users[user_id].last_seen = datetime.utcnow()
            
            if connection_quality:
                self.users[user_id].connection_quality = connection_quality
            
            self._broadcast_user_status_update(self.users[user_id])
    
    def get_user(self, user_id: str) -> Optional[ChatUser]:
        """Get user by ID"""
        return self.users.get(user_id)
    
    def search_users(self, query: str, exclude_user_id: str = None) -> List[ChatUser]:
        """Search users by username or display name"""
        query_lower = query.lower()
        results = []
        
        for user in self.users.values():
            if exclude_user_id and user.user_id == exclude_user_id:
                continue
                
            if (query_lower in user.username.lower() or 
                query_lower in user.display_name.lower()):
                results.append(user)
        
        return results[:10]  # Limit results
    
    # Chat Management
    def create_chat(self, creator_id: str, participants: List[str], 
                   chat_name: str = None) -> str:
        """Create a new chat room"""
        chat_id = str(uuid.uuid4())
        
        # Add creator to participants
        all_participants = set([creator_id] + participants)
        
        self.active_chats[chat_id] = all_participants
        
        # Update user chat mappings
        for user_id in all_participants:
            if user_id not in self.user_chats:
                self.user_chats[user_id] = set()
            self.user_chats[user_id].add(chat_id)
        
        # Create initial system message
        system_message = ChatMessage(
            id=str(uuid.uuid4()),
            chat_id=chat_id,
            sender_id="system",
            content=f"Chat created by {self.users.get(creator_id, {}).username or creator_id}",
            message_type=MessageType.SYSTEM,
            timestamp=datetime.utcnow(),
            status=MessageStatus.DELIVERED
        )
        
        self.messages[chat_id] = [system_message]
        self._save_data()
        
        # Join SocketIO rooms
        if self.socketio:
            for user_id in all_participants:
                user = self.users.get(user_id)
                if user and user.session_id:
                    self.socketio.server.enter_room(user.session_id, chat_id)
        
        return chat_id
    
    def invite_user_to_chat(self, chat_id: str, inviter_id: str, user_id: str) -> bool:
        """Invite a user to an existing chat"""
        if chat_id not in self.active_chats:
            return False
        
        if inviter_id not in self.active_chats[chat_id]:
            return False
        
        if user_id in self.active_chats[chat_id]:
            return True  # Already in chat
        
        # Add user to chat
        self.active_chats[chat_id].add(user_id)
        
        if user_id not in self.user_chats:
            self.user_chats[user_id] = set()
        self.user_chats[user_id].add(chat_id)
        
        # Send system message
        inviter_name = self.users.get(inviter_id, {}).display_name or inviter_id
        user_name = self.users.get(user_id, {}).display_name or user_id
        
        system_message = ChatMessage(
            id=str(uuid.uuid4()),
            chat_id=chat_id,
            sender_id="system",
            content=f"{inviter_name} added {user_name} to the chat",
            message_type=MessageType.SYSTEM,
            timestamp=datetime.utcnow(),
            status=MessageStatus.DELIVERED
        )
        
        self.messages[chat_id].append(system_message)
        self._save_data()
        
        # Join SocketIO room
        if self.socketio:
            user = self.users.get(user_id)
            if user and user.session_id:
                self.socketio.server.enter_room(user.session_id, chat_id)
        
        # Notify chat participants
        self._broadcast_to_chat(chat_id, 'user_joined', {
            'chat_id': chat_id,
            'user': asdict(self.users[user_id]) if user_id in self.users else None,
            'message': asdict(system_message)
        })
        
        return True
    
    def get_user_chats(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all chats for a user with metadata"""
        user_chat_ids = self.user_chats.get(user_id, set())
        chats = []
        
        for chat_id in user_chat_ids:
            if chat_id not in self.active_chats:
                continue
            
            participants = self.active_chats[chat_id]
            chat_messages = self.messages.get(chat_id, [])
            last_message = chat_messages[-1] if chat_messages else None
            
            # Count unread messages
            unread_count = 0
            if last_message:
                user_last_read = getattr(self.users.get(user_id), 'last_read_times', {}).get(chat_id)
                if user_last_read:
                    for msg in reversed(chat_messages):
                        if msg.timestamp <= user_last_read:
                            break
                        if msg.sender_id != user_id:
                            unread_count += 1
            
            chat_info = {
                'chat_id': chat_id,
                'participants': [asdict(self.users[uid]) for uid in participants if uid in self.users],
                'last_message': asdict(last_message) if last_message else None,
                'unread_count': unread_count,
                'message_count': len(chat_messages)
            }
            
            chats.append(chat_info)
        
        # Sort by last message timestamp
        chats.sort(key=lambda x: x['last_message']['timestamp'] if x['last_message'] else '', reverse=True)
        return chats
    
    # Message Handling
    def send_message(self, sender_id: str, chat_id: str, content: str, 
                    message_type: MessageType = MessageType.TEXT,
                    reply_to: str = None, file_metadata: Dict = None) -> ChatMessage:
        """Send a message to a chat"""
        
        if chat_id not in self.active_chats or sender_id not in self.active_chats[chat_id]:
            raise ValueError("User not authorized for this chat")
        
        message = ChatMessage(
            id=str(uuid.uuid4()),
            chat_id=chat_id,
            sender_id=sender_id,
            content=content,
            message_type=message_type,
            timestamp=datetime.utcnow(),
            status=MessageStatus.SENT,
            reply_to=reply_to,
            file_metadata=file_metadata
        )
        
        self.messages[chat_id].append(message)
        self._save_data()
        
        # Broadcast to chat participants
        self._broadcast_to_chat(chat_id, 'new_message', asdict(message), exclude_sender=True)
        
        # Send delivery receipts
        self._send_delivery_receipt(message)
        
        return message
    
    def _broadcast_to_chat(self, chat_id: str, event: str, data: Any, exclude_sender: bool = False):
        """Broadcast an event to all chat participants"""
        if not self.socketio:
            return
        
        participants = self.active_chats.get(chat_id, set())
        exclude_id = data.get('sender_id') if exclude_sender and isinstance(data, dict) else None
        
        for user_id in participants:
            if exclude_id and user_id == exclude_id:
                continue
                
            user = self.users.get(user_id)
            if user and user.session_id:
                self.socketio.emit(event, data, room=user.session_id)
    
    def _broadcast_user_status_update(self, user: ChatUser):
        """Broadcast user status update to relevant chats"""
        if not self.socketio:
            return
        
        user_data = asdict(user)
        user_chat_ids = self.user_chats.get(user.user_id, set())
        
        for chat_id in user_chat_ids:
            self._broadcast_to_chat(chat_id, 'user_status_update', {
                'user': user_data,
                'chat_id': chat_id
            })
    
    def _send_delivery_receipt(self, message: ChatMessage):
        """Send delivery receipt for a message"""
        receipt = ChatMessage(
            id=str(uuid.uuid4()),
            chat_id=message.chat_id,
            sender_id="system",
            content=message.id,  # Reference to original message
            message_type=MessageType.DELIVERY_RECEIPT,
            timestamp=datetime.utcnow(),
            status=MessageStatus.DELIVERED
        )
        
        # Don't store receipt messages, just broadcast them
        self._broadcast_to_chat(message.chat_id, 'delivery_receipt', asdict(receipt))
    
    # File Transfer Methods
    def start_file_transfer(self, sender_id: str, chat_id: str, file_path: str, 
                           chunk_size: int = None) -> str:
        """Start a file transfer with chunking for large files"""
        
        if not os.path.exists(file_path):
            raise FileNotFoundError("File not found")
        
        file_info = os.stat(file_path)
        filename = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        
        # Calculate optimal chunk size based on connection quality
        user = self.users.get(sender_id)
        if not chunk_size:
            if user and user.connection_quality == ConnectionQuality.LOW:
                chunk_size = 32 * 1024  # 32KB for low bandwidth
            elif user and user.connection_quality == ConnectionQuality.MEDIUM:
                chunk_size = 128 * 1024  # 128KB for medium bandwidth
            else:
                chunk_size = 512 * 1024  # 512KB for high bandwidth
        
        # Calculate file checksum
        checksum = self._calculate_file_checksum(file_path)
        
        # Create file metadata
        chunks_total = (file_info.st_size + chunk_size - 1) // chunk_size
        
        file_metadata = FileMetadata(
            filename=filename,
            file_size=file_info.st_size,
            mime_type=mime_type or "application/octet-stream",
            checksum=checksum,
            chunks_total=chunks_total,
            chunk_size=chunk_size
        )
        
        # Generate thumbnail for images
        if mime_type and mime_type.startswith('image/'):
            file_metadata.thumbnail = self._generate_thumbnail(file_path)
        
        transfer_id = str(uuid.uuid4())
        
        # Store transfer info
        self.file_transfers[transfer_id] = {
            'transfer_id': transfer_id,
            'sender_id': sender_id,
            'chat_id': chat_id,
            'file_path': file_path,
            'metadata': asdict(file_metadata),
            'chunks_sent': 0,
            'chunks_confirmed': 0,
            'started_at': datetime.utcnow(),
            'status': 'uploading'
        }
        
        # Send file transfer initiation message
        message = self.send_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=f"📎 {filename}",
            message_type=MessageType.FILE,
            file_metadata={
                'transfer_id': transfer_id,
                **asdict(file_metadata)
            }
        )
        
        # Start sending chunks in background
        self.executor.submit(self._send_file_chunks, transfer_id)
        
        return transfer_id
    
    def start_folder_transfer(self, sender_id: str, chat_id: str, folder_path: str) -> str:
        """Transfer a folder by creating a zip archive"""
        
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            raise NotADirectoryError("Folder not found")
        
        # Create temporary zip file
        temp_dir = tempfile.gettempdir()
        zip_filename = f"{os.path.basename(folder_path)}_{int(time.time())}.zip"
        zip_path = os.path.join(temp_dir, zip_filename)
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        archive_name = os.path.relpath(file_path, folder_path)
                        zipf.write(file_path, archive_name)
            
            # Start file transfer for the zip
            transfer_id = self.start_file_transfer(sender_id, chat_id, zip_path)
            
            # Update metadata to indicate it's a folder
            if transfer_id in self.file_transfers:
                self.file_transfers[transfer_id]['is_folder'] = True
                self.file_transfers[transfer_id]['original_folder'] = folder_path
            
            return transfer_id
            
        except Exception as e:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            raise e
    
    def _send_file_chunks(self, transfer_id: str):
        """Send file chunks with progress tracking"""
        transfer_info = self.file_transfers.get(transfer_id)
        if not transfer_info:
            return
        
        file_path = transfer_info['file_path']
        metadata = transfer_info['metadata']
        chat_id = transfer_info['chat_id']
        
        try:
            with open(file_path, 'rb') as f:
                chunk_num = 0
                while chunk_num < metadata['chunks_total']:
                    # Read chunk
                    chunk_data = f.read(metadata['chunk_size'])
                    if not chunk_data:
                        break
                    
                    # Encode chunk
                    chunk_b64 = base64.b64encode(chunk_data).decode('utf-8')
                    
                    # Send chunk
                    chunk_message = {
                        'transfer_id': transfer_id,
                        'chunk_num': chunk_num,
                        'chunk_data': chunk_b64,
                        'total_chunks': metadata['chunks_total'],
                        'is_last_chunk': chunk_num == metadata['chunks_total'] - 1
                    }
                    
                    self._broadcast_to_chat(chat_id, 'file_chunk', chunk_message)
                    
                    # Update progress
                    transfer_info['chunks_sent'] = chunk_num + 1
                    
                    # Send progress update
                    progress = (chunk_num + 1) / metadata['chunks_total'] * 100
                    self._broadcast_to_chat(chat_id, 'transfer_progress', {
                        'transfer_id': transfer_id,
                        'progress': progress,
                        'chunks_sent': chunk_num + 1,
                        'total_chunks': metadata['chunks_total']
                    })
                    
                    chunk_num += 1
                    
                    # Small delay for bandwidth management
                    user = self.users.get(transfer_info['sender_id'])
                    if user and user.connection_quality == ConnectionQuality.LOW:
                        time.sleep(0.1)  # 100ms delay for low bandwidth
            
            # Mark transfer as completed
            transfer_info['status'] = 'completed'
            transfer_info['completed_at'] = datetime.utcnow()
            
            # Clean up temporary files for folder transfers
            if transfer_info.get('is_folder') and os.path.exists(file_path):
                os.remove(file_path)
            
        except Exception as e:
            logger.error(f"File transfer error: {e}")
            transfer_info['status'] = 'failed'
            transfer_info['error'] = str(e)
            
            # Notify participants of failure
            self._broadcast_to_chat(chat_id, 'transfer_failed', {
                'transfer_id': transfer_id,
                'error': str(e)
            })
    
    def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate MD5 checksum for file integrity"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Checksum calculation error: {e}")
            return ""
    
    def _generate_thumbnail(self, image_path: str) -> Optional[str]:
        """Generate base64 encoded thumbnail for images"""
        try:
            from PIL import Image
            import io
            
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Create thumbnail
                img.thumbnail((150, 150), Image.Resampling.LANCZOS)
                
                # Convert to base64
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=70)
                thumbnail_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                return f"data:image/jpeg;base64,{thumbnail_b64}"
                
        except Exception as e:
            logger.error(f"Thumbnail generation error: {e}")
            return None
    
    # Typing Indicators
    def set_typing_status(self, user_id: str, chat_id: str, is_typing: bool):
        """Set typing status for a user in a chat"""
        if chat_id not in self.typing_users:
            self.typing_users[chat_id] = {}
        
        if is_typing:
            self.typing_users[chat_id][user_id] = datetime.utcnow()
        else:
            self.typing_users[chat_id].pop(user_id, None)
        
        # Broadcast typing status
        typing_users = list(self.typing_users[chat_id].keys())
        self._broadcast_to_chat(chat_id, 'typing_update', {
            'chat_id': chat_id,
            'typing_users': typing_users
        })
    
    # Read Receipts
    def mark_messages_as_read(self, user_id: str, chat_id: str, message_ids: List[str]):
        """Mark messages as read by a user"""
        if chat_id not in self.messages:
            return
        
        # Update message status
        for message in self.messages[chat_id]:
            if message.id in message_ids and message.sender_id != user_id:
                if message.status != MessageStatus.READ:
                    message.status = MessageStatus.READ
        
        # Send read receipts
        for message_id in message_ids:
            receipt = {
                'message_id': message_id,
                'reader_id': user_id,
                'chat_id': chat_id,
                'read_at': datetime.utcnow().isoformat()
            }
            
            self._broadcast_to_chat(chat_id, 'read_receipt', receipt)
        
        self._save_data()
    
    # Bandwidth Optimization
    def optimize_message_for_bandwidth(self, message: ChatMessage, 
                                     connection_quality: ConnectionQuality) -> Dict[str, Any]:
        """Optimize message payload based on connection quality"""
        message_data = asdict(message)
        
        if connection_quality == ConnectionQuality.LOW:
            # Remove unnecessary fields for low bandwidth
            message_data.pop('encryption_key', None)
            if message_data.get('file_metadata'):
                # Remove thumbnail for low bandwidth
                message_data['file_metadata'].pop('thumbnail', None)
        
        elif connection_quality == ConnectionQuality.MEDIUM:
            # Compress thumbnails
            if message_data.get('file_metadata', {}).get('thumbnail'):
                # Keep smaller thumbnails
                pass
        
        return message_data
    
    # Utility Methods
    def get_chat_messages(self, chat_id: str, limit: int = 50, 
                         before_message_id: str = None) -> List[Dict[str, Any]]:
        """Get messages from a chat with pagination"""
        if chat_id not in self.messages:
            return []
        
        messages = self.messages[chat_id]
        
        # Find starting point if before_message_id is specified
        start_index = 0
        if before_message_id:
            for i, msg in enumerate(messages):
                if msg.id == before_message_id:
                    start_index = max(0, i - limit)
                    break
        else:
            start_index = max(0, len(messages) - limit)
        
        # Get messages slice
        result_messages = messages[start_index:start_index + limit]
        
        return [asdict(msg) for msg in result_messages]
    
    def get_transfer_status(self, transfer_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a file transfer"""
        return self.file_transfers.get(transfer_id)
    
    def cancel_transfer(self, transfer_id: str, user_id: str) -> bool:
        """Cancel a file transfer"""
        transfer_info = self.file_transfers.get(transfer_id)
        if not transfer_info:
            return False
        
        # Only sender can cancel
        if transfer_info['sender_id'] != user_id:
            return False
        
        transfer_info['status'] = 'cancelled'
        transfer_info['cancelled_at'] = datetime.utcnow()
        
        # Notify participants
        self._broadcast_to_chat(transfer_info['chat_id'], 'transfer_cancelled', {
            'transfer_id': transfer_id
        })
        
        return True
    
    def cleanup_old_transfers(self, days_old: int = 7):
        """Clean up old completed/failed transfers"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        to_remove = []
        for transfer_id, transfer_info in self.file_transfers.items():
            completed_at = transfer_info.get('completed_at')
            if completed_at and datetime.fromisoformat(completed_at) < cutoff_date:
                to_remove.append(transfer_id)
        
        for transfer_id in to_remove:
            del self.file_transfers[transfer_id]