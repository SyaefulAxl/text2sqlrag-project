# 📚 RAG Document Chatbot Frontend

A modern, responsive chatbot interface for querying your documents using the RAG (Retrieval-Augmented Generation) API.

## Features

✨ **Clean, Modern UI** - Inspired by Gemini chatbot design
📱 **Fully Responsive** - Works on desktop, tablet, and mobile
🎯 **Rich Information Display** - Shows answers with detailed source information
📊 **Token Usage Tracking** - View API usage statistics
⚡ **Cache Awareness** - Displays cache hits and cost savings
🔍 **Source Attribution** - View all sources with relevance scores and previews

## Quick Start

### Option 1: Using Python HTTP Server (Recommended)

1. **Ensure the backend API is running** on `http://localhost:8000`:

   ```bash
   cd ../
   uvicorn app.main:app --reload
   ```

2. **In another terminal, start the frontend server**:

   ```bash
   cd frontend
   python server.py
   ```

3. **Open your browser** to `http://localhost:8080`

### Option 2: Using VS Code Live Server

1. Install the "Live Server" extension in VS Code
2. Right-click on `index.html` → "Open with Live Server"
3. Make sure your backend API is running on `http://localhost:8000`

### Option 3: Using Node.js HTTP Server

```bash
cd frontend
npx http-server -p 8080 -c-1
```

### Option 4: Using Ruby

```bash
cd frontend
ruby -run -ehttpd . -p 8080
```

## How to Use

1. **Ask a Question** - Type your question in the input field at the bottom
2. **Wait for Response** - The API will search documents and generate an answer
3. **View Answer** - The main answer is displayed in the chat
4. **See Details** - Click "View Details" button to see:
   - Token usage statistics
   - All sources with relevance scores
   - Source previews
   - Cost savings (if cached)

## Features Explained

### 📊 Token Usage

Shows exactly how many tokens were used:

- **Embedding Tokens** - Cost of searching documents
- **Prompt Tokens** - Input to the language model
- **Completion Tokens** - Generated response
- **Total Tokens** - Sum of all tokens used

### 📚 Sources

Each source shows:

- **Filename** - Which document the chunk came from
- **Chunk Index** - Which part of the document
- **Relevance Score** - How relevant (0.0-1.0)
- **Preview** - First 100 characters of the source text

### ⚡ Cache Hit

When a query is cached:

- Response is instant
- Cost savings are applied
- Badge shows "⚡ Cached"

## API Endpoint

The frontend calls: `POST http://localhost:8000/query/documents`

Request body:

```json
{
  "question": "Your question here",
  "top_k": 10
}
```

Response contains:

- `answer` - The generated answer
- `question` - Your original question
- `chunks_used` - Number of source chunks
- `model` - LLM model used
- `usage` - Token usage statistics
- `sources` - List of source documents with scores
- `cache_hit` - Whether result was cached
- `cost_saved` - Amount saved by caching

## Customization

### Change API URL

Edit `script.js` line 4:

```javascript
const API_BASE_URL = 'http://your-api-server:8000';
```

### Change Server Port

Edit `server.py` line 9:

```python
PORT = 8080  # Change this to your desired port
```

### Customize Colors

Edit `style.css` CSS variables (lines 11-20):

```css
:root {
  --primary-color: #1f2937;
  --accent-color: #3b82f6;
  /* ... etc */
}
```

## Troubleshooting

### "Cannot connect to API"

- ✅ Ensure backend is running: `uvicorn app.main:app --reload`
- ✅ Check backend is on port 8000
- ✅ Verify no firewall blocking localhost

### CORS Error

- The server.py automatically adds CORS headers
- If using a different server, ensure it allows cross-origin requests

### API Returns 404

- Check the document has been uploaded to the backend
- Verify the endpoint is `/query/documents`

### Slow Response

- First query will be slower (building embeddings)
- Subsequent similar queries will be faster (cached)
- Check token usage in the Details panel

## Browser Support

- ✅ Chrome/Edge (Latest)
- ✅ Firefox (Latest)
- ✅ Safari (Latest)
- ✅ Mobile browsers

## File Structure

```
frontend/
├── index.html       # Main HTML structure
├── style.css        # Styling (responsive design)
├── script.js        # API interaction & UI logic
├── server.py        # Simple HTTP server
└── README.md        # This file
```

## Development

To modify the frontend:

1. **HTML** - Edit `index.html` to change structure
2. **Styling** - Edit `style.css` for colors, layout, responsive behavior
3. **Logic** - Edit `script.js` for API calls, message handling, UI updates

### Adding Features

Example: Add dark mode toggle

1. Add button to HTML
2. Add CSS classes for dark mode
3. Add JavaScript to toggle classes on click

## License

MIT - Free to use and modify

## Support

If you encounter issues:

1. Check browser console (F12 → Console)
2. Check network tab for API errors
3. Verify backend logs for API issues
4. Ensure correct API URL in `script.js`

---

**Happy querying! 🚀**
