
from rag import add_failure, count_failures
import uuid


SEED_FAILURES = [
    {
        "pipeline_name": "api-service-ci",
        "error_category": "Dependency Error",
        "description": "pip install failed. numpy 1.24.0 has no pre-built wheel for Python 3.12. Build exits with 'Could not build wheels for numpy'.",
        "fix_applied": "Pin numpy to >=1.26.0 in requirements.txt. That version ships Python 3.12 wheels."
    },
    {
        "pipeline_name": "frontend-ci",
        "error_category": "Docker Build Error",
        "description": "npm install fails with EACCES permission denied on /usr/local/lib/node_modules. Running as root inside Docker.",
        "fix_applied": "Add 'USER node' before RUN npm install in Dockerfile. Never run npm as root."
    },
    {
        "pipeline_name": "checkout-service-cd",
        "error_category": "Resource Error",
        "description": "Kubernetes pod OOMKilled immediately after deploy. CrashLoopBackOff. Memory limit was 256Mi, service needs 512Mi under load.",
        "fix_applied": "Increase resources.limits.memory to 512Mi in k8s/deployment.yaml. Also set resources.requests.memory to 256Mi."
    },
    {
        "pipeline_name": "auth-service-ci",
        "error_category": "Test Failure",
        "description": "pytest AssertionError in test_token_expiry. unittest.mock patch was not resetting between tests because of shared module-level state.",
        "fix_applied": "Switch from unittest.mock to pytest monkeypatch. Add autouse fixture to reset state between tests."
    },
    {
        "pipeline_name": "data-pipeline-ci",
        "error_category": "Auth Error",
        "description": "GCP service account JSON key expired. gcloud auth returns 401 Unauthorized during BigQuery write step.",
        "fix_applied": "Rotate GCP_SERVICE_ACCOUNT_KEY secret in CI/CD settings. Long term: switch to Workload Identity Federation to avoid key rotation."
    },
    {
        "pipeline_name": "backend-api-ci",
        "error_category": "Config Error",
        "description": "Alembic migration failed: column users.role of type ENUM does not exist. Migrations ran out of sequence after branch merge.",
        "fix_applied": "Run 'alembic downgrade base' then 'alembic upgrade head'. Check migration version chain with 'alembic history'."
    },
    {
        "pipeline_name": "notification-service-ci",
        "error_category": "Network Error",
        "description": "Integration test timed out connecting to Redis on localhost:6379. Docker Compose started the test container before Redis was ready.",
        "fix_applied": "Add healthcheck to redis service in docker-compose.test.yml. Add 'depends_on: redis: condition: service_healthy' to test service."
    },
    {
        "pipeline_name": "frontend-deploy",
        "error_category": "Dependency Error",
        "description": "TypeScript compilation error after upgrading from TS 4.9 to 5.0. 'Property X does not exist on type Y' in multiple files.",
        "fix_applied": "Check @types/react and ts-morph versions for TS 5.0 compatibility. Update type declarations for breaking changes listed in TS 5.0 release notes."
    },
    {
        "pipeline_name": "infra-terraform",
        "error_category": "Config Error",
        "description": "terraform apply exits with Error 409: resource already exists. Terraform state file is out of sync with actual cloud resources.",
        "fix_applied": "Run 'terraform import <resource_type>.<name> <cloud_id>' to sync state. Or 'terraform state rm <resource>' and re-import."
    },
    {
        "pipeline_name": "ml-training-ci",
        "error_category": "Resource Error",
        "description": "CUDA out of memory during model forward pass. Batch size 128 exceeds GPU VRAM on the shared CI runner (8GB).",
        "fix_applied": "Set BATCH_SIZE=16 in .env.ci. Add --no-cuda flag in CI pipeline YAML. GPU runners are only for scheduled nightly training jobs."
    },
    {
        "pipeline_name": "payments-service-cd",
        "error_category": "Docker Build Error",
        "description": "Docker build fails: failed to solve: failed to read dockerfile: open Dockerfile: no such file or directory.",
        "fix_applied": "Check that the working directory in the CI YAML matches where the Dockerfile lives. Add 'context: ./payments-service' to docker build step."
    },
    {
        "pipeline_name": "search-service-ci",
        "error_category": "Test Failure",
        "description": "Test flakiness: 3 of 50 CI runs fail with connection reset by Elasticsearch. Tests share a single ES index and interfere with each other.",
        "fix_applied": "Generate a unique index name per test run using uuid4(). Tear down the index in a pytest fixture finalizer."
    },
]


def seed():
    existing = count_failures()
    if existing > 0:
        print(f"Knowledge base already has {existing} entries. Skipping.")
        print("Delete ./chroma_db directory to re-seed from scratch.")
        return

    for failure in SEED_FAILURES:
        add_failure(
            id=str(uuid.uuid4()),
            failure_text=f"{failure['error_category']}: {failure['description']}",
            metadata={
                "pipeline_name": failure["pipeline_name"],
                "error_category": failure["error_category"],
                "fix_applied": failure["fix_applied"]
            }
        )

    print(f" Seeded {len(SEED_FAILURES)} failures into knowledge base.")


if __name__ == "__main__":
    seed()
