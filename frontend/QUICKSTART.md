# 🚀 Quick Start Guide - Frontend

## 1️⃣ Start Backend (If Not Already Running)

Open a terminal in the project root:

```bash
cd text2sqlrag-project
uvicorn app.main:app --reload
```

✅ Backend should be running on: `http://localhost:8000`

## 2️⃣ Start Frontend Server

Open a new terminal in the frontend folder:

```bash
cd text2sqlrag-project/frontend
python server.py
```

✅ Frontend should be running on: `http://localhost:8080`

## 3️⃣ Open in Browser

Visit: **http://localhost:8080**

You should see:

```
📚 Document RAG Assistant
Ask questions about your documents and get detailed answers
```

## 4️⃣ Ask Questions!

Example questions you could ask:

- "How did the industrial revolution transform traditional spinning methods?"
- "What are the different types of spinning techniques?"
- "Explain ring spinning process"
- "What is the history of textile spinning?"

## What You'll See

### Main Chat Area

- Your questions appear on the right (blue bubbles)
- AI answers appear on the left (gray bubbles)
- Answer is the main text content

### Below Each Answer

```
📄 10 sources used | 🤖 gpt-4-turbo-preview | ⚡ Cached
📚 View Details (10 sources)
```

### Click "View Details" to See:

- **📊 Token Usage** - How many tokens were consumed
- **💰 Cost Savings** - How much was saved by caching
- **ℹ️ Query Info** - Model, chunks used, cache status
- **📚 Sources** - Table with all sources:
  - Filename
  - Chunk index
  - Relevance score (with visual bar)
  - Preview text
- **💬 Full Answer** - Complete answer in large text

##🛠️ Troubleshooting

### "Cannot connect to API"

Check terminal where backend is running - should show startup complete

### "Page won't load"

- Frontend server running? Check terminal
- Try `http://localhost:8080` in address bar

### "Ask button doesn't work"

- Check browser console (F12 → Console tab)
- Look for error messages

### No results from API

- Verify documents were uploaded first
- Check backend is fully initialized (look for "API is ready!")

## 📱 Works On

- 🖥️ Desktop (Windows, Mac, Linux)
- 📱 Tablet (iPad, Android tablets)
- 📱 Mobile (iPhone, Android phones)

## ⌨️ Keyboard Shortcuts

- **Enter** - Send message (focus on input field)
- **Tab** - Move between focus areas
- **Esc** - Close details modal (when open)

## 🎨 Interface Overview

```
┌─────────────────────────────────────────┐
│  📚 Document RAG Assistant              │  Header
├─────────────────────────────────────────┤
│                                         │
│  👋 Hello! I'm your Document...         │  Messages
│                                         │
│  You: "How did..."                      │
│                                         │
│  AI: The Industrial Revolution...       │
│  📄 10 sources | 🤖 gpt-4 | ⚡ Cached   │
│  📚 View Details                        │
│                                         │
├─────────────────────────────────────────┤
│  [Ask a question...............] [Send] │  Input
│  Press Enter or click Send              │
└─────────────────────────────────────────┘
```

## 📊 Sample Response Details

When you click "View Details":

**Token Usage Table**
| Metric | Count |
|--------|-------|
| Embedding Tokens | 10 |
| Prompt Tokens | 2,650 |
| Completion Tokens | 341 |
| Total Tokens | 3,001 |

**Sources Used Table**
| Filename | Chunk | Relevance | Preview |
|----------|-------|-----------|---------|
| SPINNING - Textile... | 3 | 70.7% | The simple spindle spinning... |
| SPINNING - Textile... | 6 | 59.2% | The major reason for... |

## 💡 Tips

1. **First question is slower** - API builds embeddings on first query
2. **Same questions are instant** - Results are cached
3. **More specific questions = better answers** - Provide context
4. **Check sources** - Understand where answers come from
5. **Watch token usage** - Know how many tokens each question uses

## 🔗 Useful Links

- Backend API Docs: `http://localhost:8000/docs`
- Backend Health: `http://localhost:8000/health`
- Frontend: `http://localhost:8080`

---

**That's it! You're ready to go! 🎉**
