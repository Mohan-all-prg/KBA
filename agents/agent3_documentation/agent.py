import re
import json
import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union, Tuple
from config.settings import DOCS_DIR, DOCS_PROJECTS_DIR, BASE_DIR
from config.logging_config import get_logger
from config.mcp_bridge import mcp_bridge
from agents.agent3_documentation.models import DocumentationInput, DocumentationOutput

logger = get_logger("agent.documentation")

class DocumentationAgent:
    """
    Agent 3: Documentation Agent
    Automatically generates and maintains project documentation using the information
    produced by Agent 1 (Markdown Agent) and Agent 2 (Database Agent).
    """

    def __init__(self, docs_dir: Path = DOCS_DIR):
        self.docs_dir = Path(docs_dir)
        self.projects_docs_dir = self.docs_dir / "projects"
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.projects_docs_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def slugify(text: str) -> str:
        """Convert a project name into a safe, normalized URL-friendly slug."""
        text = text.strip().lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "-", text)
        return text.strip("-") or "project"

    def validate_input(self, data: DocumentationInput) -> Tuple[bool, str]:
        """Validate input payload for documentation generation."""
        if not data.project_name or len(data.project_name.strip()) < 2:
            return False, "Project name is required and must be at least 2 characters long."
        if not data.description or len(data.description.strip()) < 5:
            return False, "Project description is required and must be at least 5 characters long."
        return True, ""

    def generate_project_doc(
        self,
        project_name: str,
        slug: str,
        description: str,
        requirements: Any,
        additional_info: str,
        markdown_res: Dict[str, Any],
        database_res: Dict[str, Any],
        workflow_run_id: str,
        timestamp: str
    ) -> str:
        """
        Generate comprehensive, synchronized technical documentation covering:
        - Project overview
        - Requirements
        - Agent architecture
        - Workflow
        - Database schema
        - Markdown generation
        - APIs
        - Inputs and outputs
        - Configuration
        - Installation
        - Testing
        """
        md_file = markdown_res.get("file_path", "N/A")
        md_status = markdown_res.get("action") or markdown_res.get("status", "N/A")
        md_version = markdown_res.get("version", 1)

        db_id = database_res.get("record_id", "N/A")
        db_status = database_res.get("action") or database_res.get("status", "N/A")
        db_version = database_res.get("version", 1)
        db_table = database_res.get("table", "projects")

        req_str = json.dumps(requirements, indent=2) if not isinstance(requirements, str) else requirements

        doc = f"""# Comprehensive Project Documentation: {project_name}

> **Workflow Run ID:** `{workflow_run_id}`  
> **Generated Timestamp:** `{timestamp}`  
> **Synchronization Status:** Synchronized & Active

---

## 1. Project Overview
This document provides complete technical, operational, and architectural documentation for **{project_name}**.
It is automatically compiled and maintained by **Agent 3 (Documentation Agent)** to remain synchronized with implementation artifacts.

- **Project Identifier / Slug:** `{slug}`
- **Operational Status:** Active
- **Version:** v{db_version}
- **Description:**  
  > {description.strip()}

---

## 2. Requirements & Specifications
The functional and technical requirements specified for this project:

```text
{req_str}
```

**Additional Notes & Constraints:**
```text
{additional_info.strip() if additional_info else "None specified"}
```

---

## 3. Agent Architecture
The system employs a 3-agent autonomous architecture coordinated by a central orchestrator:

| Agent | Responsibility | Implementation File | Key Mechanism |
| :--- | :--- | :--- | :--- |
| **Agent 1: Markdown Agent** | Generates & updates clean Markdown files | `agents/agent1_markdown/agent.py` | Frontmatter parsing, checklist formatting, version incrementing, deduplication |
| **Agent 2: Database Agent** | Validates and stores data in SQLite | `agents/agent2_database/agent.py` | Schema assurance, parameterized SQL, duplicate prevention, audit logs |
| **Agent 3: Documentation Agent** | Maintains synchronized system docs | `agents/agent3_documentation/agent.py` | Cross-agent artifact collation, project catalog synchronization |

---

## 4. Multi-Agent Workflow
Execution trace detailing sequential execution:

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Entry Form
    participant O as Orchestrator
    participant A1 as Agent 1 (Markdown Agent)
    participant A2 as Agent 2 (Database Agent)
    participant A3 as Agent 3 (Documentation Agent)

    User->>O: Submit Project Info (Form)
    O->>O: Validate Form Data
    O->>A1: Dispatch Markdown Task
    A1-->>O: Markdown Generated ({md_file})
    O->>A2: Dispatch Storage Task with Markdown Path
    A2-->>O: Record Persisted (ID #{db_id})
    O->>A3: Dispatch Documentation Task (Results A1 + A2)
    A3-->>O: Documentation Synchronized
    O-->>User: Unified Workflow Response
```

---

## 5. Database Schema & Persistence
Data is persisted in SQLite with Write-Ahead Logging (WAL) enabled:

- **Target Table:** `{db_table}`
- **Record Primary Key:** `#{db_id}`
- **Revision Counter:** `v{db_version}`
- **Operation Performed:** `{db_status}`

### Schema Structure:
```sql
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    slug TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    requirements TEXT NOT NULL,
    additional_info TEXT,
    markdown_path TEXT,
    version INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. Markdown Generation & Artifacts
Agent 1 creates clean, structured Markdown specifications:

- **Artifact Path:** [`{md_file}`]({md_file})
- **Document Version:** `v{md_version}`
- **Generation Status:** `{md_status}`
- **Format:** YAML frontmatter, executive overview, checklist items, and Mermaid diagrams.

---

## 7. APIs & Integration Reference

### REST Endpoints
```http
POST /api/submit
Content-Type: application/json

{{
  "project_name": "{project_name}",
  "description": "{description.strip()}",
  "requirements": "...",
  "additional_info": "{additional_info.strip() if additional_info else ''}"
}}
```

```http
GET /api/projects?status=active|archived|all
GET /api/projects/{{id}}
PUT /api/projects/{{id}}
DELETE /api/projects/{{id}}?permanent=false|true
GET /api/preview?path=output/markdown/...
```

### Model Context Protocol (MCP) Tools
- `orchestrate_workflow(project_name, description, requirements, additional_info)`: Full 3-agent pipeline
- `update_existing_project(project_id, project_name, description, requirements, additional_info)`: Full update pipeline
- `archive_or_delete_project(project_id, permanent)`: Soft archive or permanent delete
- `create_or_update_markdown(...)`: Independent Agent 1 execution
- `store_project_in_database(...)`: Independent Agent 2 execution
- `generate_project_documentation(...)`: Independent Agent 3 execution
- `list_projects(status)`: Query SQLite project catalog

---

## 8. Inputs and Outputs Specification

### Data Validation & Integrity Rules
- **Strict Typing:** Rejects boolean, number, array, and object types without silent coercion.
- **Content Hygiene:** Leading and trailing whitespace is automatically stripped; empty or whitespace-only strings are rejected.
- **Length Boundaries:**
  - `project_name`: 2 to 120 characters
  - `description`: 5 to 5000 characters
  - `requirements`: 5 to 5000 characters
  - `additional_info`: Maximum 3000 characters
- **SQL Injection Prevention:** Fully parameterized SQLite queries across all operations.
- **Revision Control:** Version increments monotonically with each update, logging audit events in `workflow_runs`.

### Agent Inputs & Outputs
- **Agent 1 (Markdown Agent):**
  - **Input:** `MarkdownInput(project_name, description, requirements, additional_info)`
  - **Output:** `{{ "status": "success/failure", "file_path": "...", "summary": "..." }}`

- **Agent 2 (Database Agent):**
  - **Input:** `DatabaseInput(project_name, description, requirements, additional_info, markdown_path)`
  - **Output:** `{{ "status": "success/failure", "record_id": "...", "message": "..." }}`

- **Agent 3 (Documentation Agent):**
  - **Input:** `DocumentationInput(project_name, description, requirements, markdown_result, database_result)`
  - **Output:** `{{ "status": "success/failure", "documentation_path": "...", "summary": "..." }}`

---

## 9. Configuration & Environment Variables
Configuration is loaded dynamically from `.env`:

| Key | Default | Purpose |
| :--- | :--- | :--- |
| `DATABASE_PATH` | `database/projects.db` | Path to SQLite file |
| `MARKDOWN_OUTPUT_DIR` | `output/markdown` | Target directory for Markdown files |
| `DOCS_DIR` | `docs` | Target directory for documentation |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Web server listening address |
| `MCP_ENABLED` | `True` | FastMCP protocol activation |

---

## 10. Installation & Setup Guide
1. Clone / open repository.
2. Initialize virtual environment and install dependencies:
   ```powershell
   uv sync
   # Or using standard python:
   python -m venv .venv
   .\\.venv\\Scripts\\pip install -e .
   ```
3. Run Web Server & Entry Form:
   ```powershell
   .\\.venv\\Scripts\\python.exe server.py
   ```

---

## 11. Testing & Verification Runbook
Execute tests independently or collectively:
```powershell
# Run Master Test Suite
.\\.venv\\Scripts\\python.exe tests/run_all_tests.py

# Run Individual Agent Tests
.\\.venv\\Scripts\\python.exe tests/test_agent1_markdown.py
.\\.venv\\Scripts\\python.exe tests/test_agent2_database.py
.\\.venv\\Scripts\\python.exe tests/test_agent3_documentation.py
.\\.venv\\Scripts\\python.exe tests/test_orchestrator.py
```
"""
        return doc

    def update_catalog(
        self,
        project_name: str,
        slug: str,
        description: str,
        md_file: str,
        db_id: Any,
        doc_rel_path: str,
        timestamp: str
    ) -> Path:
        """Update or create the central project catalog index in docs/PROJECTS_CATALOG.md."""
        catalog_path = self.docs_dir / "PROJECTS_CATALOG.md"

        header = """# 📚 Multi-Agent System: Project Catalog

This catalog is maintained automatically by **Agent 3 (Documentation Agent)**.
It tracks every project processed through the workflow, linking its Markdown artifact, Database record, and Technical Documentation.

| Project Name | DB ID | Markdown File | Documentation | Last Updated |
| :--- | :---: | :--- | :--- | :--- |
"""
        rows = {}
        if catalog_path.exists():
            content = mcp_bridge.read_file(catalog_path)
            lines = content.splitlines()
            for line in lines:
                if line.startswith("|") and not line.startswith("| Project Name") and not line.startswith("| :---"):
                    parts = [p.strip() for p in line.split("|")[1:-1]]
                    if len(parts) >= 5:
                        p_name = parts[0]
                        rows[p_name.lower()] = line

        # Add or update current project row
        new_row = f"| **{project_name}** | `#{db_id}` | [`{Path(md_file).name}`](../{md_file}) | [View Doc]({doc_rel_path}) | {timestamp[:19]} |"
        rows[project_name.lower()] = new_row

        catalog_content = header + "\n".join(rows.values()) + "\n"
        mcp_bridge.write_file(catalog_path, catalog_content)
        return catalog_path

    def process(self, input_data: Union[DocumentationInput, Dict[str, Any]]) -> DocumentationOutput:
        """
        Main execution method for Agent 3.
        Generates dedicated project doc and updates central catalog index.
        Returns:
        {
          "status": "success/failure",
          "documentation_path": "...",
          "summary": "..."
        }
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if isinstance(input_data, dict):
            try:
                input_data = DocumentationInput(**input_data)
            except Exception as e:
                logger.warning(f"Agent 3 dict parsing error: {e}")
                return DocumentationOutput(
                    status="failure",
                    documentation_path="",
                    summary=f"Validation failed: {str(e)}",
                    action="none",
                    success=False,
                    error=str(e)
                )

        logger.info(f"Agent 3 processing documentation for: '{input_data.project_name}'")

        # 1. Validation
        is_valid, validation_error = self.validate_input(input_data)
        if not is_valid:
            logger.warning(f"Agent 3 validation failed: {validation_error}")
            return DocumentationOutput(
                status="failure",
                documentation_path="",
                summary=f"Validation failed: {validation_error}",
                action="none",
                success=False,
                error=validation_error
            )

        try:
            slug = self.slugify(input_data.project_name)
            doc_filename = f"{slug}_doc.md"
            target_path = self.projects_docs_dir / doc_filename
            is_update = target_path.exists()
            action = "updated" if is_update else "created"

            workflow_id = input_data.workflow_run_id or f"wf_{int(datetime.datetime.now().timestamp())}"

            doc_text = self.generate_project_doc(
                project_name=input_data.project_name,
                slug=slug,
                description=input_data.description,
                requirements=input_data.requirements,
                additional_info=input_data.additional_info or "",
                markdown_res=input_data.markdown_result,
                database_res=input_data.database_result,
                workflow_run_id=workflow_id,
                timestamp=now_iso
            )

            # Write document file using MCP bridge (MCP tool or safe local fallback)
            mcp_bridge.write_file(target_path, doc_text)

            # Project-relative path
            try:
                rel_doc_path = str(target_path.relative_to(BASE_DIR)).replace("\\", "/")
            except ValueError:
                rel_doc_path = str(target_path).replace("\\", "/")

            # Update central catalog
            md_path_str = input_data.markdown_result.get("relative_path") or input_data.markdown_result.get("file_path", "")
            catalog_file = self.update_catalog(
                project_name=input_data.project_name,
                slug=slug,
                description=input_data.description,
                md_file=md_path_str,
                db_id=input_data.database_result.get("record_id", "N/A"),
                doc_rel_path=f"projects/{doc_filename}",
                timestamp=now_iso
            )

            summary = (
                f"Successfully {action} project documentation at '{rel_doc_path}' "
                f"and synchronized central project catalog."
            )
            logger.info(f"Agent 3 completed: {summary}")

            return DocumentationOutput(
                status="success",
                documentation_path=str(target_path.resolve()).replace("\\", "/"),
                doc_file_path=str(target_path.resolve()).replace("\\", "/"),
                relative_doc_path=rel_doc_path,
                catalog_path=str(catalog_file.resolve()).replace("\\", "/"),
                summary=summary,
                action=action,
                success=True,
                error=None
            )

        except Exception as e:
            logger.error(f"Agent 3 documentation generation failed: {e}", exc_info=True)
            return DocumentationOutput(
                status="failure",
                documentation_path="",
                doc_file_path="",
                relative_doc_path="",
                catalog_path="",
                summary=f"Failed to generate documentation: {str(e)}",
                action="error",
                success=False,
                error=str(e)
            )
