"""
Test Suite for MCP Host Mode and Tool Execution Endpoints
"""

import sys
from pathlib import Path
from starlette.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import app, mcp_host_manager


def test_mcp_host_suite():
    client = TestClient(app)

    print("\n--- 1. Testing User Mode Preferences ---")
    # Test GET mode
    res = client.get("/api/mode")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    assert "mode" in data
    assert "available_modes" in data
    assert "server" in data["available_modes"]
    assert "host" in data["available_modes"]
    print("--> [PASS] GET /api/mode returns valid structure")

    # Test POST mode -> host
    res = client.post("/api/mode", json={"mode": "host"})
    assert res.status_code == 200
    assert res.json()["mode"] == "host"
    assert mcp_host_manager.get_mode() == "host"
    print("--> [PASS] POST /api/mode switches to 'host'")

    # Test POST invalid mode
    res = client.post("/api/mode", json={"mode": "invalid_mode"})
    assert res.status_code == 400
    print("--> [PASS] POST /api/mode rejects invalid mode with 400")

    # Reset back to server
    res = client.post("/api/mode", json={"mode": "server"})
    assert res.status_code == 200
    assert res.json()["mode"] == "server"
    print("--> [PASS] Reset mode to 'server'")

    print("\n--- 2. Testing MCP Host Tools Discovery ---")
    res = client.get("/api/host/tools")
    assert res.status_code == 200
    data = res.json()
    assert "tools" in data
    assert data["count"] >= 9
    tool_names = [t["name"] for t in data["tools"]]
    for expected in ["add", "orchestrate_workflow", "list_projects", "list_airtable_projects", "sync_all_to_airtable", "clear_airtable_data"]:
        assert expected in tool_names, f"Expected tool '{expected}' not found in discovery"
    print(f"--> [PASS] Discovered {data['count']} registered MCP tools with JSON schemas")

    print("\n--- 3. Testing Host Tool Execution (tools/call) ---")
    # Test add
    payload_add = {
        "tool": "add",
        "arguments": {"a": 42, "b": 58}
    }
    res = client.post("/api/host/execute", json=payload_add)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["success"] is True
    assert res_data["result"] == 100
    assert "execution_time_ms" in res_data
    assert "rpc_request" in res_data
    assert res_data["rpc_request"]["method"] == "tools/call"
    print(f"--> [PASS] MCP Tool 'add' executed in {res_data['execution_time_ms']}ms, result=100")

    # Test list_projects
    payload_list = {
        "tool": "list_projects",
        "arguments": {"status": "all"}
    }
    res = client.post("/api/host/execute", json=payload_list)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["success"] is True
    assert isinstance(res_data["result"], list)
    print(f"--> [PASS] MCP Tool 'list_projects' executed via Host, retrieved {len(res_data['result'])} items")

    # Test POST /api/airtable/clear endpoint
    res_clear = client.post("/api/airtable/clear")
    assert res_clear.status_code in [200, 400]
    print(f"--> [PASS] POST /api/airtable/clear handled properly")

    print("\n--- 4. Testing Host AI Assistant Chat ---")
    # Natural language add
    res = client.post("/api/host/chat", json={"message": "please add 15 and 25"})
    assert res.status_code == 200
    chat_data = res.json()
    assert chat_data["tool_called"] == "add"
    assert "40" in chat_data["message"]
    print("--> [PASS] Natural language add chat resolved and executed")

    # Natural language list projects
    res = client.post("/api/host/chat", json={"message": "list all projects in database"})
    assert res.status_code == 200
    chat_data = res.json()
    assert chat_data["tool_called"] == "list_projects"
    print("--> [PASS] Natural language list projects chat resolved and executed")

    # Gemini provider fallback when key is missing
    res_gemini = client.post("/api/host/chat", json={"message": "sync airtable", "provider": "gemini"})
    assert res_gemini.status_code == 200
    assert "Gemini" in res_gemini.json()["message"]
    print("--> [PASS] Gemini provider handled properly")

    # Claude provider fallback when key is missing
    res_claude = client.post("/api/host/chat", json={"message": "sync airtable", "provider": "claude"})
    assert res_claude.status_code == 200
    assert "Claude" in res_claude.json()["message"]
    print("--> [PASS] Claude provider handled properly")

    print("\n--- 5. Testing Host Status & Telemetry ---")
    res = client.get("/api/host/status")
    assert res.status_code == 200
    stat_data = res.json()
    assert stat_data["host_status"] == "ready"
    assert stat_data["total_executions"] >= 2
    print(f"--> [PASS] Host status ready with {stat_data['total_executions']} recorded executions")

    print("\n--- 6. Testing Claude Desktop Configuration Integration ---")
    res_claude_cfg = client.get("/api/host/claude-config")
    assert res_claude_cfg.status_code == 200
    cfg_data = res_claude_cfg.json()
    assert "config_path" in cfg_data
    assert "config_snippet" in cfg_data
    assert "multi-agent-workflow-server" in cfg_data["config_snippet"]["mcpServers"]
    print(f"--> [PASS] Claude Desktop config schema verified ({cfg_data['config_path']})")

    res_claude_install = client.post("/api/host/claude-config/install")
    assert res_claude_install.status_code == 200
    assert res_claude_install.json()["status"] == "success"
    print("--> [PASS] Claude Desktop auto-install written successfully")


if __name__ == "__main__":
    test_mcp_host_suite()
    print("\nAll MCP Host tests passed successfully!")

