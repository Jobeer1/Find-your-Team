"""
Multi-Protocol Communication Client for Find Your Team
Supports MQTT, WebRTC, and offline queuing for resilient communication
"""

import json
import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from enum import Enum
import uuid
import sqlite3
from pathlib import Path

try:
    import websockets
    import paho.mqtt.client as mqtt
    from aiortc import RTCPeerConnection, RTCDataChannel, RTCConfiguration, RTCIceServer
    from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling
except ImportError as e:
    logging.warning(f"Some communication dependencies not available: {e}")

logger = logging.getLogger(__name__)

class ConnectionStatus(Enum):
    """Connection status enumeration"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"

class MessagePriority(Enum):
    """Message priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

class ProtocolType(Enum):
    """Supported communication protocols"""
    MQTT = "mqtt"
    WEBRTC = "webrtc"
    WEBSOCKET = "websocket"
    OFFLINE_QUEUE = "offline_queue"

class Message:
    """Universal message format for all protocols"""
    
    def __init__(self, content: str, sender_id: str, recipient_id: str = None, 
                 message_type: str = "chat", priority: MessagePriority = MessagePriority.NORMAL):
        self.id = str(uuid.uuid4())
        self.content = content
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.message_type = message_type
        self.priority = priority
        self.timestamp = datetime.now().isoformat()
        self.protocol_used = None
        self.retry_count = 0
        self.max_retries = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for transmission"""
        return {
            'id': self.id,
            'content': self.content,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'message_type': self.message_type,
            'priority': self.priority.value,
            'timestamp': self.timestamp,
            'protocol_used': self.protocol_used,
            'retry_count': self.retry_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary"""
        msg = cls(
            content=data['content'],
            sender_id=data['sender_id'],
            recipient_id=data.get('recipient_id'),
            message_type=data.get('message_type', 'chat'),
            priority=MessagePriority(data.get('priority', MessagePriority.NORMAL.value))
        )
        msg.id = data['id']
        msg.timestamp = data['timestamp']
        msg.protocol_used = data.get('protocol_used')
        msg.retry_count = data.get('retry_count', 0)
        return msg

class OfflineQueue:
    """SQLite-based offline message queue"""
    
    def __init__(self, db_path: str = "data/offline_messages.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    recipient_id TEXT,
                    message_type TEXT DEFAULT 'chat',
                    priority INTEGER DEFAULT 2,
                    timestamp TEXT NOT NULL,
                    retry_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_priority_timestamp 
                ON messages(priority DESC, timestamp ASC)
            """)
    
    def enqueue(self, message: Message):
        """Add message to offline queue"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO messages 
                (id, content, sender_id, recipient_id, message_type, priority, timestamp, retry_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.id, message.content, message.sender_id, message.recipient_id,
                message.message_type, message.priority.value, message.timestamp, message.retry_count
            ))
        logger.info(f"Message {message.id} queued for offline delivery")
    
    def dequeue_batch(self, limit: int = 10) -> List[Message]:
        """Get batch of messages for sending"""
        messages = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, content, sender_id, recipient_id, message_type, priority, timestamp, retry_count
                FROM messages 
                ORDER BY priority DESC, timestamp ASC 
                LIMIT ?
            """, (limit,))
            
            for row in cursor.fetchall():
                msg = Message(
                    content=row[1],
                    sender_id=row[2],
                    recipient_id=row[3],
                    message_type=row[4],
                    priority=MessagePriority(row[5])
                )
                msg.id = row[0]
                msg.timestamp = row[6]
                msg.retry_count = row[7]
                messages.append(msg)
        
        return messages
    
    def remove(self, message_id: str):
        """Remove message from queue after successful delivery"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        logger.info(f"Message {message_id} removed from offline queue")
    
    def update_retry_count(self, message_id: str, retry_count: int):
        """Update retry count for failed message"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE messages SET retry_count = ? WHERE id = ?", 
                (retry_count, message_id)
            )
    
    def get_queue_size(self) -> int:
        """Get number of queued messages"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM messages")
            return cursor.fetchone()[0]

