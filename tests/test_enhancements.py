import sys
import time
from pathlib import Path

# Configure utf-8 encoding for Windows consoles safely
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient
from server import app
from agents.agent2_database.db import DatabaseManager

def test_all_enhancements():
    client = TestClient(app)
    db = DatabaseManager()

    print("\n--- 1. Valid Project Creation (201 Created / Success) ---")
    ts = int(time.time())
    unique_name = f"Enhancement Pipeline Pro {ts}"
    payload_valid = {
        "project_name": unique_name,
        "description": "High performance event streaming architecture with Kafka and ClickHouse.",
        "requirements": "Process 50k events/sec\nSub-100ms analytical aggregation\nSchema validation via Avro",
        "additional_info": "Multi-region AWS deployment with cross-datacenter replication."
    }
    res = client.post("/api/submit", json=payload_valid)
    assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["overall_status"] == "success"
    assert data["database_status"] == "inserted"
    project_id = data["database_record_id"]
    assert project_id is not None
    print(f"--> [PASS] Created project ID #{project_id} (Status 201)")

    print("\n--- 2. Input Validation Rejections ---")
    # A. Empty project_name
    res_empty_name = client.post("/api/submit", json={
        "project_name": "   ",
        "description": "Valid description for empty name test.",
        "requirements": "Some valid requirements."
    })
    assert res_empty_name.status_code == 422, f"Expected 422 for empty name, got {res_empty_name.status_code}"
    print("--> [PASS] Empty project_name rejected with 422")

    # B. Numeric project_name (must NOT be silently coerced)
    res_num_name = client.post("/api/submit", json={
        "project_name": 12345,
        "description": "Valid description for numeric name test.",
        "requirements": "Some valid requirements."
    })
    assert res_num_name.status_code == 422, f"Expected 422 for numeric name, got {res_num_name.status_code}"
    print("--> [PASS] Numeric project_name rejected with 422 (no silent coercion)")

    # C. Boolean project_name (must NOT be silently coerced)
    res_bool_name = client.post("/api/submit", json={
        "project_name": True,
        "description": "Valid description for boolean name test.",
        "requirements": "Some valid requirements."
    })
    assert res_bool_name.status_code == 422, f"Expected 422 for boolean name, got {res_bool_name.status_code}"
    print("--> [PASS] Boolean project_name rejected with 422")

    # D. Null project_name
    res_null_name = client.post("/api/submit", json={
        "project_name": None,
        "description": "Valid description for null name test.",
        "requirements": "Some valid requirements."
    })
    assert res_null_name.status_code == 422, f"Expected 422 for null name, got {res_null_name.status_code}"
    print("--> [PASS] Null project_name rejected with 422")

    # E. Missing required fields
    res_missing = client.post("/api/submit", json={
        "project_name": "Only Name Given"
    })
    assert res_missing.status_code == 422, f"Expected 422 for missing fields, got {res_missing.status_code}"
    print("--> [PASS] Missing fields rejected with 422")

    # F. Excessively long project_name (> 120 chars)
    res_long_name = client.post("/api/submit", json={
        "project_name": "A" * 125,
        "description": "Valid description for long name test.",
        "requirements": "Some valid requirements."
    })
    assert res_long_name.status_code == 422, f"Expected 422 for long name, got {res_long_name.status_code}"
    print("--> [PASS] Excessively long name (>120 chars) rejected with 422")

    # G. Excessively long description (> 5000 chars)
    res_long_desc = client.post("/api/submit", json={
        "project_name": "Valid Short Name",
        "description": "D" * 5005,
        "requirements": "Some valid requirements."
    })
    assert res_long_desc.status_code == 422, f"Expected 422 for long description, got {res_long_desc.status_code}"
    print("--> [PASS] Excessively long description (>5000 chars) rejected with 422")

    # H. Malformed JSON payload
    res_malformed = client.post("/api/submit", content=b"invalid json { {", headers={"Content-Type": "application/json"})
    assert res_malformed.status_code == 400, f"Expected 400 for malformed json, got {res_malformed.status_code}"
    print("--> [PASS] Malformed JSON rejected with 400")

    print("\n--- 3. Duplicate Prevention & In-Place Update ---")
    # Submitting same project_name again through /api/submit should update in-place without duplicate
    res_dup = client.post("/api/submit", json={
        "project_name": unique_name,
        "description": "Updated description for duplicate test.",
        "requirements": "Updated requirements list.",
        "additional_info": "Updated additional notes."
    })
    assert res_dup.status_code == 200, f"Expected 200 for update, got {res_dup.status_code}"
    data_dup = res_dup.json()
    assert data_dup["database_record_id"] == project_id
    assert data_dup["database_status"] == "updated"
    print(f"--> [PASS] Duplicate name updated in-place (ID #{project_id})")

    print("\n--- 4. Edit / Update Project via PUT /api/projects/{id} ---")
    update_payload = {
        "project_name": f"{unique_name} (Updated)",
        "description": "Completely refreshed architecture description with TLS 1.3 encryption and zero trust.",
        "requirements": "Zero Trust mTLS\nAutomated canary deployments\n99.999% availability SLA",
        "additional_info": "Updated compliance target: SOC2 Type II."
    }
    res_update = client.put(f"/api/projects/{project_id}", json=update_payload)
    assert res_update.status_code == 200, f"Expected 200 on PUT, got {res_update.status_code}: {res_update.text}"
    data_upd = res_update.json()
    assert data_upd["overall_status"] == "success"
    assert data_upd["markdown_status"] in ("created", "updated")
    assert data_upd["database_status"] == "updated"

    # Verify database record updated & version incremented
    rec = db.get_project_by_id(project_id)
    assert rec is not None
    assert rec["project_name"] == f"{unique_name} (Updated)"
    assert rec["version"] >= 2
    print(f"--> [PASS] Project updated successfully: Name='{rec['project_name']}', Version=v{rec['version']}")

    # Verify Markdown file contains updated requirements
    md_res = client.get(f"/api/preview?path={data_upd['markdown_file_path']}")
    assert md_res.status_code == 200
    assert "Zero Trust mTLS" in md_res.json()["content"]
    print("--> [PASS] Markdown file verified with updated content")

    # Verify Doc file contains updated info
    doc_res = client.get(f"/api/preview?path={data_upd['documentation_file_path']}")
    assert doc_res.status_code == 200
    assert "SOC2 Type II" in doc_res.json()["content"]
    print("--> [PASS] Documentation synchronized with updated content")

    # Invalid update test (numeric description)
    res_bad_upd = client.put(f"/api/projects/{project_id}", json={"description": 99999})
    assert res_bad_upd.status_code == 422
    print("--> [PASS] Invalid update (numeric description) rejected with 422")

    print("\n--- 5. Delete & Archive Operations ---")
    # A. Archive (Soft Delete)
    res_archive = client.delete(f"/api/projects/{project_id}?permanent=false")
    assert res_archive.status_code == 200
    assert res_archive.json()["action"] == "archived"
    rec_archived = db.get_project_by_id(project_id)
    assert rec_archived["status"] == "archived"
    print(f"--> [PASS] Soft delete / archive verified: status='{rec_archived['status']}'")

    # Verify filter /api/projects?status=archived
    res_arch_list = client.get("/api/projects?status=archived")
    assert res_arch_list.status_code == 200
    arch_ids = [p["id"] for p in res_arch_list.json()["projects"]]
    assert project_id in arch_ids
    print("--> [PASS] Archived project correctly listed in ?status=archived filter")

    # B. Hard Delete (Permanent)
    res_delete = client.delete(f"/api/projects/{project_id}?permanent=true")
    assert res_delete.status_code == 200
    assert res_delete.json()["action"] == "permanently deleted"
    rec_deleted = db.get_project_by_id(project_id)
    assert rec_deleted is None
    print(f"--> [PASS] Permanent delete verified: Record ID #{project_id} no longer exists in SQLite")

    print("\n--- 6. Non-existent Project Operations (404 Handling) ---")
    bad_id = 99999999
    res_get_404 = client.get(f"/api/projects/{bad_id}")
    assert res_get_404.status_code == 404, f"Expected 404, got {res_get_404.status_code}"

    res_put_404 = client.put(f"/api/projects/{bad_id}", json={"project_name": "Ghost Project"})
    assert res_put_404.status_code == 404, f"Expected 404, got {res_put_404.status_code}"

    res_del_404 = client.delete(f"/api/projects/{bad_id}")
    assert res_del_404.status_code == 404, f"Expected 404, got {res_del_404.status_code}"
    print("--> [PASS] GET, PUT, and DELETE on non-existent ID return 404 Not Found")

    print("\n--- 7. Security: Path Traversal Prevention ---")
    res_traversal1 = client.get("/api/preview?path=../../../../../../windows/win.ini")
    assert res_traversal1.status_code in (403, 404), f"Expected 403 or 404, got {res_traversal1.status_code}"

    res_traversal2 = client.get("/api/preview?path=/etc/passwd")
    assert res_traversal2.status_code in (403, 404), f"Expected 403 or 404, got {res_traversal2.status_code}"
    print("--> [PASS] Path traversal attempts safely rejected")

    print("\n--- 8. Multi-Agent Sequential Workflow Integrity ---")
    test_run = client.post("/api/submit", json={
        "project_name": f"Workflow Pipeline Check {ts}",
        "description": "Verifying end-to-end agent orchestration integrity.",
        "requirements": "Agent 1 generates markdown\nAgent 2 stores in SQLite\nAgent 3 compiles documentation",
        "additional_info": "Continuous test run"
    })
    assert test_run.status_code == 201
    run_data = test_run.json()
    assert run_data["agent_details"]["agent1"]["success"] is True
    assert run_data["agent_details"]["agent2"]["success"] is True
    assert run_data["agent_details"]["agent3"]["success"] is True
    print("--> [PASS] Agent 1 -> Agent 2 -> Agent 3 pipeline executed flawlessly!")

    # Clean up test_run project
    client.delete(f"/api/projects/{run_data['database_record_id']}?permanent=true")

    print("\n--- 9. Meaningless, Gibberish, and Spam Rejection Tests ---")
    count_before = len(db.list_all_projects(status='all'))

    # A. All-numeric meaningless string (exact user report: "11111111111111111111111")
    res_num_spam = client.post("/api/submit", json={
        "project_name": "11111111111111111111111",
        "description": "11111111111111111111111",
        "requirements": "11111111111111111111111"
    })
    assert res_num_spam.status_code == 422, f"Expected 422, got {res_num_spam.status_code}"
    print("--> [PASS] All-numeric meaningless data ('11111111111111111111111') rejected with 422")

    # B. Repetitive character spam ("aaaaaaa")
    res_char_spam = client.post("/api/submit", json={
        "project_name": "aaaaaaa",
        "description": "Repetitive character description test",
        "requirements": "Valid requirement statement"
    })
    assert res_char_spam.status_code == 422
    print("--> [PASS] Repetitive character spam ('aaaaaaa') rejected with 422")

    # C. Pure symbols (".........")
    res_sym_spam = client.post("/api/submit", json={
        "project_name": ".........",
        "description": "Valid description statement here",
        "requirements": "Valid requirement statement"
    })
    assert res_sym_spam.status_code == 422
    print("--> [PASS] Pure symbol spam ('.........') rejected with 422")

    # D. Low character variety ("ababab")
    res_low_var = client.post("/api/submit", json={
        "project_name": "ababab",
        "description": "Valid description statement here",
        "requirements": "Valid requirement statement"
    })
    assert res_low_var.status_code == 422
    print("--> [PASS] Low character variety ('ababab') rejected with 422")

    # E. Verify SQLite database remained completely untouched
    count_after = len(db.list_all_projects(status='all'))
    assert count_after == count_before, f"Database count changed! Expected {count_before}, got {count_after}"
    print(f"--> [PASS] SQLite database remained protected (0 corrupt records inserted)")

    # F. Verify Orchestrator Short-Circuiting if Agent 1 fails
    from orchestrator import orchestrator, SubmissionRequest
    from agents.agent1_markdown.models import MarkdownOutput
    from unittest.mock import MagicMock

    mock_agent1 = MagicMock()
    mock_agent1.process.return_value = MarkdownOutput(
        status="failure",
        file_path="",
        summary="Validation failed: Mocked failure in Agent 1",
        action="none",
        success=False,
        error="Simulated Agent 1 failure"
    )
    mock_agent2 = MagicMock()
    mock_agent3 = MagicMock()

    from orchestrator.orchestrator import WorkflowOrchestrator
    test_orch = WorkflowOrchestrator(
        markdown_agent=mock_agent1,
        database_agent=mock_agent2,
        documentation_agent=mock_agent3
    )

    valid_req = SubmissionRequest(
        project_name="Short Circuit Check",
        description="Testing that failure in Agent 1 immediately aborts the pipeline.",
        requirements="Requirement A\nRequirement B"
    )
    short_circuit_res = test_orch.run(valid_req)
    assert short_circuit_res.overall_status == "failed"
    assert short_circuit_res.database_status == "not_run"
    assert short_circuit_res.database_record_id is None
    assert not mock_agent2.process.called, "Agent 2 must NEVER be called when Agent 1 fails!"
    assert not mock_agent3.process.called, "Agent 3 must NEVER be called when Agent 1 fails!"
    print("--> [PASS] Orchestrator short-circuits on Agent 1 failure: Agent 2 and Agent 3 are NOT called!")

if __name__ == "__main__":
    test_all_enhancements()
    print("\n=======================================================")
    print("ALL 9 ENHANCEMENT TEST SUITES PASSED SUCCESSFULLY!")
    print("=======================================================\n")
