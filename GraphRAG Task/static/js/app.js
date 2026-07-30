/**
 * GraphRAG Web UI — Frontend Application v2
 * SSE Streaming Pipeline + Conversation Memory
 */

// ================================================
// State
// ================================================
let isLoading = false;
let activeConversationId = null;
let conversations = [];

// ================================================
// Init
// ================================================
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    setupTextarea();
    loadConversations();
});

// ================================================
// Stats
// ================================================
async function loadStats() {
    try {
        const res = await fetch('/api/stats');
        if (!res.ok) return;
        const stats = await res.json();
        animateNumber('stat-entities-val', stats.entities || 0);
        animateNumber('stat-chunks-val', stats.chunks || 0);
        animateNumber('stat-communities-val', stats.communities || 0);
        animateNumber('stat-relations-val', stats.relations || 0);
        animateNumber('stat-documents-val', stats.documents || 0);
    } catch (e) { console.warn('Stats error:', e); }
}

function animateNumber(elementId, target) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const start = performance.now();
    function update(now) {
        const p = Math.min((now - start) / 800, 1);
        el.textContent = Math.round((1 - Math.pow(1 - p, 3)) * target).toLocaleString('tr-TR');
        if (p < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

// ================================================
// Textarea
// ================================================
function setupTextarea() {
    const textarea = document.getElementById('query-input');
    textarea.addEventListener('input', () => {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    });
    textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendQuery(); }
    });
}

// ================================================
// Sidebar Toggle
// ================================================
function toggleSidebar() {
    const sidebar = document.getElementById('conversations-sidebar');
    sidebar.classList.toggle('collapsed');
}

// ================================================
// Conversations
// ================================================
async function loadConversations() {
    try {
        const res = await fetch('/api/conversations');
        conversations = await res.json();
        renderConversationList();
    } catch (e) { console.warn('Conversations load error:', e); }
}

