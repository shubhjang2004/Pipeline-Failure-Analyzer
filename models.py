"""
models.py — Pydantic data shapes used across the whole app.

Pydantic does two things here:
1. Validates incoming API request bodies automatically
2. Serializes outgoing responses to JSON

If someone sends pipeline_name=123 (int), Pydantic coerces it to "123".
If stage is missing entirely, FastAPI returns a 422 error before your code runs.
"""
from pydantic import BaseModel
from typing import Optional


class PipelineFailure(BaseModel):
    """What the caller sends to /analyze"""
    pipeline_name: str
    stage: str          # "build" | "test" | "deploy" — we don't enforce, just informational
    logs: str           # raw stdout/stderr from the failed run
    branch: Optional[str] = None
    commit_sha: Optional[str] = None


class SimilarFailure(BaseModel):
    """One entry from the RAG knowledge base returned in the result"""
    pipeline: str
    category: str
    fix: str
    similarity_pct: float   # 0–100, how close the past failure is to this one


class AnalysisResult(BaseModel):
    """What /analyze returns"""
    pipeline_name: str
    error_category: str     # e.g. "Dependency Error", "OOMKilled", "Auth Error"
    root_cause: str         # 2-3 sentence explanation
    similar_past_failures: list[SimilarFailure]
    fix_suggestion: str     # Concrete steps, ideally with commands
    confidence: str         # "high" | "medium" | "low"
    analyzed_at: str        # ISO 8601 timestamp
