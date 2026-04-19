import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert "knowledge_base_entries" in r.json()

def test_analyze_requires_auth():
    r = client.post("/analyze", json={
        "pipeline_name": "test", "stage": "build", "logs": "ERROR: npm not found"
    })
    assert r.status_code == 403  # no API key = forbidden

def test_analyze_with_auth():
    r = client.post("/analyze",
        headers={"X-API-Key": "test-key"},
        json={"pipeline_name": "test-pipeline", "stage": "build",
              "logs": "ERROR: Cannot find module 'express'\nnpm ERR! code MODULE_NOT_FOUND"}
    )
    assert r.status_code == 200
    assert r.json()["error_category"] in ["Dependency Error", "Other"]