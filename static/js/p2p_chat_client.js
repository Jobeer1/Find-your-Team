/**
 * WhatsApp-like P2P Chat Interface
 * Advanced chat client with file transfer and bandwidth optimization
 */

class P2PChatClient {
    constructor() {
        // Prevent multiple instances
        if (window.p2pChatClientInstance) {
            console.log('P2P Chat Client instance already exists, returning existing instance');
            return window.p2pChatClientInstance;
        }
        
        this.socket = null;
        this.currentUser = null;
        this.currentChat = null;
        this.chats = new Map();
        this.users = new Map();
        this.transfers = new Map();
        this.connectionQuality = 'high';
        this.registrationInProgress = false;
        this.registrationCompleted = false;
        this.initialized = false;
        this.userLoadAttempted = false;
        
        // UI Elements
        this.chatList = document.getElementById('chat-list');
        this.messagesContainer = document.getElementById('messages-container');
        this.messageInput = document.getElementById('message-input');
        this.sendButton = document.getElementById('send-button');
        this.fileButton = document.getElementById('file-button');
        this.userSearch = document.getElementById('user-search');
        
        // Store instance globally to prevent duplicates
        window.p2pChatClientInstance = this;
        
        console.log('Initializing new P2P Chat Client instance');
        this.init();
    }
    
    async init() {
        if (this.initialized) {
            console.log('P2P Chat Client already initialized, skipping...');
            return;
        }
        
        console.log('Initializing P2P Chat Client...');
        this.initialized = true;
        
        // Initialize SocketIO
        this.socket = io();
        this.setupSocketHandlers();
        
        // Setup UI event handlers
        this.setupUIHandlers();
        
        // Load user from localStorage or prompt for login
        await this.loadUser();
        
        // Detect connection quality
        this.detectConnectionQuality();
        
        // Start periodic tasks
        this.startPeriodicTasks();
        
        console.log('P2P Chat Client initialization complete');
    }
    
    setupSocketHandlers() {
        this.socket.on('connect', () => {
            console.log('Connected to chat server');
            this.updateConnectionStatus(true);
            
            if (this.currentUser) {
                this.registerUser();
            }
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from chat server');
            this.updateConnectionStatus(false);
        });
        
        this.socket.on('user_registered', (data) => {
            this.currentUser = data.user;
            this.chats.clear();
            data.chats.forEach(chat => {
                this.chats.set(chat.chat_id, chat);
            });
            this.renderChatList();
        });
        
        this.socket.on('new_message', (message) => {
            this.handleNewMessage(message);
        });
        
        this.socket.on('typing_update', (data) => {
            this.handleTypingUpdate(data);
        });
        
        this.socket.on('user_status_update', (data) => {
            this.handleUserStatusUpdate(data);
        });
        
        this.socket.on('file_chunk', (data) => {
            this.handleFileChunk(data);
        });
        
        this.socket.on('transfer_progress', (data) => {
            this.handleTransferProgress(data);
        });
        
        this.socket.on('transfer_failed', (data) => {
            this.handleTransferFailed(data);
        });
        
        this.socket.on('read_receipt', (receipt) => {
            this.handleReadReceipt(receipt);
        });
        
        this.socket.on('delivery_receipt', (receipt) => {
            this.handleDeliveryReceipt(receipt);
        });
        
        this.socket.on('error', (error) => {
            console.error('Chat error:', error);
            this.showNotification(error.message, 'error');
        });
    }
    
