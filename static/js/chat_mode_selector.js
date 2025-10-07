/**
 * Chat Mode Selector and Bandwidth Manager
 * Provides user interface for chat mode selection and network status monitoring
 */

class ChatModeSelector {
    constructor(options = {}) {
        this.options = {
            containerId: 'chat-mode-panel',
            autoHide: true,
            hideDelay: 5000,
            showNotifications: true,
            ...options
        };
        
        this.currentMode = 'offline';
        this.bandwidthQuality = 'unknown';
        this.networkType = 'unknown';
        this.isLanAvailable = false;
        this.autoModeEnabled = true;
        this.availableModes = new Set(['offline']);
        
        this.callbacks = {
            onModeChange: [],
            onBandwidthChange: [],
            onModeSelect: []
        };
        
        this.init();
    }
    
    init() {
        this.createUI();
        this.bindEvents();
        this.startBandwidthMonitoring();
        console.log('ChatModeSelector initialized');
    }
    
    createUI() {
        // Create main panel
        const panel = document.createElement('div');
        panel.id = this.options.containerId;
        panel.className = 'chat-mode-panel';
        panel.innerHTML = this.getPanelHTML();
        
        // Add to document
        document.body.appendChild(panel);
        
        // Create notification container
        const notificationContainer = document.createElement('div');
        notificationContainer.id = 'mode-notifications';
        notificationContainer.className = 'mode-notifications';
        document.body.appendChild(notificationContainer);
        
        this.panel = panel;
        this.updateUI();
    }
    
    getPanelHTML() {
        return `
            <div class="mode-status-header">
                <div class="current-mode-indicator">
                    <div class="mode-icon offline" id="current-mode-icon">
                        <i class="fas fa-wifi-slash"></i>
                    </div>
                    <span id="current-mode-text">Offline Mode</span>
                </div>
                <div class="bandwidth-indicator">
                    <div class="bandwidth-bars" id="bandwidth-bars">
                        <div class="bandwidth-bar"></div>
                        <div class="bandwidth-bar"></div>
                        <div class="bandwidth-bar"></div>
                        <div class="bandwidth-bar"></div>
                    </div>
                    <span id="bandwidth-text">Unknown</span>
                </div>
            </div>
            
            <div class="mode-selector">
                <h4>
                    <i class="fas fa-network-wired"></i>
                    Connection Mode
                </h4>
                <div class="mode-options" id="mode-options">
                    <!-- Mode options will be populated dynamically -->
                </div>
            </div>
            
            <div class="auto-mode-toggle">
                <span>Auto-select best mode</span>
                <div class="toggle-switch active" id="auto-toggle">
                </div>
            </div>
            
            <div class="network-details">
                <div class="network-item">
                    <span class="network-label">Network Type:</span>
                    <span class="network-value" id="network-type">Unknown</span>
                </div>
                <div class="network-item">
                    <span class="network-label">LAN Available:</span>
                    <span class="network-value" id="lan-status">No</span>
                </div>
                <div class="network-item">
                    <span class="network-label">Connection Quality:</span>
                    <span class="network-value" id="connection-quality">Unknown</span>
                </div>
            </div>
        `;
    }
    
    bindEvents() {
        // Auto-mode toggle
        const autoToggle = document.getElementById('auto-toggle');
        autoToggle.addEventListener('click', () => {
            this.toggleAutoMode();
        });
        
        // Mode option selection (delegated event)
        const modeOptions = document.getElementById('mode-options');
        modeOptions.addEventListener('click', (e) => {
            const option = e.target.closest('.mode-option');
            if (option && !option.classList.contains('disabled')) {
                const mode = option.dataset.mode;
                this.selectMode(mode);
            }
        });
        
        // Panel auto-hide
        if (this.options.autoHide) {
            let hideTimeout;
            
            this.panel.addEventListener('mouseenter', () => {
                clearTimeout(hideTimeout);
                this.panel.style.opacity = '1';
            });
            
            this.panel.addEventListener('mouseleave', () => {
                hideTimeout = setTimeout(() => {
                    this.panel.style.opacity = '0.7';
                }, this.options.hideDelay);
            });
        }
    }
    
