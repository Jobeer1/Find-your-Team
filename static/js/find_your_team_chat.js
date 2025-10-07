function handleInputChange(e) {
const input = e.target;
const charCount = input.value.length;
const maxChars = 1000;

// Update character counter
const counter = document.querySelector('.char-counter');
if (counter) {
counter.textContent = `${charCount}/${maxChars}`;
counter.style.color = charCount > maxChars * 0.9 ? '#FFD700' : '#8e9aaf';
}

// Auto-resize textarea
input.style.height = 'auto';
input.style.height = Math.min(input.scrollHeight, 200) + 'px';

// Enable/disable send button
const sendButton = document.getElementById('send-button');
sendButton.disabled = charCount === 0 || charCount > maxChars;
}

function handleKeyPress(e) {
if (e.key === 'Enter' && !e.shiftKey) {
e.preventDefault();
sendMessage();
}
}

async function sendMessage() {
const input = document.getElementById('chat-input');
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

function addMessage(type, content, confidence = null) {
const messagesContainer = document.getElementById('chat-messages');
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
