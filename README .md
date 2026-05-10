# Pipeline Failure Analyzer

> An **AI-powered CI/CD failure diagnosis system** that pinpoints root causes in noisy pipeline logs using LangGraph, RAG, and FastAPI — turning hours of manual debugging into seconds.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-orange)](https://langchain-ai.github.io/langgraph/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-VectorStore-purple)](https://www.trychroma.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## Overview

**CI/CD failures bury root causes in noisy logs** — Docker layer hashes, timestamps, and stack traces make manual debugging slow and error-prone at scale. This system diagnoses pipeline failures automatically by combining regex-based signal extraction, semantic search over historical incidents, and LLM synthesis.

> **Companion project:** [DORA Deployment Risk Scorer](https://github.com/shubhjang2004/AI-Powered-DORA-Metrics-Dashboard-with-Predictive-Deployment-Risk-Scoring) predicts failures *before* they happen. This project diagnoses them *after* they happen. Together they form a complete CI/CD intelligence layer.

**What it does:**
- Extracts error signals from raw logs via regex — no tokens wasted on noise
- Searches ChromaDB for top-3 semantically similar past incidents
- Synthesizes a focused root-cause analysis using LLM with only clean context
- Reduces prompt size by **60–70%** via pre-filtering, cutting inference cost significantly
- Exposes production REST API with Pydantic schema validation and confidence scoring

---

## Architecture

```
POST /analyze
     │
     ▼
┌─────────────────────────────────────────────────────┐
│              LangGraph StateGraph                    │
│                                                      │
│  ┌──────────────┐   ┌─────────────┐   ┌──────────┐  │
│  │extract_errors│──▶│ search_rag  │──▶│ generate │  │
│  │   (regex)    │   │ (chromadb)  │   │ analysis │  │
│  │  no LLM call │   │  no LLM call│   │  1 call  │  │
│  └──────────────┘   └─────────────┘   └──────────┘  │
└─────────────────────────────────────────────────────┘
```

**Why 3 nodes instead of one LLM call?**

Sending raw logs directly to the LLM would:
- Waste tokens on Docker layer hashes, progress bars, and timestamps
- Provide no benefit from past failure history
- Pay full prompt cost on every request

Instead the pipeline separates concerns cleanly:

1. **extract_errors** — regex pulls signal from noise (fast, free, no LLM)
2. **search_rag** — vector search finds similar resolved failures (fast, free, no LLM)
3. **generate_analysis** — LLM sees only clean errors + relevant history (focused, cheap, 1 call)

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/shubhjang2004/Pipeline-Failure-Analyzer.git
cd Pipeline-Failure-Analyzer

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your Anthropic API key
cp .env.example .env
# Edit .env: ANTHROPIC_API_KEY=your_key_here

# 4. Seed the knowledge base with sample failures
python seed.py

# 5. Start the server
uvicorn main:app --reload

# 6. Run test scenarios
python test_analyze.py

# 7. Explore the interactive Swagger UI
open http://localhost:8000/docs
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/analyze` | POST | Diagnose a CI/CD failure from raw logs |
| `/ingest` | POST | Add a resolved failure to the knowledge base |
| `/health` | GET | Service health check |

### Example: Analyze a Failure

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline_name": "api-service-ci",
    "stage": "build",
    "branch": "main",
    "logs": "ERROR: Could not build wheels for numpy\nexit code: 1"
  }'
```

### Example: Ingest a Resolved Failure

```bash
curl -X POST "http://localhost:8000/ingest?\
pipeline_name=api-ci&\
error_category=Dependency+Error&\
description=numpy+wheel+missing+for+python+3.12&\
fix_applied=Pin+numpy+to+1.26.0+in+requirements.txt"
```

---

## Project Structure

```
├── main.py             # FastAPI routes — /analyze and /ingest endpoints
├── agent.py            # LangGraph StateGraph — 3-node analysis pipeline
├── rag.py              # ChromaDB vector store — ingest and search failures
├── models.py           # Pydantic request/response schemas + confidence scoring
├── seed.py             # Populate KB with realistic historical failures
├── test_analyze.py     # Test the API with realistic log samples
├── chroma_db/          # Persisted ChromaDB vector store
└── requirements.txt    # Dependencies
```

---

## Key Design Decisions

**Why regex pre-filtering before the LLM?**
Raw CI/CD logs are 80–90% noise — layer hashes, timestamps, download progress. Regex extracts only error lines first, reducing prompt size by 60–70% and cutting LLM inference cost significantly without losing diagnostic signal.

**Why ChromaDB with all-MiniLM-L6-v2 embeddings?**
Historical failures are unstructured text. Semantic search via cosine similarity finds past incidents that are conceptually similar even when the exact error message differs — something keyword search can't do.

**Why LangGraph StateGraph over a single chain?**
Each node has a single responsibility: extract, search, synthesize. This makes the pipeline debuggable, testable per stage, and extensible — add a new node (e.g. Slack notifier) without touching existing logic.

**Why confidence scoring?**
The API returns `high/medium/low` confidence based on how closely the retrieved incidents match. This lets downstream consumers decide whether to auto-remediate or escalate to a human.

---

## Extending This

**Add GitHub webhook** — trigger `/analyze` automatically when a pipeline fails instead of calling it manually.

**Add history store** — add SQLite or Postgres to save every analysis result for trending and reporting over time.

**Add streaming** — use FastAPI's `StreamingResponse` + LangChain streaming callbacks to stream the analysis in real time.

**Grow the KB** — after every real incident, call `/ingest` to add it. The system gets smarter with every failure resolved.

---

## Requirements

- **Python** >= 3.8
- **Anthropic API key** (get one at [console.anthropic.com](https://console.anthropic.com))
- **ChromaDB**, **LangGraph**, **FastAPI**, **uvicorn**

See `requirements.txt` for the full list.

---

## Related Project

**[DORA Deployment Risk Scorer](https://github.com/shubhjang2004/AI-Powered-DORA-Metrics-Dashboard-with-Predictive-Deployment-Risk-Scoring)** — predicts CI/CD failures *before* deployment using XGBoost + DORA metrics + LLM advisory. Use both together: score risk before deploy, diagnose root cause if it fails.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
