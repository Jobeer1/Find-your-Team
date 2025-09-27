/**
 * Multi-Protocol Communication Client for Find Your Team
 * Handles WebSocket, offline queuing, and protocol fallback
 */

class CommunicationClient {
    constructor(userId, options = {}) {
        this.userId = userId;
        this.options = {
            socketUrl: options.socketUrl || window.location.origin,
            reconnectAttempts: options.reconnectAttempts || 5,
            reconnectDelay: options.reconnectDelay || 1000,
            queueStorageKey: options.queueStorageKey || 'fyt_message_queue',
            ...options
        };
        
        // Connection state
        this.socket = null;
        this.isConnected = false;
        this.reconnectCount = 0;
        this.connectionStatus = {
            websocket: 'disconnected',
            mqtt: 'disconnected',
            webrtc: 'disconnected',
            offline_queue: 'available'
        };
        
        // Message handling
        this.messageHandlers = new Map();
        this.statusHandlers = new Set();
        this.messageQueue = this.loadMessageQueue();
        
        // Auto-retry settings
        this.retryInterval = 30000; // 30 seconds
        this.retryTimer = null;
        
        // Initialize
        this.init();
    }
    
    /**
     * Initialize the communication client
     */
    init() {
        this.connectWebSocket();
        this.startRetryTimer();
        this.setupVisibilityHandling();
        this.setupStorageSync();
    }
    
    /**
     * Connect to WebSocket server
     */
    connectWebSocket() {
        try {
            // Load Socket.IO if not already loaded
            if (typeof io === 'undefined') {
                this.loadSocketIO().then(() => this.establishConnection());
            } else {
                this.establishConnection();
            }
        } catch (error) {
            console.error('WebSocket connection error:', error);
            this.handleConnectionError();
        }
    }
    
