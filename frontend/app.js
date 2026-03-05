/**
 * OpenAgent Frontend — app.js
 * Integrates with LangGraph API via Server-Sent Events (SSE)
 */

// ═══════════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════════
const CONFIG = {
  apiBase: 'http://localhost:2024',
  defaultAgent: 'openagent',
  agents: {
    openagent: { label: 'OpenAgent', icon: '🤖', description: 'Orquestrador geral' },
    coder:     { label: 'Coder',     icon: '⌨️',  description: 'Especialista em código' },
    researcher:{ label: 'Researcher',icon: '🔍', description: 'Pesquisa e scraping web' },
  }
};

// ═══════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════
const state = {
  currentAgent:  localStorage.getItem('oa_agent') || CONFIG.defaultAgent,
  threads:       JSON.parse(localStorage.getItem('oa_threads') || '[]'),
  currentThread: null,
  streaming:     false,
  activeToolPills: {},
};

// ═══════════════════════════════════════════════════════════
// DOM REFS
// ═══════════════════════════════════════════════════════════
const $ = id => document.getElementById(id);
const dom = {
  sidebar:          $('sidebar'),
  sidebarToggle:    $('btn-sidebar-toggle'),
  sidebarOpen:      $('btn-sidebar-open'),
  agentSelector:    $('agent-selector'),
  agentTabs:        document.querySelectorAll('.agent-tab'),
  searchInput:      $('search-input'),
  threadList:       $('thread-list'),
  btnNewChat:       $('btn-new-chat'),
  chatHeader:       $('active-agent-label'),
  connectionDot:    $('connection-status'),
  btnClear:         $('btn-clear-chat'),
  messagesArea:     $('messages-area'),
  emptyState:       $('empty-state'),
  toolBar:          $('tool-bar'),
  toolPills:        $('tool-pills'),
  msgInput:         $('msg-input'),
  btnSend:          $('btn-send'),
  btnAttach:        $('btn-attach'),
};

