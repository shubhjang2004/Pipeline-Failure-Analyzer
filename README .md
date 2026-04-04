# Pipeline Failure Analyzer

AI-powered CI/CD failure analysis using **LangGraph + RAG + FastAPI**.

Built as a portfolio project targeting AI Engineer roles at DevOps platforms like Harness.

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

If you sent raw logs directly to the LLM, you'd:
- Waste tokens on Docker layer hashes, progress bars, timestamps
- Get no benefit from past failure history
- Pay for a large prompt every time

Instead:
1. **extract_errors** — regex pulls signal from noise (fast, free)
2. **search_rag** — vector search finds similar resolved failures (fast, free)
3. **generate_analysis** — LLM sees only errors + relevant history (focused, cheap)

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key
cp .env.example .env
# Edit .env with your Anthropic API key

# 3. Populate knowledge base with sample failures
python seed.py

# 4. Start the server
uvicorn main:app --reload
```

Open http://localhost:8000/docs for the Swagger UI.

---

## Usage

### Analyze a failure

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

### Add a resolved failure to the KB

```bash
curl -X POST "http://localhost:8000/ingest?\
pipeline_name=api-ci&\
error_category=Dependency+Error&\
description=numpy+wheel+missing+for+python+3.12&\
fix_applied=Pin+numpy+to+1.26.0+in+requirements.txt"
```

### Run test cases

```bash
python test_analyze.py
```

---

## Files

| File | Purpose |
|------|---------|
| `models.py` | Pydantic request/response shapes |
| `rag.py` | ChromaDB vector store — add + search failures |
| `agent.py` | LangGraph StateGraph — the 3-node analysis pipeline |
| `main.py` | FastAPI routes |
| `seed.py` | Populate KB with realistic past failures |
| `test_analyze.py` | Test the API with realistic log samples |

---

## Extending This

**Add more failure types to the KB**: After every real incident, call `/ingest` to add it. The KB gets smarter over time.

**Add GitHub webhook**: Trigger `/analyze` automatically when a pipeline fails instead of calling it manually.

**Add a history store**: Add SQLite (or Postgres) to save every analysis result for trending/reporting.

**Add streaming**: Use FastAPI's `StreamingResponse` + LangChain streaming callbacks to stream the analysis in real time.