    /**
     * Load Socket.IO library dynamically
     */
    loadSocketIO() {
        return new Promise((resolve, reject) => {
            if (typeof io !== 'undefined') {
                resolve();
                return;
            }
            
            const script = document.createElement('script');
            script.src = '/static/js/socket.io.min.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }
    
    /**
     * Establish Socket.IO connection
     */
    establishConnection() {
        this.socket = io(this.options.socketUrl, {
            transports: ['websocket', 'polling'],
            upgrade: true,
            rememberUpgrade: true
        });
        
        this.setupSocketHandlers();
    }
    
    /**
     * Setup Socket.IO event handlers
     */
    setupSocketHandlers() {
        this.socket.on('connect', () => {
            console.log('Connected to communication server');
            this.isConnected = true;
            this.reconnectCount = 0;
            this.connectionStatus.websocket = 'connected';
            
            // Join user channel
            this.socket.emit('join_user', { user_id: this.userId });
            
            // Process queued messages
            this.processMessageQueue();
            
            // Notify status handlers
            this.notifyStatusHandlers();
        });
        
        this.socket.on('disconnect', (reason) => {
            console.log('Disconnected from communication server:', reason);
            this.isConnected = false;
            this.connectionStatus.websocket = 'disconnected';
            
            // Notify status handlers
            this.notifyStatusHandlers();
            
            // Attempt reconnection
            this.handleDisconnection();
        });
        
        this.socket.on('connect_error', (error) => {
            console.error('Connection error:', error);
            this.handleConnectionError();
        });
        
        this.socket.on('joined', (data) => {
            console.log('Joined communication channel:', data);
        });
        
        this.socket.on('message_received', (message) => {
            this.handleIncomingMessage(message);
        });
        
        this.socket.on('message_sent', (data) => {
            console.log('Message sent acknowledgment:', data);
        });
        
        this.socket.on('message_delivered', (data) => {
            console.log('Message delivered:', data);
        });
        
        this.socket.on('message_error', (error) => {
            console.error('Message error:', error);
            this.showNotification('Message delivery failed', 'error');
        });
        
        this.socket.on('status_changed', (status) => {
            this.updateConnectionStatus(status);
        });
        
        this.socket.on('connection_status', (status) => {
            this.updateConnectionStatus(status);
        });
        
        this.socket.on('error', (error) => {
            console.error('Socket error:', error);
            this.showNotification(error.message || 'Communication error', 'error');
        });
    }
    
    /**
     * Handle incoming message
     */
    handleIncomingMessage(message) {
        console.log('Received message:', message);
        
        // Call registered handlers
        const handlers = this.messageHandlers.get(message.message_type) || [];
        const globalHandlers = this.messageHandlers.get('*') || [];
        
        [...handlers, ...globalHandlers].forEach(handler => {
            try {
                handler(message);
            } catch (error) {
                console.error('Message handler error:', error);
            }
        });
        
        // Show notification for chat messages
        if (message.message_type === 'chat') {
            this.showMessageNotification(message);
        }
    }
    
    /**
     * Update connection status
     */
    updateConnectionStatus(status) {
        if (status.protocols) {
            Object.assign(this.connectionStatus, status.protocols);
        }
        
        console.log('Connection status updated:', this.connectionStatus);
        this.notifyStatusHandlers();
    }
    
    /**
     * Send message
     */
    async sendMessage(content, options = {}) {
        const message = {
            content: content,
            recipient_id: options.recipientId,
            message_type: options.messageType || 'chat',
            priority: options.priority || 2, // Normal priority
            timestamp: new Date().toISOString(),
            id: this.generateMessageId()
        };
        
        if (this.isConnected) {
            try {
                this.socket.emit('send_message', message);
                return { success: true, queued: false };
            } catch (error) {
                console.error('Send message error:', error);
                this.queueMessage(message);
                return { success: true, queued: true };
            }
        } else {
            // Queue for later delivery
            this.queueMessage(message);
            return { success: true, queued: true };
        }
    }
    
    /**
     * Queue message for offline delivery
     */
    queueMessage(message) {
        this.messageQueue.push({
            ...message,
            queued_at: new Date().toISOString(),
            retry_count: 0
        });
        
        this.saveMessageQueue();
        console.log('Message queued for offline delivery:', message.id);
        
        this.showNotification('Message queued for delivery', 'info');
    }
    
    /**
     * Process queued messages
     */
    async processMessageQueue() {
        if (!this.isConnected || this.messageQueue.length === 0) {
            return;
        }
        
        const messagesToProcess = [...this.messageQueue];
        this.messageQueue = [];
        
        for (const message of messagesToProcess) {
            try {
                this.socket.emit('send_message', message);
                console.log('Queued message sent:', message.id);
            } catch (error) {
                console.error('Error sending queued message:', error);
                
                // Re-queue if retry count is below limit
                if (message.retry_count < 3) {
                    message.retry_count++;
                    this.messageQueue.push(message);
                } else {
                    console.warn('Message exceeded retry limit, discarded:', message.id);
                }
            }
        }
        
        this.saveMessageQueue();
        
        if (messagesToProcess.length > 0) {
            this.showNotification(`${messagesToProcess.length} queued messages sent`, 'success');
        }
    }
    
    /**
     * Join team communication channel
     */
    joinTeam(teamId) {
        if (this.isConnected) {
            this.socket.emit('join_team', { team_id: teamId });
        }
    }
    
    /**
     * Leave team communication channel
     */
    leaveTeam(teamId) {
        if (this.isConnected) {
            this.socket.emit('leave_team', { team_id: teamId });
        }
    }
    
    /**
     * Add message handler
     */
    addMessageHandler(messageType, handler) {
        if (!this.messageHandlers.has(messageType)) {
            this.messageHandlers.set(messageType, []);
        }
        this.messageHandlers.get(messageType).push(handler);
    }
    
    /**
     * Remove message handler
     */
    removeMessageHandler(messageType, handler) {
        const handlers = this.messageHandlers.get(messageType);
        if (handlers) {
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }
    
    /**
     * Add status change handler
     */
    addStatusHandler(handler) {
        this.statusHandlers.add(handler);
    }
    
    /**
     * Remove status change handler
     */
    removeStatusHandler(handler) {
        this.statusHandlers.delete(handler);
    }
    
    /**
     * Notify status handlers
     */
    notifyStatusHandlers() {
        const status = {
            connected: this.isConnected,
            protocols: { ...this.connectionStatus },
            queueSize: this.messageQueue.length,
            bestProtocol: this.getBestProtocol()
        };
        
        this.statusHandlers.forEach(handler => {
            try {
                handler(status);
            } catch (error) {
                console.error('Status handler error:', error);
            }
        });
    }
    
    /**
     * Get best available protocol
     */
    getBestProtocol() {
        if (this.connectionStatus.webrtc === 'connected') return 'webrtc';
        if (this.connectionStatus.mqtt === 'connected') return 'mqtt';
        if (this.connectionStatus.websocket === 'connected') return 'websocket';
        return 'offline_queue';
    }
    
    /**
     * Handle disconnection
     */
    handleDisconnection() {
        if (this.reconnectCount < this.options.reconnectAttempts) {
            const delay = this.options.reconnectDelay * Math.pow(2, this.reconnectCount);
            
            setTimeout(() => {
                console.log(`Attempting reconnection ${this.reconnectCount + 1}/${this.options.reconnectAttempts}`);
                this.reconnectCount++;
                this.connectWebSocket();
            }, delay);
        } else {
            console.error('Max reconnection attempts reached');
            this.showNotification('Connection lost. Messages will be queued.', 'warning');
        }
    }
    
    /**
     * Handle connection error
     */
    handleConnectionError() {
        this.connectionStatus.websocket = 'failed';
        this.notifyStatusHandlers();
    }
    
    /**
     * Start retry timer for processing queue
     */
    startRetryTimer() {
        this.retryTimer = setInterval(() => {
            if (this.isConnected && this.messageQueue.length > 0) {
                this.processMessageQueue();
            }
        }, this.retryInterval);
    }
    
    /**
     * Setup page visibility handling
     */
    setupVisibilityHandling() {
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && !this.isConnected) {
                // Page became visible and we're disconnected, try to reconnect
                this.connectWebSocket();
            }
        });
    }
    
    /**
     * Setup storage synchronization across tabs
     */
    setupStorageSync() {
        window.addEventListener('storage', (event) => {
            if (event.key === this.options.queueStorageKey) {
                this.messageQueue = this.loadMessageQueue();
            }
        });
    }
    
    /**
     * Load message queue from localStorage
     */
    loadMessageQueue() {
        try {
            const stored = localStorage.getItem(this.options.queueStorageKey);
            return stored ? JSON.parse(stored) : [];
        } catch (error) {
            console.error('Error loading message queue:', error);
            return [];
        }
    }
    
    /**
     * Save message queue to localStorage
     */
    saveMessageQueue() {
        try {
            localStorage.setItem(this.options.queueStorageKey, JSON.stringify(this.messageQueue));
        } catch (error) {
            console.error('Error saving message queue:', error);
        }
    }
    
    /**
     * Generate unique message ID
     */
    generateMessageId() {
        return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    /**
     * Show notification to user
     */
    showNotification(message, type = 'info') {
        // Use the existing notification system from the main app
        if (typeof showNotification === 'function') {
            showNotification(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }
    
    /**
     * Show message notification
     */
    showMessageNotification(message) {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(`Message from ${message.sender_id}`, {
                body: message.content,
                icon: '/static/icon-192.png',
                tag: message.id
            });
        }
    }
    
    /**
     * Request notification permission
     */
    async requestNotificationPermission() {
        if ('Notification' in window && Notification.permission === 'default') {
            const permission = await Notification.requestPermission();
            return permission === 'granted';
        }
        return Notification.permission === 'granted';
    }
    
    /**
     * Get connection statistics
     */
    getStats() {
        return {
            connected: this.isConnected,
            reconnectCount: this.reconnectCount,
            queueSize: this.messageQueue.length,
            protocols: { ...this.connectionStatus },
            bestProtocol: this.getBestProtocol()
        };
    }
    
    /**
     * Disconnect and cleanup
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
        
        if (this.retryTimer) {
            clearInterval(this.retryTimer);
        }
        
        this.isConnected = false;
        this.messageHandlers.clear();
        this.statusHandlers.clear();
        
        console.log('Communication client disconnected');
    }
}

/**
 * Connection Status Indicator Component
 */
class ConnectionStatusIndicator {
    constructor(containerId, communicationClient) {
        this.container = document.getElementById(containerId);
        this.client = communicationClient;
        
        if (!this.container) {
            console.warn('Connection status container not found');
            return;
        }
        
        this.render();
        this.client.addStatusHandler(this.updateStatus.bind(this));
    }
    
    render() {
        this.container.innerHTML = `
            <div class="connection-status">
                <div class="status-indicator">
                    <div class="status-dot"></div>
                    <span class="status-text">Connecting...</span>
                </div>
                <div class="protocol-status">
                    <div class="protocol websocket" title="WebSocket">
                        <i class="fas fa-wifi"></i>
                        <span class="protocol-name">WebSocket</span>
                        <span class="protocol-status-text">Disconnected</span>
                    </div>
                    <div class="protocol mqtt" title="MQTT">
                        <i class="fas fa-satellite-dish"></i>
                        <span class="protocol-name">MQTT</span>
                        <span class="protocol-status-text">Disconnected</span>
                    </div>
                    <div class="protocol webrtc" title="WebRTC">
                        <i class="fas fa-network-wired"></i>
                        <span class="protocol-name">WebRTC</span>
                        <span class="protocol-status-text">Disconnected</span>
                    </div>
                </div>
                <div class="queue-status">
                    <i class="fas fa-clock"></i>
                    <span class="queue-count">0</span> queued messages
                </div>
            </div>
        `;
    }
    
    updateStatus(status) {
        const statusDot = this.container.querySelector('.status-dot');
        const statusText = this.container.querySelector('.status-text');
        const queueCount = this.container.querySelector('.queue-count');
        
        // Update main status
        if (status.connected) {
            statusDot.className = 'status-dot connected';
            statusText.textContent = `Connected (${status.bestProtocol})`;
        } else {
            statusDot.className = 'status-dot disconnected';
            statusText.textContent = 'Offline Mode';
        }
        
        // Update protocol status
        Object.entries(status.protocols).forEach(([protocol, protocolStatus]) => {
            const protocolElement = this.container.querySelector(`.protocol.${protocol.replace('_', '')}`);
            if (protocolElement) {
                const statusElement = protocolElement.querySelector('.protocol-status-text');
                statusElement.textContent = protocolStatus.charAt(0).toUpperCase() + protocolStatus.slice(1);
                protocolElement.className = `protocol ${protocol.replace('_', '')} ${protocolStatus}`;
            }
        });
        
        // Update queue count
        if (queueCount) {
            queueCount.textContent = status.queueSize || 0;
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CommunicationClient, ConnectionStatusIndicator };
} else {
    window.CommunicationClient = CommunicationClient;
    window.ConnectionStatusIndicator = ConnectionStatusIndicator;
}