    setupUIHandlers() {
        // Send message on Enter (Shift+Enter for new line)
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Send button click
        this.sendButton.addEventListener('click', () => {
            this.sendMessage();
        });
        
        // File upload
        this.fileButton.addEventListener('click', () => {
            this.showFileUploadDialog();
        });
        
        // Typing indicators
        let typingTimer;
        this.messageInput.addEventListener('input', () => {
            if (this.currentChat) {
                this.socket.emit('typing_status', {
                    chat_id: this.currentChat,
                    is_typing: true
                });
                
                clearTimeout(typingTimer);
                typingTimer = setTimeout(() => {
                    this.socket.emit('typing_status', {
                        chat_id: this.currentChat,
                        is_typing: false
                    });
                }, 1000);
            }
        });
        
        // User search for adding to chats
        this.userSearch.addEventListener('input', (e) => {
            this.searchUsers(e.target.value);
        });
        
        // Auto-resize message input
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';
        });
    }
    
    async loadUser() {
        // Prevent multiple calls
        if (this.registrationInProgress || this.registrationCompleted || this.userLoadAttempted) {
            console.log('User load already attempted, skipping...', {
                registrationInProgress: this.registrationInProgress,
                registrationCompleted: this.registrationCompleted,
                userLoadAttempted: this.userLoadAttempted
            });
            return;
        }
        
        this.userLoadAttempted = true;
        console.log('Loading user data...');
        
        const savedUser = localStorage.getItem('chatUser');
        console.log('SavedUser from localStorage:', savedUser ? 'exists' : 'not found');
        
        if (savedUser) {
            try {
                const parsedUser = JSON.parse(savedUser);
                console.log('Parsed user data:', parsedUser);
                
                if (this.validateUser(parsedUser)) {
                    this.currentUser = parsedUser;
                    console.log('Loaded existing user:', this.currentUser.display_name);
                    this.registrationCompleted = true;
                    this.registerUser();
                    return;
                } else {
                    console.log('User validation failed:', parsedUser);
                }
            } catch (error) {
                console.error('Error parsing saved user:', error);
            }
        }
        
        console.log('No valid user found, will show registration once');
        localStorage.removeItem('chatUser'); // Clear invalid data
        
        // Only show registration if not already in progress and not completed
        if (!this.registrationInProgress && !this.registrationCompleted) {
            console.log('Calling showUserRegistration...');
            await this.showUserRegistration();
        } else {
            console.log('Registration already in progress or completed, skipping showUserRegistration');
        }
    }
    
    validateUser(user) {
        const isValid = user && user.user_id && user.username && user.display_name && user.user_id.startsWith('user_');
        console.log('User validation result:', isValid, 'for user:', user);
        return isValid;
    }
    
    async showUserRegistration() {
        if (this.registrationInProgress || this.registrationCompleted) {
            console.log('Registration already in progress or completed, skipping...');
            return;
        }
        
        // Check if modal already exists
        if (document.querySelector('.registration-modal')) {
            console.log('Registration modal already exists, skipping...');
            return;
        }
        
        console.log('Starting user registration...');
        this.registrationInProgress = true;
        
        // Create registration modal
        const modal = document.createElement('div');
        modal.className = 'registration-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>Join the Chat</h3>
                <form id="registration-form">
                    <input type="text" id="username" placeholder="Username" required>
                    <input type="text" id="display-name" placeholder="Display Name" required>
                    <input type="url" id="avatar-url" placeholder="Avatar URL (optional)">
                    <button type="submit">Join Chat</button>
                </form>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        const form = document.getElementById('registration-form');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const userData = {
                user_id: this.generateUserId(),
                username: document.getElementById('username').value,
                display_name: document.getElementById('display-name').value,
                avatar_url: document.getElementById('avatar-url').value || null
            };
            
            try {
                const response = await fetch('/api/chat/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(userData)
                });
                
                if (response.ok) {
                    const result = await response.json();
                    this.currentUser = result.user;
                    localStorage.setItem('chatUser', JSON.stringify(this.currentUser));
                    
                    this.registrationInProgress = false;
                    this.registrationCompleted = true;
                    
                    document.body.removeChild(modal);
                    console.log('Registration successful for:', this.currentUser.display_name);
                    this.registerUser();
                } else {
                    this.registrationInProgress = false;
                    throw new Error('Registration failed');
                }
            } catch (error) {
                this.showNotification('Registration failed: ' + error.message, 'error');
            }
        });
    }
    
    registerUser() {
        if (this.socket.connected && this.currentUser) {
            this.socket.emit('user_register', this.currentUser);
        }
    }
    
    generateUserId() {
        return 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    async searchUsers(query) {
        if (!query.trim()) {
            this.hideUserSearchResults();
            return;
        }
        
        try {
            const response = await fetch(`/api/chat/users/search?q=${encodeURIComponent(query)}`);
            if (response.ok) {
                const result = await response.json();
                this.showUserSearchResults(result.users);
            }
        } catch (error) {
            console.error('User search error:', error);
        }
    }
    
    showUserSearchResults(users) {
        let resultsContainer = document.getElementById('user-search-results');
        if (!resultsContainer) {
            resultsContainer = document.createElement('div');
            resultsContainer.id = 'user-search-results';
            resultsContainer.className = 'user-search-results';
            this.userSearch.parentNode.appendChild(resultsContainer);
        }
        
        resultsContainer.innerHTML = users.map(user => `
            <div class="user-result" data-user-id="${user.user_id}">
                <img src="${user.avatar_url || '/static/img/default-avatar.png'}" alt="Avatar" class="user-avatar">
                <div class="user-info">
                    <div class="user-name">${user.display_name}</div>
                    <div class="user-username">@${user.username}</div>
                </div>
                <button class="invite-btn" onclick="chatClient.startChatWith('${user.user_id}')">
                    <i class="fas fa-comment"></i>
                </button>
            </div>
        `).join('');
        
        resultsContainer.style.display = 'block';
    }
    
    hideUserSearchResults() {
        const resultsContainer = document.getElementById('user-search-results');
        if (resultsContainer) {
            resultsContainer.style.display = 'none';
        }
    }
    
    async startChatWith(userId) {
        try {
            const response = await fetch('/api/chat/chats/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    participants: [userId]
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                await this.loadChats(); // Refresh chat list
                this.openChat(result.chat_id);
                this.hideUserSearchResults();
                this.userSearch.value = '';
            }
        } catch (error) {
            this.showNotification('Failed to create chat: ' + error.message, 'error');
        }
    }
    
    async loadChats() {
        try {
            const response = await fetch('/api/chat/chats');
            if (response.ok) {
                const result = await response.json();
                this.chats.clear();
                result.chats.forEach(chat => {
                    this.chats.set(chat.chat_id, chat);
                });
                this.renderChatList();
            }
        } catch (error) {
            console.error('Load chats error:', error);
        }
    }
    
    renderChatList() {
        if (!this.chatList) return;
        
        const chatsArray = Array.from(this.chats.values());
        
        this.chatList.innerHTML = chatsArray.map(chat => {
            const otherParticipants = chat.participants.filter(p => p.user_id !== this.currentUser.user_id);
            const chatName = otherParticipants.map(p => p.display_name).join(', ') || 'Empty Chat';
            const lastMessage = chat.last_message;
            const unreadBadge = chat.unread_count > 0 ? `<span class="unread-badge">${chat.unread_count}</span>` : '';
            
            return `
                <div class="chat-item ${this.currentChat === chat.chat_id ? 'active' : ''}" 
                     onclick="chatClient.openChat('${chat.chat_id}')">
                    <div class="chat-avatar">
                        ${otherParticipants.length === 1 ? 
                            `<img src="${otherParticipants[0].avatar_url || '/static/img/default-avatar.png'}" alt="Avatar">` :
                            `<div class="group-avatar"><i class="fas fa-users"></i></div>`
                        }
                    </div>
                    <div class="chat-info">
                        <div class="chat-name">${chatName}</div>
                        <div class="chat-last-message">
                            ${lastMessage ? this.formatLastMessage(lastMessage) : 'No messages yet'}
                        </div>
                    </div>
                    <div class="chat-meta">
                        <div class="chat-time">
                            ${lastMessage ? this.formatMessageTime(lastMessage.timestamp) : ''}
                        </div>
                        ${unreadBadge}
                    </div>
                </div>
            `;
        }).join('');
    }
    
    formatLastMessage(message) {
        if (message.message_type === 'file') {
            return `📎 ${message.file_metadata?.filename || 'File'}`;
        } else if (message.message_type === 'image') {
            return '🖼️ Image';
        } else if (message.message_type === 'system') {
            return message.content;
        }
        return message.content.length > 50 ? message.content.substr(0, 50) + '...' : message.content;
    }
    
    formatMessageTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        
        if (date.toDateString() === now.toDateString()) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } else {
            return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
        }
    }
    
    async openChat(chatId) {
        this.currentChat = chatId;
        this.renderChatList(); // Update active state
        
        // Join chat room
        this.socket.emit('join_chat', { chat_id: chatId });
        
        // Load messages
        await this.loadMessages(chatId);
        
        // Mark messages as read
        this.markChatAsRead(chatId);
        
        // Update UI
        this.updateChatHeader(chatId);
        this.messageInput.focus();
    }
    
    async loadMessages(chatId, beforeMessageId = null) {
        try {
            let url = `/api/chat/chats/${chatId}/messages?limit=50`;
            if (beforeMessageId) {
                url += `&before=${beforeMessageId}`;
            }
            
            const response = await fetch(url);
            if (response.ok) {
                const result = await response.json();
                this.renderMessages(result.messages, !beforeMessageId);
            }
        } catch (error) {
            console.error('Load messages error:', error);
        }
    }
    
    renderMessages(messages, clearContainer = true) {
        if (!this.messagesContainer) return;
        
        if (clearContainer) {
            this.messagesContainer.innerHTML = '';
        }
        
        messages.forEach(message => {
            this.addMessageToUI(message);
        });
        
        // Scroll to bottom for new messages
        if (clearContainer) {
            this.scrollToBottom();
        }
    }
    
    addMessageToUI(message) {
        const messageEl = document.createElement('div');
        messageEl.className = `message ${message.sender_id === this.currentUser.user_id ? 'sent' : 'received'}`;
        messageEl.dataset.messageId = message.id;
        
        const isFile = message.message_type === 'file';
        const isImage = message.message_type === 'image';
        
        messageEl.innerHTML = `
            <div class="message-content">
                ${this.renderMessageContent(message)}
                <div class="message-meta">
                    <span class="message-time">${this.formatMessageTime(message.timestamp)}</span>
                    ${message.sender_id === this.currentUser.user_id ? this.renderMessageStatus(message.status) : ''}
                </div>
            </div>
        `;
        
        this.messagesContainer.appendChild(messageEl);
    }
    
    renderMessageContent(message) {
        switch (message.message_type) {
            case 'file':
                return this.renderFileMessage(message);
            case 'image':
                return this.renderImageMessage(message);
            case 'system':
                return `<div class="system-message">${message.content}</div>`;
            default:
                return `<div class="text-message">${this.formatTextMessage(message.content)}</div>`;
        }
    }
    
    renderFileMessage(message) {
        const metadata = message.file_metadata;
        const transferId = metadata?.transfer_id;
        
        return `
            <div class="file-message" data-transfer-id="${transferId}">
                <div class="file-icon">
                    <i class="fas fa-file"></i>
                </div>
                <div class="file-info">
                    <div class="file-name">${metadata?.filename || 'Unknown File'}</div>
                    <div class="file-size">${this.formatFileSize(metadata?.file_size || 0)}</div>
                    <div class="file-progress" style="display: none;">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: 0%"></div>
                        </div>
                    </div>
                </div>
                <button class="download-btn" onclick="chatClient.downloadFile('${transferId}')">
                    <i class="fas fa-download"></i>
                </button>
            </div>
        `;
    }
    
    renderImageMessage(message) {
        const metadata = message.file_metadata;
        const thumbnail = metadata?.thumbnail;
        
        return `
            <div class="image-message">
                ${thumbnail ? 
                    `<img src="${thumbnail}" alt="Image" class="message-image" onclick="chatClient.showImagePreview('${message.id}')">` :
                    `<div class="image-placeholder"><i class="fas fa-image"></i></div>`
                }
            </div>
        `;
    }
    
    formatTextMessage(content) {
        // Basic text formatting (URLs, mentions, etc.)
        return content
            .replace(/\n/g, '<br>')
            .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank">$1</a>');
    }
    
    renderMessageStatus(status) {
        const icons = {
            pending: '<i class="fas fa-clock"></i>',
            sent: '<i class="fas fa-check"></i>',
            delivered: '<i class="fas fa-check-double"></i>',
            read: '<i class="fas fa-check-double read"></i>',
            failed: '<i class="fas fa-exclamation-triangle"></i>'
        };
        
        return `<span class="message-status ${status}">${icons[status] || ''}</span>`;
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    sendMessage() {
        const content = this.messageInput.value.trim();
        if (!content || !this.currentChat) return;
        
        this.socket.emit('send_message', {
            chat_id: this.currentChat,
            content: content,
            message_type: 'text'
        });
        
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
    }
    
    showFileUploadDialog() {
        const input = document.createElement('input');
        input.type = 'file';
        input.multiple = true;
        input.onchange = (e) => {
            const files = Array.from(e.target.files);
            files.forEach(file => this.uploadFile(file));
        };
        input.click();
    }
    
    async uploadFile(file) {
        if (!this.currentChat) return;
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('chat_id', this.currentChat);
        
        try {
            // Show upload progress in UI
            const progressId = this.showUploadProgress(file.name);
            
            const response = await fetch('/api/chat/files/upload', {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                const result = await response.json();
                this.transfers.set(result.transfer_id, {
                    id: result.transfer_id,
                    filename: file.name,
                    size: file.size,
                    progress: 0
                });
            } else {
                throw new Error('Upload failed');
            }
            
            this.hideUploadProgress(progressId);
            
        } catch (error) {
            this.showNotification('File upload failed: ' + error.message, 'error');
        }
    }
    
    showUploadProgress(filename) {
        const progressId = 'upload_' + Date.now();
        // Implementation for showing upload progress UI
        return progressId;
    }
    
    hideUploadProgress(progressId) {
        // Implementation for hiding upload progress UI
    }
    
    handleNewMessage(message) {
        if (message.chat_id === this.currentChat) {
            this.addMessageToUI(message);
            this.scrollToBottom();
            
            // Mark as read immediately if chat is open
            this.socket.emit('mark_read', {
                chat_id: message.chat_id,
                message_ids: [message.id]
            });
        } else {
            // Update unread count for other chats
            const chat = this.chats.get(message.chat_id);
            if (chat) {
                chat.unread_count = (chat.unread_count || 0) + 1;
                chat.last_message = message;
                this.renderChatList();
            }
        }
        
        // Show notification for new messages
        if (message.sender_id !== this.currentUser.user_id) {
            this.showMessageNotification(message);
        }
    }
    
    handleTypingUpdate(data) {
        if (data.chat_id === this.currentChat) {
            this.updateTypingIndicator(data.typing_users);
        }
    }
    
    updateTypingIndicator(typingUsers) {
        let indicator = document.getElementById('typing-indicator');
        
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'typing-indicator';
            indicator.className = 'typing-indicator';
            this.messagesContainer.appendChild(indicator);
        }
        
        const otherUsers = typingUsers.filter(userId => userId !== this.currentUser.user_id);
        
        if (otherUsers.length > 0) {
            const userNames = otherUsers.map(userId => {
                const user = this.users.get(userId);
                return user ? user.display_name : 'Someone';
            });
            
            indicator.innerHTML = `
                <div class="typing-content">
                    <div class="typing-dots">
                        <span></span><span></span><span></span>
                    </div>
                    <span class="typing-text">${userNames.join(', ')} ${userNames.length === 1 ? 'is' : 'are'} typing...</span>
                </div>
            `;
            indicator.style.display = 'block';
        } else {
            indicator.style.display = 'none';
        }
    }
    
    handleTransferProgress(data) {
        const transferEl = document.querySelector(`[data-transfer-id="${data.transfer_id}"]`);
        if (transferEl) {
            const progressBar = transferEl.querySelector('.progress-fill');
            const progressContainer = transferEl.querySelector('.file-progress');
            
            if (progressBar && progressContainer) {
                progressContainer.style.display = 'block';
                progressBar.style.width = `${data.progress}%`;
            }
        }
    }
    
    detectConnectionQuality() {
        if ('connection' in navigator) {
            const connection = navigator.connection;
            const effectiveType = connection.effectiveType;
            
            if (effectiveType === 'slow-2g' || effectiveType === '2g') {
                this.connectionQuality = 'low';
            } else if (effectiveType === '3g') {
                this.connectionQuality = 'medium';
            } else {
                this.connectionQuality = 'high';
            }
            
            // Update server
            this.updateBandwidth();
        }
    }
    
    async updateBandwidth() {
        try {
            await fetch('/api/chat/bandwidth/update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    connection_quality: this.connectionQuality
                })
            });
        } catch (error) {
            console.error('Bandwidth update error:', error);
        }
    }
    
    markChatAsRead(chatId) {
        const chat = this.chats.get(chatId);
        if (chat && chat.unread_count > 0) {
            // Get all unread message IDs
            const messages = this.messagesContainer.querySelectorAll('.message');
            const messageIds = Array.from(messages).map(msg => msg.dataset.messageId);
            
            this.socket.emit('mark_read', {
                chat_id: chatId,
                message_ids: messageIds
            });
            
            chat.unread_count = 0;
            this.renderChatList();
        }
    }
    
    updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connection-status');
        if (statusEl) {
            statusEl.className = `connection-status ${connected ? 'connected' : 'disconnected'}`;
            statusEl.textContent = connected ? 'Connected' : 'Disconnected';
        }
    }
    
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 5000);
    }
    
    showMessageNotification(message) {
        if (Notification.permission === 'granted') {
            const sender = this.users.get(message.sender_id) || { display_name: 'Someone' };
            new Notification(`${sender.display_name}`, {
                body: message.content,
                icon: sender.avatar_url || '/static/img/default-avatar.png'
            });
        }
    }
    
    scrollToBottom() {
        if (this.messagesContainer) {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }
    }
    
    updateChatHeader(chatId) {
        const chat = this.chats.get(chatId);
        if (!chat) return;
        
        const headerEl = document.getElementById('chat-header');
        if (headerEl) {
            const otherParticipants = chat.participants.filter(p => p.user_id !== this.currentUser.user_id);
            const chatName = otherParticipants.map(p => p.display_name).join(', ') || 'Empty Chat';
            
            headerEl.innerHTML = `
                <div class="chat-header-info">
                    <h3>${chatName}</h3>
                    <div class="participant-count">${chat.participants.length} participants</div>
                </div>
                <div class="chat-header-actions">
                    <button onclick="chatClient.showChatInfo('${chatId}')" title="Chat Info">
                        <i class="fas fa-info-circle"></i>
                    </button>
                </div>
            `;
        }
    }
    
    startPeriodicTasks() {
        // Heartbeat to maintain connection
        setInterval(() => {
            if (this.socket.connected) {
                this.socket.emit('ping');
            }
        }, 30000); // 30 seconds
        
        // Request notification permission
        if (Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }
    
    handleModeChange(modeInfo) {
        /**
         * Handle chat mode changes from the mode selector
         * @param {Object} modeInfo - Mode information object
         */
        try {
            console.log('P2P Chat handling mode change:', modeInfo);
            
            if (modeInfo && modeInfo.current_mode) {
                const mode = modeInfo.current_mode.mode;
                const displayName = modeInfo.current_mode.display_name;
                
                // Update connection quality based on mode
                if (mode.includes('high')) {
                    this.connectionQuality = 'high';
                } else if (mode.includes('low')) {
                    this.connectionQuality = 'low';
                } else {
                    this.connectionQuality = 'medium';
                }
                
                // Update UI to reflect mode change
                this.updateModeDisplay(displayName, mode);
                
                // Adjust chat behavior based on mode
                this.adjustChatBehavior(mode);
                
                // Notify user of mode change
                this.showModeChangeNotification(displayName);
            }
        } catch (error) {
            console.error('Error handling mode change:', error);
        }
    }
    
    updateModeDisplay(displayName, mode) {
        /**
         * Update UI elements to show current mode
         */
        const modeIndicator = document.querySelector('.mode-indicator');
        if (modeIndicator) {
            modeIndicator.textContent = displayName;
            modeIndicator.className = `mode-indicator mode-${mode.replace('_', '-')}`;
        }
        
        // Update chat header with mode info
        const chatHeader = document.querySelector('.chat-header');
        if (chatHeader) {
            let modebadge = chatHeader.querySelector('.mode-badge');
            if (!modebadge) {
                modebadge = document.createElement('span');
                modebadge.className = 'mode-badge';
                chatHeader.appendChild(modebadge);
            }
            modeBadge.textContent = displayName;
            modeBadge.className = `mode-badge mode-${mode.replace('_', '-')}`;
        }
    }
    
    adjustChatBehavior(mode) {
        /**
         * Adjust chat functionality based on current mode
         */
        const fileButton = document.getElementById('file-button');
        const messageInput = document.getElementById('message-input');
        
        if (mode.includes('low') || mode === 'offline') {
            // Low bandwidth mode - disable heavy features
            if (fileButton) {
                fileButton.disabled = true;
                fileButton.title = 'File sharing disabled in low bandwidth mode';
            }
            if (messageInput) {
                messageInput.placeholder = 'Type a message (text only)...';
            }
        } else {
            // High bandwidth mode - enable all features
            if (fileButton) {
                fileButton.disabled = false;
                fileButton.title = 'Send file';
            }
            if (messageInput) {
                messageInput.placeholder = 'Type a message...';
            }
        }
    }
    
    showModeChangeNotification(displayName) {
        /**
         * Show a notification about mode change
         */
        const notification = document.createElement('div');
        notification.className = 'mode-change-notification';
        notification.innerHTML = `
            <div class="notification-content">
                <i class="fas fa-network-wired"></i>
                <span>Switched to ${displayName}</span>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove notification after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    }
}

// Initialize chat client when DOM is ready
let chatClient;
document.addEventListener('DOMContentLoaded', () => {
    chatClient = new P2PChatClient();
});

// Export for global access
window.chatClient = chatClient;