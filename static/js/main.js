/* ═══════════════════════════════════════════════════════
   IPL FanZone v2 - Main JavaScript
   ═══════════════════════════════════════════════════════ */

// API Helper Functions
const API = {
    async post(url, data) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCookie('csrftoken'),
            },
            body: JSON.stringify(data),
        });
        return response.json();
    },

    async get(url) {
        const response = await fetch(url);
        return response.json();
    },

    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
};

// Live Score Widget Update
function updateLiveScores() {
    const matchId = document.querySelector('[data-match-id]')?.getAttribute('data-match-id');
    if (!matchId) return;

    setInterval(async () => {
        try {
            const data = await API.get(`/match/${matchId}/api/`);
            updateScoreDisplay(data);
        } catch (e) {
            console.log('Score update error:', e);
        }
    }, 12000); // Update every 12 seconds
}

function updateScoreDisplay(data) {
    if (data.status === 'live') {
        document.querySelector('.score-status')?.textContent = 'LIVE 🔴';
        document.querySelector('.score-status').style.color = '#ff6b6b';
    } else {
        document.querySelector('.score-status')?.textContent = data.status.toUpperCase();
    }

    const team1 = document.querySelector('[data-team="1"]');
    const team2 = document.querySelector('[data-team="2"]');

    if (team1 && data.team1) {
        team1.querySelector('.score')?.textContent = data.team1.score;
        team1.querySelector('.overs')?.textContent = data.team1.overs;
    }

    if (team2 && data.team2) {
        team2.querySelector('.score')?.textContent = data.team2.score;
        team2.querySelector('.overs')?.textContent = data.team2.overs;
    }

    if (data.reactions) {
        updateReactions(data.reactions);
    }
}

function updateReactions(reactions) {
    Object.entries(reactions).forEach(([type, count]) => {
        const el = document.querySelector(`[data-reaction="${type}"] .count`);
        if (el) el.textContent = count;
    });
}

// Reaction Handler
async function addReaction(matchId, reactionType) {
    try {
        const username = prompt('Your name (optional):') || 'Anonymous';
        const data = await API.post(`/match/${matchId}/react/`, {
            reaction: reactionType,
            username: username,
        });
        
        const el = document.querySelector(`[data-reaction="${reactionType}"] .count`);
        if (el) el.textContent = data.count;
        
        showNotification('✅ Reaction added!');
    } catch (e) {
        console.error('Reaction error:', e);
    }
}

// Notifications
function showNotification(message, type = 'success') {
    const notif = document.createElement('div');
    notif.className = `notification notification-${type} slide-in`;
    notif.textContent = message;
    notif.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 25px;
        background: ${type === 'success' ? '#4caf50' : '#f44336'};
        color: white;
        border-radius: 5px;
        z-index: 9999;
    `;
    document.body.appendChild(notif);
    setTimeout(() => notif.remove(), 3000);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    updateLiveScores();
});
