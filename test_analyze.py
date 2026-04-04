
import httpx

BASE_URL = "http://localhost:8000"
TIMEOUT = 60  


def run(failure: dict):
    print(f"\n{'='*65}")
    print(f"→ Testing: {failure['pipeline_name']} ({failure['stage']} stage)")
    print("  Sending to /analyze...")

    resp = httpx.post(f"{BASE_URL}/analyze", json=failure, timeout=TIMEOUT)

    if resp.status_code != 200:
        print(f"  ERROR {resp.status_code}: {resp.text}")
        return

    r = resp.json()
    print(f"\n  Category  : {r['error_category']}")
    print(f"  Confidence: {r['confidence']}")
    print(f"\n  Root Cause:\n  {r['root_cause']}")
    print(f"\n  Fix:\n  {r['fix_suggestion']}")

    if r["similar_past_failures"]:
        print(f"\n  Similar Past Failures:")
        for s in r["similar_past_failures"]:
            print(f"    {s['similarity_pct']}% match — {s['pipeline']} ({s['category']})")
            print(f"    Fix used then: {s['fix']}")


# ─── Test Case 1: Python dependency / wheel mismatch ──────────────────────────
NUMPY_BUILD_FAIL = {
    "pipeline_name": "recommendation-engine-ci",
    "stage": "build",
    "branch": "feature/upgrade-python",
    "commit_sha": "a1b2c3d4",
    "logs": """
[2024-01-15 09:12:03] Step 1/9 : FROM python:3.12-slim
[2024-01-15 09:12:05] Step 2/9 : WORKDIR /app
[2024-01-15 09:12:05] Step 3/9 : COPY requirements.txt .
[2024-01-15 09:12:07] Step 4/9 : RUN pip install -r requirements.txt
[2024-01-15 09:12:08] Collecting numpy==1.24.0
[2024-01-15 09:12:12]   Downloading numpy-1.24.0.tar.gz (10.9 MB)
[2024-01-15 09:13:45]   Installing build dependencies: started
[2024-01-15 09:15:02]   Installing build dependencies: finished
[2024-01-15 09:15:03]   Getting requirements to build wheel: started
[2024-01-15 09:15:20]   Getting requirements to build wheel: finished
[2024-01-15 09:15:21]   Preparing metadata (pyproject.toml): started
[2024-01-15 09:15:55]   Preparing metadata (pyproject.toml): finished
[2024-01-15 09:15:55]   Building wheel for numpy (pyproject.toml): started
[2024-01-15 09:18:30]   Building wheel for numpy (pyproject.toml): finished with status 'error'
[2024-01-15 09:18:30]   error: subprocess-exited-with-error
[2024-01-15 09:18:30]   × python setup.py egg_info did not run successfully.
[2024-01-15 09:18:30]   │ exit code: 1
[2024-01-15 09:18:30]   ERROR: Could not build wheels for numpy, which is required to install pyproject.toml-based projects
[2024-01-15 09:18:31] The command '/bin/sh -c pip install -r requirements.txt' returned a non-zero code: 1
"""
}

# ─── Test Case 2: Kubernetes OOMKilled deployment ─────────────────────────────
OOM_DEPLOY_FAIL = {
    "pipeline_name": "inventory-service-cd",
    "stage": "deploy",
    "branch": "main",
    "commit_sha": "e5f6g7h8",
    "logs": """
[deploy] Applying k8s manifests to production cluster
[deploy] kubectl apply -f k8s/
[deploy] deployment.apps/inventory-service configured
[deploy] Waiting for rollout to complete (timeout: 5m)...
[k8s] inventory-service-7d4b9c-xkp2l   0/1   Pending      0   5s
[k8s] inventory-service-7d4b9c-xkp2l   0/1   Running      0   12s
[k8s] inventory-service-7d4b9c-xkp2l   0/1   OOMKilled    0   18s
[k8s] inventory-service-7d4b9c-xkp2l   0/1   CrashLoopBackOff  1   30s
[k8s] inventory-service-7d4b9c-xkp2l   0/1   OOMKilled    1   45s
[k8s] inventory-service-7d4b9c-xkp2l   0/1   CrashLoopBackOff  2   60s
[deploy] Error: deployment "inventory-service" exceeded its progress deadline
[deploy] Rollout failed. Rolling back to previous version.
[deploy] exit code 1
"""
}

# ─── Test Case 3: Flaky integration test with Redis ───────────────────────────
REDIS_TIMEOUT_FAIL = {
    "pipeline_name": "messaging-service-ci",
    "stage": "test",
    "branch": "fix/retry-logic",
    "commit_sha": "i9j0k1l2",
    "logs": """
[test] Starting test suite...
[test] pytest tests/ -v --timeout=30
[test] tests/test_queue.py::test_enqueue PASSED
[test] tests/test_queue.py::test_dequeue PASSED
[test] tests/test_integration.py::test_message_persistence ...
[test] redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379. Connection refused.
[test] FAILED tests/test_integration.py::test_message_persistence - redis.exceptions.ConnectionError
[test] tests/test_integration.py::test_retry_on_failure ...
[test] redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379. Connection refused.
[test] FAILED tests/test_integration.py::test_retry_on_failure - redis.exceptions.ConnectionError
[test] ======================== 2 failed, 2 passed in 12.34s =========================
[test] exit code 1
"""
}


if __name__ == "__main__":
    # Quick health check first
    health = httpx.get(f"{BASE_URL}/health").json()
    print(f"Server status: {health}")

    if health["knowledge_base_entries"] == 0:
        print("\n⚠️  Knowledge base is empty. Run: python seed.py")
        print("   The analyzer will still work but won't have past failure context.\n")

    run(NUMPY_BUILD_FAIL)
    run(OOM_DEPLOY_FAIL)
    run(REDIS_TIMEOUT_FAIL)
