import re
import datetime
from pathlib import Path
from typing import List, Union, Dict, Any, Tuple
from config.settings import MARKDOWN_OUTPUT_DIR, BASE_DIR
from config.logging_config import get_logger
from config.mcp_bridge import mcp_bridge
from agents.agent1_markdown.models import MarkdownInput, MarkdownOutput

logger = get_logger("agent.markdown")

class MarkdownAgent:
    """
    Agent 1: Markdown Agent
    Receives structured data from the Entry Form and automatically creates
    or updates a clean, well-formatted Markdown (.md) file.
    """

    def __init__(self, output_dir: Path = MARKDOWN_OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def slugify(text: str) -> str:
        """
        Convert a project name into a safe, normalized URL-friendly slug.
        Ensures consistent filename resolution to avoid duplicate files.
        Guarantees no directory traversal sequences exist.
        """
        text = str(text).strip().lower()
        # Remove directory traversal patterns
        text = text.replace("..", "").replace("/", "").replace("\\", "")
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "-", text)
        slug = text.strip("-") or "project"
        return slug

    @staticmethod
    def parse_requirements(raw_reqs: Union[List[str], str]) -> List[str]:
        """Normalize requirements into a list of clean requirement strings."""
        if isinstance(raw_reqs, list):
            items = []
            for item in raw_reqs:
                if not isinstance(item, str) or isinstance(item, bool):
                    continue
                for line in str(item).split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    cleaned_line = re.sub(r"^[\s\-*•0-9\.)]+\s*", "", line).strip() or line
                    if len(re.findall(r'[a-zA-Z]', cleaned_line)) >= 2 and not re.search(r'(.)\1{4,}', cleaned_line):
                        items.append(cleaned_line)
            return items if items else []
        elif isinstance(raw_reqs, str):
            lines = []
            for line in raw_reqs.split("\n"):
                line = line.strip()
                if not line:
                    continue
                cleaned_line = re.sub(r"^[\s\-*•0-9\.)]+\s*", "", line).strip() or line
                if len(re.findall(r'[a-zA-Z]', cleaned_line)) >= 2 and not re.search(r'(.)\1{4,}', cleaned_line):
                    lines.append(cleaned_line)
            return lines if lines else []
        return []

    def validate_input(self, data: MarkdownInput) -> Tuple[bool, str]:
        """
        Validate incoming data from Entry Form.
        Enforces required fields, length constraints, meaningful content, and valid types.
        """
        if not isinstance(data.project_name, str) or isinstance(data.project_name, bool):
            return False, "Project name must be a string."
        p_name = data.project_name.strip()
        if len(p_name) < 2:
            return False, "Project name is required and must be at least 2 characters."
        if len(p_name) > 120:
            return False, f"Project name exceeds maximum length of 120 characters (currently {len(p_name)})."
        if len(re.findall(r'[a-zA-Z]', p_name)) < 2:
            return False, "Project name must contain meaningful text with letters, not purely numbers or symbols."
        if re.search(r'(.)\1{4,}', p_name):
            return False, "Project name contains excessive repetitive characters."
        alnum_name = [c.lower() for c in p_name if c.isalnum()]
        if len(alnum_name) >= 6 and len(set(alnum_name)) < 3:
            return False, "Project name lacks sufficient character variety and appears to be meaningless spam."

        if not isinstance(data.description, str) or isinstance(data.description, bool):
            return False, "Project description must be a string."
        desc = data.description.strip()
        if len(desc) < 5:
            return False, "Project description is required and must be at least 5 characters."
        if len(desc) > 5000:
            return False, f"Project description exceeds maximum length of 5000 characters (currently {len(desc)})."
        if len(re.findall(r'[a-zA-Z]', desc)) < 2:
            return False, "Project description must contain meaningful text with letters, not purely numbers or symbols."
        if re.search(r'(.)\1{4,}', desc):
            return False, "Project description contains excessive repetitive characters."
        alnum_desc = [c.lower() for c in desc if c.isalnum()]
        if len(alnum_desc) >= 6 and len(set(alnum_desc)) < 3:
            return False, "Project description lacks sufficient character variety and appears to be meaningless spam."

        if isinstance(data.requirements, (int, float, bool, dict)):
            return False, "Requirements must be a string or list of strings."
        reqs = self.parse_requirements(data.requirements)
        if not reqs or all(not r.strip() for r in reqs):
            return False, "At least one valid requirement with meaningful text must be provided."

        if data.additional_info is not None:
            if not isinstance(data.additional_info, str) or isinstance(data.additional_info, bool):
                return False, "Additional info must be a string if provided."
            info = data.additional_info.strip()
            if len(info) > 3000:
                return False, "Additional info exceeds maximum length of 3000 characters."
            if info:
                if re.search(r'(.)\1{4,}', info):
                    return False, "Additional info contains excessive repetitive characters."
                if len(info) >= 5 and len(re.findall(r'[a-zA-Z]', info)) < 2:
                    return False, "Additional info must contain meaningful text if provided."

        return True, ""

    def _extract_existing_metadata(self, file_path: Path) -> Tuple[int, str]:
        """Extract previous version and original creation date from existing markdown if available."""
        if not file_path.exists():
            return 1, datetime.datetime.now(datetime.timezone.utc).isoformat()

        try:
            content = mcp_bridge.read_file(file_path)
            version_match = re.search(r"version:\s*(\d+)", content)
            created_match = re.search(r"created_at:\s*([^\n]+)", content)
            prev_version = int(version_match.group(1)) if version_match else 1
            created_at = created_match.group(1).strip() if created_match else datetime.datetime.now(datetime.timezone.utc).isoformat()
            return prev_version + 1, created_at
        except Exception as e:
            logger.warning(f"Could not parse existing metadata from {file_path}: {e}")
            return 1, datetime.datetime.now(datetime.timezone.utc).isoformat()

    def generate_markdown_content(
        self,
        project_name: str,
        slug: str,
        description: str,
        requirements: List[str],
        additional_info: str,
        version: int,
        created_at: str,
        updated_at: str
    ) -> str:
        """Compose a structured, clean Markdown document with sections, lists, and code blocks."""
        req_items = "\n".join([f"- [ ] {req}" for req in requirements])
        add_info_section = (
            additional_info.strip()
            if additional_info and additional_info.strip()
            else "*No additional constraints or notes provided.*"
        )

        content = f"""---
title: "{project_name}"
slug: "{slug}"
version: {version}
status: "active"
created_at: "{created_at}"
updated_at: "{updated_at}"
---

# {project_name}

## 📋 Project Overview
- **Project Name:** {project_name}
- **Document Version:** v{version}
- **Status:** Active
- **Last Modified:** {updated_at}

---

## 🎯 Description
{description.strip()}

---

## ⚙️ Requirements & Specifications
The following requirements have been documented for this project:

{req_items}

---

## 📝 Additional Information & Notes
{add_info_section}

---

## 🏗️ Architectural Blueprint
```mermaid
graph TD
    User([User / Client]) --> EntryForm[Entry Form]
    EntryForm --> Orchestrator[Workflow Orchestrator]
    Orchestrator --> Agent1[Agent 1: Markdown Agent]
    Orchestrator --> Agent2[Agent 2: Database Agent]
    Agent1 -. Markdown Artifact .-> Agent3[Agent 3: Documentation Agent]
    Agent2 -. Database Record .-> Agent3
    Agent3 --> ProjectDocs[Documentation Catalog & Project Specs]
```

---

## 📊 Document History
- **Version:** {version}
- **Generated by:** Agent 1 (Markdown Agent)
- **Specification:** Model Context Protocol Multi-Agent Workflow
"""
        return content

    def process(self, input_data: Union[MarkdownInput, Dict[str, Any]]) -> MarkdownOutput:
        """
        Main execution method for Agent 1.
        Validates input, creates or updates the markdown file, and returns:
        {
          "status": "success/failure",
          "file_path": "...",
          "summary": "..."
        }
        """
        if isinstance(input_data, dict):
            try:
                input_data = MarkdownInput(**input_data)
            except Exception as e:
                logger.warning(f"Agent 1 dict parsing failed: {e}")
                return MarkdownOutput(
                    status="failure",
                    file_path="",
                    relative_path="",
                    file_name="",
                    summary=f"Validation failed: {str(e)}",
                    action="none",
                    version=0,
                    char_count=0,
                    success=False,
                    error=str(e)
                )

        logger.info(f"Agent 1 processing task for project: '{input_data.project_name}'")

        # 1. Validation
        is_valid, validation_error = self.validate_input(input_data)
        if not is_valid:
            logger.warning(f"Agent 1 input validation failed: {validation_error}")
            return MarkdownOutput(
                status="failure",
                file_path="",
                relative_path="",
                file_name="",
                summary=f"Validation failed: {validation_error}",
                action="none",
                version=0,
                char_count=0,
                success=False,
                error=validation_error
            )

        try:
            slug = self.slugify(input_data.project_name)
            file_name = f"{slug}.md"
            target_path = (self.output_dir / file_name).resolve()
            if not str(target_path).startswith(str(self.output_dir.resolve())):
                raise PermissionError("Security violation: path traversal outside markdown output directory.")
            is_update = target_path.exists()

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if is_update:
                version, created_at = self._extract_existing_metadata(target_path)
                action = "updated"
                logger.info(f"Existing file found for '{slug}'. Updating to version {version}.")
            else:
                version = 1
                created_at = now_iso
                action = "created"
                logger.info(f"Creating new markdown document for '{slug}' (v1).")

            reqs = self.parse_requirements(input_data.requirements)

            markdown_text = self.generate_markdown_content(
                project_name=input_data.project_name,
                slug=slug,
                description=input_data.description,
                requirements=reqs,
                additional_info=input_data.additional_info or "",
                version=version,
                created_at=created_at,
                updated_at=now_iso
            )

            # Write file using MCP bridge (MCP tool or safe local fallback)
            mcp_bridge.write_file(target_path, markdown_text)
            char_count = len(markdown_text)

            try:
                rel_path = str(target_path.relative_to(BASE_DIR)).replace("\\", "/")
            except ValueError:
                rel_path = str(target_path).replace("\\", "/")

            summary = (
                f"Successfully {action} Markdown file '{file_name}' (v{version}) "
                f"with {len(reqs)} requirements ({char_count} chars)."
            )

            logger.info(f"Agent 1 completed: {summary}")

            return MarkdownOutput(
                status="success",
                file_path=str(target_path.resolve()).replace("\\", "/"),
                relative_path=rel_path,
                file_name=file_name,
                summary=summary,
                action=action,
                version=version,
                char_count=char_count,
                success=True,
                error=None
            )

        except Exception as e:
            logger.error(f"Agent 1 encountered an error: {e}", exc_info=True)
            return MarkdownOutput(
                status="failure",
                file_path="",
                relative_path="",
                file_name="",
                summary=f"Failed to generate markdown: {str(e)}",
                action="error",
                version=0,
                char_count=0,
                success=False,
                error=str(e)
            )
