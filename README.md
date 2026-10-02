# Multi-Agent Workflow System

An enterprise-ready, modular multi-agent workflow platform integrating three specialized AI agents, an interactive web Entry Form, an SQLite database persistence engine, and the **Model Context Protocol (MCP)**.

```
USER
  ↓
ENTRY FORM (Web UI)
  ↓
ORCHESTRATOR / MAIN AGENT
  ↓
 ┌─────────────────────────────────────┐
 │                                     │
 ▼                                     ▼
AGENT 1                              AGENT 2
Markdown Agent                       Database Agent
 │                                     │
 ▼                                     ▼
Create/update .md file              Store data in database
 │                                     │
 └──────────────────┬──────────────────┘
                    ▼
                 AGENT 3
            Documentation Agent
                    │
                    ▼
          Generate documentation
```

---

## 🌟 Key Features

1. **Agent 1 — Markdown Agent (`agents/agent1_markdown`)**:
   - Analyzes incoming task/project submissions.
   - Generates structured Markdown (`.md`) files with YAML frontmatter, checklists, architecture blueprints (Mermaid), and metadata.
   - Saves artifacts to `output/markdown/`.
   - **Intelligent Deduplication:** Detects existing files by slug, preserves creation history, and increments document version (`v1` → `v2`).

2. **Agent 2 — Database Agent (`agents/agent2_database`)**:
   - Validates input payloads before storage.
   - Automatically initializes SQLite tables and indexes (`projects` and `workflow_runs`).
   - Prevents duplicate project records; automatically updates existing records and increments the revision counter.
   - Implements transactional audit logs in `workflow_runs` with safe rollback on errors.

3. **Agent 3 — Documentation Agent (`agents/agent3_documentation`)**:
   - Consumes the composite outputs of Agent 1 and Agent 2.
   - Generates dedicated project technical documentation in `docs/projects/<slug>_doc.md`.
   - Maintains a centralized, synchronized project catalog in `docs/PROJECTS_CATALOG.md`.

4. **Workflow Orchestrator (`orchestrator`)**:
   - Central coordinator executing the sequence: `Validate` → `Agent 1` → `Agent 2` → `Agent 3`.
   - Compiles a unified response payload with status, file paths, and record IDs.

5. **Web Entry Form (`frontend/entry-form`)**:
   - Clean, dark-mode single page application (SPA).
   - Real-time client-side validation and helpful error feedback.
   - Animated 4-step pipeline visualizer tracking agent progress.
   - Pre-fill button for instant demonstration.
   - Integrated modal preview for reviewing generated markdown and documentation.
   - Recent projects database table with live refresh.

6. **Model Context Protocol (MCP) Integration**:
   - Exposes workflow capabilities as standard FastMCP tools (`orchestrate_workflow`, `create_or_update_markdown`, `store_project_in_database`, `generate_project_documentation`, `list_projects`).
   - Supports both Web Server mode and MCP stdio server mode (`python server.py --mcp`).
   - Isolated configuration in `config/mcp_config.json`.

---

## 🗄️ Database Schema

The system uses SQLite (stored in `database/projects.db`) with WAL mode enabled:

### `projects` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique record ID |
| `project_name` | TEXT | NOT NULL UNIQUE (NOCASE) | Project title |
| `slug` | TEXT | NOT NULL UNIQUE | URL-safe identifier |
| `description` | TEXT | NOT NULL | Project description |
| `requirements` | TEXT | NOT NULL | JSON array of specifications |
| `additional_info` | TEXT | | Additional notes and constraints |
| `markdown_path` | TEXT | | Path to markdown file from Agent 1 |
| `version` | INTEGER | DEFAULT 1 | Revision version counter |
| `status` | TEXT | DEFAULT 'active' | Operational status |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update timestamp |

### `workflow_runs` Table (Audit Log)
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique log ID |
| `workflow_run_id` | TEXT | NOT NULL | Unique workflow execution ID |
| `project_id` | INTEGER | REFERENCES `projects(id)` | Foreign key to project |
| `project_name` | TEXT | NOT NULL | Project title |
| `agent_name` | TEXT | NOT NULL | Executing agent identifier |
| `action` | TEXT | NOT NULL | Action executed (`inserted`, `updated`) |
| `status` | TEXT | NOT NULL | `success`, `warning`, `error` |
| `details` | TEXT | | JSON payload of execution details |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Run timestamp |

---

## 📂 Project Structure

