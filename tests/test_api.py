import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient
from server import app

def test_api_endpoints():
    client = TestClient(app)

    # 1. Test GET / (HTML Entry Form)
    res_index = client.get("/")
    assert res_index.status_code == 200, f"Expected 200, got {res_index.status_code}"
    assert "Multi-Agent Workflow Portal" in res_index.text
    assert "Project Entry Form" in res_index.text
    print("[PASS] API Test GET /")

    # 2. Test GET /api/health
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    data_health = res_health.json()
    assert data_health["status"] == "healthy"
    assert "agent1_markdown" in data_health["agents"]
    print("[PASS] API Test GET /api/health")

    # 3. Test POST /api/submit (Workflow Submission)
    payload = {
        "project_name": "API Gateway Rate Limiter",
        "description": "Token bucket rate limiting middleware with Redis backplane and IP reputation check.",
        "requirements": "Max 100 req/sec per API key\nBurst capacity of 150 requests\nHTTP 429 Too Many Requests response",
        "additional_info": "Low latency requirement: < 2ms overhead."
    }
    res_submit = client.post("/api/submit", json=payload)
    assert res_submit.status_code in (200, 201), f"Submit failed: {res_submit.text}"
    data_submit = res_submit.json()
    assert data_submit["overall_status"] == "success"
    assert data_submit["markdown_status"] in ("created", "updated")
    assert data_submit["database_status"] in ("inserted", "updated")
    assert data_submit["database_record_id"] is not None
    assert data_submit["documentation_status"] in ("created", "updated")
    print(f"[PASS] API Test POST /api/submit (Record ID #{data_submit['database_record_id']})")

    # 4. Test GET /api/projects
    res_projects = client.get("/api/projects")
    assert res_projects.status_code == 200
    data_projects = res_projects.json()
    assert "projects" in data_projects
    assert len(data_projects["projects"]) > 0
    print("[PASS] API Test GET /api/projects")

    # 5. Test GET /api/preview
    md_path = data_submit["markdown_file_path"]
    res_prev = client.get(f"/api/preview?path={md_path}")
    assert res_prev.status_code == 200
    data_prev = res_prev.json()
    assert "API Gateway Rate Limiter" in data_prev["content"]
    print("[PASS] API Test GET /api/preview")

if __name__ == "__main__":
    test_api_endpoints()
    print("All API tests passed successfully!")
