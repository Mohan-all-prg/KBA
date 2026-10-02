import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tempfile
import shutil
import os
from agents.agent2_database import DatabaseAgent, DatabaseInput, DatabaseManager

def test_database_agent_validation():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_db_val_"))
    try:
        db_file = temp_dir / "test_val.db"
        agent = DatabaseAgent(db_manager=DatabaseManager(db_path=db_file))

        # Test empty project name
        res_empty_name = agent.process(DatabaseInput(
            project_name="",
            description="Valid description here",
            requirements=["Req 1"]
        ))
        assert res_empty_name.status == "failure"
        assert res_empty_name.record_id is None
        assert "Validation failed" in res_empty_name.message
        print("[PASS] Validation: Empty project name rejected")

        # Test empty description
        res_empty_desc = agent.process(DatabaseInput(
            project_name="Valid Project",
            description="",
            requirements=["Req 1"]
        ))
        assert res_empty_desc.status == "failure"
        assert res_empty_desc.record_id is None
        assert "Validation failed" in res_empty_desc.message
        print("[PASS] Validation: Empty description rejected")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_database_agent_insert_update_and_audit():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_db_agent_"))
    try:
        db_file = temp_dir / "test_projects.db"
        db_mgr = DatabaseManager(db_path=db_file)
        agent = DatabaseAgent(db_manager=db_mgr)

        # 1. Test insertion of new project
        input_data = DatabaseInput(
            project_name="Inventory Sync Service",
            description="Synchronize warehouse physical inventory with Shopify storefront.",
            requirements=["Inventory levels update every 5 mins", "Alert when stock < 10"],
            additional_info="High priority queue",
            markdown_path="output/markdown/inventory-sync-service.md",
            workflow_run_id="wf_test_001"
        )

        res1 = agent.process(input_data)
        
        # Verify required return dictionary schema:
        # { "status": "success/failure", "record_id": "...", "message": "..." }
        d1 = res1.to_dict()
        assert d1["status"] == "success"
        assert d1["record_id"] == str(res1.record_id)
        assert d1["message"] != ""
        assert res1.action == "inserted"
        assert res1.record_id is not None
        assert res1.version == 1
        print(f"[PASS] Agent 2 Insert Test (Record ID #{res1.record_id}, message: '{res1.message}')")

        # 2. Test duplicate prevention & update
        input_update = DatabaseInput(
            project_name="Inventory Sync Service",  # Same project name -> triggers duplicate prevention
            description="Updated description with Amazon sync as well.",
            requirements=["Shopify sync", "Amazon sync", "Low stock alerts"],
            additional_info="Multi-channel",
            markdown_path="output/markdown/inventory-sync-service.md",
            workflow_run_id="wf_test_002"
        )

        res2 = agent.process(input_update)
        d2 = res2.to_dict()
        assert d2["status"] == "success"
        assert d2["record_id"] == str(res1.record_id), "Record ID must remain identical on update"
        assert res2.action == "updated"
        assert res2.version == 2, f"Expected version 2, got {res2.version}"
        assert "already exists" in res2.message
        print(f"[PASS] Agent 2 Duplicate Prevention & Update Test (Updated ID #{res2.record_id} to v2)")

        # 3. Verify actual database record in SQLite
        project = db_mgr.get_project_by_name_or_slug("Inventory Sync Service", "inventory-sync-service")
        assert project is not None
        assert project["version"] == 2
        assert "Amazon sync" in project["requirements"]
        print("[PASS] Agent 2 Database Record Verification")

        # 4. Verify audit trail logs in workflow_runs
        with db_mgr.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM workflow_runs WHERE project_id = ?", (res1.record_id,))
            count = cursor.fetchone()[0]
            assert count == 2, f"Expected 2 audit log runs, found {count}"
        print("[PASS] Agent 2 Audit Trail Test")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_database_environment_variable_override():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_db_env_"))
    try:
        custom_db = temp_dir / "custom_env.db"
        # Test creating DatabaseManager with environment variable path
        mgr = DatabaseManager(db_path=custom_db)
        assert custom_db.exists()
        with mgr.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            assert "projects" in tables
            assert "workflow_runs" in tables
        print("[PASS] Agent 2 Environment Variable & Dynamic Path Override Test")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    test_database_agent_validation()
    test_database_agent_insert_update_and_audit()
    test_database_environment_variable_override()
    print("All Agent 2 tests passed successfully!")
