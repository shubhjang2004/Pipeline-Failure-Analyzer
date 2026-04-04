
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv() 

from models import PipelineFailure, AnalysisResult
from agent import analyze_failure
from rag import add_failure, count_failures


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


@app.get("/health")
def health():
    """Quick check that the service is up and the KB has data."""
    return {
        "status": "ok",
        "knowledge_base_entries": count_failures(),
        "tip": "Run seed.py first if knowledge_base_entries is 0"
    }


@app.post("/analyze", response_model=AnalysisResult)
def analyze(failure: PipelineFailure):
    """
    Analyze a pipeline failure.

    Send raw logs + metadata. The agent will:
    1. Extract meaningful error lines from the log noise
    2. Search for similar past failures in the knowledge base
    3. Ask the LLM to synthesize a root cause + fix suggestion

    The response includes similar past failures so you can see
    what the LLM used as context (important for debugging bad answers).
    """
    try:
        return analyze_failure(failure)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest", status_code=201)
def ingest(
    pipeline_name: str,
    error_category: str,
    description: str,   # What the error was
    fix_applied: str    # What fixed it
):
    """
    Add a resolved failure to the knowledge base.

    Call this after you fix a real pipeline failure so future
    similar failures benefit from your institutional knowledge.

    Example:
        POST /ingest?pipeline_name=api-ci&error_category=Dependency+Error
             &description=numpy+wheel+missing+for+python+3.12
             &fix_applied=Pin+numpy+to+1.26.0+in+requirements.txt
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

    return {
        "message": "Added to knowledge base",
        "id": failure_id,
        "total_entries": count_failures()
    }