function renderConversationList() {
    const list = document.getElementById('conversations-list');
    list.innerHTML = '';

    if (conversations.length === 0) {
        list.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--text-tertiary); font-size: 0.75rem;">
            Henuz sohbet yok.<br>Yeni bir sohbet baslatmak icin + butonuna tiklayin.
        </div>`;
        return;
    }

    conversations.forEach(conv => {
        const item = document.createElement('div');
        item.className = `conv-item ${conv.id === activeConversationId ? 'active' : ''}`;
        item.onclick = (e) => {
            if (!e.target.closest('.conv-delete')) switchConversation(conv.id);
        };

        const msgCount = conv.message_count || 0;
        const msgLabel = msgCount > 0 ? `${Math.floor(msgCount / 2)} soru` : 'Bos';

        item.innerHTML = `
            <div class="conv-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
                </svg>
            </div>
            <div class="conv-info">
                <div class="conv-title">${escapeHtml(conv.title)}</div>
                <div class="conv-meta">${msgLabel}</div>
            </div>
            <button class="conv-delete" onclick="deleteConversation('${conv.id}')" title="Sil">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                </svg>
            </button>
        `;

        list.appendChild(item);
    });
}

async function createNewConversation() {
    try {
        const res = await fetch('/api/conversations', { method: 'POST' });
        const conv = await res.json();
        activeConversationId = conv.id;
        await loadConversations();
        clearChatUI();
        showWelcomeScreen();
        document.getElementById('query-input').focus();
    } catch (e) { console.error('Create conversation error:', e); }
}

async function switchConversation(convId) {
    if (isLoading) return;
    activeConversationId = convId;
    renderConversationList();

    try {
        const res = await fetch(`/api/conversations/${convId}`);
        const conv = await res.json();
        loadConversationMessages(conv.messages || []);
    } catch (e) { console.error('Switch conversation error:', e); }
}

function loadConversationMessages(messages) {
    const chatMessages = document.getElementById('chat-messages');
    const welcome = document.getElementById('welcome-screen');

    if (messages.length === 0) {
        chatMessages.style.display = 'none';
        chatMessages.innerHTML = '';
        welcome.style.display = 'flex';
        resetSidePanel();
        return;
    }

    welcome.style.display = 'none';
    chatMessages.style.display = 'flex';
    chatMessages.innerHTML = '';

    messages.forEach(msg => {
        addMessageToDOM(msg.role, msg.content);
    });

    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Son asistan mesajindaki pipeline verilerini geri yukle
    let lastAssistantMsg = null;
    for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].role === 'assistant' && messages[i].pipeline_stages) {
            lastAssistantMsg = messages[i];
            break;
        }
    }

    if (lastAssistantMsg && lastAssistantMsg.pipeline_stages && lastAssistantMsg.pipeline_stages.length > 0) {
        restorePipelineData(
            lastAssistantMsg.pipeline_stages,
            lastAssistantMsg.sources || [],
            lastAssistantMsg.total_duration_ms || 0
        );
    } else {
        resetSidePanel();
    }
}

async function deleteConversation(convId) {
    try {
        await fetch(`/api/conversations/${convId}`, { method: 'DELETE' });
        if (activeConversationId === convId) {
            activeConversationId = null;
            clearChatUI();
            showWelcomeScreen();
        }
        await loadConversations();
    } catch (e) { console.error('Delete conversation error:', e); }
}

// ================================================
// Suggestion Chip
// ================================================
function askSuggestion(chipEl) {
    document.getElementById('query-input').value = chipEl.textContent.trim();
    sendQuery();
}

// ================================================
// Send Query (SSE Streaming)
// ================================================
async function sendQuery() {
    const textarea = document.getElementById('query-input');
    const query = textarea.value.trim();
    if (!query || isLoading) return;

    // Auto-create conversation if none active
    if (!activeConversationId) {
        try {
            const res = await fetch('/api/conversations', { method: 'POST' });
            const conv = await res.json();
            activeConversationId = conv.id;
            await loadConversations();
        } catch (e) {
            console.error('Auto-create conversation error:', e);
            return;
        }
    }

    isLoading = true;

    const welcome = document.getElementById('welcome-screen');
    if (welcome) welcome.style.display = 'none';

    const chatMessages = document.getElementById('chat-messages');
    chatMessages.style.display = 'flex';

    addMessageToDOM('user', query);
    textarea.value = '';
    textarea.style.height = 'auto';

    const loadingId = addLoadingMessage();
    const sendBtn = document.getElementById('send-btn');
    sendBtn.disabled = true;

    resetSidePanel();
    showPipelineSection();

    try {
        const res = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query,
                conversation_id: activeConversationId
            })
        });

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let totalDurationMs = 0;

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Parse SSE events from buffer
            const events = buffer.split('\n\n');
            buffer = events.pop(); // Keep incomplete event in buffer

            for (const eventStr of events) {
                if (!eventStr.trim()) continue;

                const lines = eventStr.split('\n');
                let eventType = '';
                let eventData = '';

                for (const line of lines) {
                    if (line.startsWith('event: ')) eventType = line.slice(7);
                    if (line.startsWith('data: ')) eventData = line.slice(6);
                }

                if (!eventType || !eventData) continue;

                try {
                    const data = JSON.parse(eventData);
                    handleSSEEvent(eventType, data);

                    if (eventType === 'answer') {
                        removeLoadingMessage(loadingId);
                        addMessageToDOM('assistant', data.answer);
                        renderSources(data.sources);
                        // Pipeline verilerini yanit ile birlikte sakla
                        lastPipelineData = {
                            stages: data.pipeline_stages || [],
                            sources: data.sources || [],
                            total_duration_ms: data.total_duration_ms || 0
                        };
                    }

                    if (eventType === 'done') {
                        totalDurationMs = data.total_duration_ms;
                        document.getElementById('total-time').textContent = `Toplam: ${formatDuration(totalDurationMs)}`;
                    }

                    if (eventType === 'error') {
                        removeLoadingMessage(loadingId);
                        addMessageToDOM('assistant', `Hata: ${data.message}`);
                    }
                } catch (e) {
                    console.warn('SSE parse error:', e);
                }
            }
        }

        // Refresh conversation list to update title
        await loadConversations();

    } catch (e) {
        removeLoadingMessage(loadingId);
        addMessageToDOM('assistant', 'Baglanti Hatasi: Sunucuya ulasilamadi.');
    } finally {
        isLoading = false;
        sendBtn.disabled = false;
        textarea.focus();
    }
}

// ================================================
// SSE Event Handler
// ================================================
function handleSSEEvent(eventType, data) {
    if (eventType === 'stage') {
        addPipelineStage(data);
    }
}

// ================================================
// Messages
// ================================================
function addMessageToDOM(role, content, durationMs) {
    const chatMessages = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    if (role === 'user') {
        bubble.textContent = content;
    } else {
        bubble.innerHTML = renderMarkdown(content);
        bubble.querySelectorAll('a').forEach(a => { a.target = '_blank'; a.rel = 'noopener noreferrer'; });
    }

    msgDiv.appendChild(bubble);

    if (role === 'assistant' && durationMs) {
        const meta = document.createElement('div');
        meta.className = 'message-meta';
        meta.innerHTML = `<span class="duration-badge">${formatDuration(durationMs)}</span>`;
        msgDiv.appendChild(meta);
    }

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

let loadingCounter = 0;
function addLoadingMessage() {
    const chatMessages = document.getElementById('chat-messages');
    const id = `loading-${++loadingCounter}`;
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message assistant';
    msgDiv.id = id;
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.innerHTML = `
        <div class="loading-dots"><span></span><span></span><span></span></div>
        <div style="font-size: 0.72rem; color: var(--text-tertiary); margin-top: 4px;">GraphRAG sorgusu isleniyor...</div>
    `;
    msgDiv.appendChild(bubble);
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
}

function removeLoadingMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

// ================================================
// Markdown
// ================================================
function renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
        marked.setOptions({ breaks: true, gfm: true, headerIds: false, mangle: false });
        return marked.parse(text);
    }
    return text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>')
        .replace(/\n/g, '<br>');
}

// ================================================
// Pipeline Stages (Streaming — one at a time)
// ================================================
const STAGE_CONFIG = {
    embedding: { emoji: '&#128269;', name: 'Embedding' },
    vector_search: { emoji: '&#128196;', name: 'Vektor Arama' },
    graph_expansion: { emoji: '&#128279;', name: 'Graf Genisletme' },
    community_selection: { emoji: '&#127760;', name: 'Topluluk Secimi' },
    generation: { emoji: '&#10024;', name: 'Yanit Uretimi' }
};

function showPipelineSection() {
    document.getElementById('side-panel-empty').style.display = 'none';
    document.getElementById('pipeline-section').style.display = 'block';
    document.getElementById('pipeline-timeline').innerHTML = '';
    document.getElementById('total-time').textContent = '';
}

function addPipelineStage(data) {
    const timeline = document.getElementById('pipeline-timeline');
    const config = STAGE_CONFIG[data.stage] || { emoji: '&#9881;', name: data.stage };
    const detailsId = `stage-detail-${data.stage}-${Date.now()}`;

    const stageEl = document.createElement('div');
    stageEl.className = 'pipeline-stage';
    stageEl.style.animationDelay = '0s';

    stageEl.innerHTML = `
        <div class="stage-indicator">
            <div class="stage-dot done"></div>
            <div class="stage-line"></div>
        </div>
        <div class="stage-content">
            <div class="stage-header" onclick="toggleStageDetail('${detailsId}')">
                <div class="stage-title">
                    <span class="stage-emoji">${config.emoji}</span>
                    <span class="stage-name">${config.name}</span>
                </div>
                <span class="stage-duration">${data.duration_ms}ms</span>
            </div>
            <div class="stage-detail-text">${data.detail || ''}</div>
            <div class="stage-details" id="${detailsId}">
                ${renderStageDetails(data.stage, data)}
            </div>
        </div>
    `;

    timeline.appendChild(stageEl);

    // Scroll side panel to show new stage
    const sidePanel = document.getElementById('side-panel');
    sidePanel.scrollTop = sidePanel.scrollHeight;
}

function toggleStageDetail(id) {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('open');
}

function renderStageDetails(key, stage) {
    let html = '';

    if (key === 'vector_search' && stage.chunks) {
        stage.chunks.forEach(chunk => {
            const sp = Math.round(chunk.score * 100);
            const sc = sp >= 70 ? 'high' : sp >= 40 ? 'mid' : 'low';
            html += `<div class="detail-item">
                <span class="detail-label">&#128196;</span>
                <span class="detail-value" style="flex:1;">
                    <strong>${escapeHtml(chunk.article_title)}</strong><br>
                    <span style="color:var(--text-tertiary);font-size:0.68rem;">${escapeHtml(chunk.text_preview)}</span>
                </span>
                <span class="detail-score">
                    <div class="score-bar"><div class="score-fill ${sc}" style="width:${sp}%"></div></div>
                    <span style="font-family:var(--font-mono);font-size:0.66rem;color:var(--text-secondary);">${chunk.score}</span>
                </span>
            </div>`;
        });
    }

    if (key === 'graph_expansion' && stage.triples) {
        stage.triples.slice(0, 10).forEach(t => {
            html += `<div class="detail-item" style="gap:4px;">
                <span class="triple-node">${escapeHtml(t.source)}</span>
                <span class="triple-arrow">&rarr;</span>
                <span class="triple-rel">${escapeHtml(t.relation)}</span>
                <span class="triple-arrow">&rarr;</span>
                <span class="triple-node">${escapeHtml(t.target)}</span>
            </div>`;
        });
    }

    if (key === 'community_selection' && stage.communities) {
        stage.communities.forEach(c => {
            const bc = c.selected ? 'selected' : 'rejected';
            const bl = c.selected ? '&#10003; Secildi' : '&#10007; Elendi';
            html += `<div class="detail-item" style="flex-direction:column;gap:4px;">
                <div style="display:flex;justify-content:space-between;align-items:center;width:100%;">
                    <span class="community-badge ${bc}">${bl}</span>
                    <span style="font-family:var(--font-mono);font-size:0.66rem;color:var(--text-secondary);">Skor: ${c.score}</span>
                </div>
                <span class="detail-value" style="font-size:0.68rem;">${escapeHtml(c.summary)}</span>
            </div>`;
        });
    }

    if (key === 'generation') {
        html += `<div class="detail-item"><span class="detail-label">Model</span><span class="detail-value" style="font-family:var(--font-mono);">${stage.model || '-'}</span></div>`;
    }

    if (key === 'embedding') {
        html += `<div class="detail-item"><span class="detail-label">Detay</span><span class="detail-value">${stage.detail || '-'}</span></div>`;
    }

    return html || '<div class="detail-item"><span class="detail-value">Detay mevcut degil.</span></div>';
}

function restorePipelineData(stages, sources, totalDurationMs) {
    showPipelineSection();
    stages.forEach(stageData => {
        addPipelineStage(stageData);
    });
    if (totalDurationMs) {
        document.getElementById('total-time').textContent = `Toplam: ${formatDuration(totalDurationMs)}`;
    }
    if (sources && sources.length > 0) {
        renderSources(sources);
    }
}

let lastPipelineData = null;

// ================================================
// Sources
// ================================================
function renderSources(sources) {
    const section = document.getElementById('sources-section');
    const list = document.getElementById('sources-list');
    if (!sources || sources.length === 0) {
        if (section) section.style.display = 'none';
        if (list) list.innerHTML = '';
        return;
    }
    section.style.display = 'block';
    list.innerHTML = '';

    sources.forEach(source => {
        const sp = Math.round(source.score * 100);
        const card = document.createElement('a');
        card.className = 'source-card';
        card.href = source.url || '#';
        card.target = '_blank';
        card.rel = 'noopener noreferrer';
        card.innerHTML = `
            <div class="source-icon">&#128214;</div>
            <div class="source-info">
                <div class="source-title">${escapeHtml(source.title)}</div>
                <div class="source-url">${escapeHtml(source.url || '')}</div>
            </div>
            <div class="source-score-container">
                <span class="source-score-value">${source.score}</span>
                <div class="source-score-bar"><div class="source-score-fill" style="width:${sp}%"></div></div>
            </div>
            <svg class="source-external-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/>
            </svg>
        `;
        list.appendChild(card);
    });
}



// ================================================
// UI Helpers
// ================================================
function resetSidePanel() {
    document.getElementById('side-panel-empty').style.display = 'flex';
    document.getElementById('pipeline-section').style.display = 'none';
    document.getElementById('sources-section').style.display = 'none';
    document.getElementById('pipeline-timeline').innerHTML = '';
    document.getElementById('sources-list').innerHTML = '';
}

function clearChatUI() {
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.innerHTML = '';
    chatMessages.style.display = 'none';
    resetSidePanel();
}

function showWelcomeScreen() {
    document.getElementById('welcome-screen').style.display = 'flex';
}

function formatDuration(ms) {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
}

function escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}
