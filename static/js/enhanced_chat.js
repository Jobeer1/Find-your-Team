/**
 * Enhanced P2P Chat Interface
 * Improved error handling, retry logic, and user feedback
 */

// Chat state management
let chatState = {
    isConnected: false,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectDelay: 2000,
    messageQueue: [],
    currentUser: null,
    conversationId: null
};

// Initialize chat functionality
function initializePeerChat() {
    console.log('Initializing enhanced P2P chat...');
    
    // Get DOM elements
    const chatContainer = document.getElementById('onboarding-chat');
    const chatInput = document.getElementById('onboarding-input');
    const sendButton = document.getElementById('send-onboarding');
    const charCounter = document.getElementById('char-count');
    
    if (!chatContainer || !chatInput || !sendButton) {
        console.warn('Chat elements not found, retrying in 1 second...');
        setTimeout(initializePeerChat, 1000);
        return;
    }
    
    // Setup event listeners
    setupChatEventListeners();
    
    // Initialize connection status indicator
    createConnectionStatusIndicator();
    
    // Load chat history if available
    loadChatHistory();
    
    // Start heartbeat for connection monitoring
    startConnectionHeartbeat();
    
    console.log('P2P Chat initialized successfully');
}

// Setup event listeners for chat interface
function setupChatEventListeners() {
    const chatInput = document.getElementById('onboarding-input');
    const sendButton = document.getElementById('send-onboarding');
    const charCounter = document.getElementById('char-count');
    
    // Input character counting
    if (chatInput && charCounter) {
        chatInput.addEventListener('input', function(e) {
            const length = e.target.value.length;
            charCounter.textContent = length;
            
            // Visual feedback for character limit
            if (length > 800) {
                charCounter.style.color = '#ff6b6b';
            } else if (length > 600) {
                charCounter.style.color = '#ffd700';
            } else {
                charCounter.style.color = '#007A4D';
            }
        });
        
        // Enter key to send (Shift+Enter for new line)
        chatInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendEnhancedMessage();
            }
        });
    }
    
    // Send button click
    if (sendButton) {
        sendButton.addEventListener('click', sendEnhancedMessage);
    }
}

// Create connection status indicator
function createConnectionStatusIndicator() {
    const statusIndicator = document.createElement('div');
    statusIndicator.id = 'connection-status';
    statusIndicator.className = 'connection-status';
    statusIndicator.innerHTML = `
        <div class="status-dot"></div>
        <span class="status-text">Connecting...</span>
    `;
    
    // Insert at top of chat container
    const chatContainer = document.getElementById('onboarding-chat');
    if (chatContainer && chatContainer.parentNode) {
        chatContainer.parentNode.insertBefore(statusIndicator, chatContainer);
    }
    
    updateConnectionStatus('connecting');
}

// Update connection status indicator
function updateConnectionStatus(status) {
    const statusIndicator = document.getElementById('connection-status');
    if (!statusIndicator) return;
    
    const statusDot = statusIndicator.querySelector('.status-dot');
    const statusText = statusIndicator.querySelector('.status-text');
    
    if (!statusDot || !statusText) return;
    
    switch (status) {
        case 'connected':
            statusDot.className = 'status-dot connected';
            statusText.textContent = 'Connected';
            chatState.isConnected = true;
            break;
        case 'disconnected':
            statusDot.className = 'status-dot disconnected';
            statusText.textContent = 'Disconnected';
            chatState.isConnected = false;
            break;
        case 'reconnecting':
            statusDot.className = 'status-dot reconnecting';
            statusText.textContent = `Reconnecting... (${chatState.reconnectAttempts}/${chatState.maxReconnectAttempts})`;
            break;
        case 'error':
            statusDot.className = 'status-dot error';
            statusText.textContent = 'Connection Error';
            chatState.isConnected = false;
            break;
        default:
            statusDot.className = 'status-dot connecting';
            statusText.textContent = 'Connecting...';
    }
}

