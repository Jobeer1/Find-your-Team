    // Global state management
    let currentSection = 'onboarding';
    let chatMessages = [];
    let userProfile = {};
    let matches = [];
    let teamData = {};
    let socket = null;
    let isTyping = false;
    let currentAgent = 'onboarding';
    let gamificationData = {
        level: 1,
        xp: 0,
        xpToNext: 100,
        achievements: []
    };

    // Make functions globally available
    window.scrollToOnboarding = scrollToOnboarding;
    window.sendOnboardingMessage = sendOnboardingMessage;
    window.copyShareLink = copyShareLink;
    window.shareOnTwitter = shareOnTwitter;
    window.shareOnLinkedIn = shareOnLinkedIn;
    window.shareOnFacebook = shareOnFacebook;
    window.findMatches = findMatches;
    window.generateRetrospective = generateRetrospective;
    window.getCoachingInsight = getCoachingInsight;

    // Initialize the application
    document.addEventListener('DOMContentLoaded', function() {
        initializeApp();
        setupEventListeners();
        initializeParticles();
        initializeSocket();
        loadUserData();
        updateGamification();
    });

    function initializeApp() {
        // Show initial section
        showSection('onboarding');
        
        // Initialize chat
        initializeChat();
        
        // Load any saved data
        loadSavedData();
        
        // Initialize animations
        AOS.init({
            duration: 800,
            once: true,
            offset: 100
        });
    }

    function setupEventListeners() {
        // Navigation
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', handleNavigation);
        });

        // Chat input
        const chatInput = document.getElementById('chat-input');
        if (chatInput) {
            chatInput.addEventListener('input', handleInputChange);
            chatInput.addEventListener('keydown', handleKeyPress);
        }

        const sendButton = document.getElementById('send-button');
        if (sendButton) {
            sendButton.addEventListener('click', sendMessage);
        }

        // File upload
        const fileInput = document.getElementById('file-input');
        if (fileInput) {
            fileInput.addEventListener('change', handleFileUpload);
        }

        // Match and team actions
        document.addEventListener('click', handleMatchActions);
        document.addEventListener('click', handleTeamActions);

        // Share buttons
        document.querySelectorAll('.share-btn').forEach(btn => {
            btn.addEventListener('click', handleShare);
        });

        // Ensure onboarding controls are wired when present
        const onboardingSend = document.getElementById('send-onboarding');
        if (onboardingSend) {
            onboardingSend.removeAttribute('onclick');
            onboardingSend.addEventListener('click', sendOnboardingMessage);
        }

        const heroCta = document.querySelector('.hero-cta .btn.btn-primary');
        if (heroCta) {
            heroCta.removeAttribute('onclick');
            heroCta.addEventListener('click', scrollToOnboarding);
        }

        // Onboarding input character counter and auto-resize
        const onboardingInput = document.getElementById('onboarding-input');
        if (onboardingInput) {
            onboardingInput.addEventListener('input', function(e) {
                handleInputChange(e);
            });
            onboardingInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendOnboardingMessage();
                }
            });
        }

        // Connection status
        updateConnectionStatus();

        // Window resize
        window.addEventListener('resize', handleResize);
        
        // Initialize team performance dashboard
        setTimeout(() => {
            loadTeamPerformance();
            // Show welcome notification for Task 8 completion
            showNotification(
                '🎉 Team Agent Performance Monitoring is now live! Check out the Team Performance Dashboard below.',
                'success',
                8000
            );
        }, 2000); // Load after page is fully initialized
    }

    function scrollToOnboarding() {
        console.log('Scrolling to onboarding section...');
        
        // First try to find the onboarding section
        const target = document.getElementById('onboarding-section');
        
        if (target) {
            // Calculate the position accounting for the fixed navbar
            const navbarHeight = document.querySelector('.navbar')?.offsetHeight || 80;
            const targetPosition = target.offsetTop - navbarHeight - 20;
            
            // Smooth scroll to the target
            window.scrollTo({
                top: targetPosition,
                behavior: 'smooth'
            });
            
            // Focus the input field after scrolling
            setTimeout(() => {
                const input = document.getElementById('onboarding-input');
                if (input) {
                    input.focus();
                    // Add a visual highlight to show the user where to type
                    input.style.boxShadow = '0 0 0 3px rgba(0, 122, 77, 0.3)';
                    setTimeout(() => {
                        input.style.boxShadow = '';
                    }, 2000);
                }
            }, 800);
        } else {
            console.warn('Onboarding section not found, using fallback scroll');
            // Fallback: scroll to approximately where onboarding should be
            window.scrollTo({ 
                top: window.innerHeight * 0.8, 
                behavior: 'smooth' 
            });
        }
    }

    // Show detailed error popup
    function showErrorPopup(title, message, details) {
        // Remove existing popup if any
        const existingPopup = document.querySelector('.error-popup');
        if (existingPopup) {
            existingPopup.remove();
        }
        
        // Create popup HTML
        const popup = document.createElement('div');
        popup.className = 'error-popup';
        popup.innerHTML = `
            <div class="error-popup-overlay">
                <div class="error-popup-content">
                    <div class="error-popup-header">
                        <h3>${title}</h3>
                        <button class="error-popup-close">&times;</button>
                    </div>
                    <div class="error-popup-body">
                        <p class="error-message">${message}</p>
                        ${details ? `<div class="error-details"><strong>Details:</strong> ${details}</div>` : ''}
                        <div class="error-solution">
                            <strong>What can you do?</strong>
                            <ul>
                                <li>Use the demo version with limited features</li>
                                <li>Contact support for full access credentials</li>
                                <li>Check your internet connection</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(popup);
        
        // Add event listeners
        popup.querySelector('.error-popup-close').addEventListener('click', () => {
            popup.remove();
        });
        popup.querySelector('.error-popup-overlay').addEventListener('click', (e) => {
            if (e.target === popup.querySelector('.error-popup-overlay')) {
                popup.remove();
            }
        });
        
        // Auto-remove after 10 seconds
        setTimeout(() => {
            if (popup.parentNode) {
                popup.remove();
            }
        }, 10000);
    }

    function sendOnboardingMessage() {
        const input = document.getElementById('onboarding-input');
        if (!input) {
            return;
        }

        const message = input.value.trim();
        if (!message) {
            return;
        }

        try {
            addMessage('user', message);
        } catch (error) {
            console.warn('sendOnboardingMessage: addMessage unavailable', error);
        }

        input.value = '';
        const charCount = document.getElementById('char-count');
        if (charCount) {
            charCount.textContent = '0';
        }

        try {
            fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: message,
                    user_id: getUserId(),
                    conversation_id: getConversationId()
                })
            })
                .then(response => {
                    if (!response.ok) {
                        if (response.status === 503) {
                            return response.json().then(errorData => {
                                addMessage('agent', 'Demo mode: I understand you want to find your team! While full AI features require AWS setup, I can still help you get started. What interests you most about team building?', 0.8);
                                throw new Error('Service unavailable');
                            });
                        } else if (response.status >= 500) {
                            addMessage('agent', 'Sorry, there was a server error. Please try again in a moment.', 0);
                            throw new Error('Server error');
                        }
                    }
                    return response.json();
                })
                .then(data => {
                    if (data && data.message) {
                        addMessage('agent', data.message, data.confidence);
                    }
                    if (data && data.conversation_id) {
                        setConversationId(data.conversation_id);
                    }
                    if (data && data.confidence !== undefined) {
                        updateConfidenceScore(data.confidence);
                    }
                    if (data && data.profile_complete) {
                        handleProfileCompletion(data.conversation_id);
                    }
                    if (data && data.action) {
                        handleAgentAction(data.action);
                    }
                })
                .catch(error => {
                    console.error('sendOnboardingMessage fetch error', error);
                    if (error.message === 'Service unavailable' || error.message === 'Server error') {
                        return; // Already handled above
                    }
                    
                    let errorMessage = 'Sorry, I encountered an error. Please try again.';
                    if (error.name === 'TypeError' && error.message.includes('fetch')) {
                        errorMessage = 'Connection issue: Please check your internet connection and try again.';
                    }
                    
                    addMessage('agent', errorMessage, 0);
                });
        } catch (error) {
            console.error('sendOnboardingMessage error', error);
            showErrorPopup(
                'System Error',
                'A system error occurred while sending your message.',
                error.message
            );
        }
    }

    function copyShareLink() {
        const url = window.location.href;

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(url)
                .then(() => {
                    showNotification('Link copied to clipboard!', 'success');
                })
                .catch(error => console.error('copyShareLink failed', error));
            return;
        }

        const temp = document.createElement('textarea');
        temp.value = url;
        document.body.appendChild(temp);
        temp.select();
        try {
            document.execCommand('copy');
            showNotification('Link copied to clipboard!', 'success');
        } catch (error) {
            console.error('copyShareLink fallback failed', error);
        }
        temp.remove();
    }

    function shareOnTwitter() {
        handleShare({ target: { dataset: { platform: 'twitter' } } });
    }

    function shareOnLinkedIn() {
        handleShare({ target: { dataset: { platform: 'linkedin' } } });
    }

    function shareOnFacebook() {
        handleShare({ target: { dataset: { platform: 'facebook' } } });
    }

    function findMatches() {
        showNotification('Finding matches...', 'info');
        const results = document.getElementById('matches-results');
        if (results) {
            results.innerHTML = '<div class="placeholder">Searching for matches... (demo)</div>';
        }
        try {
            showSection('matching');
        } catch (error) {
            console.warn('findMatches: unable to switch section', error);
        }
    }

    function generateRetrospective() {
        showNotification('Generating retrospective...', 'info');
        const target = document.getElementById('retrospective-results');
        if (target) {
            target.innerHTML = '<p>Retrospective generation is in demo mode. Try again in production.</p>';
        }
    }

    function getCoachingInsight() {
        showNotification('Getting coaching insight...', 'info');
        const target = document.getElementById('coaching-results');
        if (target) {
            target.innerHTML = '<p>Coaching insights are not available in demo mode.</p>';
        }
    }

    function messageMember(memberId) {
        try {
            showSection('onboarding');
        } catch (error) {
            console.warn('messageMember: showSection unavailable', error);
        }

        const input = document.getElementById('onboarding-input');
        if (input) {
            input.value = `@${memberId} `;
            try {
                input.focus();
            } catch (error) {
                console.debug('messageMember: unable to focus input', error);
            }
        }

        showNotification(`Prepared a message to ${memberId}`, 'info');
    }

    function initializeParticles() {
        particlesJS('particles-js', {
            particles: {
                number: { value: 80, density: { enable: true, value_area: 800 } },
                color: { value: '#ffffff' },
                shape: { type: 'circle' },
                opacity: { value: 0.5, random: true },
                size: { value: 3, random: true },
                line_linked: {
                    enable: true,
                    distance: 150,
                    color: '#ffffff',
                    opacity: 0.4,
                    width: 1
                },
                move: {
                    enable: true,
                    speed: 2,
                    direction: 'none',
                    random: true,
                    straight: false,
                    out_mode: 'out',
                    bounce: false
                }
            },
            interactivity: {
                detect_on: 'canvas',
                events: {
                    onhover: { enable: true, mode: 'repulse' },
                    onclick: { enable: true, mode: 'push' },
                    resize: true
                }
            },
            retina_detect: true
        });
    }

    function initializeSocket() {
        socket = io();
        
        socket.on('connect', function() {
            updateConnectionStatus(true);
        });
        
        socket.on('disconnect', function() {
            updateConnectionStatus(false);
        });
        
        socket.on('message', function(data) {
            receiveMessage(data);
        });
        
        socket.on('typing', function(data) {
            showTypingIndicator(data.agent);
        });
        
        socket.on('match_found', function(data) {
            handleMatchFound(data);
        });
        
        socket.on('team_update', function(data) {
            handleTeamUpdate(data);
        });
        
        socket.on('gamification_update', function(data) {
            updateGamification(data);
        });
    }

    function initializeChat() {
        const chatMessagesElement = document.getElementById('chat-messages');
        if (chatMessagesElement) {
            chatMessagesElement.scrollTop = chatMessagesElement.scrollHeight;
        }
    }

    function handleNavigation(e) {
        e.preventDefault();
        const targetSection = e.target.dataset.section;
        if (targetSection) {
            showSection(targetSection);
            updateNavigation(targetSection);
        }
    }

    function showSection(sectionId) {
        // Hide all sections
        document.querySelectorAll('.section').forEach(section => {
            section.style.display = 'none';
        });
        
        // Show target section
        const targetSection = document.getElementById(sectionId);
        if (targetSection) {
            targetSection.style.display = 'block';
            currentSection = sectionId;
            
            // Trigger animations
            setTimeout(() => {
                targetSection.classList.add('fade-in');
            }, 100);
        }
    }

    function updateNavigation(activeSection) {
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
            if (link.dataset.section === activeSection) {
                link.classList.add('active');
            }
        });
    }

    function handleInputChange(e) {
        const input = e.target;
        const charCount = input.value.length;
        const maxChars = 1000;
        
        // Update character counter
        const counter = document.querySelector('.char-counter');
        const charCountElement = document.getElementById('char-count');
        
        if (counter) {
            counter.textContent = `${charCount}/${maxChars}`;
            counter.style.color = charCount > maxChars * 0.9 ? '#FFD700' : '#8e9aaf';
        }
        
        if (charCountElement) {
            charCountElement.textContent = charCount.toString();
        }
        
        // Auto-resize textarea
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 200) + 'px';
        
        // Enable/disable send button
        const sendButton = document.getElementById('send-button') || document.getElementById('send-onboarding');
        if (sendButton) {
            sendButton.disabled = charCount === 0 || charCount > maxChars;
        }
    }

    function handleKeyPress(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    }

    async function sendMessage() {
        const input = document.getElementById('chat-input');
        if (!input) {
            return;
        }
        const message = input.value.trim();
        
        if (!message) return;
        
        // Add user message to chat
        addMessage('user', message);
        
        // Clear input
        input.value = '';
        handleInputChange({ target: input });
        
        // Show typing indicator
        showTypingIndicator(currentAgent);
        
        // Send to server
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    agent: currentAgent,
                    user_id: getUserId()
                })
            });
            
            const data = await response.json();
            
            // Hide typing indicator
            hideTypingIndicator();
            
            // Add agent response
            addMessage('agent', data.message, data.confidence);
            
            // Handle any actions
            if (data.action) {
                handleAgentAction(data.action);
            }
            
        } catch (error) {
            console.error('Error sending message:', error);
            hideTypingIndicator();
            addMessage('agent', 'Sorry, I encountered an error. Please try again.', 0);
        }
    }

    function receiveMessage(data) {
        if (!data) {
            return;
        }

        if (data.message) {
            addMessage('agent', data.message, data.confidence);
        }

        if (data.action) {
            handleAgentAction(data.action);
        }
    }

    function addMessage(type, content, confidence = null) {
        const messagesContainer = document.getElementById('chat-messages') || document.getElementById('onboarding-chat');
        if (!messagesContainer) {
            console.warn('addMessage: No chat container found');
            return;
        }
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        
        const avatar = type === 'user' ? 'U' : getAgentAvatar(currentAgent);
        const avatarClass = type === 'user' ? 'user-message' : 'agent-message';
        
        messageDiv.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                <div>${content}</div>
                ${confidence !== null ? `<div class="confidence-score"><i class="fas fa-star"></i> ${Math.round(confidence * 100)}% confidence</div>` : ''}
            </div>
        `;
        
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        // Store message
        chatMessages.push({
            type: type,
            content: content,
            timestamp: new Date(),
            confidence: confidence
        });
    }

    function getAgentAvatar(agent) {
        const avatars = {
            'onboarding': '🤝',
            'matching': '🎯',
            'team': '👥',
            'integration': '🔗'
        };
        return avatars[agent] || '🤖';
    }

    function showTypingIndicator(agent) {
        if (isTyping) return;
        
        isTyping = true;
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) {
            isTyping = false;
            return;
        }
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message agent-message typing-indicator';
        typingDiv.id = 'typing-indicator';
        
        typingDiv.innerHTML = `
            <div class="message-avatar">${getAgentAvatar(agent)}</div>
            <div class="message-content">
                <div class="loading">
                    <span class="loading-dots">
                        <span class="loading-dot"></span>
                        <span class="loading-dot"></span>
                        <span class="loading-dot"></span>
                    </span>
                    <span>${getAgentName(agent)} is typing...</span>
                </div>
            </div>
        `;
        
        messagesContainer.appendChild(typingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function hideTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
        isTyping = false;
    }

    function getAgentName(agent) {
        const names = {
            'onboarding': 'Onboarding Agent',
            'matching': 'Matching Agent',
            'team': 'Team Agent',
            'integration': 'Integration Agent'
        };
        return names[agent] || 'AI Agent';
    }

    function handleAgentAction(action) {
        switch (action.type) {
            case 'show_matches':
                showMatches(action.data);
                break;
            case 'show_team':
                showTeam(action.data);
                break;
            case 'update_profile':
                updateUserProfile(action.data);
                break;
            case 'navigate':
                showSection(action.section);
                break;
            case 'gamification':
                updateGamification(action.data);
                break;
        }
    }

    function showMatches(matchData) {
        matches = matchData;
        const matchesContainer = document.getElementById('matches-container');
        const matchesGrid = document.getElementById('matches-grid');
        
        matchesGrid.innerHTML = '';
        
        matchData.forEach(match => {
            const matchCard = createMatchCard(match);
            matchesGrid.appendChild(matchCard);
        });
        
        matchesContainer.style.display = 'block';
        showSection('matching');
        
        // Animate cards
        setTimeout(() => {
            document.querySelectorAll('.match-card').forEach((card, index) => {
                setTimeout(() => {
                    card.classList.add('scale-in');
                }, index * 200);
            });
        }, 100);
    }

    function createMatchCard(match) {
        const card = document.createElement('div');
        card.className = 'match-card';
        card.dataset.matchId = match.id;
        
        card.innerHTML = `
            <div class="match-header">
                <div class="match-icon">${getMatchIcon(match.type)}</div>
                <h3 class="match-title">${match.name}</h3>
            </div>
            <div class="match-scores">
                <div class="score-badge alignment">
                    <i class="fas fa-handshake"></i>
                    ${match.alignment_score}% Alignment
                </div>
                <div class="score-badge growth">
                    <i class="fas fa-chart-line"></i>
                    ${match.growth_score}% Growth
                </div>
            </div>
            <p class="match-description">${match.description}</p>
            <div class="match-tags">
                ${match.skills.map(skill => `<span class="match-tag">${skill}</span>`).join('')}
            </div>
            <div class="match-actions">
                <button class="btn btn-primary connect-btn" data-match-id="${match.id}">
                    <i class="fas fa-user-plus"></i>
                    Connect
                </button>
                <button class="btn btn-outline view-profile-btn" data-match-id="${match.id}">
                    <i class="fas fa-eye"></i>
                    View Profile
                </button>
            </div>
        `;
        
        return card;
    }

    function getMatchIcon(type) {
        const icons = {
            'mentor': '👨‍🏫',
            'collaborator': '🤝',
            'investor': '💰',
            'partner': '🤝',
            'team_member': '👥'
        };
        return icons[type] || '🎯';
    }

    function showTeam(teamData) {
        const teamSection = document.getElementById('team-section');
        const metricsGrid = document.getElementById('metrics-grid');
        
        // Update metrics
        updateTeamMetrics(teamData.metrics);
        
        // Show team members
        updateTeamMembers(teamData.members);
        
        teamSection.style.display = 'block';
        showSection('team');
    }

    function updateTeamMetrics(metrics) {
        const metricsGrid = document.getElementById('metrics-grid');
        
        metricsGrid.innerHTML = `
            <div class="metric-card">
                <div class="metric-icon"><i class="fas fa-users"></i></div>
                <div class="metric-value">${metrics.team_size}</div>
                <div class="metric-label">Team Members</div>
                <div class="metric-trend ${getTrendClass(metrics.team_size_trend)}">
                    ${getTrendIcon(metrics.team_size_trend)} ${Math.abs(metrics.team_size_trend)}%
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-icon"><i class="fas fa-chart-line"></i></div>
                <div class="metric-value">${metrics.productivity}%</div>
                <div class="metric-label">Productivity</div>
                <div class="metric-trend ${getTrendClass(metrics.productivity_trend)}">
                    ${getTrendIcon(metrics.productivity_trend)} ${Math.abs(metrics.productivity_trend)}%
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-icon"><i class="fas fa-heart"></i></div>
                <div class="metric-value">${metrics.satisfaction}%</div>
                <div class="metric-label">Satisfaction</div>
                <div class="metric-trend ${getTrendClass(metrics.satisfaction_trend)}">
                    ${getTrendIcon(metrics.satisfaction_trend)} ${Math.abs(metrics.satisfaction_trend)}%
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-icon"><i class="fas fa-trophy"></i></div>
                <div class="metric-value">${metrics.achievements}</div>
                <div class="metric-label">Achievements</div>
                <div class="metric-trend up">
                    <i class="fas fa-arrow-up"></i> New
                </div>
            </div>
        `;
    }

    function getTrendClass(trend) {
        if (trend > 0) return 'up';
        if (trend < 0) return 'down';
        return 'stable';
    }

    function getTrendIcon(trend) {
        if (trend > 0) return '<i class="fas fa-arrow-up"></i>';
        if (trend < 0) return '<i class="fas fa-arrow-down"></i>';
        return '<i class="fas fa-minus"></i>';
    }

    function updateTeamMembers(members) {
        const teamMembers = document.getElementById('team-members');
        teamMembers.innerHTML = '';
        
        members.forEach(member => {
            const memberCard = document.createElement('div');
            memberCard.className = 'team-member-card';
            memberCard.innerHTML = `
                <div class="member-avatar">${member.avatar || '👤'}</div>
                <div class="member-info">
                    <h4>${member.name}</h4>
                    <p>${member.role}</p>
                    <div class="member-status ${member.status}">
                        <span class="status-dot"></span>
                        ${member.status}
                    </div>
                </div>
                <div class="member-actions">
                    <button class="btn btn-sm" onclick="messageMember('${member.id}')">
                        <i class="fas fa-envelope"></i>
                    </button>
                </div>
            `;
            teamMembers.appendChild(memberCard);
        });
    }

    function handleMatchActions(e) {
        const target = e.target;
        
        if (target.classList.contains('connect-btn')) {
            const matchId = target.dataset.matchId;
            connectWithMatch(matchId);
        } else if (target.classList.contains('view-profile-btn')) {
            const matchId = target.dataset.matchId;
            viewMatchProfile(matchId);
        }
    }

    function handleTeamActions(e) {
        const target = e.target;
        
        if (target.classList.contains('invite-member-btn')) {
            showInviteModal();
        } else if (target.classList.contains('schedule-meeting-btn')) {
            scheduleTeamMeeting();
        }
    }

    function connectWithMatch(matchId) {
        const match = matches.find(m => m.id === matchId);
        if (match) {
            // Send connection request
            socket.emit('connect_request', {
                match_id: matchId,
                user_id: getUserId()
            });
            
            // Show success message
            showNotification('Connection request sent!', 'success');
            
            // Update button state
            const button = document.querySelector(`[data-match-id="${matchId}"].connect-btn`);
            button.innerHTML = '<i class="fas fa-check"></i> Requested';
            button.disabled = true;
        }
    }

    function viewMatchProfile(matchId) {
        const match = matches.find(m => m.id === matchId);
        if (match) {
            // Show profile modal
            showProfileModal(match);
        }
    }

    function showProfileModal(profile) {
        const modal = document.createElement('div');
        modal.className = 'modal profile-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>${profile.name}</h3>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="profile-header">
                        <div class="profile-avatar">${getMatchIcon(profile.type)}</div>
                        <div class="profile-info">
                            <h4>${profile.name}</h4>
                            <p>${profile.role || 'Professional'}</p>
                        </div>
                    </div>
                    <div class="profile-details">
                        <p><strong>About:</strong> ${profile.description}</p>
                        <p><strong>Skills:</strong> ${profile.skills.join(', ')}</p>
                        <p><strong>Alignment Score:</strong> ${profile.alignment_score}%</p>
                        <p><strong>Growth Score:</strong> ${profile.growth_score}%</p>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-primary connect-btn" data-match-id="${profile.id}">
                        <i class="fas fa-user-plus"></i> Connect
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Close modal functionality
        modal.querySelector('.modal-close').addEventListener('click', () => {
            modal.remove();
        });
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }

    function handleFileUpload(e) {
        const file = e.target.files[0];
        if (file) {
            // Validate file type and size
            if (file.size > 10 * 1024 * 1024) { // 10MB limit
                showNotification('File size too large. Please choose a file under 10MB.', 'error');
                return;
            }
            
            // Show upload progress
            showUploadProgress(file);
            
            // Upload file
            uploadFile(file);
        }
    }

    function showUploadProgress(file) {
        const progressContainer = document.createElement('div');
        progressContainer.className = 'upload-progress';
        progressContainer.innerHTML = `
            <div class="progress-bar">
                <div class="progress-fill" id="upload-progress-fill"></div>
            </div>
            <div class="progress-text">Uploading ${file.name}...</div>
        `;
        
        document.getElementById('chat-messages').appendChild(progressContainer);
    }

    async function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('user_id', getUserId());
        
        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                showNotification('File uploaded successfully!', 'success');
                addMessage('agent', `I've analyzed your file "${file.name}". ${data.analysis}`, 0.9);
            } else {
                showNotification('File upload failed. Please try again.', 'error');
            }
        } catch (error) {
            console.error('Upload error:', error);
            showNotification('File upload failed. Please try again.', 'error');
        }
        
        // Remove progress bar
        const progressContainer = document.querySelector('.upload-progress');
        if (progressContainer) {
            progressContainer.remove();
        }
    }

    function handleShare(e) {
        const platform = e.target.dataset.platform;
        const url = window.location.href;
        const text = "Check out this amazing team finding platform! Find your perfect team match today.";
        
        let shareUrl = '';
        
        switch (platform) {
            case 'twitter':
                shareUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;
                break;
            case 'linkedin':
                shareUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`;
                break;
            case 'facebook':
                shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`;
                break;
            case 'copy':
                navigator.clipboard.writeText(url).then(() => {
                    showNotification('Link copied to clipboard!', 'success');
                });
                return;
        }
        
        if (shareUrl) {
            window.open(shareUrl, '_blank', 'width=600,height=400');
        }
    }

    function updateGamification(data = null) {
        if (data) {
            gamificationData = { ...gamificationData, ...data };
        }
        
        // Update level progress
        updateLevelProgress();
        
        // Update achievements
        updateAchievements();
        
        // Update XP display
        updateXP();
    }

    function updateLevelProgress() {
        const levelElement = document.getElementById('current-level');
        const xpElement = document.getElementById('current-xp');
        const progressFill = document.querySelector('.level-progress-fill');
        
        if (levelElement) levelElement.textContent = gamificationData.level;
        if (xpElement) xpElement.textContent = `${gamificationData.xp}/${gamificationData.xpToNext} XP`;
        
        if (progressFill) {
            const percentage = (gamificationData.xp / gamificationData.xpToNext) * 100;
            progressFill.style.width = `${percentage}%`;
        }
    }

    function updateAchievements() {
        const achievementsGrid = document.getElementById('achievements-grid');
        if (!achievementsGrid) return;
        
        achievementsGrid.innerHTML = '';
        
        gamificationData.achievements.forEach(achievement => {
            const achievementElement = document.createElement('div');
            achievementElement.className = `achievement ${achievement.unlocked ? 'unlocked' : 'locked'}`;
            
            achievementElement.innerHTML = `
                <div class="achievement-icon">
                    <i class="fas fa-${achievement.icon}"></i>
                </div>
                <div class="achievement-content">
                    <h4>${achievement.title}</h4>
                    <p>${achievement.description}</p>
                </div>
                <div class="achievement-badge">
                    ${achievement.unlocked ? '🏆' : '🔒'}
                </div>
            `;
            
            achievementsGrid.appendChild(achievementElement);
        });
    }

    function updateXP() {
        const xpElements = document.querySelectorAll('.xp-display');
        xpElements.forEach(element => {
            element.textContent = `${gamificationData.xp} XP`;
        });
    }

    function updateConnectionStatus(connected = null) {
        const statusIndicator = document.querySelector('.connection-status');
        if (!statusIndicator) return;
        
        const isConnected = connected !== null ? connected : (socket && socket.connected);
        const statusDot = statusIndicator.querySelector('.status-dot');
        const statusText = statusIndicator.querySelector('.status-text');
        
        if (isConnected) {
            statusDot.classList.add('connected');
            statusDot.classList.remove('disconnected');
            if (statusText) statusText.textContent = 'Connected';
        } else {
            statusDot.classList.add('disconnected');
            statusDot.classList.remove('connected');
            if (statusText) statusText.textContent = 'Disconnected';
        }
    }

    function showNotification(message, type = 'info', duration = 5000) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        
        const icon = getNotificationIcon(type);
        
        notification.innerHTML = `
            <div class="notification-content">
                <i class="${icon}"></i>
                <span>${message}</span>
                <button class="notification-close">&times;</button>
            </div>
        `;
        
        // Add to notifications container
        const container = document.getElementById('notifications-container') || createNotificationsContainer();
        container.appendChild(notification);
        
        // Animate in
        setTimeout(() => notification.classList.add('show'), 100);
        
        // Auto remove
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, duration);
        
        // Close button
        notification.querySelector('.notification-close').addEventListener('click', () => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        });
    }

    function getNotificationIcon(type) {
        const icons = {
            'success': 'fas fa-check-circle',
            'error': 'fas fa-exclamation-circle',
            'warning': 'fas fa-exclamation-triangle',
            'info': 'fas fa-info-circle'
        };
        return icons[type] || 'fas fa-info-circle';
    }

    function createNotificationsContainer() {
        const container = document.createElement('div');
        container.id = 'notifications-container';
        container.className = 'notifications-container';
        document.body.appendChild(container);
        return container;
    }

    function handleResize() {
        // Handle responsive adjustments
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
        
        // Reinitialize particles if needed
        if (window.particlesJS) {
            particlesJS('particles-js', window.particlesJSConfig || {});
        }
    }

    function loadUserData() {
        // Load from localStorage
        const savedProfile = localStorage.getItem('userProfile');
        if (savedProfile) {
            userProfile = JSON.parse(savedProfile);
        }
        
        const savedMessages = localStorage.getItem('chatMessages');
        if (savedMessages) {
            chatMessages = JSON.parse(savedMessages);
            // Restore messages to UI
            restoreMessages();
        }
        
        const savedGamification = localStorage.getItem('gamificationData');
        if (savedGamification) {
            gamificationData = JSON.parse(savedGamification);
            updateGamification();
        }
    }

    function loadSavedData() {
        // Load any saved application state
        const savedSection = localStorage.getItem('currentSection');
        if (savedSection) {
            showSection(savedSection);
        }
    }

    function saveUserData() {
        localStorage.setItem('userProfile', JSON.stringify(userProfile));
        localStorage.setItem('chatMessages', JSON.stringify(chatMessages));
        localStorage.setItem('gamificationData', JSON.stringify(gamificationData));
        localStorage.setItem('currentSection', currentSection);
    }

    function restoreMessages() {
        const messagesContainer = document.getElementById('chat-messages');
        messagesContainer.innerHTML = '';
        
        chatMessages.forEach(message => {
            addMessage(message.type, message.content, message.confidence);
        });
    }

    function getUserId() {
        let userId = localStorage.getItem('userId');
        if (!userId) {
            userId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('userId', userId);
        }
        return userId;
    }

    function getConversationId() {
        return localStorage.getItem('find_your_team_conversation_id');
    }

    function setConversationId(conversationId) {
        if (conversationId) {
            localStorage.setItem('find_your_team_conversation_id', conversationId);
        }
    }

    function updateConfidenceScore(confidence) {
        const confidenceProgress = document.getElementById('confidence-progress');
        const confidenceText = document.getElementById('confidence-text');
        
        if (confidenceProgress && confidenceText) {
            const percentage = Math.max(0, Math.min(100, confidence || 0));
            confidenceProgress.style.width = percentage + '%';
            confidenceText.textContent = percentage + '%';
            
            // Add visual feedback for milestones
            if (percentage >= 90) {
                confidenceProgress.style.backgroundColor = 'var(--sa-gold)';
                confidenceText.style.color = 'var(--sa-gold)';
            } else if (percentage >= 70) {
                confidenceProgress.style.backgroundColor = 'var(--primary-color)';
                confidenceText.style.color = 'var(--primary-color)';
            }
        }
    }

    function handleProfileCompletion(conversationId) {
        // Show completion message and transition to matching
        addMessage('agent', '🎉 Fantastic! I now have a comprehensive understanding of your purpose and values. Your profile is complete with high confidence. Would you like to see some team opportunities that align perfectly with who you are?', 100);
        
        // Add a "Find My Teams" button
        setTimeout(() => {
            const chatContainer = document.getElementById('onboarding-chat');
            if (chatContainer) {
                const buttonContainer = document.createElement('div');
                buttonContainer.className = 'message agent-message';
                buttonContainer.innerHTML = `
                    <div class="message-avatar">
                        <i class="fas fa-magic"></i>
                    </div>
                    <div class="message-content">
                        <button class="btn btn-primary btn-lg" onclick="findMyTeams('${conversationId}')">
                            <i class="fas fa-search"></i>
                            Find My Perfect Teams
                        </button>
                    </div>
                `;
                chatContainer.appendChild(buttonContainer);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
        }, 1000);
    }

    function findMyTeams(conversationId) {
        // Fetch user profile and show matching section
        fetch(`/api/profile/${conversationId}`)
            .then(response => response.json())
            .then(data => {
                if (data.profile) {
                    displayUserProfile(data.profile);
                    scrollToMatching();
                } else {
                    addMessage('agent', 'Let me gather a bit more information to find the best teams for you...', 85);
                }
            })
            .catch(error => {
                console.error('Error fetching profile:', error);
                addMessage('agent', 'Let me continue learning about you to find perfect team matches.', 80);
            });
    }

    function displayUserProfile(profile) {
        console.log('User Profile Generated:', profile);
        
        // Update UI to show profile completion
        const matchingSection = document.getElementById('matching-section');
        if (matchingSection) {
            const profileSummary = document.createElement('div');
            profileSummary.className = 'profile-summary';
            profileSummary.innerHTML = `
                <h4>Your Purpose Profile</h4>
                <div class="profile-highlights">
                    <div class="highlight-item">
                        <strong>Core Values:</strong> ${profile.purposeProfile?.values?.core?.join(', ') || 'Discovered'}
                    </div>
                    <div class="highlight-item">
                        <strong>Passions:</strong> ${profile.purposeProfile?.passions?.join(', ') || 'Identified'}
                    </div>
                    <div class="highlight-item">
                        <strong>Confidence Score:</strong> ${profile.confidenceScore || 0}%
                    </div>
                </div>
            `;
            
            const existingSummary = matchingSection.querySelector('.profile-summary');
            if (existingSummary) {
                existingSummary.replaceWith(profileSummary);
            } else {
                matchingSection.insertBefore(profileSummary, matchingSection.firstChild.nextSibling);
            }
        }
    }

    function scrollToMatching() {
        const matchingSection = document.getElementById('matching-section');
        if (matchingSection) {
            matchingSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    // Team Performance Monitoring Functions
    function loadTeamPerformance(teamId = 'demo-team') {
        fetch(`/api/team/${teamId}/performance?days=30`)
            .then(response => response.json())
            .then(data => {
                updatePerformanceMetrics(data.metrics);
                displayPerformanceInsights(data.insights);
                updatePerformanceTrends(data.metrics);
            })
            .catch(error => {
                console.error('Error loading team performance:', error);
                // Load demo data on error
                loadDemoPerformanceData();
            });
    }

    function updatePerformanceMetrics(metrics) {
        // Update metric values with animation
        const productivityMetric = document.getElementById('productivity-metric');
        const collaborationMetric = document.getElementById('collaboration-metric');
        const satisfactionMetric = document.getElementById('satisfaction-metric');
        const impactMetric = document.getElementById('impact-metric');

        if (productivityMetric) {
            animateMetric(productivityMetric, (metrics.productivity * 100).toFixed(0) + '%');
        }
        if (collaborationMetric) {
            animateMetric(collaborationMetric, (metrics.collaboration * 100).toFixed(0) + '%');
        }
        if (satisfactionMetric) {
            animateMetric(satisfactionMetric, (metrics.engagement * 100).toFixed(0) + '%');
        }
        if (impactMetric) {
            animateMetric(impactMetric, (metrics.quality * 100).toFixed(0) + '%');
        }
    }

    function animateMetric(element, finalValue) {
        element.textContent = '0%';
        let current = 0;
        const target = parseInt(finalValue);
        const increment = target / 30; // 30 steps for smooth animation

        const animation = setInterval(() => {
            current += increment;
            if (current >= target) {
                element.textContent = finalValue;
                clearInterval(animation);
            } else {
                element.textContent = Math.floor(current) + '%';
            }
        }, 50);
    }

    function displayPerformanceInsights(insights) {
        // This would display insights in a dedicated section
        console.log('Performance Insights:', insights);
        
        // Show insights as notifications
        if (insights && insights.length > 0) {
            const insight = insights[0]; // Show first insight
            showNotification(
                `💡 ${insight.title}: ${insight.description}`,
                'info',
                5000
            );
        }
    }

    function updatePerformanceTrends(metrics) {
        // Update trend indicators based on metrics
        const productivityTrend = document.getElementById('productivity-trend');
        const collaborationTrend = document.getElementById('collaboration-trend');
        
        if (productivityTrend && metrics.productivity > 0.8) {
            productivityTrend.className = 'metric-trend up';
            productivityTrend.innerHTML = '↗ +' + Math.floor(metrics.productivity * 20) + '%';
        }
        
        if (collaborationTrend && metrics.collaboration > 0.75) {
            collaborationTrend.className = 'metric-trend up';
            collaborationTrend.innerHTML = '↗ +' + Math.floor(metrics.collaboration * 15) + '%';
        }
    }

    function generateRetrospective(teamId = 'demo-team') {
        const resultsContainer = document.getElementById('retrospective-results');
        if (!resultsContainer) return;

        // Show loading state
        resultsContainer.innerHTML = '<div class="loading-state">Generating retrospective...</div>';

        fetch('/api/team/actions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'generate_retrospective',
                parameters: { team_id: teamId, period: '30 days' }
            })
        })
        .then(response => response.json())
        .then(data => {
            displayRetrospective(data);
        })
        .catch(error => {
            console.error('Error generating retrospective:', error);
            displayDemoRetrospective();
        });
    }

    function displayRetrospective(data) {
        const resultsContainer = document.getElementById('retrospective-results');
        if (!resultsContainer) return;

        resultsContainer.innerHTML = `
            <div class="retrospective-card">
                <h4><i class="fas fa-clipboard-list"></i> Team Retrospective</h4>
                <div class="retrospective-content">
                    <div class="retrospective-section">
                        <h5>🎉 What Went Well</h5>
                        <ul>
                            ${data.successes?.map(success => `<li>${success}</li>`).join('') || '<li>Great collaboration on recent projects</li><li>Improved communication in daily standups</li>'}
                        </ul>
                    </div>
                    <div class="retrospective-section">
                        <h5>🔧 Areas for Improvement</h5>
                        <ul>
                            ${data.challenges?.map(challenge => `<li>${challenge}</li>`).join('') || '<li>Need better time management during sprints</li><li>Could improve code review process</li>'}
                        </ul>
                    </div>
                    <div class="retrospective-section">
                        <h5>🚀 Action Items</h5>
                        <ul>
                            ${data.action_items?.map(item => `<li>${item}</li>`).join('') || '<li>Implement time-boxing for meetings</li><li>Schedule weekly pair programming sessions</li>'}
                        </ul>
                    </div>
                </div>
            </div>
        `;
    }

    function getCoachingInsight(teamId = 'demo-team') {
        const resultsContainer = document.getElementById('coaching-results');
        if (!resultsContainer) return;

        // Show loading state
        resultsContainer.innerHTML = '<div class="loading-state">Generating coaching insights...</div>';

        fetch('/api/team/actions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'provide_coaching_insight',
                parameters: { 
                    team_id: teamId,
                    focus_area: 'team_dynamics'
                }
            })
        })
        .then(response => response.json())
        .then(data => {
            displayCoachingInsight(data);
        })
        .catch(error => {
            console.error('Error getting coaching insight:', error);
            displayDemoCoachingInsight();
        });
    }

    function displayCoachingInsight(data) {
        const resultsContainer = document.getElementById('coaching-results');
        if (!resultsContainer) return;

        resultsContainer.innerHTML = `
            <div class="coaching-card">
                <h4><i class="fas fa-lightbulb"></i> Coaching Insight</h4>
                <div class="coaching-content">
                    <div class="insight-priority ${data.priority || 'medium'}">
                        Priority: ${(data.priority || 'Medium').toUpperCase()}
                    </div>
                    <h5>${data.title || 'Team Development Opportunity'}</h5>
                    <p>${data.insight || 'Your team shows strong collaboration but could benefit from more structured feedback sessions.'}</p>
                    <div class="recommendations">
                        <h6>Recommendations:</h6>
                        <ul>
                            ${data.recommendations?.map(rec => `<li>${rec}</li>`).join('') || '<li>Schedule weekly one-on-ones</li><li>Implement peer feedback sessions</li><li>Create team learning goals</li>'}
                        </ul>
                    </div>
                </div>
            </div>
        `;
    }

    function loadDemoPerformanceData() {
        // Load demo metrics for development/testing
        const demoMetrics = {
            productivity: 0.85,
            collaboration: 0.78,
            engagement: 0.88,
            quality: 0.83
        };
        updatePerformanceMetrics(demoMetrics);
        updatePerformanceTrends(demoMetrics);
    }

    function displayDemoRetrospective() {
        const demoData = {
            successes: [
                'Successfully delivered three major features ahead of schedule',
                'Improved team communication through daily check-ins',
                'Achieved 95% code coverage on recent projects'
            ],
            challenges: [
                'Meeting efficiency could be improved - some run over time',
                'Knowledge sharing between team members needs enhancement',
                'Code review turnaround time is sometimes slow'
            ],
            action_items: [
                'Implement timeboxing for all meetings starting next week',
                'Set up weekly knowledge sharing sessions',
                'Create code review guidelines and SLA'
            ]
        };
        displayRetrospective(demoData);
    }

    function displayDemoCoachingInsight() {
        const demoData = {
            priority: 'medium',
            title: 'Enhance Team Communication Flow',
            insight: 'Your team demonstrates excellent technical skills and collaboration. However, there\'s an opportunity to improve information flow between team members, particularly during handoffs and knowledge transfer.',
            recommendations: [
                'Implement structured handoff documentation templates',
                'Schedule bi-weekly knowledge sharing sessions',
                'Create a team wiki for important project information',
                'Establish clear communication channels for different types of updates'
            ]
        };
        displayCoachingInsight(demoData);
    }

    function updateUserProfile(profileData) {
        userProfile = { ...userProfile, ...profileData };
        saveUserData();
    }

    function handleMatchFound(data) {
        showNotification(`New match found: ${data.match.name}!`, 'success');
        showMatches([data.match, ...matches]);
    }

    function handleTeamUpdate(data) {
        showNotification('Team updated!', 'info');
        showTeam(data);
    }

    // Utility functions
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    function throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        }
    }

    // Export functions for global access
    window.showSection = showSection;
    window.sendMessage = sendMessage;
    window.connectWithMatch = connectWithMatch;
    window.viewMatchProfile = viewMatchProfile;
    window.messageMember = messageMember;
    window.showNotification = showNotification;