```
my-mcp-server/
├── agents/
│   ├── agent1_markdown/         # Agent 1: Markdown generator & updater
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   └── models.py
│   ├── agent2_database/         # Agent 2: Database persistence & audit logger
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── db.py
│   │   └── models.py
│   └── agent3_documentation/    # Agent 3: Documentation & catalog synchronizer
│       ├── __init__.py
│       ├── agent.py
│       └── models.py
├── orchestrator/                # Main Workflow Orchestrator
│   ├── __init__.py
│   ├── orchestrator.py
│   └── models.py
├── frontend/
│   └── entry-form/              # Clean Web Entry Form (HTML/CSS/JS)
│       ├── index.html
│       ├── style.css
│       └── app.js
├── config/                      # Configuration & MCP integration
│   ├── settings.py
│   ├── logging_config.py
│   ├── mcp_bridge.py
│   ├── mcp_config.json
│   └── README.md
├── database/                    # SQLite storage & SQL schema
│   ├── schema.sql
│   └── projects.db
├── docs/                        # Generated documentation & project catalog
│   ├── PROJECTS_CATALOG.md
│   └── projects/
├── output/
│   └── markdown/                # Generated project Markdown files
├── tests/                       # Complete unit & integration test suite
│   ├── test_agent1_markdown.py
│   ├── test_agent2_database.py
│   ├── test_agent3_documentation.py
│   ├── test_orchestrator.py
│   ├── test_api.py
│   └── run_all_tests.py
├── .env.example
├── .env
├── pyproject.toml
├── server.py                    # Web portal + REST API + MCP server
└── README.md
```

---

## 🚀 How to Run

### 1. Start the Web Portal & REST API
```powershell
.\.venv\Scripts\python.exe server.py
# Or with uv:
uv run python server.py
```
Open your browser and navigate to:
👉 **`http://127.0.0.1:8000`**

### 2. Run as an MCP Server (Stdio Mode)
To connect this workflow directly to Claude Desktop, Cursor, or another MCP client:
```powershell
.\.venv\Scripts\python.exe server.py --mcp
```

---

## 🧪 Testing

Execute the complete automated test suite:
```powershell
.\.venv\Scripts\python.exe tests/run_all_tests.py
```

Or test each agent independently:
- **Test Agent 1:** `.\.venv\Scripts\python.exe tests/test_agent1_markdown.py`
- **Test Agent 2:** `.\.venv\Scripts\python.exe tests/test_agent2_database.py`
- **Test Agent 3:** `.\.venv\Scripts\python.exe tests/test_agent3_documentation.py`
- **Test Orchestrator:** `.\.venv\Scripts\python.exe tests/test_orchestrator.py`
- **Test REST API:** `.\.venv\Scripts\python.exe tests/test_api.py`

---

## 🔌 API Reference

### Submit Project (`POST /api/submit`)
**Request:**
```json
{
  "project_name": "API Gateway Rate Limiter",
  "description": "Token bucket rate limiting middleware with Redis backplane.",
  "requirements": "Max 100 req/sec per API key\nBurst capacity of 150 requests",
  "additional_info": "Low latency requirement: < 2ms overhead."
}
```

**Response:**
```json
{
  "workflow_run_id": "wf_20260924_174032_b11716",
  "overall_status": "success",
  "markdown_status": "created",
  "markdown_file_path": "C:/Users/.../output/markdown/api-gateway-rate-limiter.md",
  "markdown_summary": "Successfully created Markdown file 'api-gateway-rate-limiter.md' (v1) with 2 requirements (1414 chars).",
  "database_status": "inserted",
  "database_record_id": 1,
  "database_operation": "Inserted new project record ID #1 (revision v1)",
  "documentation_status": "created",
  "documentation_file_path": "C:/Users/.../docs/projects/api-gateway-rate-limiter_doc.md",
  "documentation_summary": "Successfully created project documentation at 'docs/projects/api-gateway-rate-limiter_doc.md' and updated project catalog.",
  "timestamp": "2026-09-24T12:10:32.333000+00:00"
}
```

### Project Management Endpoints (CRUD)
- `GET /` — Entry Form Single Page Application (with Edit Mode & Confirm Dialogs)
- `POST /api/submit` — Submit new project to run the 3-agent workflow (`201 Created` on new, `200 OK` on duplicate update)
- `GET /api/projects?status=active|archived|all` — List registered projects with optional status filter
- `GET /api/projects/{id}` — Retrieve a single project record by ID (`404 Not Found` if missing)
- `PUT /api/projects/{id}` — Update an existing project, increment version, and re-run Agent 1 (Markdown) and Agent 3 (Documentation)
- `DELETE /api/projects/{id}?permanent=false` — Soft delete / archive project (sets `status='archived'`)
- `DELETE /api/projects/{id}?permanent=true` — Permanently delete project record (cascading audit logs)
- `GET /api/preview?path=<file_path>` — Safe preview of markdown/doc files with path containment verification
- `GET /api/health` — Health check and agent readiness status

---

## 🔒 Security & Strict Validation Rules

1. **Strict Type Enforcement:**
   - Rejects boolean, number, array, and dictionary types on string fields without silent coercion.
   - Trims whitespace and rejects whitespace-only or meaningless symbol strings.
2. **Field Length Boundaries:**
   - `project_name`: 2 to 120 characters
   - `description`: 5 to 5000 characters
   - `requirements`: 5 to 5000 characters
   - `additional_info`: Maximum 3000 characters
3. **Database Integrity:**
   - 100% parameterized SQLite queries preventing SQL injection.
   - Transactional isolation with atomic commit/rollback.
   - Monotonic revision incrementing (`v1` → `v2` → `v3`).
4. **Path Traversal Protection:**
   - Preview and file operations strictly bound within project `BASE_DIR`. Attempts to traverse outside return `403 Forbidden`.