// Enhanced message sending with retry logic
async function sendEnhancedMessage() {
    const chatInput = document.getElementById('onboarding-input');
    const sendButton = document.getElementById('send-onboarding');
    
    if (!chatInput || !sendButton) {
        showErrorMessage('Chat interface not available');
        return;
    }
    
    const message = chatInput.value.trim();
    if (!message) {
        showErrorMessage('Please enter a message');
        return;
    }
    
    // Disable input during send
    setInputEnabled(false);
    
    try {
        // Add user message to UI immediately
        addMessageToUI({
            type: 'user',
            content: message,
            timestamp: new Date().toISOString(),
            status: 'sending'
        });
        
        // Clear input
        chatInput.value = '';
        updateCharacterCount();
        
        // Send message with retry logic
        const response = await sendMessageWithRetry(message);
        
        if (response && response.success !== false) {
            // Add agent response
            addMessageToUI({
                type: 'agent',
                content: response.message || response.response || 'Message received',
                timestamp: new Date().toISOString(),
                confidence: response.confidence,
                status: 'delivered'
            });
            
            updateConnectionStatus('connected');
            
            // Save to chat history
            saveChatHistory();
            
        } else {
            throw new Error(response?.error || 'Failed to send message');
        }
        
    } catch (error) {
        console.error('Enhanced message send error:', error);
        showRetryableError(error.message, () => sendEnhancedMessage());
        updateConnectionStatus('error');
    } finally {
        setInputEnabled(true);
    }
}

// Send message with automatic retry logic
async function sendMessageWithRetry(message, maxRetries = 3) {
    let lastError;
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            updateConnectionStatus(attempt > 1 ? 'reconnecting' : 'connected');
            
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    user_id: chatState.currentUser || `user_${Date.now()}`,
                    conversation_id: chatState.conversationId
                }),
                timeout: 10000 // 10 second timeout
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Update conversation ID if provided
            if (data.conversation_id) {
                chatState.conversationId = data.conversation_id;
            }
            
            return data;
            
        } catch (error) {
            lastError = error;
            console.warn(`Send attempt ${attempt}/${maxRetries} failed:`, error.message);
            
            if (attempt < maxRetries) {
                // Exponential backoff delay
                const delay = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
    }
    
    throw lastError;
}

// Add message to UI with enhanced styling
function addMessageToUI(message) {
    const chatContainer = document.getElementById('onboarding-chat');
    if (!chatContainer) return;
    
    const messageElement = document.createElement('div');
    messageElement.className = `message ${message.type}-message`;
    
    const avatarIcon = message.type === 'user' ? 'fas fa-user' : 'fas fa-robot';
    const avatarLabel = message.type === 'user' ? 'You' : 'AI Guide';
    
    messageElement.innerHTML = `
        <div class="message-avatar">
            <i class="${avatarIcon}"></i>
        </div>
        <div class="message-content">
            <div class="message-header">
                <strong>${avatarLabel}</strong>
                ${message.status ? `<span class="message-status ${message.status}">${message.status}</span>` : ''}
                ${message.confidence ? `<div class="confidence-score">
                    <i class="fas fa-chart-line"></i>
                    <span>${message.confidence}% confidence</span>
                </div>` : ''}
            </div>
            <div class="message-text">${message.content}</div>
            <div class="message-timestamp">${formatTimestamp(message.timestamp)}</div>
        </div>
    `;
    
    chatContainer.appendChild(messageElement);
    
    // Auto-scroll to bottom
    setTimeout(() => {
        messageElement.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }, 100);
    
    // Add animation
    messageElement.style.opacity = '0';
    messageElement.style.transform = 'translateY(20px)';
    setTimeout(() => {
        messageElement.style.transition = 'all 0.3s ease';
        messageElement.style.opacity = '1';
        messageElement.style.transform = 'translateY(0)';
    }, 10);
}