class MQTTClient:
    """MQTT client for IoT Core communication"""
    
    def __init__(self, broker_host: str, broker_port: int = 8883, 
                 client_id: str = None, use_ssl: bool = True):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id or f"fyt_client_{uuid.uuid4().hex[:8]}"
        self.use_ssl = use_ssl
        self.status = ConnectionStatus.DISCONNECTED
        
        self.client = mqtt.Client(self.client_id)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        
        self.message_handlers: List[Callable] = []
        self.connection_handlers: List[Callable] = []
        
        if use_ssl:
            self.client.tls_set()
    
    def add_message_handler(self, handler: Callable[[Message], None]):
        """Add message handler callback"""
        self.message_handlers.append(handler)
    
    def add_connection_handler(self, handler: Callable[[ConnectionStatus], None]):
        """Add connection status handler"""
        self.connection_handlers.append(handler)
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.status = ConnectionStatus.CONNECTED
            logger.info(f"MQTT connected to {self.broker_host}")
            # Subscribe to user's personal topic
            client.subscribe(f"fyt/user/{self.client_id}/messages")
            client.subscribe("fyt/broadcast/messages")
        else:
            self.status = ConnectionStatus.FAILED
            logger.error(f"MQTT connection failed with code {rc}")
        
        for handler in self.connection_handlers:
            handler(self.status)
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        self.status = ConnectionStatus.DISCONNECTED
        logger.info("MQTT disconnected")
        
        for handler in self.connection_handlers:
            handler(self.status)
    
    def _on_message(self, client, userdata, msg):
        """MQTT message received callback"""
        try:
            data = json.loads(msg.payload.decode())
            message = Message.from_dict(data)
            message.protocol_used = ProtocolType.MQTT.value
            
            for handler in self.message_handlers:
                handler(message)
                
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        logger.debug(f"MQTT message {mid} published")
    
    async def connect(self):
        """Connect to MQTT broker"""
        try:
            self.status = ConnectionStatus.CONNECTING
            self.client.connect_async(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            
            # Wait for connection
            for _ in range(50):  # 5 second timeout
                if self.status in [ConnectionStatus.CONNECTED, ConnectionStatus.FAILED]:
                    break
                await asyncio.sleep(0.1)
                
        except Exception as e:
            self.status = ConnectionStatus.FAILED
            logger.error(f"MQTT connection error: {e}")
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
    
    def send_message(self, message: Message) -> bool:
        """Send message via MQTT"""
        try:
            if self.status != ConnectionStatus.CONNECTED:
                return False
            
            topic = f"fyt/user/{message.recipient_id}/messages" if message.recipient_id else "fyt/broadcast/messages"
            payload = json.dumps(message.to_dict())
            
            result = self.client.publish(topic, payload, qos=1)
            message.protocol_used = ProtocolType.MQTT.value
            
            return result.rc == mqtt.MQTT_ERR_SUCCESS
            
        except Exception as e:
            logger.error(f"MQTT send error: {e}")
            return False

class WebRTCClient:
    """WebRTC client for peer-to-peer communication"""
    
    def __init__(self, ice_servers: List[str] = None):
        self.ice_servers = ice_servers or [
            "stun:stun.l.google.com:19302",
            "stun:stun1.l.google.com:19302"
        ]
        
        self.pc = None
        self.data_channel = None
        self.status = ConnectionStatus.DISCONNECTED
        self.message_handlers: List[Callable] = []
        self.connection_handlers: List[Callable] = []
    
    def add_message_handler(self, handler: Callable[[Message], None]):
        """Add message handler callback"""
        self.message_handlers.append(handler)
    
    def add_connection_handler(self, handler: Callable[[ConnectionStatus], None]):
        """Add connection status handler"""
        self.connection_handlers.append(handler)
    
    async def create_peer_connection(self):
        """Create WebRTC peer connection"""
        config = RTCConfiguration(
            iceServers=[RTCIceServer(urls=server) for server in self.ice_servers]
        )
        
        self.pc = RTCPeerConnection(configuration=config)
        
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            state = self.pc.connectionState
            if state == "connected":
                self.status = ConnectionStatus.CONNECTED
            elif state == "disconnected":
                self.status = ConnectionStatus.DISCONNECTED
            elif state == "failed":
                self.status = ConnectionStatus.FAILED
            
            for handler in self.connection_handlers:
                handler(self.status)
        
        # Create data channel for messaging
        self.data_channel = self.pc.createDataChannel("messages")
        
        @self.data_channel.on("open")
        def on_open():
            logger.info("WebRTC data channel opened")
        
        @self.data_channel.on("message")
        def on_message(message):
            try:
                data = json.loads(message)
                msg = Message.from_dict(data)
                msg.protocol_used = ProtocolType.WEBRTC.value
                
                for handler in self.message_handlers:
                    handler(msg)
                    
            except Exception as e:
                logger.error(f"WebRTC message error: {e}")
    
    async def create_offer(self) -> Dict[str, Any]:
        """Create WebRTC offer"""
        if not self.pc:
            await self.create_peer_connection()
        
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        
        return {
            "type": offer.type,
            "sdp": offer.sdp
        }
    
    async def handle_answer(self, answer: Dict[str, Any]):
        """Handle WebRTC answer"""
        from aiortc import RTCSessionDescription
        
        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
        )
    
    async def handle_offer(self, offer: Dict[str, Any]) -> Dict[str, Any]:
        """Handle WebRTC offer and create answer"""
        from aiortc import RTCSessionDescription
        
        if not self.pc:
            await self.create_peer_connection()
        
        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=offer["sdp"], type=offer["type"])
        )
        
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        
        return {
            "type": answer.type,
            "sdp": answer.sdp
        }
    
    def send_message(self, message: Message) -> bool:
        """Send message via WebRTC"""
        try:
            if not self.data_channel or self.data_channel.readyState != "open":
                return False
            
            message.protocol_used = ProtocolType.WEBRTC.value
            payload = json.dumps(message.to_dict())
            self.data_channel.send(payload)
            
            return True
            
        except Exception as e:
            logger.error(f"WebRTC send error: {e}")
            return False
    
    async def close(self):
        """Close WebRTC connection"""
        if self.pc:
            await self.pc.close()
        self.status = ConnectionStatus.DISCONNECTED