    startBandwidthMonitoring() {
        // Simulate bandwidth monitoring (replace with real implementation)
        setInterval(() => {
            this.detectBandwidth();
            this.detectNetworkType();
            this.detectLanAvailability();
            this.updateAvailableModes();
            
            if (this.autoModeEnabled) {
                this.autoSelectMode();
            }
        }, 5000);
        
        // Initial detection
        this.detectBandwidth();
        this.detectNetworkType();
        this.detectLanAvailability();
        this.updateAvailableModes();
    }
    
    detectBandwidth() {
        // Use Navigator Connection API if available
        if ('connection' in navigator) {
            const connection = navigator.connection;
            const effectiveType = connection.effectiveType;
            
            let quality = 'unknown';
            if (effectiveType === '4g' || effectiveType === 'wifi') {
                quality = 'high';
            } else if (effectiveType === '3g') {
                quality = 'medium';
            } else if (effectiveType === '2g' || effectiveType === 'slow-2g') {
                quality = 'low';
            }
            
            this.updateBandwidth(quality, connection.type || 'unknown');
        } else {
            // Fallback bandwidth test
            this.performBandwidthTest().then(quality => {
                this.updateBandwidth(quality, 'unknown');
            });
        }
    }
    
    async performBandwidthTest() {
        try {
            const startTime = performance.now();
            
            // Download small test file or make API call
            const response = await fetch('/api/p2p-chat/health', {
                cache: 'no-cache'
            });
            
            const endTime = performance.now();
            const duration = endTime - startTime;
            
            // Estimate bandwidth quality based on response time
            if (duration < 100) return 'high';
            if (duration < 300) return 'medium';
            return 'low';
            
        } catch (error) {
            console.warn('Bandwidth test failed:', error);
            return 'unknown';
        }
    }
    
    detectNetworkType() {
        // Simple network type detection
        let networkType = 'unknown';
        
        if ('connection' in navigator) {
            networkType = navigator.connection.type || 'unknown';
        }
        
        this.networkType = networkType;
        this.updateUI();
    }
    
    detectLanAvailability() {
        // Check if we're on a local network
        const hostname = window.location.hostname;
        const isLocal = hostname === 'localhost' || 
                       hostname === '127.0.0.1' ||
                       hostname.startsWith('192.168.') ||
                       hostname.startsWith('10.') ||
                       hostname.startsWith('172.');
        
        this.isLanAvailable = isLocal;
        this.updateUI();
    }
    
    updateBandwidth(quality, type) {
        const oldQuality = this.bandwidthQuality;
        this.bandwidthQuality = quality;
        this.networkType = type;
        
        if (oldQuality !== quality) {
            this.triggerCallback('onBandwidthChange', { quality, type });
            
            if (this.options.showNotifications) {
                this.showNotification({
                    title: 'Connection Quality Changed',
                    message: `Bandwidth quality is now: ${quality.toUpperCase()}`,
                    type: quality === 'high' ? 'success' : quality === 'medium' ? 'warning' : 'error',
                    duration: 3000
                });
            }
        }
        
        this.updateUI();
    }
    
    updateAvailableModes() {
        this.availableModes.clear();
        this.availableModes.add('offline'); // Always available
        
        // Add modes based on bandwidth and network availability
        if (this.bandwidthQuality === 'high') {
            this.availableModes.add('high_global');
            this.availableModes.add('low_global');
            if (this.isLanAvailable) {
                this.availableModes.add('lan_high');
                this.availableModes.add('lan_low');
            }
        } else if (this.bandwidthQuality === 'medium') {
            this.availableModes.add('high_global');
            this.availableModes.add('low_global');
            if (this.isLanAvailable) {
                this.availableModes.add('lan_low');
            }
        } else if (this.bandwidthQuality === 'low') {
            this.availableModes.add('low_global');
            if (this.isLanAvailable) {
                this.availableModes.add('lan_low');
            }
        }
        
        this.updateModeOptions();
    }
    
    autoSelectMode() {
        const modePriority = ['high_global', 'lan_high', 'low_global', 'lan_low', 'offline'];
        
        for (const mode of modePriority) {
            if (this.availableModes.has(mode)) {
                if (mode !== this.currentMode) {
                    this.changeMode(mode, true);
                }
                break;
            }
        }
    }
    
