/* ═══════════════════════════════════════════════════════
   Chat WebSocket Handler
   ═══════════════════════════════════════════════════════ */

class ChatHandler {
    constructor(roomName) {
        this.roomName = roomName;
        this.socket = null;
        this.messagesContainer = document.querySelector('.messages');
        this.inputField = document.querySelector('.input-area input');
        this.connectWebSocket();
        this.setupEventListeners();
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${window.location.host}/ws/chat/${this.roomName}/`;

        this.socket = new WebSocket(url);

        this.socket.onopen = () => {
            console.log('Chat connected');
            this.addSystemMessage('✅ Connected to chat');
        };

        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };

        this.socket.onerror = (error) => {
            console.error('Chat error:', error);
            this.addSystemMessage('❌ Connection error');
        };

        this.socket.onclose = () => {
            console.log('Chat closed');
            this.addSystemMessage('⚠️ Disconnected');
            setTimeout(() => this.connectWebSocket(), 3000);
        };
    }

    handleMessage(data) {
        if (data.type === 'connection_established') {
            this.addSystemMessage(data.message);
        } else if (data.type === 'chat_message') {
            this.addMessage(data.username, data.message, 'bot');
        }
    }

    setupEventListeners() {
        this.inputField?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        document.querySelector('.input-area button')?.addEventListener('click', () => {
            this.sendMessage();
        });
    }

    sendMessage() {
        const message = this.inputField?.value.trim();
        if (!message) return;

        const username = prompt('Your name:') || 'Anonymous';
        this.addMessage(username, message, 'user');

        this.socket.send(JSON.stringify({
            username: username,
            message: message,
        }));

        this.inputField.value = '';
    }

    addMessage(username, message, type) {
        const msgEl = document.createElement('div');
        msgEl.className = `message ${type}`;
        msgEl.innerHTML = `<strong>${username}:</strong> ${this.escapeHtml(message)}`;
        this.messagesContainer?.appendChild(msgEl);
        this.messagesContainer?.scrollTop = this.messagesContainer?.scrollHeight;
    }

    addSystemMessage(message) {
        const msgEl = document.createElement('div');
        msgEl.className = 'message system';
        msgEl.textContent = message;
        msgEl.style.cssText = 'text-align: center; color: #ffd700; font-size: 12px; margin: 10px 0;';
        this.messagesContainer?.appendChild(msgEl);
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;',
        };
        return text.replace(/[&<>"']/g, (m) => map[m]);
    }
}

// Jarvis AI Chat Handler
class JarvisChat {
    constructor() {
        this.messagesContainer = document.querySelector('.jarvis-messages');
        this.inputField = document.querySelector('.jarvis-input input');
        this.sendBtn = document.querySelector('.jarvis-input button');
        this.history = [];
        this.setupEventListeners();
    }

    setupEventListeners() {
        this.sendBtn?.addEventListener('click', () => this.askJarvis());
        this.inputField?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.askJarvis();
            }
        });
    }

    async askJarvis() {
        const message = this.inputField?.value.trim();
        if (!message) return;

        this.addMessage(message, 'user');
        this.inputField.value = '';

        try {
            const response = await fetch('/jarvis/ask/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken'),
                },
                body: JSON.stringify({
                    message: message,
                    history: this.history,
                }),
            });

            const data = await response.json();
            this.addMessage(data.response, 'assistant');

            this.history.push({ role: 'user', content: message });
            this.history.push({ role: 'assistant', content: data.response });

            if (data.memory) {
                this.updateMemoryDisplay(data.memory);
            }
        } catch (e) {
            console.error('Jarvis error:', e);
            this.addMessage('🏏 Oops! Something went wrong.', 'assistant');
        }
    }

    addMessage(text, type) {
        const msgEl = document.createElement('div');
        msgEl.className = `message ${type === 'user' ? 'user' : 'bot'} slide-in`;
        msgEl.textContent = text;
        this.messagesContainer?.appendChild(msgEl);
        this.messagesContainer?.scrollTop = this.messagesContainer?.scrollHeight;
    }

    updateMemoryDisplay(memory) {
        const memoryPanel = document.querySelector('.memory-panel');
        if (!memoryPanel) return;

        let html = '<h3>🧠 Jarvis Memory</h3>';
        if (memory.name) html += `<p><strong>Your name:</strong> ${memory.name}</p>`;
        if (memory.fav_team) html += `<p><strong>Your team:</strong> ${memory.fav_team}</p>`;

        memoryPanel.innerHTML = html;
    }

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
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const roomName = document.querySelector('[data-room-name]')?.getAttribute('data-room-name');
    if (roomName && document.querySelector('.chat-container')) {
        new ChatHandler(roomName);
    }

    if (document.querySelector('.jarvis-chat')) {
        new JarvisChat();
    }
});