class MultiProtocolClient:
    """Main client that manages all communication protocols"""
    
    def __init__(self, user_id: str, config: Dict[str, Any] = None):
        self.user_id = user_id
        self.config = config or {}
        
        # Initialize protocol clients
        self.mqtt_client = None
        self.webrtc_client = None
        self.offline_queue = OfflineQueue()
        
        # Connection status tracking
        self.protocol_status = {
            ProtocolType.MQTT: ConnectionStatus.DISCONNECTED,
            ProtocolType.WEBRTC: ConnectionStatus.DISCONNECTED,
            ProtocolType.OFFLINE_QUEUE: ConnectionStatus.CONNECTED  # Always available
        }
        
        # Message handlers
        self.message_handlers: List[Callable] = []
        self.status_handlers: List[Callable] = []
        
        # Auto-retry settings
        self.retry_interval = 30  # seconds
        self.max_retry_attempts = 3
        
        # Start background tasks
        self._retry_task = None
        self._start_background_tasks()
    
    def add_message_handler(self, handler: Callable[[Message], None]):
        """Add global message handler"""
        self.message_handlers.append(handler)
    
    def add_status_handler(self, handler: Callable[[Dict[ProtocolType, ConnectionStatus]], None]):
        """Add connection status handler"""
        self.status_handlers.append(handler)
    
    async def initialize_mqtt(self, broker_host: str, broker_port: int = 8883):
        """Initialize MQTT client"""
        try:
            self.mqtt_client = MQTTClient(
                broker_host=broker_host,
                broker_port=broker_port,
                client_id=f"fyt_{self.user_id}"
            )
            
            self.mqtt_client.add_message_handler(self._handle_message)
            self.mqtt_client.add_connection_handler(
                lambda status: self._update_protocol_status(ProtocolType.MQTT, status)
            )
            
            await self.mqtt_client.connect()
            
        except Exception as e:
            logger.error(f"MQTT initialization error: {e}")
            self._update_protocol_status(ProtocolType.MQTT, ConnectionStatus.FAILED)
    
    async def initialize_webrtc(self, ice_servers: List[str] = None):
        """Initialize WebRTC client"""
        try:
            self.webrtc_client = WebRTCClient(ice_servers)
            
            self.webrtc_client.add_message_handler(self._handle_message)
            self.webrtc_client.add_connection_handler(
                lambda status: self._update_protocol_status(ProtocolType.WEBRTC, status)
            )
            
            await self.webrtc_client.create_peer_connection()
            
        except Exception as e:
            logger.error(f"WebRTC initialization error: {e}")
            self._update_protocol_status(ProtocolType.WEBRTC, ConnectionStatus.FAILED)
    
    def _handle_message(self, message: Message):
        """Handle incoming message from any protocol"""
        logger.info(f"Received message {message.id} via {message.protocol_used}")
        
        for handler in self.message_handlers:
            try:
                handler(message)
            except Exception as e:
                logger.error(f"Message handler error: {e}")
    
    def _update_protocol_status(self, protocol: ProtocolType, status: ConnectionStatus):
        """Update protocol connection status"""
        self.protocol_status[protocol] = status
        logger.info(f"{protocol.value} status: {status.value}")
        
        for handler in self.status_handlers:
            try:
                handler(self.protocol_status.copy())
            except Exception as e:
                logger.error(f"Status handler error: {e}")
    
    def _start_background_tasks(self):
        """Start background tasks for retry and queue processing"""
        async def retry_loop():
            while True:
                try:
                    await self._process_offline_queue()
                    await asyncio.sleep(self.retry_interval)
                except Exception as e:
                    logger.error(f"Retry loop error: {e}")
                    await asyncio.sleep(5)
        
        # Start retry task if not already running
        if not self._retry_task or self._retry_task.done():
            self._retry_task = asyncio.create_task(retry_loop())
    
    async def _process_offline_queue(self):
        """Process queued messages when connection is available"""
        if self.offline_queue.get_queue_size() == 0:
            return
        
        # Get available protocols
        available_protocols = [
            protocol for protocol, status in self.protocol_status.items()
            if status == ConnectionStatus.CONNECTED and protocol != ProtocolType.OFFLINE_QUEUE
        ]
        
        if not available_protocols:
            logger.debug("No protocols available for queue processing")
            return
        
        # Process batch of messages
        messages = self.offline_queue.dequeue_batch(limit=10)
        
        for message in messages:
            success = False
            
            # Try each available protocol
            for protocol in available_protocols:
                if await self._send_via_protocol(message, protocol):
                    success = True
                    self.offline_queue.remove(message.id)
                    logger.info(f"Queued message {message.id} sent via {protocol.value}")
                    break
            
            if not success:
                # Update retry count
                message.retry_count += 1
                if message.retry_count >= message.max_retries:
                    self.offline_queue.remove(message.id)
                    logger.warning(f"Message {message.id} exceeded max retries, discarded")
                else:
                    self.offline_queue.update_retry_count(message.id, message.retry_count)
                    logger.warning(f"Message {message.id} retry {message.retry_count}")
    
    async def _send_via_protocol(self, message: Message, protocol: ProtocolType) -> bool:
        """Send message via specific protocol"""
        try:
            if protocol == ProtocolType.MQTT and self.mqtt_client:
                return self.mqtt_client.send_message(message)
            elif protocol == ProtocolType.WEBRTC and self.webrtc_client:
                return self.webrtc_client.send_message(message)
            else:
                return False
                
        except Exception as e:
            logger.error(f"Send via {protocol.value} error: {e}")
            return False
    
    async def send_message(self, content: str, recipient_id: str = None, 
                          message_type: str = "chat", priority: MessagePriority = MessagePriority.NORMAL) -> bool:
        """Send message using best available protocol"""
        message = Message(
            content=content,
            sender_id=self.user_id,
            recipient_id=recipient_id,
            message_type=message_type,
            priority=priority
        )
        
        # Try protocols in order of preference
        protocol_order = [ProtocolType.WEBRTC, ProtocolType.MQTT]
        
        for protocol in protocol_order:
            if self.protocol_status[protocol] == ConnectionStatus.CONNECTED:
                if await self._send_via_protocol(message, protocol):
                    logger.info(f"Message {message.id} sent via {protocol.value}")
                    return True
        
        # If no protocol available, queue for later
        self.offline_queue.enqueue(message)
        logger.info(f"Message {message.id} queued for offline delivery")
        return True  # Queued successfully
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status"""
        return {
            "protocols": {protocol.value: status.value for protocol, status in self.protocol_status.items()},
            "queue_size": self.offline_queue.get_queue_size(),
            "best_protocol": self._get_best_protocol()
        }
    
    def _get_best_protocol(self) -> Optional[str]:
        """Get the best available protocol"""
        if self.protocol_status[ProtocolType.WEBRTC] == ConnectionStatus.CONNECTED:
            return ProtocolType.WEBRTC.value
        elif self.protocol_status[ProtocolType.MQTT] == ConnectionStatus.CONNECTED:
            return ProtocolType.MQTT.value
        else:
            return ProtocolType.OFFLINE_QUEUE.value
    
    async def close(self):
        """Close all connections"""
        if self._retry_task:
            self._retry_task.cancel()
        
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        
        if self.webrtc_client:
            await self.webrtc_client.close()
        
        logger.info("Multi-protocol client closed")

# Example usage and testing
async def main():
    """Example usage of MultiProtocolClient"""
    client = MultiProtocolClient(user_id="demo_user")
    
    # Add message handler
    def handle_message(message: Message):
        print(f"Received: {message.content} from {message.sender_id}")
    
    client.add_message_handler(handle_message)
    
    # Initialize protocols
    await client.initialize_mqtt("your-iot-endpoint.amazonaws.com")
    await client.initialize_webrtc()
    
    # Send test message
    await client.send_message("Hello, Find Your Team!", recipient_id="team_member_1")
    
    # Keep running
    await asyncio.sleep(60)
    
    # Cleanup
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())