// Show error message with retry option
function showRetryableError(errorMessage, retryCallback) {
    const errorElement = document.createElement('div');
    errorElement.className = 'message error-message';
    errorElement.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-exclamation-triangle"></i>
        </div>
        <div class="message-content">
            <strong>Connection Error</strong>
            ${errorMessage}
            <div class="error-actions">
                <button class="btn btn-sm" onclick="retryLastMessage()">
                    <i class="fas fa-redo"></i> Retry
                </button>
                <button class="btn btn-sm btn-outline" onclick="this.parentElement.parentElement.parentElement.remove()">
                    <i class="fas fa-times"></i> Dismiss
                </button>
            </div>
        </div>
    `;
    
    const chatContainer = document.getElementById('onboarding-chat');
    if (chatContainer) {
        chatContainer.appendChild(errorElement);
        errorElement.scrollIntoView({ behavior: 'smooth' });
    }
    
    // Store retry callback
    window.retryLastMessage = retryCallback;
}

// Helper functions
function setInputEnabled(enabled) {
    const chatInput = document.getElementById('onboarding-input');
    const sendButton = document.getElementById('send-onboarding');
    
    if (chatInput) chatInput.disabled = !enabled;
    if (sendButton) sendButton.disabled = !enabled;
    
    if (sendButton) {
        sendButton.innerHTML = enabled ? 
            '<i class="fas fa-paper-plane"></i> <span>Send</span>' :
            '<i class="fas fa-spinner fa-spin"></i> <span>Sending...</span>';
    }
}

function updateCharacterCount() {
    const chatInput = document.getElementById('onboarding-input');
    const charCounter = document.getElementById('char-count');
    
    if (chatInput && charCounter) {
        charCounter.textContent = chatInput.value.length;
    }
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function showErrorMessage(message) {
    // Create temporary error notification
    const notification = document.createElement('div');
    notification.className = 'error-notification';
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #ff6b6b;
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Chat history management
function saveChatHistory() {
    try {
        const chatContainer = document.getElementById('onboarding-chat');
        if (chatContainer) {
            const messages = Array.from(chatContainer.children)
                .filter(el => el.classList.contains('message'))
                .map(el => ({
                    html: el.outerHTML,
                    timestamp: Date.now()
                }));
            
            localStorage.setItem('chatHistory', JSON.stringify(messages));
        }
    } catch (error) {
        console.warn('Failed to save chat history:', error);
    }
}

function loadChatHistory() {
    try {
        const saved = localStorage.getItem('chatHistory');
        if (saved) {
            const messages = JSON.parse(saved);
            const chatContainer = document.getElementById('onboarding-chat');
            
            if (chatContainer && messages.length > 0) {
                // Keep only recent messages (last 24 hours)
                const dayAgo = Date.now() - (24 * 60 * 60 * 1000);
                const recentMessages = messages.filter(msg => msg.timestamp > dayAgo);
                
                // Clear existing messages except the initial AI greeting
                const existingMessages = chatContainer.querySelectorAll('.message');
                if (existingMessages.length > 1) {
                    Array.from(existingMessages).slice(1).forEach(el => el.remove());
                }
                
                // Add recent messages
                recentMessages.forEach(msg => {
                    chatContainer.insertAdjacentHTML('beforeend', msg.html);
                });
            }
        }
    } catch (error) {
        console.warn('Failed to load chat history:', error);
    }
}

// Connection heartbeat
function startConnectionHeartbeat() {
    setInterval(async () => {
        try {
            const response = await fetch('/health', { method: 'GET' });
            if (response.ok) {
                if (!chatState.isConnected) {
                    updateConnectionStatus('connected');
                    chatState.reconnectAttempts = 0;
                }
            } else {
                throw new Error('Health check failed');
            }
        } catch (error) {
            if (chatState.isConnected) {
                updateConnectionStatus('disconnected');
                attemptReconnection();
            }
        }
    }, 30000); // Check every 30 seconds
}

function attemptReconnection() {
    if (chatState.reconnectAttempts >= chatState.maxReconnectAttempts) {
        updateConnectionStatus('error');
        return;
    }
    
    chatState.reconnectAttempts++;
    updateConnectionStatus('reconnecting');
    
    setTimeout(() => {
        startConnectionHeartbeat();
    }, chatState.reconnectDelay);
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializePeerChat);
} else {
    initializePeerChat();
}

// Export functions for global access
window.sendEnhancedMessage = sendEnhancedMessage;
window.initializePeerChat = initializePeerChat;