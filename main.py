import uuid
import os
import logging
import time

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv

load_dotenv()

from models import PipelineFailure, AnalysisResult, FeedbackRequest
from agent import analyze_failure
from rag import add_failure, count_failures

# ── Logging setup ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

# ── Auth setup ─────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key")

def verify_key(key: str = Security(api_key_header)):
    if key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")

# ── App setup ──────────────────────────────────────────────────
app = FastAPI(
    title="Pipeline Failure Analyzer",
    description=(
        "AI-powered CI/CD pipeline failure analysis. "
        "Uses a LangGraph 3-node pipeline: log extraction → RAG retrieval → LLM synthesis."
    ),
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Quick check that the service is up and the KB has data."""
    return {
        "status": "ok",
        "knowledge_base_entries": count_failures(),
        "tip": "Run seed.py first if knowledge_base_entries is 0"
    }


@app.post("/analyze", response_model=AnalysisResult, dependencies=[Depends(verify_key)])
def analyze(failure: PipelineFailure):
    """
    Analyze a pipeline failure.
    Requires X-API-Key header.
    """
    start = time.time()
    try:
        result = analyze_failure(failure)
        logger.info(
            f"analyzed pipeline={failure.pipeline_name} "
            f"stage={failure.stage} "
            f"category={result.error_category} "
            f"confidence={result.confidence} "
            f"duration={time.time() - start:.2f}s"
        )
        return result
    except Exception as e:
        logger.error(f"analysis failed pipeline={failure.pipeline_name} error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest", status_code=201, dependencies=[Depends(verify_key)])
def ingest(
    pipeline_name: str,
    error_category: str,
    description: str,
    fix_applied: str
):
    """
    Add a resolved failure to the knowledge base.
    Requires X-API-Key header.
    """
    failure_id = str(uuid.uuid4())
    embeddable_text = f"{error_category}: {description}"
    add_failure(
        id=failure_id,
        failure_text=embeddable_text,
        metadata={
            "pipeline_name": pipeline_name,
            "error_category": error_category,
            "fix_applied": fix_applied
        }
    )
    logger.info(f"ingested failure id={failure_id} pipeline={pipeline_name} category={error_category}")
    return {
        "message": "Added to knowledge base",
        "id": failure_id,
        "total_entries": count_failures()
    }


@app.post("/feedback", dependencies=[Depends(verify_key)])
def feedback(req: FeedbackRequest):
    """
    Tell the system if the suggested fix was helpful.
    If not helpful and you provide the actual fix, it gets
    added to the knowledge base so future analyses improve.
    """
    if not req.was_helpful and req.actual_fix:
        correction_id = str(uuid.uuid4())
        add_failure(
            id=correction_id,
            failure_text=f"Correction: {req.actual_fix}",
            metadata={
                "source": "user_feedback",
                "original_analysis_id": req.analysis_id,
                "fix_applied": req.actual_fix
            }
        )
        logger.info(f"feedback correction ingested id={correction_id} original={req.analysis_id}")
        return {"message": "Correction recorded and added to knowledge base", "id": correction_id}

    logger.info(f"feedback received analysis_id={req.analysis_id} helpful={req.was_helpful}")
    return {"message": "Feedback recorded"}


@app.get("/stats")
def stats():
    """
    Aggregated knowledge base stats.
    Hook this up to a dashboard or Slack bot.
    """
    return {
        "total_in_knowledge_base": count_failures(),
        "note": "Connect PostgreSQL to get per-category breakdowns and MTTR tracking"
    }