// ═══════════════════════════════════════════════════════════
// LANGGRAPH API CLIENT
// ═══════════════════════════════════════════════════════════
const api = {

  async createThread() {
    const res = await fetch(`${CONFIG.apiBase}/threads`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error(`Failed to create thread: ${res.status}`);
    return res.json();
  },

  async *streamRun(threadId, agentId, userMessage) {
    const res = await fetch(`${CONFIG.apiBase}/threads/${threadId}/runs/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        assistant_id: agentId,
        input: {
          messages: [{ role: 'human', content: userMessage }]
        },
        stream_mode: ['messages', 'updates'],
        stream_subgraphs: true,
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Stream failed (${res.status}): ${errText}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // keep incomplete line

      let eventType = null;
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') return;
          try {
            const data = JSON.parse(raw);
            yield { event: eventType, data };
          } catch {
            // skip malformed
          }
        }
      }
    }
  },

  async getThreadHistory(threadId) {
    const res = await fetch(`${CONFIG.apiBase}/threads/${threadId}/history`);
    if (!res.ok) return [];
    return res.json();
  },
};

// ═══════════════════════════════════════════════════════════
// THREAD MANAGEMENT
// ═══════════════════════════════════════════════════════════
function saveThreads() {
  localStorage.setItem('oa_threads', JSON.stringify(state.threads));
}

function findThread(id) {
  return state.threads.find(t => t.id === id);
}

function addThread(id, agent) {
  const thread = {
    id,
    agent,
    title: 'Nova conversa',
    createdAt: Date.now(),
    lastMessage: null,
  };
  state.threads.unshift(thread);
  saveThreads();
  return thread;
}

function updateThread(id, patch) {
  const t = findThread(id);
  if (t) Object.assign(t, patch);
  saveThreads();
}

function deleteThread(id) {
  state.threads = state.threads.filter(t => t.id !== id);
  saveThreads();

  if (state.currentThread?.id === id) {
    state.currentThread = null;
    clearMessages();
    showEmpty(true);
  }
  renderThreadList();
}

function deriveTitle(text) {
  const clean = text.replace(/\s+/g, ' ').trim();
  return clean.length > 40 ? clean.slice(0, 40) + '…' : clean;
}

// ═══════════════════════════════════════════════════════════
// RENDER — SIDEBAR THREAD LIST
// ═══════════════════════════════════════════════════════════
function renderThreadList(filter = '') {
  const q = filter.toLowerCase();
  const filtered = state.threads.filter(t =>
    !q || t.title.toLowerCase().includes(q) || (t.lastMessage || '').toLowerCase().includes(q)
  );

  if (filtered.length === 0) {
    dom.threadList.innerHTML = `<div class="thread-empty">${filter ? 'Nenhum resultado' : 'Nenhuma conversa ainda'}</div>`;
    return;
  }

  dom.threadList.innerHTML = filtered.map(t => {
    const agent = CONFIG.agents[t.agent] || CONFIG.agents.openagent;
    const isActive = state.currentThread?.id === t.id;
    return `
      <div class="thread-item${isActive ? ' active' : ''}" data-id="${t.id}" id="thread-${t.id}">
        <span class="thread-item-icon">${agent.icon}</span>
        <div class="thread-item-info">
          <div class="thread-item-title">${escHtml(t.title)}</div>
          <div class="thread-item-sub">${t.lastMessage ? escHtml(t.lastMessage) : agent.label}</div>
        </div>
        <button class="thread-item-delete" data-id="${t.id}" title="Excluir conversa" aria-label="Excluir">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6 6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>
    `;
  }).join('');
}

// ═══════════════════════════════════════════════════════════
// RENDER — MESSAGES
// ═══════════════════════════════════════════════════════════
function showEmpty(show) {
  dom.emptyState.style.display = show ? '' : 'none';
}

function clearMessages() {
  const msgs = dom.messagesArea.querySelectorAll('.message');
  msgs.forEach(m => m.remove());
  state.activeToolPills = {};
  dom.toolBar.style.display = 'none';
  dom.toolPills.innerHTML = '';
}

function renderUserMessage(text) {
  showEmpty(false);
  const div = document.createElement('div');
  div.className = 'message user';
  div.innerHTML = `
    <div class="msg-bubble">${escHtml(text)}</div>
  `;
  dom.messagesArea.appendChild(div);
  scrollToBottom();
  return div;
}

function createAgentMessageEl() {
  showEmpty(false);
  const agent = CONFIG.agents[state.currentAgent] || CONFIG.agents.openagent;
  const div = document.createElement('div');
  div.className = 'message agent';
  div.innerHTML = `
    <div class="msg-avatar">${agent.icon}</div>
    <div class="msg-content">
      <div class="msg-agent-name">OpenAgent · ${agent.label}</div>
      <div class="msg-bubble">
        <div class="typing-indicator">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    </div>
  `;
  dom.messagesArea.appendChild(div);
  scrollToBottom();
  return div;
}

function finalizeAgentMessage(el, markdown) {
  const bubble = el.querySelector('.msg-bubble');
  bubble.innerHTML = renderMarkdown(markdown);
  const ts = document.createElement('div');
  ts.className = 'msg-ts';
  ts.textContent = formatTime(new Date());
  el.querySelector('.msg-content').appendChild(ts);
  scrollToBottom();
}

// ═══════════════════════════════════════════════════════════
// RENDER — TOOL PILLS
// ═══════════════════════════════════════════════════════════
function showToolPill(toolName, toolId) {
  dom.toolBar.style.display = '';
  const pill = document.createElement('div');
  pill.className = 'tool-pill running';
  pill.id = `pill-${toolId}`;
  pill.textContent = toolName;
  dom.toolPills.appendChild(pill);
  state.activeToolPills[toolId] = pill;
}

function resolveToolPill(toolId, success) {
  const pill = state.activeToolPills[toolId];
  if (!pill) return;
  pill.classList.remove('running');
  pill.classList.add(success ? 'done' : 'error');
  if (!success) pill.textContent += ' ✗';
}

function clearToolPills() {
  setTimeout(() => {
    dom.toolBar.style.display = 'none';
    dom.toolPills.innerHTML = '';
    state.activeToolPills = {};
  }, 1200);
}

// ═══════════════════════════════════════════════════════════
// STREAMING ENGINE
// ═══════════════════════════════════════════════════════════
async function sendMessage(text) {
  if (state.streaming || !text.trim()) return;

  // Create thread if needed
  if (!state.currentThread) {
    try {
      const t = await api.createThread();
      const thread = addThread(t.thread_id, state.currentAgent);
      state.currentThread = thread;
      updateThread(thread.id, { title: deriveTitle(text) });
      renderThreadList();
    } catch (err) {
      showError('Falha ao criar thread. Verifique se o servidor LangGraph está rodando.');
      return;
    }
  }

  state.streaming = true;
  setSendState('loading');
  renderUserMessage(text);

  // Update thread title and last message
  updateThread(state.currentThread.id, {
    title: deriveTitle(text),
    lastMessage: text,
  });
  renderThreadList();

  const agentEl = createAgentMessageEl();
  let accText = '';
  // Map of message id → accumulated text, to track multiple AI messages (e.g. after tool calls)
  const msgTextMap = new Map();

  try {
    for await (const { event, data } of api.streamRun(
      state.currentThread.id,
      state.currentAgent,
      text
    )) {
      if (!event || !data) continue;

      // ── Token streaming (messages mode) ──────────────────
      if (event === 'messages/partial') {
        const msgs = Array.isArray(data) ? data : [data];

        // Find the LAST AI message in the array that has text content.
        // LangGraph sends all messages in the thread; the final response
        // comes after tool messages, so we must not stop at the first one.
        let latestText = '';
        for (const msg of msgs) {
          if (msg.type !== 'AIMessageChunk' && msg.type !== 'ai') continue;

          const content = msg.content;
          let text = '';
          if (typeof content === 'string') {
            text = content;
          } else if (Array.isArray(content)) {
            for (const block of content) {
              if (block.type === 'text' && block.text) text += block.text;
            }
          }

          if (text) {
            const msgId = msg.id || 'default';
            msgTextMap.set(msgId, text);
            latestText = text; // keep updating — last one with text wins
          }
        }

        if (latestText) {
          accText = latestText;
          const bubble = agentEl.querySelector('.msg-bubble');
          bubble.innerHTML = renderMarkdown(accText) + '<span class="typing-cursor">▌</span>';
          scrollToBottom();
        }
      }

      // ── Tool calls (updates mode) ─────────────────────────
      if (event === 'updates') {
        const updates = Array.isArray(data) ? data : [data];
        for (const update of updates) {
          // Tool invocations from agent node
          if (update?.agent?.messages) {
            for (const msg of update.agent.messages) {
              if (msg.tool_calls?.length) {
                for (const tc of msg.tool_calls) {
                  showToolPill(tc.name, tc.id);
                }
              }
            }
          }
          // Tool results
          if (update?.tools?.messages) {
            for (const msg of update.tools.messages) {
              if (msg.type === 'tool') {
                const ok = !String(msg.content || '').toLowerCase().includes('error');
                resolveToolPill(msg.tool_call_id, ok);
              }
            }
          }
        }
      }
    }

    // Finalize
    finalizeAgentMessage(agentEl, accText || '_(sem resposta)_');
    updateThread(state.currentThread.id, {
      lastMessage: accText.slice(0, 80),
    });
    renderThreadList();

  } catch (err) {
    console.error('Stream error:', err);
    const errMsg = err.message.includes('Failed to fetch')
      ? 'Não foi possível conectar ao LangGraph. Verifique se `langgraph dev` está rodando na porta 2024.'
      : err.message;
    finalizeAgentMessage(agentEl, `❌ **Erro:** ${errMsg}`);
    setConnectionStatus('error');
  } finally {
    state.streaming = false;
    setSendState('idle');
    clearToolPills();
  }
}

// ═══════════════════════════════════════════════════════════
// CONNECTION CHECK
// ═══════════════════════════════════════════════════════════
async function checkConnection() {
  try {
    const res = await fetch(`${CONFIG.apiBase}/ok`, { signal: AbortSignal.timeout(3000) });
    setConnectionStatus(res.ok ? 'connected' : 'error');
  } catch {
    setConnectionStatus('error');
  }
}

function setConnectionStatus(status) {
  dom.connectionDot.className = 'connection-dot ' + status;
  const titles = {
    connected: 'Conectado ao LangGraph',
    error: 'Erro de conexão — verifique o servidor',
    default: 'Verificando...',
  };
  dom.connectionDot.title = titles[status] || titles.default;
}

// ═══════════════════════════════════════════════════════════
// AGENT SWITCHING
// ═══════════════════════════════════════════════════════════
function setAgent(agentId) {
  if (!CONFIG.agents[agentId]) return;
  state.currentAgent = agentId;
  localStorage.setItem('oa_agent', agentId);

  dom.agentTabs.forEach(tab => {
    tab.classList.toggle('active', tab.dataset.agent === agentId);
  });

  const agent = CONFIG.agents[agentId];
  dom.chatHeader.textContent = `${agent.icon} ${agent.label}`;
  dom.chatHeader.className = 'chat-agent-badge active';
}

// ═══════════════════════════════════════════════════════════
// THREAD SELECTION
// ═══════════════════════════════════════════════════════════
async function selectThread(threadId) {
  const thread = findThread(threadId);
  if (!thread) return;

  state.currentThread = thread;
  setAgent(thread.agent);
  clearMessages();
  renderThreadList();

  // Load history
  try {
    const history = await api.getThreadHistory(threadId);
    loadHistoryIntoChat(history);
  } catch (err) {
    console.error('Failed to load history:', err);
  }
}

function loadHistoryIntoChat(historyItems) {
  if (!historyItems?.length) { showEmpty(true); return; }

  // history is an array of states, each has .values.messages
  const allMessages = [];
  for (const item of historyItems) {
    const msgs = item?.values?.messages;
    if (Array.isArray(msgs)) {
      for (const m of msgs) {
        allMessages.push(m);
      }
    }
  }

  // Deduplicate by id
  const seen = new Set();
  const unique = allMessages.filter(m => {
    if (!m.id || seen.has(m.id)) return false;
    seen.add(m.id);
    return true;
  });

  if (!unique.length) { showEmpty(true); return; }
  showEmpty(false);

  for (const msg of unique) {
    const role = msg.type || msg.role;
    if (role === 'human') {
      const content = typeof msg.content === 'string' ? msg.content : '';
      renderUserMessage(content);
    } else if (role === 'ai' || role === 'AIMessage') {
      const content = typeof msg.content === 'string' ? msg.content : '';
      if (!content) continue;
      const agent = CONFIG.agents[state.currentAgent] || CONFIG.agents.openagent;
      const div = document.createElement('div');
      div.className = 'message agent';
      div.innerHTML = `
        <div class="msg-avatar">${agent.icon}</div>
        <div class="msg-content">
          <div class="msg-agent-name">OpenAgent · ${agent.label}</div>
          <div class="msg-bubble">${renderMarkdown(content)}</div>
        </div>
      `;
      dom.messagesArea.appendChild(div);
    }
  }
  scrollToBottom();
}

// ═══════════════════════════════════════════════════════════
// UI HELPERS
// ═══════════════════════════════════════════════════════════
function setSendState(state_) {
  if (state_ === 'loading') {
    dom.btnSend.classList.add('loading');
    dom.btnSend.disabled = true;
    dom.btnSend.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
      </svg>`;
    dom.msgInput.disabled = true;
  } else {
    dom.btnSend.classList.remove('loading');
    dom.btnSend.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <line x1="22" y1="2" x2="11" y2="13"/>
        <polygon points="22 2 15 22 11 13 2 9 22 2"/>
      </svg>`;
    dom.msgInput.disabled = false;
    updateSendButton();
    dom.msgInput.focus();
  }
}

function updateSendButton() {
  dom.btnSend.disabled = !dom.msgInput.value.trim() || state.streaming;
}

function scrollToBottom() {
  dom.messagesArea.scrollTo({ top: dom.messagesArea.scrollHeight, behavior: 'smooth' });
}

function showError(msg) {
  const div = document.createElement('div');
  div.className = 'message agent';
  div.innerHTML = `
    <div class="msg-avatar">⚠️</div>
    <div class="msg-content">
      <div class="msg-agent-name">Sistema</div>
      <div class="msg-bubble">${escHtml(msg)}</div>
    </div>`;
  showEmpty(false);
  dom.messagesArea.appendChild(div);
  scrollToBottom();
}

// ═══════════════════════════════════════════════════════════
// MARKDOWN RENDERER (minimal, no dependencies)
// ═══════════════════════════════════════════════════════════
function renderMarkdown(text) {
  if (!text) return '';
  let html = escHtml(text);

  // Code blocks (``` ... ```)
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) =>
    `<pre><code class="lang-${lang || 'text'}">${code.trim()}</code></pre>`
  );

  // Inline code
  html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');

  // Bold + italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Headings
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // Horizontal rule
  html = html.replace(/^---+$/gm, '<hr>');

  // Unordered lists
  html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, m => `<ul>${m}</ul>`);

  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

  // Links
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // Paragraphs (double newline → p)
  html = html.replace(/\n\n+/g, '</p><p>');
  html = '<p>' + html + '</p>';

  // Single newlines within paragraphs → br
  html = html.replace(/(?<!>)\n(?!<)/g, '<br>');

  // Clean up empty <p> tags
  html = html.replace(/<p>\s*<\/p>/g, '');

  return html;
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatTime(date) {
  return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

// ═══════════════════════════════════════════════════════════
// EVENT LISTENERS
// ═══════════════════════════════════════════════════════════
function initEvents() {

  // Send on button click
  dom.btnSend.addEventListener('click', () => {
    const text = dom.msgInput.value.trim();
    if (!text || state.streaming) return;
    dom.msgInput.value = '';
    dom.msgInput.style.height = 'auto';
    updateSendButton();
    sendMessage(text);
  });

  // Send on Enter (Shift+Enter = newline)
  dom.msgInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      dom.btnSend.click();
    }
  });

  // Auto-resize textarea
  dom.msgInput.addEventListener('input', () => {
    dom.msgInput.style.height = 'auto';
    dom.msgInput.style.height = Math.min(dom.msgInput.scrollHeight, 180) + 'px';
    updateSendButton();
  });

  // Agent tabs
  dom.agentSelector.addEventListener('click', e => {
    const tab = e.target.closest('.agent-tab');
    if (!tab) return;
    setAgent(tab.dataset.agent);
    // New agent → new thread
    state.currentThread = null;
    clearMessages();
    showEmpty(true);
  });

  // New chat
  dom.btnNewChat.addEventListener('click', () => {
    state.currentThread = null;
    clearMessages();
    showEmpty(true);
    renderThreadList();
    dom.msgInput.focus();
  });

  // Clear chat
  dom.btnClear.addEventListener('click', () => {
    state.currentThread = null;
    clearMessages();
    showEmpty(true);
    renderThreadList();
  });

  // Sidebar toggle
  dom.sidebarToggle.addEventListener('click', () => {
    dom.sidebar.classList.toggle('collapsed');
    const isCollapsed = dom.sidebar.classList.contains('collapsed');
    dom.sidebarOpen.style.display = isCollapsed ? 'flex' : 'none';
    dom.sidebarToggle.style.display = isCollapsed ? 'none' : 'flex';
  });

  if (dom.sidebarOpen) {
    dom.sidebarOpen.addEventListener('click', () => {
      dom.sidebar.classList.remove('collapsed');
      dom.sidebarOpen.style.display = 'none';
    });
  }

  // Thread list — click and delete
  dom.threadList.addEventListener('click', e => {
    const deleteBtn = e.target.closest('.thread-item-delete');
    if (deleteBtn) {
      e.stopPropagation();
      deleteThread(deleteBtn.dataset.id);
      return;
    }
    const item = e.target.closest('.thread-item');
    if (item) selectThread(item.dataset.id);
  });

  // Search
  dom.searchInput.addEventListener('input', () => {
    renderThreadList(dom.searchInput.value);
  });

  // Suggestion chips
  dom.messagesArea.addEventListener('click', e => {
    const chip = e.target.closest('.suggestion-chip');
    if (chip) {
      dom.msgInput.value = chip.dataset.prompt;
      dom.msgInput.dispatchEvent(new Event('input'));
      dom.msgInput.focus();
    }
  });

  // Attach (placeholder — no upload backend yet)
  dom.btnAttach.addEventListener('click', () => {
    alert('Anexo de arquivos: em desenvolvimento.\nPor enquanto, cole o conteúdo diretamente na mensagem.');
  });
}

// ═══════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════
function init() {
  setAgent(state.currentAgent);
  renderThreadList();
  showEmpty(true);
  updateSendButton();
  initEvents();
  checkConnection();

  // Periodic connection check every 30s
  setInterval(checkConnection, 30_000);

  dom.msgInput.focus();
  console.log('[OpenAgent] Frontend initialized. LangGraph API:', CONFIG.apiBase);
}

document.addEventListener('DOMContentLoaded', init);
