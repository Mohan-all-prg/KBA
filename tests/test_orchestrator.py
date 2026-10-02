import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tempfile
import shutil
from orchestrator import WorkflowOrchestrator, SubmissionRequest
from agents.agent1_markdown import MarkdownAgent
from agents.agent2_database import DatabaseAgent, DatabaseManager
from agents.agent3_documentation import DocumentationAgent

def test_full_orchestrator_pipeline():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_orch_"))
    try:
        md_dir = temp_dir / "output" / "markdown"
        docs_dir = temp_dir / "docs"
        db_file = temp_dir / "database" / "projects.db"

        agent1 = MarkdownAgent(output_dir=md_dir)
        db_mgr = DatabaseManager(db_path=db_file)
        agent2 = DatabaseAgent(db_manager=db_mgr)
        agent3 = DocumentationAgent(docs_dir=docs_dir)

        orch = WorkflowOrchestrator(
            markdown_agent=agent1,
            database_agent=agent2,
            documentation_agent=agent3
        )

        # 1. Run pipeline
        req = SubmissionRequest(
            project_name="Autonomous Code Reviewer",
            description="LLM-assisted code review bot providing static analysis and security scanning on pull requests.",
            requirements=["GitHub PR integration", "SonarQube rule checks", "Automatic inline review comments"],
            additional_info="Hosted on Kubernetes cluster with horizontal pod autoscaler."
        )

        response = orch.run(req)

        # Verify orchestrator response fields required by specification:
        # - Markdown status
        # - Markdown file path
        # - Database status
        # - Database record ID
        # - Documentation status
        # - Documentation file path
        assert response.overall_status == "success"
        assert response.markdown_status == "created"
        assert Path(response.markdown_file_path).exists()
        assert response.database_status == "inserted"
        assert response.database_record_id is not None
        assert response.documentation_status == "created"
        assert Path(response.documentation_file_path).exists()
        print("[PASS] End-to-End Orchestrator Pipeline Test")

        # Verify physical artifacts created
        md_text = Path(response.markdown_file_path).read_text(encoding="utf-8")
        assert "Autonomous Code Reviewer" in md_text

        doc_text = Path(response.documentation_file_path).read_text(encoding="utf-8")
        assert "Autonomous Code Reviewer" in doc_text
        assert f"#{response.database_record_id}" in doc_text

        db_row = db_mgr.get_project_by_name_or_slug("Autonomous Code Reviewer", "autonomous-code-reviewer")
        assert db_row is not None
        assert db_row["id"] == response.database_record_id
        print("[PASS] Verified physical files and database persistence")

        # 2. Test re-submitting same project (Update / Deduplication through orchestrator)
        req_update = SubmissionRequest(
            project_name="Autonomous Code Reviewer",
            description="Updated description with GitLab CI/CD support.",
            requirements=["GitHub PR integration", "GitLab MR integration", "Security scanning"],
            additional_info="Now supporting GitLab."
        )

        update_response = orch.run(req_update)
        assert update_response.overall_status == "success"
        assert update_response.markdown_status == "updated"
        assert update_response.database_status == "updated"
        assert update_response.database_record_id == response.database_record_id
        assert update_response.documentation_status == "updated"
        print("[PASS] End-to-End Re-submission / Deduplication Update Test")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    test_full_orchestrator_pipeline()
    print("All Orchestrator tests passed successfully!")
