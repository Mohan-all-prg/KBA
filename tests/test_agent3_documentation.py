import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tempfile
import shutil
from agents.agent3_documentation import DocumentationAgent, DocumentationInput

def test_documentation_agent_validation():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_doc_val_"))
    try:
        agent = DocumentationAgent(docs_dir=temp_dir)

        # Empty project name
        res_empty = agent.process(DocumentationInput(
            project_name="",
            description="Valid description here"
        ))
        assert res_empty.status == "failure"
        assert res_empty.documentation_path == ""
        assert "Validation failed" in res_empty.summary
        print("[PASS] Validation: Empty project name rejected")

        # Empty description
        res_empty_desc = agent.process(DocumentationInput(
            project_name="Valid Project",
            description=""
        ))
        assert res_empty_desc.status == "failure"
        assert "Validation failed" in res_empty_desc.summary
        print("[PASS] Validation: Empty description rejected")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_documentation_agent_generate_and_catalog():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_doc_agent_"))
    try:
        agent = DocumentationAgent(docs_dir=temp_dir)

        payload = DocumentationInput(
            project_name="AI Video Transcriber",
            description="Whisper-based batch video transcribing service with subtitle alignment.",
            requirements=["MP4 and MKV ingestion", "SRT subtitle export", "Language auto-detection"],
            additional_info="GPU acceleration with CUDA 12",
            markdown_result={
                "file_path": "output/markdown/ai-video-transcriber.md",
                "relative_path": "output/markdown/ai-video-transcriber.md",
                "status": "created",
                "action": "created",
                "version": 1,
                "summary": "Created markdown file with 3 requirements."
            },
            database_result={
                "record_id": 42,
                "status": "inserted",
                "action": "inserted",
                "table": "projects",
                "version": 1,
                "operation": "Inserted new project record ID #42"
            },
            workflow_run_id="wf_test_doc_999"
        )

        res = agent.process(payload)

        # Verify required return dictionary schema:
        # { "status": "success/failure", "documentation_path": "...", "summary": "..." }
        d = res.to_dict()
        assert d["status"] == "success"
        assert d["documentation_path"] != ""
        assert d["summary"] != ""
        assert res.action == "created"
        assert Path(res.documentation_path).exists(), f"Doc file missing: {res.documentation_path}"
        assert Path(res.catalog_path).exists(), f"Catalog missing: {res.catalog_path}"

        doc_content = Path(res.documentation_path).read_text(encoding="utf-8")
        
        # Verify all 11 required sections are present
        assert "1. Project Overview" in doc_content
        assert "2. Requirements & Specifications" in doc_content
        assert "3. Agent Architecture" in doc_content
        assert "4. Multi-Agent Workflow" in doc_content
        assert "5. Database Schema & Persistence" in doc_content
        assert "6. Markdown Generation & Artifacts" in doc_content
        assert "7. APIs & Integration Reference" in doc_content
        assert "8. Inputs and Outputs Specification" in doc_content
        assert "9. Configuration & Environment Variables" in doc_content
        assert "10. Installation & Setup Guide" in doc_content
        assert "11. Testing & Verification Runbook" in doc_content
        
        # Verify specific project data integration
        assert "AI Video Transcriber" in doc_content
        assert "Whisper-based batch video transcribing" in doc_content
        assert "#42" in doc_content
        assert "wf_test_doc_999" in doc_content
        print("[PASS] Agent 3 Documentation Generation Test: All 11 required sections verified")

        catalog_content = Path(res.catalog_path).read_text(encoding="utf-8")
        assert "AI Video Transcriber" in catalog_content
        assert "#42" in catalog_content
        print("[PASS] Agent 3 Catalog Synchronization Test")

        # Test updating documentation (deduplication)
        payload_update = DocumentationInput(
            project_name="AI Video Transcriber",
            description="Updated description with diarization.",
            requirements=["MP4 ingestion", "Speaker diarization"],
            markdown_result={"file_path": "output/markdown/ai-video-transcriber.md", "action": "updated", "version": 2},
            database_result={"record_id": 42, "action": "updated", "version": 2, "table": "projects"}
        )
        res_update = agent.process(payload_update)
        assert res_update.status == "success"
        assert res_update.action == "updated"
        assert res_update.documentation_path == res.documentation_path, "Must update same doc without creating duplicate"
        print("[PASS] Agent 3 Update & Deduplication Test: Synchronized without duplicates")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    test_documentation_agent_validation()
    test_documentation_agent_generate_and_catalog()
    print("All Agent 3 tests passed successfully!")
