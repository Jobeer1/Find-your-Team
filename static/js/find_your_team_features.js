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
    // Allow opening a chat targeted at a specific team member. If the function
    // is called before the chat module is loaded/initialized, fall back to a
    // no-op that triggers the chat section when possible.
    function messageMember(memberId) {
        // Open the chat UI
        try {
            showSection('chat');

            // If chat input exists, prefill with an @mention and focus
            const chatInput = document.getElementById('chat-input');
            if (chatInput) {
                // Prefill an at-mention for clarity — UI can parse this
                chatInput.value = `@${memberId} `;
                chatInput.focus();
            } else {
                // If chat input isn't ready, save a simple draft to localStorage
                localStorage.setItem('chatDraftTarget', memberId);
            }
        } catch (err) {
            // Fail silently but log for debug
            console.warn('messageMember failed', err);
        }
    }
    window.messageMember = messageMember;
    window.showNotification = showNotification;