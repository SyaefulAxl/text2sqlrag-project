// Configuration - Auto-detect API endpoint based on current host
const getAPIBaseURL = () => {
  const hostname = window.location.hostname;

  // If accessing from local network IP, use matching API
  if (hostname === '192.168.0.253') {
    return 'http://192.168.0.253:8000';
  }
  // For localhost, use localhost
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8000';
  }
  // Fallback
  return 'http://localhost:8000';
};

const API_BASE_URL = getAPIBaseURL();
const API_ENDPOINT = `${API_BASE_URL}/query/documents`;

// Configure marked for markdown parsing
if (typeof marked !== 'undefined') {
  marked.setOptions({
    breaks: true,
    gfm: true,
  });
}

// Friendly responses and messages
const friendlyGreetings = [
  "👋 Hi there, my texcoms friend! I'm your textile knowledge buddy, here to help you explore and understand everything about our textile world. Just ask me anything about the documents, and I'll share what I found with you in the most interesting way possible! Let's learn together! 🚀",
  "🌟 Hey there! Welcome to your personal textile knowledge assistant. I'm super excited to help you find answers to all your textile-related questions. Whether it's about yarn spinning, fabrics, or textile processes, I'm here for you. Let's dive in together! 💪",
  "📖 Welcome, my texcoms colleague! I'm your humble guide through the textile knowledge universe. Think of me as your friendly textile expert companion. Ask me literally anything about your documents, and I'll explain it in a way that's super interesting and easy to understand. We've got this! 🎯",
];

const notFoundMessages = [
  "🤔 We're really sorry about this! 😅 It looks like we don't have enough information in our documents to answer that question yet. But hey, don't you worry my friend! Our amazing expert team would absolutely love to help you with this. Just reach out to them directly and they'll give you the perfect answer with all the clarity you need. Trust me, it'll be worth your time! 💪",
  "😅 Oops! This knowledge hasn't been updated in our documents yet, but that's totally okay! Here's the good news though - our expert team is just a message away and would genuinely love to help you out. They'll dive deep into your question and give you a detailed answer that really makes sense. Don't hesitate to reach out, friend! 🤝",
  "🔍 Hmm, I couldn't find the specific information about this in our current documents. But hey, that's what makes our expert team so valuable! Please don't hesitate to contact them directly. They're super knowledgeable, always happy to help, and they'll provide you with the best answer and all the clarity you need. We're all here to support you! 🙌",
];

const loadingMessages = [
  '⏳ Searching through the documents for you...',
  '🔍 Let me find that amazing answer for you...',
  '⚡ Working my textile magic...',
  '🤔 Thinking deeply about this, my friend...',
  '📚 Diving into our textile knowledge vault...',
  '✨ Finding the perfect answer just for you...',
];

// DOM Elements
const messagesContainer = document.getElementById('messagesContainer');
const questionInput = document.getElementById('questionInput');
const sendBtn = document.getElementById('sendBtn');
const loadingSpinner = document.getElementById('loadingSpinner');
const responseModal = document.getElementById('responseModal');
const modalBody = document.getElementById('modalBody');
const modalClose = document.querySelector('.modal-close');

// Event Listeners
sendBtn.addEventListener('click', handleSendMessage);
questionInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    handleSendMessage();
  }
});

modalClose.addEventListener('click', closeModal);
responseModal.addEventListener('click', (e) => {
  if (e.target === responseModal) {
    closeModal();
  }
});

/**
 * Handle sending a message
 */
async function handleSendMessage() {
  const question = questionInput.value.trim();

  if (!question) {
    showError(
      'Hey there! You gotta ask me something to get started! 😄 What would you like to know about our textile knowledge?',
    );
    return;
  }

  // Add user message to chat
  addMessage(question, 'user');
  questionInput.value = '';
  questionInput.focus();

  // Show loading spinner with friendly message
  showLoading(true, getRandomItem(loadingMessages));

  try {
    // Call API
    const response = await fetchQuery(question);

    // Add assistant message with answer
    addMessage(response, 'assistant');
  } catch (error) {
    console.error('Error:', error);
    // Show friendly error message
    const friendlyError = getFriendlyErrorMessage(error);
    addMessage(friendlyError, 'assistant', true);
  } finally {
    showLoading(false);
  }
}

