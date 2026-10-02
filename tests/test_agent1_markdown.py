import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shutil
import tempfile
from agents.agent1_markdown import MarkdownAgent, MarkdownInput

def test_markdown_agent_validation():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_md_val_"))
    try:
        agent = MarkdownAgent(output_dir=temp_dir)

        # Test empty project name
        res_empty_name = agent.process(MarkdownInput(
            project_name="",
            description="Valid description for testing validation failure.",
            requirements=["Req 1"]
        ))
        assert res_empty_name.status == "failure"
        assert res_empty_name.success is False
        assert "Validation failed" in res_empty_name.summary
        print("[PASS] Validation: Empty project name rejected")

        # Test empty description
        res_empty_desc = agent.process(MarkdownInput(
            project_name="Valid Project",
            description="",
            requirements=["Req 1"]
        ))
        assert res_empty_desc.status == "failure"
        assert res_empty_desc.success is False
        print("[PASS] Validation: Empty description rejected")

        # Test empty requirements
        res_empty_req = agent.process(MarkdownInput(
            project_name="Valid Project",
            description="Valid description here",
            requirements=""
        ))
        assert res_empty_req.status == "failure"
        assert res_empty_req.success is False
        print("[PASS] Validation: Empty requirements rejected")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_markdown_agent_create_and_update():
    temp_dir = Path(tempfile.mkdtemp(prefix="test_md_agent_"))
    try:
        agent = MarkdownAgent(output_dir=temp_dir)

        # 1. Test creation of new markdown file
        payload = MarkdownInput(
            project_name="Payment Gateway Integration",
            description="Process credit card transactions via Stripe and PayPal with PCI compliance.",
            requirements=[
                "Webhook listener for payment events",
                "Idempotent transaction processing",
                "Refund workflow with ledger sync"
            ],
            additional_info="Requires SSL and Redis distributed locking. Target latency < 200ms."
        )

        res1 = agent.process(payload)
        
        # Verify required response schema
        # { "status": "success/failure", "file_path": "...", "summary": "..." }
        d1 = res1.to_dict()
        assert d1["status"] == "success"
        assert d1["file_path"] != ""
        assert d1["summary"] != ""
        assert res1.action == "created"
        assert res1.version == 1
        assert Path(res1.file_path).exists(), f"File does not exist: {res1.file_path}"

        # Verify Markdown structure (headings, sections, lists, code blocks)
        content1 = Path(res1.file_path).read_text(encoding="utf-8")
        assert "# Payment Gateway Integration" in content1
        assert "## 📋 Project Overview" in content1
        assert "## 🎯 Description" in content1
        assert "## ⚙️ Requirements & Specifications" in content1
        assert "- [ ] Webhook listener for payment events" in content1
        assert "## 📝 Additional Information & Notes" in content1
        assert "```mermaid" in content1
        assert "## 📊 Document History" in content1
        print("[PASS] Agent 1 Create Test: Clean Markdown generated with headings, sections, lists, code blocks")

        # 2. Test update of existing file (deduplication)
        payload_update = MarkdownInput(
            project_name="Payment Gateway Integration",  # Same name -> resolves to same slug
            description="Updated description with Apple Pay support.",
            requirements=["Webhook listener", "Apple Pay checkout"],
            additional_info="Updated constraints."
        )

        res2 = agent.process(payload_update)
        d2 = res2.to_dict()
        assert d2["status"] == "success"
        assert res2.action == "updated"
        assert res2.version == 2
        assert res2.file_path == res1.file_path, "Should update same file without creating duplicate"

        content2 = Path(res2.file_path).read_text(encoding="utf-8")
        assert "Apple Pay checkout" in content2
        assert "version: 2" in content2
        print("[PASS] Agent 1 Update & Deduplication Test: Updated existing file (v2) without duplicate")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    test_markdown_agent_validation()
    test_markdown_agent_create_and_update()
    print("All Agent 1 tests passed successfully!")
