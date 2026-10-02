# Configuration & MCP Documentation

This directory contains configuration, logging, and Model Context Protocol (MCP) bridging for the multi-agent workflow.

## Environment Variables (`.env`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `HOST` | `127.0.0.1` | Web server host address |
| `PORT` | `8000` | Web server port |
| `DEBUG` | `False` | Debug mode toggle |
| `DATABASE_PATH` | `database/projects.db` | SQLite database file location |
| `MARKDOWN_OUTPUT_DIR` | `output/markdown` | Directory where Agent 1 saves markdown files |
| `DOCS_DIR` | `docs` | Directory where Agent 3 saves documentation |
| `MCP_SERVER_NAME` | `multi-agent-workflow-server` | Registered MCP server identifier |
| `MCP_ENABLED` | `True` | Flag to enable MCP tool endpoints |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## MCP (Model Context Protocol) Integration

### Architecture
- **MCP Server**: The application exposes specialized agent tools via FastMCP (`mcp.server.MCPServer`), accessible to AI models and MCP clients.
- **MCP Bridge**: The `config/mcp_bridge.py` module manages tool discovery. If external MCP servers (such as filesystem or SQLite) are present, requests can route through them; otherwise, safe local alternatives (`pathlib` and `sqlite3`) are executed without interruption.
- **Isolation**: All MCP configuration resides in `config/mcp_config.json`.