/**
 * Fetch query result from API
 */
async function fetchQuery(question) {
  const response = await fetch(API_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question: question,
      top_k: 10,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `API Error: ${response.status}`);
  }

  const data = await response.json();
  return data;
}

/**
 * Get a friendly error message
 */
function getFriendlyErrorMessage(error) {
  const errorMsg = error.message.toLowerCase();

  if (errorMsg.includes('not found') || errorMsg.includes('not available')) {
    return getRandomItem(notFoundMessages);
  } else if (errorMsg.includes('connection') || errorMsg.includes('cannot')) {
    return "🔌 Oops! My friend, I'm having trouble connecting to the backend. It seems the API server might not be running on port 8000. No worries though! Just make sure the server is up and running, then give it another shot. We'll get you sorted! 🚀";
  } else if (errorMsg.includes('validation')) {
    return "📋 Hey there! It looks like there might be a little issue with how your question was formatted. No biggie! Just try rephrasing it a bit and ask again. I'm here to help! 😊";
  } else {
    return `😟 Oh man, something went a bit sideways on our end: ${escapeHtml(error.message)}. But hey, don't worry! Please give it another try, or if it keeps happening, reach out to our expert team - they'd be happy to help you out! 🤝`;
  }
}

/**
 * Add message to chat
 */
