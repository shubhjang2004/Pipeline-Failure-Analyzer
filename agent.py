import re
import json
import os
from typing import TypedDict
from datetime import datetime, timezone

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END

from rag import search_failures
from models import PipelineFailure, AnalysisResult, SimilarFailure



from langchain_groq import ChatGroq

llm = ChatGroq(
    model="llama-3.3-70b-versatile",  # free, very capable
    temperature=0,
    api_key=os.getenv("GROQ_API_KEY")
)



class AnalysisState(TypedDict):
    pipeline_name: str
    stage: str
    logs: str
    branch: str
    commit_sha: str


    extracted_errors: str       
    similar_failures: list      
    final_analysis: dict       


def extract_errors_node(state: AnalysisState) -> AnalysisState:
   
    lines = state["logs"].split("\n")

    # These patterns cover most CI failure signatures
    error_re = re.compile(
        r"(error|ERROR|Error|FAILED|failed|Fatal|fatal"
        r"|Exception|Traceback|exit code [^0]"
        r"|npm ERR!|pip.*error|Cannot find|No such file"
        r"|Permission denied|Connection refused|timed? ?out"
        r"|OOMKilled|CrashLoopBackOff|ImagePullBackOff"
        r"|EACCES|ENOENT|ModuleNotFoundError|ImportError"
        r"|AssertionError|TypeError|ValueError|KeyError)",
        re.IGNORECASE
    )

    seen = set()
    error_lines = []
    for line in lines:
        stripped = line.strip()
        if error_re.search(stripped) and len(stripped) > 10 and stripped not in seen:
            seen.add(stripped)
            error_lines.append(stripped)

    extracted = "\n".join(error_lines[:30]) if error_lines else "\n".join(lines[-20:])

    return {**state, "extracted_errors": extracted}



def search_rag_node(state: AnalysisState) -> AnalysisState:
   
    query = f"{state['stage']}: {state['extracted_errors'][:400]}"
    raw_results = search_failures(query, n_results=3)

    similar = []
    for r in raw_results:
        similarity = (1 - r["distance"]) * 100
        if similarity > 25:  # Skip results with <25% similarity
            similar.append({
                "pipeline": r["metadata"].get("pipeline_name", "unknown"),
                "category": r["metadata"].get("error_category", "unknown"),
                "fix": r["metadata"].get("fix_applied", "unknown"),
                "similarity_pct": round(similarity, 1),
                "description": r["content"][:250]
            })

    return {**state, "similar_failures": similar}



def generate_analysis_node(state: AnalysisState) -> AnalysisState:

    if state["similar_failures"]:
        past_context = "Past failures from knowledge base (use these to inform your fix):\n"
        for f in state["similar_failures"]:
            past_context += (
                f"  [{f['similarity_pct']}% match] {f['category']} in {f['pipeline']}\n"
                f"  Fix used: {f['fix']}\n\n"
            )
    else:
        past_context = "No similar past failures found in knowledge base."

    prompt = f"""You are a senior DevOps/SRE engineer. Analyze this CI/CD failure.

Pipeline: {state["pipeline_name"]}
Stage: {state["stage"]}
Branch: {state["branch"]}
Commit: {state["commit_sha"]}

Key error lines (extracted from raw logs):
{state["extracted_errors"]}

{past_context}

Instructions:
- Be specific. "Update the package version" is bad.
  "Pin numpy to >=1.26.0 in requirements.txt" is good.
- If a past failure has a high similarity match, reuse its fix unless the errors differ.
- error_category must be one of:
  Dependency Error | Docker Build Error | Test Failure | Deployment Error |
  Auth Error | Network Error | Resource Error | Config Error | Other

Return ONLY valid JSON. No markdown. No explanation outside the JSON.

{{
    "error_category": "...",
    "root_cause": "2-3 sentences max",
    "fix_suggestion": "Numbered steps with actual commands or file paths",
    "confidence": "high | medium | low"
}}"""

    response = llm.invoke([HumanMessage(content=prompt)])
    text = response.content.strip()

    
    if "```" in text:
        # Extract content between first ``` and last ```
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) >= 2 else text

    try:
        analysis = json.loads(text)
    except json.JSONDecodeError:
        # Graceful fallback — never crash on bad LLM output
        analysis = {
            "error_category": "Other",
            "root_cause": text[:400],
            "fix_suggestion": "Manual investigation required. LLM response was not valid JSON.",
            "confidence": "low"
        }

    return {**state, "final_analysis": analysis}



def _build_graph() -> StateGraph:
    graph = StateGraph(AnalysisState)

    graph.add_node("extract_errors", extract_errors_node)
    graph.add_node("search_rag", search_rag_node)
    graph.add_node("generate_analysis", generate_analysis_node)

    # Linear pipeline: each node feeds directly into the next
    graph.set_entry_point("extract_errors")
    graph.add_edge("extract_errors", "search_rag")
    graph.add_edge("search_rag", "generate_analysis")
    graph.add_edge("generate_analysis", END)

    return graph.compile()



pipeline_graph = _build_graph()



def analyze_failure(failure: PipelineFailure) -> AnalysisResult:
    """
    Entry point: takes a PipelineFailure, runs the graph, returns AnalysisResult.
    FastAPI calls this; it knows nothing about LangGraph internals.
    """
    initial_state: AnalysisState = {
        "pipeline_name": failure.pipeline_name,
        "stage": failure.stage,
        "logs": failure.logs,
        "branch": failure.branch or "unknown",
        "commit_sha": failure.commit_sha or "unknown",
        "extracted_errors": "",
        "similar_failures": [],
        "final_analysis": {}
    }

    final_state = pipeline_graph.invoke(initial_state)
    analysis = final_state["final_analysis"]

    # Convert raw dicts to SimilarFailure Pydantic objects
    similar = [
        SimilarFailure(
            pipeline=f["pipeline"],
            category=f["category"],
            fix=f["fix"],
            similarity_pct=f["similarity_pct"]
        )
        for f in final_state["similar_failures"]
    ]

    return AnalysisResult(
        pipeline_name=failure.pipeline_name,
        error_category=analysis.get("error_category", "Other"),
        root_cause=analysis.get("root_cause", "Unknown"),
        similar_past_failures=similar,
        fix_suggestion=analysis.get("fix_suggestion", "Manual investigation required."),
        confidence=analysis.get("confidence", "low"),
        analyzed_at=datetime.now(timezone.utc).isoformat()
    )
