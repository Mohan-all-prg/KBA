import sys
import json
from pathlib import Path
from typing import Optional
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, FileResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.requests import Request
import uvicorn

from mcp.server import MCPServer
from mcp_host import mcp_host_manager
from config.settings import HOST, PORT, DEBUG, BASE_DIR, FRONTEND_DIR, MARKDOWN_OUTPUT_DIR, DOCS_DIR
from config.logging_config import get_logger
from config.mcp_bridge import mcp_bridge
from orchestrator import orchestrator, SubmissionRequest, ProjectUpdateRequest
from agents.agent1_markdown import MarkdownAgent, MarkdownInput
from agents.agent2_database import DatabaseAgent, DatabaseInput, DatabaseManager, airtable_sync
from agents.agent3_documentation import DocumentationAgent, DocumentationInput

logger = get_logger("server")

# ==============================================================================
# 1. MCP Server Setup (Tools exposed to MCP Clients / AI Agents)
# ==============================================================================
mcp = MCPServer("Multi-Agent Workflow Server")
mcp_host_manager.set_mcp_server(mcp)

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers (retained for backward compatibility)."""
    return a + b

@mcp.tool()
def orchestrate_workflow(
    project_name: str,
    description: str,
    requirements: str,
    additional_info: str = ""
) -> str:
    """
    Execute the full multi-agent pipeline:
    1. Agent 1 creates/updates Markdown specification in output/markdown/
    2. Agent 2 validates and persists record into SQLite database
    3. Agent 3 synchronizes system documentation in docs/
    """
    req = SubmissionRequest(
        project_name=project_name,
        description=description,
        requirements=requirements,
        additional_info=additional_info
    )
    result = orchestrator.run(req)
    return result.model_dump_json(indent=2)

@mcp.tool()
def create_or_update_markdown(
    project_name: str,
    description: str,
    requirements: str,
    additional_info: str = ""
) -> str:
    """Invoke Agent 1 (Markdown Agent) independently to generate or update project Markdown."""
    agent = MarkdownAgent()
    out = agent.process(MarkdownInput(
        project_name=project_name,
        description=description,
        requirements=requirements,
        additional_info=additional_info
    ))
    return out.model_dump_json(indent=2)

@mcp.tool()
def store_project_in_database(
    project_name: str,
    description: str,
    requirements: str,
    additional_info: str = "",
    markdown_path: str = ""
) -> str:
    """Invoke Agent 2 (Database Agent) independently to validate and persist project record."""
    agent = DatabaseAgent()
    out = agent.process(DatabaseInput(
        project_name=project_name,
        description=description,
        requirements=requirements,
        additional_info=additional_info,
        markdown_path=markdown_path
    ))
    return out.model_dump_json(indent=2)

@mcp.tool()
def generate_project_documentation(
    project_name: str,
    description: str,
    requirements: str,
    additional_info: str = "",
    markdown_path: str = "",
    db_record_id: int = 1
) -> str:
    """Invoke Agent 3 (Documentation Agent) independently to create synchronized documentation."""
    agent = DocumentationAgent()
    out = agent.process(DocumentationInput(
        project_name=project_name,
        description=description,
        requirements=requirements,
        additional_info=additional_info,
        markdown_result={"file_path": markdown_path, "status": "active", "version": 1},
        database_result={"record_id": db_record_id, "status": "active", "version": 1, "table": "projects"}
    ))
    return out.model_dump_json(indent=2)

@mcp.tool()
def list_projects(status: Optional[str] = None) -> str:
    """List projects stored in the SQLite database, optionally filtered by status ('active', 'archived', 'all')."""
    db_manager = DatabaseManager()
    projects = db_manager.list_all_projects(status=status)
    return json.dumps(projects, indent=2)

@mcp.tool()
def update_existing_project(
    project_id: int,
    project_name: Optional[str] = None,
    description: Optional[str] = None,
    requirements: Optional[str] = None,
    additional_info: Optional[str] = None
) -> str:
    """Update an existing project by ID across database, markdown specification, and system documentation."""
    req = ProjectUpdateRequest(
        project_name=project_name,
        description=description,
        requirements=requirements,
        additional_info=additional_info
    )
    result = orchestrator.update_project(project_id, req)
    return result.model_dump_json(indent=2)

@mcp.tool()
def archive_or_delete_project(
    project_id: int,
    permanent: bool = False
) -> str:
    """Archive (soft delete) or permanently delete a project by ID."""
    result = orchestrator.delete_project(project_id, permanent=permanent)
    return json.dumps(result, indent=2)

@mcp.tool()
def list_airtable_projects() -> str:
    """List all project records currently synchronized in the Airtable cloud base."""
    projects = airtable_sync.list_projects()
    return json.dumps(projects, indent=2)

@mcp.tool()
def sync_all_to_airtable() -> str:
    """Synchronize all projects from the SQLite database to the Airtable cloud base."""
    db_mgr = DatabaseManager()
    projects = db_mgr.list_all_projects(status="all")
    synced = []
    for p in projects:
        res = airtable_sync.upsert_project(
            project_name=p["project_name"],
            description=p["description"],
            requirements=p["requirements"],
            additional_info=p.get("additional_info", ""),
            markdown_path=p.get("markdown_path", ""),
            version=p.get("version", 1),
            status=p.get("status", "active"),
            workflow_run_id="wf_manual_sync"
        )
        synced.append({"project_name": p["project_name"], "result": res})
    return json.dumps({"synced_count": len(synced), "details": synced}, indent=2)

@mcp.tool()
def clear_airtable_data() -> str:
    """Clear all records from the Airtable cloud base completely, leaving only the table schema and field labels intact."""
    result = airtable_sync.clear_all_records()
    return json.dumps(result, indent=2)

# ==============================================================================
# 2. REST API & Web Endpoints (Starlette)
# ==============================================================================

async def handle_index(request: Request) -> HTMLResponse:
    """Serve the Entry Form single-page application."""
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Entry Form not found</h1>", status_code=404)
    return HTMLResponse(index_file.read_text(encoding="utf-8"))

async def handle_submit(request: Request) -> JSONResponse:
    """Handle Entry Form submissions and dispatch to orchestrator."""
    try:
        data = await request.json()
    except Exception as e:
        logger.warning(f"Invalid JSON submitted: {e}")
        return JSONResponse({"detail": "Malformed JSON payload in request body."}, status_code=400)

    if not isinstance(data, dict):
        return JSONResponse({"detail": "Request body must be a JSON object."}, status_code=422)

    try:
        sub_req = SubmissionRequest(
            project_name=data.get("project_name"),
            description=data.get("description"),
            requirements=data.get("requirements"),
            additional_info=data.get("additional_info")
        )
    except Exception as e:
        logger.warning(f"Payload validation error: {e}")
        return JSONResponse({"detail": str(e), "error": "Validation failed"}, status_code=422)

    try:
        result = orchestrator.run(sub_req)
        if result.overall_status == "failed":
            return JSONResponse(result.model_dump(), status_code=422)
        status_code = 201 if result.database_status == "inserted" else 200
        return JSONResponse(result.model_dump(), status_code=status_code)
    except Exception as e:
        logger.error(f"Error processing submission: {e}", exc_info=True)
        return JSONResponse({"detail": "Internal server error processing submission."}, status_code=500)

async def handle_list_projects(request: Request) -> JSONResponse:
    """Return projects saved in the SQLite database, with optional status filter."""
    try:
        status_filter = request.query_params.get("status")
        db_mgr = DatabaseManager()
        projects = db_mgr.list_all_projects(status=status_filter)
        return JSONResponse({"projects": projects}, status_code=200)
    except Exception as e:
        logger.error(f"Error fetching projects: {e}", exc_info=True)
        return JSONResponse({"detail": "Failed to retrieve projects.", "projects": []}, status_code=500)

async def handle_get_project(request: Request) -> JSONResponse:
    """Fetch a single project by ID."""
    try:
        project_id = int(request.path_params["id"])
    except (ValueError, KeyError):
        return JSONResponse({"detail": "Invalid project ID format."}, status_code=400)

    try:
        db_mgr = DatabaseManager()
        project = db_mgr.get_project_by_id(project_id)
        if not project:
            return JSONResponse({"detail": f"Project with ID #{project_id} not found."}, status_code=404)
        return JSONResponse(project, status_code=200)
    except Exception as e:
        logger.error(f"Error retrieving project #{project_id}: {e}", exc_info=True)
        return JSONResponse({"detail": "Internal server error retrieving project."}, status_code=500)

async def handle_update_project(request: Request) -> JSONResponse:
    """Update an existing project record and synchronize markdown & documentation."""
    try:
        project_id = int(request.path_params["id"])
    except (ValueError, KeyError):
        return JSONResponse({"detail": "Invalid project ID format."}, status_code=400)

    try:
        data = await request.json()
    except Exception as e:
        logger.warning(f"Invalid JSON payload for update: {e}")
        return JSONResponse({"detail": "Malformed JSON payload in request body."}, status_code=400)

    if not isinstance(data, dict):
        return JSONResponse({"detail": "Request payload must be a JSON object."}, status_code=422)

    try:
        update_req = ProjectUpdateRequest(**data)
    except Exception as e:
        logger.warning(f"Payload validation error on update: {e}")
        return JSONResponse({"detail": str(e), "error": "Validation failed"}, status_code=422)

    db_mgr = DatabaseManager()
    existing = db_mgr.get_project_by_id(project_id)
    if not existing:
        return JSONResponse({"detail": f"Project with ID #{project_id} not found."}, status_code=404)

    try:
        result = orchestrator.update_project(project_id, update_req)
        if result.overall_status == "failed":
            if result.errors and any("not found" in err.lower() for err in result.errors):
                return JSONResponse(result.model_dump(), status_code=404)
            return JSONResponse(result.model_dump(), status_code=422)
        return JSONResponse(result.model_dump(), status_code=200)
    except ValueError as e:
        logger.warning(f"Collision or domain validation error updating project #{project_id}: {e}")
        return JSONResponse({"detail": str(e)}, status_code=422)
    except Exception as e:
        logger.error(f"Unhandled error updating project #{project_id}: {e}", exc_info=True)
        return JSONResponse({"detail": "Internal server error updating project."}, status_code=500)

async def handle_delete_project(request: Request) -> JSONResponse:
    """Archive (soft delete) or permanently delete a project by ID."""
    try:
        project_id = int(request.path_params["id"])
    except (ValueError, KeyError):
        return JSONResponse({"detail": "Invalid project ID format."}, status_code=400)

    is_permanent = request.query_params.get("permanent", "false").lower() in ("true", "1", "yes")

    db_mgr = DatabaseManager()
    existing = db_mgr.get_project_by_id(project_id)
    if not existing:
        return JSONResponse({"detail": f"Project with ID #{project_id} not found."}, status_code=404)

    try:
        result = orchestrator.delete_project(project_id, permanent=is_permanent)
        action_word = "permanently deleted" if is_permanent else "archived"
        return JSONResponse({
            "status": "success",
            "project_id": project_id,
            "project_name": existing["project_name"],
            "action": action_word,
            "message": f"Project #{project_id} ('{existing['project_name']}') successfully {action_word}."
        }, status_code=200)
    except Exception as e:
        logger.error(f"Error deleting/archiving project #{project_id}: {e}", exc_info=True)
        return JSONResponse({"detail": "Internal server error deleting/archiving project."}, status_code=500)

async def handle_preview(request: Request) -> JSONResponse:
    """Safely fetch markdown or documentation file contents for preview modal."""
    raw_path = request.query_params.get("path")
    if not raw_path:
        return JSONResponse({"detail": "Missing 'path' parameter"}, status_code=400)

    try:
        target = Path(raw_path).resolve()
        # Security containment check: target must be inside BASE_DIR
        base_resolved = BASE_DIR.resolve()
        try:
            target.relative_to(base_resolved)
        except ValueError:
            return JSONResponse({"detail": "Access denied: Path outside workspace."}, status_code=403)

        if not target.exists() or not target.is_file():
            return JSONResponse({"detail": f"File not found: {target.name}"}, status_code=404)

        content = target.read_text(encoding="utf-8")
        return JSONResponse({"file": target.name, "content": content}, status_code=200)
    except Exception as e:
        logger.error(f"Error reading preview file: {e}")
        return JSONResponse({"detail": "Error reading preview file."}, status_code=500)

async def handle_airtable_status(request: Request) -> JSONResponse:
    """Return Airtable cloud synchronization status and current cloud records."""
    is_cfg = airtable_sync.is_configured()
    records = airtable_sync.list_projects() if is_cfg else []
    return JSONResponse({
        "airtable_configured": is_cfg,
        "base_id": airtable_sync.base_id if is_cfg else None,
        "table_name": airtable_sync.table_name if is_cfg else None,
        "records_count": len(records),
        "records": records
    }, status_code=200)

async def handle_airtable_clear(request: Request) -> JSONResponse:
    """Completely wipe all records from the Airtable cloud base while preserving column labels."""
    try:
        res = airtable_sync.clear_all_records()
        return JSONResponse(res, status_code=200 if res.get("success") else 400)
    except Exception as e:
        logger.error(f"Error clearing Airtable: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

async def handle_health(request: Request) -> JSONResponse:
    """Service health and agent readiness check."""
    return JSONResponse({
        "status": "healthy",
        "service": "multi-agent-workflow",
        "agents": {
            "agent1_markdown": "active",
            "agent2_database": "active",
            "agent3_documentation": "active",
            "orchestrator": "active"
        },
        "mcp": mcp_bridge.get_status(),
        "airtable": {
            "configured": airtable_sync.is_configured(),
            "status": "connected" if airtable_sync.is_configured() else "not_configured"
        }
    })

async def handle_get_mode(request: Request) -> JSONResponse:
    """Return the current user mode ('server' or 'host')."""
    return JSONResponse({
        "mode": mcp_host_manager.get_mode(),
        "available_modes": ["server", "host"]
    })

async def handle_set_mode(request: Request) -> JSONResponse:
    """Set the user mode preference ('server' or 'host')."""
    try:
        data = await request.json()
        mode = data.get("mode")
        updated = mcp_host_manager.set_mode(mode)
        return JSONResponse({"status": "success", "mode": updated})
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"Error setting mode: {e}")
        return JSONResponse({"detail": "Invalid mode request payload."}, status_code=400)

async def handle_host_tools(request: Request) -> JSONResponse:
    """List available MCP tools formatted for the MCP Host UI."""
    try:
        tools = await mcp_host_manager.list_tools()
        return JSONResponse({"tools": tools, "count": len(tools)})
    except Exception as e:
        logger.error(f"Error fetching MCP tools: {e}", exc_info=True)
        return JSONResponse({"detail": "Failed to retrieve MCP tools.", "tools": []}, status_code=500)

async def handle_host_execute(request: Request) -> JSONResponse:
    """Execute an MCP tool as an MCP Host Client."""
    try:
        data = await request.json()
        tool_name = data.get("tool")
        arguments = data.get("arguments", {})
        if not tool_name:
            return JSONResponse({"detail": "Missing 'tool' parameter."}, status_code=400)

        result = await mcp_host_manager.execute_tool(tool_name, arguments)
        status_code = 200 if result.get("success") else 400
        return JSONResponse(result, status_code=status_code)
    except Exception as e:
        logger.error(f"Host tool execution error: {e}", exc_info=True)
        return JSONResponse({"detail": str(e), "success": False}, status_code=500)

async def handle_host_chat(request: Request) -> JSONResponse:
    """Host AI Assistant natural language interaction (Local, Gemini, or Claude)."""
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        provider = data.get("provider", "local")
        api_key = data.get("api_key")
        if not message:
            return JSONResponse({"detail": "Message cannot be empty."}, status_code=400)

        response = await mcp_host_manager.chat(message, provider=provider, api_key=api_key)
        return JSONResponse(response, status_code=200)
    except Exception as e:
        logger.error(f"Host chat error: {e}", exc_info=True)
        return JSONResponse({"detail": str(e)}, status_code=500)

async def handle_host_status(request: Request) -> JSONResponse:
    """Host telemetry and runtime status."""
    return JSONResponse(mcp_host_manager.get_status(), status_code=200)

async def handle_host_claude_config(request: Request) -> JSONResponse:
    """Return Claude Desktop configuration metadata."""
    return JSONResponse(mcp_host_manager.get_claude_desktop_config(), status_code=200)

async def handle_host_claude_install(request: Request) -> JSONResponse:
    """Automatically register MCP server into Claude Desktop config file."""
    try:
        res = mcp_host_manager.install_claude_desktop_config()
        return JSONResponse(res, status_code=200)
    except Exception as e:
        logger.error(f"Error configuring Claude Desktop: {e}", exc_info=True)
        return JSONResponse({"detail": str(e), "status": "error"}, status_code=500)

routes = [
    Route("/", endpoint=handle_index, methods=["GET"]),
    Route("/api/submit", endpoint=handle_submit, methods=["POST"]),
    Route("/api/projects", endpoint=handle_list_projects, methods=["GET"]),
    Route("/api/projects/{id:int}", endpoint=handle_get_project, methods=["GET"]),
    Route("/api/projects/{id:int}", endpoint=handle_update_project, methods=["PUT"]),
    Route("/api/projects/{id:int}", endpoint=handle_delete_project, methods=["DELETE"]),
    Route("/api/preview", endpoint=handle_preview, methods=["GET"]),
    Route("/api/health", endpoint=handle_health, methods=["GET"]),
    Route("/api/airtable", endpoint=handle_airtable_status, methods=["GET"]),
    Route("/api/airtable/clear", endpoint=handle_airtable_clear, methods=["POST"]),
    Route("/api/mode", endpoint=handle_get_mode, methods=["GET"]),
    Route("/api/mode", endpoint=handle_set_mode, methods=["POST"]),
    Route("/api/host/tools", endpoint=handle_host_tools, methods=["GET"]),
    Route("/api/host/execute", endpoint=handle_host_execute, methods=["POST"]),
    Route("/api/host/chat", endpoint=handle_host_chat, methods=["POST"]),
    Route("/api/host/status", endpoint=handle_host_status, methods=["GET"]),
    Route("/api/host/claude-config", endpoint=handle_host_claude_config, methods=["GET"]),
    Route("/api/host/claude-config/install", endpoint=handle_host_claude_install, methods=["POST"]),
    Mount("/static", app=StaticFiles(directory=str(FRONTEND_DIR)), name="static"),
]

app = Starlette(debug=DEBUG, routes=routes)

# ==============================================================================
# 3. CLI & Server Entry Point
# ==============================================================================
def main():
    if "--mcp" in sys.argv:
        # Run exclusively as standard MCP Stdio Server
        logger.info("Starting in MCP Stdio Server mode...")
        mcp.run(transport="stdio")
    else:
        # Run Web Server + REST API + Entry Form UI
        logger.info(f"Starting Multi-Agent Workflow Web Portal on http://{HOST}:{PORT}")
        uvicorn.run("server:app", host=HOST, port=PORT, log_level="info")

if __name__ == "__main__":
    main()
