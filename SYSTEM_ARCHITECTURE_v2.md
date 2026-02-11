# 🏗️ System Architecture - Enhanced RAG v2.0

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT BROWSER                              │
│                 (LocalHost or Network IP Access)                    │
└────────────────┬────────────────────────────────┬───────────────────┘
                 │                                │
     ┌───────────▼──────────────┐    ┌───────────▼──────────────┐
     │  Localhost:8080          │    │  Network IP:8080         │
     │  (Same Machine)          │    │  (Other Machines)        │
     └───────────┬──────────────┘    └───────────┬──────────────┘
                 │                                │
                 └────────────────┬────────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  Auto-detection Logic     │
                    │  hostname === '192...'?   │
                    │  → 192.168.0.253:8000    │
                    │  else → localhost:8000    │
                    └─────────────┬──────────────┘
                                  │
┌─────────────────────────────────▼──────────────────────────────────┐
│                         FASTAPI BACKEND                             │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ CORS Middleware                                              │ │
│  │ • Allow localhost:8080                                       │ │
│  │ • Allow 192.168.0.253:8080  ← NEW                           │ │
│  └───────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
         ┌─────────────────────────▼──────────────────────────┐
         │               RAG PIPELINE                         │
         │          (app/services/rag_service.py)            │
         │                                                    │
         │  Step 1: Generate Query Embedding                 │
         │  Step 2: Search Vector DB (Pinecone)             │
         │  Step 3: Build Context                            │
         │  Step 4: Generate Answer [ENHANCED with Markdown]│
         │  Step 5: Calculate Costs [NEW]                    │
         │  Step 6: Format Sources                           │
         │  Step 7: Cache Result                             │
         │                                                    │
         └───────────────────────────┬──────────────────────┘
                                     │
        ┌────────────────────────────▼─────────────────────────┐
        │            RESPONSE OBJECT [NEW FORMAT]              │
        │                                                       │
        │ {                                                     │
        │   "answer": "**Spinning** is...",                   │
        │   "chunks_used": 10,                                │
        │   "usage": {...},                                    │
        │   "costs": {              ← NEW                      │
        │     "embedding_cost": "$0.000160",                  │
        │     "llm_cost": "$0.035280",                        │
        │     "total_cost": "$0.035440"                       │
        │   },                                                 │
        │   "sources": [...]                                   │
        │ }                                                     │
        │                                                       │
        └───────────────────────────┬─────────────────────────┘
                                     │
        ┌────────────────────────────▼─────────────────────────┐
        │       FRONTEND RENDERING [ENHANCED]                  │
        │                                                       │
        │  Markdown Answer with formatting                     │
        │  Metadata Badges:                                    │
        │  • 📄 10 sources found                               │
        │  • 🤖 gpt-4-turbo-preview                           │
        │  • 💰 $0.035440                                      │
        │  • ⚡ Cached (if applicable)                         │
        │                                                       │
        │  Modal Details:                                      │
        │  • 📊 Token Usage                                    │
        │  • 💰 Cost Breakdown (NEW)                           │
        │  • ℹ️ Query Information                              │
        │  • 📚 Sources Used                                   │
        └────────────────────────────────────────────────────────┘
```

---

## Cost Calculation Flow

```
Query Received
    │
    ├─ Generate Embedding
    │  └─ tokens × ($0.02 / 1,000,000) = cost
    │
    ├─ Call LLM API
    │  ├─ Prompt: tokens × ($0.01 / 1,000) = cost
    │  ├─ Completion: tokens × ($0.03 / 1,000) = cost
    │  └─ LLM Total: prompt + completion
    │
    └─ Calculate Total
       └─ embedding_cost + llm_cost

For Cache Hit:
    └─ Cost = $0.00 (no API calls)
```

---

## Network Access Flow

```
User's Computer (192.168.0.253)
          │
          │ Runs: .\run-api-network.ps1
          ↓
    Backend listening on 0.0.0.0:8000
          │
Other Computer on Network
          │
          │ Accesses: 192.168.0.253:8080
          ↓
    Frontend auto-detects origin
          ↓
    Routes API calls to 192.168.0.253:8000
          ↓
    Success! ✓
```

---

**Architecture Version**: 2.0  
**Last Updated**: February 2026  
**Status**: ✅ Production Ready
