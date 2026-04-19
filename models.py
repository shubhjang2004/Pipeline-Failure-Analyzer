
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class PipelineFailure(BaseModel):
    pipeline_name: str
    stage: str
    logs: str
    branch: Optional[str] = None
    commit_sha: Optional[str] = None

class SimilarFailure(BaseModel):
    pipeline: str
    category: str
    fix: str
    similarity_pct: float

class AnalysisResult(BaseModel):
    id: str = str(uuid.uuid4())       # ADD - needed for feedback loop
    pipeline_name: str
    error_category: str
    root_cause: str
    similar_past_failures: list[SimilarFailure]
    fix_suggestion: str
    confidence: str
    analyzed_at: str
    was_helpful: Optional[bool] = None  # ADD - for feedback loop

class FeedbackRequest(BaseModel):       # ADD - new model entirely
    analysis_id: str
    was_helpful: bool
    actual_fix: Optional[str] = None