    selectMode(mode) {
        if (!this.availableModes.has(mode)) {
            this.showNotification({
                title: 'Mode Not Available',
                message: `${this.getModeDisplayName(mode)} is not available with current connection.`,
                type: 'warning',
                duration: 3000
            });
            return false;
        }
        
        this.autoModeEnabled = false;
        this.changeMode(mode, false);
        this.updateAutoToggle();
        
        this.showNotification({
            title: 'Mode Changed',
            message: `Switched to ${this.getModeDisplayName(mode)}`,
            type: 'success',
            duration: 2000
        });
        
        return true;
    }
    
    changeMode(newMode, autoSelected) {
        const oldMode = this.currentMode;
        this.currentMode = newMode;
        
        this.triggerCallback('onModeChange', {
            oldMode,
            newMode,
            autoSelected,
            modeInfo: this.getModeInfo()
        });
        
        this.updateUI();
        
        console.log(`Mode changed: ${oldMode} -> ${newMode} (${autoSelected ? 'auto' : 'manual'})`);
    }
    
    toggleAutoMode() {
        this.autoModeEnabled = !this.autoModeEnabled;
        this.updateAutoToggle();
        
        if (this.autoModeEnabled) {
            this.autoSelectMode();
            this.showNotification({
                title: 'Auto Mode Enabled',
                message: 'Best connection mode will be selected automatically',
                type: 'success',
                duration: 2000
            });
        } else {
            this.showNotification({
                title: 'Manual Mode',
                message: 'Select your preferred connection mode manually',
                type: 'info',
                duration: 2000
            });
        }
    }
    
    updateUI() {
        this.updateCurrentModeDisplay();
        this.updateBandwidthDisplay();
        this.updateNetworkDetails();
        this.updateModeOptions();
    }
    
    updateCurrentModeDisplay() {
        const icon = document.getElementById('current-mode-icon');
        const text = document.getElementById('current-mode-text');
        
        if (icon && text) {
            icon.className = `mode-icon ${this.getModeClass(this.currentMode)}`;
            icon.innerHTML = this.getModeIcon(this.currentMode);
            text.textContent = this.getModeDisplayName(this.currentMode);
            
            // Add pulse animation for active mode
            icon.classList.add('pulse');
            setTimeout(() => icon.classList.remove('pulse'), 2000);
        }
    }
    
    updateBandwidthDisplay() {
        const bars = document.getElementById('bandwidth-bars');
        const text = document.getElementById('bandwidth-text');
        
        if (bars && text) {
            bars.className = `bandwidth-bars bandwidth-${this.bandwidthQuality}`;
            text.textContent = this.bandwidthQuality.toUpperCase();
        }
    }
    
    updateNetworkDetails() {
        const networkType = document.getElementById('network-type');
        const lanStatus = document.getElementById('lan-status');
        const connectionQuality = document.getElementById('connection-quality');
        
        if (networkType) networkType.textContent = this.networkType.toUpperCase();
        if (lanStatus) lanStatus.textContent = this.isLanAvailable ? 'Yes' : 'No';
        if (connectionQuality) connectionQuality.textContent = this.bandwidthQuality.toUpperCase();
    }
    
    updateModeOptions() {
        const container = document.getElementById('mode-options');
        if (!container) return;
        
        const modes = [
            { id: 'high_global', name: '🌐 Global Chat (High Speed)', desc: 'Full-featured global chat with rich media' },
            { id: 'low_global', name: '🌐 Global Chat (Low Bandwidth)', desc: 'Text-focused global chat for slow connections' },
            { id: 'lan_high', name: '🏠 LAN Chat (High Speed)', desc: 'Local network chat with full features' },
            { id: 'lan_low', name: '🏠 LAN Chat (Low Bandwidth)', desc: 'Local network chat optimized for slow connections' },
            { id: 'offline', name: '📱 Offline Mode', desc: 'Local-only mode, sync when connected' }
        ];
        
        container.innerHTML = modes.map(mode => {
            const isAvailable = this.availableModes.has(mode.id);
            const isCurrent = mode.id === this.currentMode;
            const isRecommended = this.getRecommendedMode() === mode.id;
            
            return `
                <div class="mode-option ${isCurrent ? 'selected' : ''} ${!isAvailable ? 'disabled' : ''}" 
                     data-mode="${mode.id}">
                    <div class="mode-info">
                        <div class="mode-name">${mode.name}</div>
                        <div class="mode-description">${mode.desc}</div>
                    </div>
                    <div class="mode-status">
                        ${isCurrent ? '<span class="status-badge current">Current</span>' : ''}
                        ${isRecommended && !isCurrent ? '<span class="status-badge recommended">Recommended</span>' : ''}
                        ${!isAvailable ? '<span class="status-badge disabled">Unavailable</span>' : ''}
                    </div>
                </div>
            `;
        }).join('');
    }
    
