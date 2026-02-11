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
  "Hi there! I'm your textile knowledge assistant. I'm here to help you explore and understand everything about our textile world. Just ask me anything about the documents!",
  "Welcome to your personal textile knowledge assistant. I'm here to help you find answers to all your textile-related questions.",
  "Welcome! I'm your guide through the textile knowledge universe. Ask me anything about your documents, and I'll explain it clearly.",
];

const notFoundMessages = [
  "We're sorry, but we don't have enough information in our documents to answer that question yet. Please contact our expert team for more help.",
  "This information hasn't been found in our documents yet. Our expert team would be happy to help you get the answer you need.",
  "I couldn't find the specific information about this in our current documents. Please contact our team directly for assistance.",
];

const loadingMessages = [
  'Searching through the documents for you...',
  'Let me find that answer for you...',
  'Processing your question...',
  'Thinking about this question...',
  'Searching our knowledge base...',
  'Preparing the answer...',
];

// DOM Elements
const messagesContainer = document.getElementById('messagesContainer');
const questionInput = document.getElementById('questionInput');
const sendBtn = document.getElementById('sendBtn');
const loadingSpinner = document.getElementById('loadingSpinner');
const responseModal = document.getElementById('responseModal');
const modalBody = document.getElementById('modalBody');
const modalClose = document.querySelector('.modal-close');

// Format selection
let selectedFormat = 'default'; // default, cornell, obsidian, study

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
      'Hey there! You gotta ask me something to get started! What would you like to know about our textile knowledge?',
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
    // Call API with format preference
    const response = await fetchQuery(question, selectedFormat);

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
async function fetchQuery(question, format = 'default') {
  // Build query parameters
  const params = new URLSearchParams({
    question: question,
    top_k: 10,
    format_style: format,
  });

  const response = await fetch(`${API_ENDPOINT}?${params}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
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
    return "Connection Error: I'm having trouble connecting to the backend. Please ensure the API server is running on port 8000 and try again.";
  } else if (errorMsg.includes('validation')) {
    return 'Validation Error: There might be an issue with how your question was formatted. Please try rephrasing it.';
  } else {
    return `Error: ${escapeHtml(error.message)}. Please try again or contact our support team.`;
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

    // Show typo correction info if applicable
    if (contentOrData.typo_corrected && contentOrData.original_question) {
      const correctionDiv = document.createElement('div');
      correctionDiv.style.padding = '8px 12px';
      correctionDiv.style.background = '#fff3cd';
      correctionDiv.style.border = '1px solid #ffc107';
      correctionDiv.style.borderRadius = '4px';
      correctionDiv.style.marginBottom = '8px';
      correctionDiv.style.fontSize = '0.9em';
      correctionDiv.innerHTML = `<strong>Typo Corrected:</strong> "${escapeHtml(contentOrData.original_question)}" → "${escapeHtml(contentOrData.question)}"`;
      contentDiv.insertBefore(correctionDiv, contentDiv.firstChild);
    }

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
  if (data.cost) {
    html += `
      <h2>💰 Cost Breakdown</h2>
      <table>
        <tbody>
          <tr>
            <td><strong>Embedding Cost</strong></td>
            <td>${data.cost.formatted.embedding_cost}</td>
          </tr>
          <tr>
            <td><strong>LLM Query Cost</strong></td>
            <td>${data.cost.formatted.llm_cost}</td>
          </tr>
          <tr style="background-color: #f0f9ff; font-weight: bold;">
            <td><strong>Total Query Cost</strong></td>
            <td>${data.cost.formatted.total_cost}</td>
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
