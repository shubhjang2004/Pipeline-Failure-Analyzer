import re
import json
import os
import time
from typing import TypedDict
from datetime import datetime, timezone

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END

from rag import search_failures
from models import PipelineFailure, AnalysisResult, SimilarFailure




import anthropic
claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))



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
    tools = [{
        "name": "report_analysis",
        "description": "Report the structured pipeline failure analysis",
        "input_schema": {
            "type": "object",
            "properties": {
                "error_category": {
                    "type": "string",
                    "enum": ["Dependency Error", "Docker Build Error", "Test Failure",
                             "Deployment Error", "Auth Error", "Network Error",
                             "Resource Error", "Config Error", "Other"]
                },
                "root_cause": {"type": "string"},
                "fix_suggestion": {"type": "string"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
            },
            "required": ["error_category", "root_cause", "fix_suggestion", "confidence"]
        }
    }]

    past_context = ""
    if state["similar_failures"]:
        past_context = "Past similar failures:\n"
        for f in state["similar_failures"]:
            past_context += f"[{f['similarity_pct']}% match] Fix used: {f['fix']}\n"

    for attempt in range(3):  # retry up to 3 times
        try:
            response = claude.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=1000,
                tools=tools,
                tool_choice={"type": "tool", "name": "report_analysis"},
                messages=[{
                    "role": "user",
                    "content": f"""Analyze this CI/CD failure.
Pipeline: {state['pipeline_name']} | Stage: {state['stage']}
Errors: {state['extracted_errors']}
{past_context}
Give specific fix steps with actual commands or file paths."""
                }]
            )

            analysis = response.content[0].input  # guaranteed structured, no JSON parsing
            return {**state, "final_analysis": analysis}

        except anthropic.RateLimitError:
            time.sleep(2 ** attempt)  # 1s, 2s, 4s backoff

        except Exception as e:
            if attempt == 2:  # only give up after 3rd failure
                return {**state, "final_analysis": {
                    "error_category": "Other",
                    "root_cause": f"Analysis failed: {str(e)}",
                    "fix_suggestion": "Manual investigation required.",
                    "confidence": "low"
                }}



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