function addMessage(contentOrData, sender, isError = false) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${sender}-message`;

  if (sender === 'user') {
    // User message - just text
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = `<p>${escapeHtml(contentOrData)}</p>`;
    messageDiv.appendChild(contentDiv);
  } else if (isError) {
    // Error message - render as markdown
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    const markdown =
      typeof marked !== 'undefined'
        ? marked.parse(contentOrData)
        : contentOrData;
    contentDiv.innerHTML = `<div class="markdown-content">${markdown}</div>`;
    messageDiv.appendChild(contentDiv);
  } else {
    // Assistant message - rich data with markdown rendering
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    // Check if any chunks were actually found (backend checked this)
    if (contentOrData.chunks_used && contentOrData.chunks_used > 0) {
      // Sources were found - show the answer (even if short)
      const markdown =
        typeof marked !== 'undefined'
          ? marked.parse(contentOrData.answer)
          : contentOrData.answer;
      contentDiv.innerHTML = `<div class="markdown-content">${markdown}</div>`;
    } else if (
      !contentOrData.answer ||
      contentOrData.answer.trim().length === 0
    ) {
      // No chunks found and no answer - show friendly message
      const friendlyMsg = getRandomItem(notFoundMessages);
      const markdown =
        typeof marked !== 'undefined' ? marked.parse(friendlyMsg) : friendlyMsg;
      contentDiv.innerHTML = `<div class="markdown-content">${markdown}</div>`;
    } else {
      // Show whatever answer we have
      const markdown =
        typeof marked !== 'undefined'
          ? marked.parse(contentOrData.answer)
          : contentOrData.answer;
      contentDiv.innerHTML = `<div class="markdown-content">${markdown}</div>`;
    }

    // Message metadata
    const metaDiv = document.createElement('div');
    metaDiv.className = 'message-meta';

    // Add badges
    if (contentOrData.chunks_used) {
      const badge = document.createElement('span');
      badge.className = 'meta-badge';
      badge.innerHTML = `📄 ${contentOrData.chunks_used} sources found`;
      metaDiv.appendChild(badge);
    }

    if (contentOrData.model) {
      const badge = document.createElement('span');
      badge.className = 'meta-badge';
      badge.innerHTML = `🤖 ${contentOrData.model}`;
      metaDiv.appendChild(badge);
    }

    if (contentOrData.costs) {
      const badge = document.createElement('span');
      badge.className = 'meta-badge';
      badge.style.background = '#fbbf24';
      badge.style.color = '#000';
      badge.innerHTML = `💰 ${contentOrData.costs.total_cost}`;
      metaDiv.appendChild(badge);
    }

    if (contentOrData.cache_hit) {
      const badge = document.createElement('span');
      badge.className = 'meta-badge';
      badge.style.background = '#10b981';
      badge.innerHTML = `⚡ Cached (Super Fast!)`;
      metaDiv.appendChild(badge);
    }

    contentDiv.appendChild(metaDiv);

    // Sources button
    if (contentOrData.sources && contentOrData.sources.length > 0) {
      const sourcesBtn = document.createElement('button');
      sourcesBtn.className = 'sources-btn';
      sourcesBtn.innerHTML = `📚 View Sources & Details (${contentOrData.sources.length})`;
      sourcesBtn.onclick = () => showDetails(contentOrData);
      contentDiv.appendChild(sourcesBtn);
    }

    messageDiv.appendChild(contentDiv);
  }

  messagesContainer.appendChild(messageDiv);

  // Auto-scroll to bottom
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Show detailed information modal
 */
function showDetails(data) {
  let html = '';

  // Token Usage Section
  if (data.usage) {
    html += `
      <h2>📊 Token Usage</h2>
      <table>
        <tbody>
          <tr>
            <td><strong>Embedding Tokens</strong></td>
            <td>${data.usage.embedding_tokens || 0}</td>
          </tr>
          <tr>
            <td><strong>Prompt Tokens</strong></td>
            <td>${data.usage.llm_prompt_tokens || 0}</td>
          </tr>
          <tr>
            <td><strong>Completion Tokens</strong></td>
            <td>${data.usage.llm_completion_tokens || 0}</td>
          </tr>
          <tr>
            <td><strong>Total Tokens</strong></td>
            <td><strong>${data.usage.total_tokens || 0}</strong></td>
          </tr>
        </tbody>
      </table>
    `;
  }

  // Cost Breakdown Section
  if (data.costs) {
    html += `
      <h2>💰 Cost Breakdown</h2>
      <table>
        <tbody>
          <tr>
            <td><strong>Embedding Cost</strong></td>
            <td>${data.costs.embedding_cost}</td>
          </tr>
          <tr>
            <td><strong>LLM Query Cost</strong></td>
            <td>${data.costs.llm_cost}</td>
          </tr>
          <tr style="background-color: #f0f9ff; font-weight: bold;">
            <td><strong>Total Query Cost</strong></td>
            <td>${data.costs.total_cost}</td>
          </tr>
        </tbody>
      </table>
    `;
  }

  // Cache Savings Section
  if (data.cost_saved) {
    html += `
      <h2>⚡ Cache Savings</h2>
      <p>Cost saved (from caching): <strong>${data.cost_saved}</strong></p>
    `;
  }

  // General Info
  html += `
    <h2>ℹ️ Query Information</h2>
    <table>
      <tbody>
        <tr>
          <td><strong>Model</strong></td>
          <td>${data.model || 'N/A'}</td>
        </tr>
        <tr>
          <td><strong>Sources Found</strong></td>
          <td>${data.chunks_used || 0}</td>
        </tr>
        <tr>
          <td><strong>Cache Hit</strong></td>
          <td>${data.cache_hit ? '✅ Yes (Retrieved from cache)' : '❌ No (Fresh query)'}</td>
        </tr>
      </tbody>
    </table>
  `;

  // Sources Section
  if (data.sources && data.sources.length > 0) {
    html += `<h2>📚 Sources Used</h2>`;
    html += `
      <table>
        <thead>
          <tr>
            <th>Document</th>
            <th>Chunk</th>
            <th>Match Score</th>
            <th>Preview</th>
          </tr>
        </thead>
        <tbody>
    `;

    data.sources.forEach((source, index) => {
      const relevancePercent = (source.relevance_score * 100).toFixed(1);
      const preview =
        source.preview.substring(0, 100) +
        (source.preview.length > 100 ? '...' : '');

      html += `
        <tr>
          <td><strong>${escapeHtml(source.filename)}</strong></td>
          <td>#${source.chunk_index}</td>
          <td>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <div style="width: 60px; height: 6px; background: #e5e7eb; border-radius: 3px; overflow: hidden;">
                <div style="width: ${relevancePercent}%; height: 100%; background: #3b82f6;"></div>
              </div>
              ${relevancePercent}%
            </div>
          </td>
          <td><small>${escapeHtml(preview)}</small></td>
        </tr>
      `;
    });

    html += `
        </tbody>
      </table>
    `;
  }

  // Answer Section
  if (data.answer) {
    html += `
      <h2>💬 Full Answer</h2>
      <div style="background: #f3f4f6; padding: 1.5rem; border-radius: 8px; line-height: 1.7;">
        <div class="markdown-content">
          ${typeof marked !== 'undefined' ? marked.parse(data.answer) : escapeHtml(data.answer)}
        </div>
      </div>
    `;
  }

  modalBody.innerHTML = html;
  responseModal.classList.add('show');
}

/**
 * Close modal
 */
function closeModal() {
  responseModal.classList.remove('show');
}

/**
 * Show/hide loading spinner
 */
function showLoading(show, message = 'Thinking...') {
  const spinner = document.getElementById('loadingSpinner');
  const spinnerText = spinner.querySelector('p');

  if (show) {
    spinnerText.textContent = message;
    spinner.classList.remove('hidden');
  } else {
    spinner.classList.add('hidden');
  }
}

/**
 * Show error message
 */
function showError(message) {
  // Simple toast-like alert
  const alertDiv = document.createElement('div');
  alertDiv.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: #dc2626;
    color: white;
    padding: 1rem 1.5rem;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    z-index: 2000;
    animation: slideInUp 0.3s ease-out;
  `;
  alertDiv.innerHTML = `⚠️ ${message}`;
  document.body.appendChild(alertDiv);

  setTimeout(() => {
    alertDiv.remove();
  }, 3000);
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  };
  return text.replace(/[&<>"']/g, (m) => map[m]);
}

/**
 * Format text with markdown-like syntax
 */
function formatText(text) {
  if (!text) return '';

  // Escape HTML first
  let formatted = escapeHtml(text);

  // Convert markdown bold (**text**)
  formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  // Convert markdown italic (*text*)
  formatted = formatted.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Convert numbered lists
  formatted = formatted.replace(/^\d+\.\s+/gm, '&nbsp;&nbsp;&nbsp;&nbsp;');

  // Convert line breaks
  formatted = formatted.replace(/\n/g, '<br>');

  return formatted;
}

/**
 * Get random item from array
 */
function getRandomItem(array) {
  return array[Math.floor(Math.random() * array.length)];
}

/**
 * Initialize - check API connectivity and show welcome message
 */
async function initialize() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) {
      console.warn('API health check failed');
    }

    // Show welcome message as error type to render as plain markdown (not response data)
    const welcomeMsg = getRandomItem(friendlyGreetings);
    addMessage(welcomeMsg, 'assistant', true);
  } catch (error) {
    console.error('Cannot connect to API at', API_BASE_URL);
    const msg = document.createElement('div');
    msg.className = 'error-message';
    msg.innerHTML = `
            ⚠️ <strong>Connection Error</strong><br>
            Cannot connect to API at <code>${API_BASE_URL}</code><br>
            Please ensure the backend server is running on port 8000
        `;
    messagesContainer.appendChild(msg);
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initialize);