    updateAutoToggle() {
        const toggle = document.getElementById('auto-toggle');
        if (toggle) {
            toggle.classList.toggle('active', this.autoModeEnabled);
        }
    }
    
    getRecommendedMode() {
        if (this.bandwidthQuality === 'high') {
            return this.isLanAvailable ? 'lan_high' : 'high_global';
        } else if (this.bandwidthQuality === 'medium') {
            return 'high_global';
        } else if (this.bandwidthQuality === 'low') {
            return this.isLanAvailable ? 'lan_low' : 'low_global';
        }
        return 'offline';
    }
    
    getModeDisplayName(mode) {
        const names = {
            'high_global': '🌐 Global Chat (High Speed)',
            'low_global': '🌐 Global Chat (Low Bandwidth)',
            'lan_high': '🏠 LAN Chat (High Speed)',
            'lan_low': '🏠 LAN Chat (Low Bandwidth)',
            'offline': '📱 Offline Mode'
        };
        return names[mode] || mode;
    }
    
    getModeClass(mode) {
        const classes = {
            'high_global': 'global-high',
            'low_global': 'global-low',
            'lan_high': 'lan-high',
            'lan_low': 'lan-low',
            'offline': 'offline'
        };
        return classes[mode] || 'offline';
    }
    
    getModeIcon(mode) {
        const icons = {
            'high_global': '<i class="fas fa-globe"></i>',
            'low_global': '<i class="fas fa-globe"></i>',
            'lan_high': '<i class="fas fa-home"></i>',
            'lan_low': '<i class="fas fa-home"></i>',
            'offline': '<i class="fas fa-wifi-slash"></i>'
        };
        return icons[mode] || '<i class="fas fa-question"></i>';
    }
    
    getModeInfo() {
        return {
            currentMode: this.currentMode,
            bandwidthQuality: this.bandwidthQuality,
            networkType: this.networkType,
            isLanAvailable: this.isLanAvailable,
            autoModeEnabled: this.autoModeEnabled,
            availableModes: Array.from(this.availableModes),
            recommendedMode: this.getRecommendedMode()
        };
    }
    
    showNotification(options) {
        if (!this.options.showNotifications) return;
        
        const notification = document.createElement('div');
        notification.className = `mode-notification ${options.type || 'info'}`;
        notification.innerHTML = `
            <div class="notification-header">
                <span class="notification-title">${options.title}</span>
                <button class="notification-close">&times;</button>
            </div>
            <div class="notification-body">
                ${options.message}
            </div>
        `;
        
        // Add to container
        const container = document.getElementById('mode-notifications');
        container.appendChild(notification);
        
        // Show notification
        setTimeout(() => notification.classList.add('show'), 100);
        
        // Bind close event
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.addEventListener('click', () => {
            this.hideNotification(notification);
        });
        
        // Auto-hide
        if (options.duration) {
            setTimeout(() => {
                if (notification.parentNode) {
                    this.hideNotification(notification);
                }
            }, options.duration);
        }
    }
    
    hideNotification(notification) {
        notification.classList.remove('show');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 400);
    }
    
    // Callback management
    on(event, callback) {
        if (this.callbacks[event]) {
            this.callbacks[event].push(callback);
        }
    }
    
    triggerCallback(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Callback error for ${event}:`, error);
                }
            });
        }
    }
    
    // Public API
    getCurrentMode() {
        return this.getModeInfo();
    }
    
    setMode(mode) {
        return this.selectMode(mode);
    }
    
    enableAutoMode() {
        this.autoModeEnabled = true;
        this.updateAutoToggle();
        this.autoSelectMode();
    }
    
    disableAutoMode() {
        this.autoModeEnabled = false;
        this.updateAutoToggle();
    }
    
    destroy() {
        if (this.panel) {
            this.panel.remove();
        }
        const notifications = document.getElementById('mode-notifications');
        if (notifications) {
            notifications.remove();
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChatModeSelector;
} else if (typeof window !== 'undefined') {
    window.ChatModeSelector = ChatModeSelector;
}