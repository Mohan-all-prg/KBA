import json
import datetime
import re
from typing import Optional, List, Union, Dict, Any, Tuple
from config.logging_config import get_logger
from config.mcp_bridge import mcp_bridge
from agents.agent2_database.models import DatabaseInput, DatabaseOutput
from agents.agent2_database.db import DatabaseManager
from agents.agent2_database.airtable_sync import airtable_sync, AirtableSyncManager

logger = get_logger("agent.database")

class DatabaseAgent:
    """
    Agent 2: Database Agent
    Receives structured data from the Entry Form, validates it, ensures the schema exists,
    prevents duplicate records, logs audit runs, stores it in SQLite, and synchronizes
    with Airtable Cloud Base.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        airtable_sync_manager: Optional[AirtableSyncManager] = None
    ):
        self.db = db_manager or DatabaseManager()
        self.airtable = airtable_sync_manager if airtable_sync_manager is not None else airtable_sync

    @staticmethod
    def slugify(text: str) -> str:
        """Convert a project name into a safe, normalized URL-friendly slug."""
        text = text.strip().lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "-", text)
        return text.strip("-") or "project"

    def validate_input(self, data: DatabaseInput) -> Tuple[bool, str]:
        """Thoroughly validate incoming data before storing in database."""
        if not data.project_name or len(data.project_name.strip()) < 2:
            return False, "Project name is required and must be at least 2 characters long."
        p_name = data.project_name.strip()
        if len(re.findall(r'[a-zA-Z]', p_name)) < 2:
            return False, "Project name must contain meaningful text with letters, not purely numbers or symbols."
        if re.search(r'(.)\1{4,}', p_name):
            return False, "Project name contains excessive repetitive characters."
        alnum_name = [c.lower() for c in p_name if c.isalnum()]
        if len(alnum_name) >= 6 and len(set(alnum_name)) < 3:
            return False, "Project name lacks sufficient character variety and appears to be meaningless spam."

        if not data.description or len(data.description.strip()) < 5:
            return False, "Project description is required and must be at least 5 characters long."
        desc = data.description.strip()
        if len(re.findall(r'[a-zA-Z]', desc)) < 2:
            return False, "Project description must contain meaningful text with letters, not purely numbers or symbols."
        if re.search(r'(.)\1{4,}', desc):
            return False, "Project description contains excessive repetitive characters."
        alnum_desc = [c.lower() for c in desc if c.isalnum()]
        if len(alnum_desc) >= 6 and len(set(alnum_desc)) < 3:
            return False, "Project description lacks sufficient character variety and appears to be meaningless spam."

        return True, ""

    def process(self, input_data: Union[DatabaseInput, Dict[str, Any]]) -> DatabaseOutput:
        """
        Main execution method for Agent 2.
        Validates input, checks for existing project (duplicate prevention),
        inserts or updates, records audit log, and returns:
        {
          "status": "success/failure",
          "record_id": "...",
          "message": "..."
        }
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Handle raw dictionary input
        if isinstance(input_data, dict):
            try:
                input_data = DatabaseInput(**input_data)
            except Exception as e:
                logger.warning(f"Agent 2 dict validation error: {e}")
                return DatabaseOutput(
                    status="failure",
                    record_id=None,
                    message=f"Validation failed: {str(e)}",
                    action="none",
                    operation="Validation error",
                    table="projects",
                    success=False,
                    error=str(e),
                    timestamp=now_iso
                )

        logger.info(f"Agent 2 processing database storage for: '{input_data.project_name}'")

        # 1. Input Validation
        is_valid, validation_error = self.validate_input(input_data)
        if not is_valid:
            logger.warning(f"Agent 2 validation failed: {validation_error}")
            return DatabaseOutput(
                status="failure",
                record_id=None,
                message=f"Validation failed: {validation_error}",
                action="none",
                project_name=input_data.project_name,
                slug="",
                version=0,
                operation="Validation failed",
                table="projects",
                success=False,
                error=validation_error,
                timestamp=now_iso
            )

        slug = self.slugify(input_data.project_name)

        # Normalize requirements to JSON string
        if isinstance(input_data.requirements, list):
            reqs_json = json.dumps(input_data.requirements)
        else:
            lines = [l.strip() for l in str(input_data.requirements).split("\n") if l.strip()]
            reqs_json = json.dumps(lines if lines else [str(input_data.requirements).strip()])

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 2. Check for duplicate / existing record
                existing = self.db.get_project_by_name_or_slug(input_data.project_name, slug)

                if existing:
                    # UPDATE existing record (preventing duplicates & incrementing version)
                    record_id = existing["id"]
                    new_version = existing.get("version", 1) + 1
                    action = "updated"
                    operation = f"Updated existing project record ID #{record_id} to revision v{new_version}"
                    message = f"Project '{input_data.project_name.strip()}' already exists. Successfully updated record ID #{record_id} to revision v{new_version}."

                    cursor.execute("""
                        UPDATE projects
                        SET description = ?,
                            requirements = ?,
                            additional_info = ?,
                            markdown_path = ?,
                            version = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        input_data.description.strip(),
                        reqs_json,
                        input_data.additional_info or "",
                        input_data.markdown_path or existing.get("markdown_path", ""),
                        new_version,
                        now_iso,
                        record_id
                    ))
                    logger.info(f"Agent 2: {operation}")

                else:
                    # INSERT new record
                    new_version = 1
                    action = "inserted"

                    cursor.execute("""
                        INSERT INTO projects (
                            project_name, slug, description, requirements,
                            additional_info, markdown_path, version, status,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                    """, (
                        input_data.project_name.strip(),
                        slug,
                        input_data.description.strip(),
                        reqs_json,
                        input_data.additional_info or "",
                        input_data.markdown_path or "",
                        new_version,
                        now_iso,
                        now_iso
                    ))
                    record_id = cursor.lastrowid
                    operation = f"Inserted new project record ID #{record_id} (revision v{new_version})"
                    message = f"Successfully inserted project '{input_data.project_name.strip()}' into database table 'projects' with record ID #{record_id}."
                    logger.info(f"Agent 2: {operation}")

                # 3. Insert audit log in workflow_runs
                if input_data.workflow_run_id:
                    cursor.execute("""
                        INSERT INTO workflow_runs (
                            workflow_run_id, project_id, project_name,
                            agent_name, action, status, details, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        input_data.workflow_run_id,
                        record_id,
                        input_data.project_name.strip(),
                        "agent2_database",
                        action,
                        "success",
                        json.dumps({
                            "version": new_version,
                            "slug": slug,
                            "markdown_path": input_data.markdown_path
                        }),
                        now_iso
                    ))

                conn.commit()

            # 4. Synchronize with Airtable Cloud Base (Dual-Storage mode)
            airtable_rec_id = None
            if self.airtable and self.airtable.is_configured():
                try:
                    at_res = self.airtable.upsert_project(
                        project_name=input_data.project_name.strip(),
                        description=input_data.description.strip(),
                        requirements=input_data.requirements,
                        additional_info=input_data.additional_info,
                        markdown_path=input_data.markdown_path,
                        version=new_version,
                        status="active",
                        workflow_run_id=input_data.workflow_run_id
                    )
                    if at_res.get("success"):
                        airtable_rec_id = at_res.get("airtable_record_id")
                        logger.info(f"Agent 2: Synchronized project to Airtable (ID: {airtable_rec_id})")
                except Exception as e:
                    logger.warning(f"Airtable cloud sync skipped/failed (non-blocking): {e}")

            return DatabaseOutput(
                status="success",
                record_id=record_id,
                airtable_record_id=airtable_rec_id,
                message=message,
                action=action,
                project_name=input_data.project_name.strip(),
                slug=slug,
                version=new_version,
                operation=operation,
                table="projects",
                success=True,
                error=None,
                timestamp=now_iso
            )

        except Exception as e:
            logger.error(f"Agent 2 database error: {e}", exc_info=True)
            return DatabaseOutput(
                status="failure",
                record_id=None,
                message=f"Database operation failed: {str(e)}",
                action="error",
                project_name=input_data.project_name if input_data else "",
                slug=slug if 'slug' in locals() else "",
                version=0,
                operation="Database execution failed",
                table="projects",
                success=False,
                error=str(e),
                timestamp=now_iso
            )

    def update_project(
        self,
        project_id: int,
        project_name: str,
        description: str,
        requirements: Union[List[str], str],
        additional_info: Optional[str] = "",
        markdown_path: Optional[str] = None,
        workflow_run_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> DatabaseOutput:
        """
        Update an existing project record safely in SQLite.
        Validates inputs, checks existence and name collision, increments version, and writes audit log.
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            validated = DatabaseInput(
                project_name=project_name,
                description=description,
                requirements=requirements,
                additional_info=additional_info or "",
                markdown_path=markdown_path or "",
                workflow_run_id=workflow_run_id
            )
        except Exception as e:
            logger.warning(f"Agent 2 update validation failed: {e}")
            return DatabaseOutput(
                status="failure",
                record_id=project_id,
                message=f"Validation failed: {str(e)}",
                action="none",
                project_name=str(project_name),
                operation="Validation failed",
                table="projects",
                success=False,
                error=str(e),
                timestamp=now_iso
            )

        existing = self.db.get_project_by_id(project_id)
        if not existing:
            msg = f"Project with ID #{project_id} not found."
            logger.warning(msg)
            return DatabaseOutput(
                status="failure",
                record_id=project_id,
                message=msg,
                action="none",
                project_name=validated.project_name,
                operation="Project not found",
                table="projects",
                success=False,
                error="Project not found",
                timestamp=now_iso
            )

        slug = self.slugify(validated.project_name)

        if isinstance(validated.requirements, list):
            reqs_json = json.dumps(validated.requirements)
        else:
            lines = [l.strip() for l in str(validated.requirements).split("\n") if l.strip()]
            reqs_json = json.dumps(lines if lines else [str(validated.requirements).strip()])

        try:
            updated = self.db.update_project(
                project_id=project_id,
                project_name=validated.project_name,
                slug=slug,
                description=validated.description,
                requirements=reqs_json,
                additional_info=validated.additional_info,
                markdown_path=markdown_path or existing.get("markdown_path"),
                status=status
            )
            if not updated:
                return DatabaseOutput(
                    status="failure",
                    record_id=project_id,
                    message=f"Failed to update project #{project_id}.",
                    action="none",
                    success=False,
                    error="Update failed",
                    timestamp=now_iso
                )

            # Record audit run
            run_id = workflow_run_id or f"wf_upd_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.db.insert_workflow_run(
                workflow_run_id=run_id,
                project_id=project_id,
                project_name=validated.project_name,
                agent_name="agent2_database",
                action="updated",
                status="success",
                details=json.dumps({
                    "version": updated["version"],
                    "slug": slug,
                    "markdown_path": updated.get("markdown_path")
                })
            )

            new_version = updated.get("version", existing.get("version", 1) + 1)
            operation = f"Updated project record ID #{project_id} to revision v{new_version}"
            message = f"Successfully updated project '{validated.project_name}' (ID #{project_id}) to revision v{new_version}."
            logger.info(f"Agent 2: {operation}")

            # Synchronize with Airtable
            airtable_rec_id = None
            if self.airtable and self.airtable.is_configured():
                try:
                    at_res = self.airtable.upsert_project(
                        project_name=validated.project_name.strip(),
                        description=validated.description.strip(),
                        requirements=validated.requirements,
                        additional_info=validated.additional_info,
                        markdown_path=markdown_path or existing.get("markdown_path"),
                        version=new_version,
                        status=status or existing.get("status", "active"),
                        workflow_run_id=workflow_run_id
                    )
                    if at_res.get("success"):
                        airtable_rec_id = at_res.get("airtable_record_id")
                except Exception as e:
                    logger.warning(f"Airtable update sync skipped/failed: {e}")

            return DatabaseOutput(
                status="success",
                record_id=project_id,
                airtable_record_id=airtable_rec_id,
                message=message,
                action="updated",
                project_name=validated.project_name,
                slug=slug,
                version=new_version,
                operation=operation,
                table="projects",
                success=True,
                error=None,
                timestamp=now_iso
            )
        except Exception as e:
            logger.error(f"Agent 2 error updating project #{project_id}: {e}", exc_info=True)
            return DatabaseOutput(
                status="failure",
                record_id=project_id,
                message=f"Database update failed: {str(e)}",
                action="error",
                project_name=validated.project_name,
                slug=slug,
                version=existing.get("version", 1),
                operation="Update failed",
                table="projects",
                success=False,
                error=str(e),
                timestamp=now_iso
            )

    def archive_project(self, project_id: int, workflow_run_id: Optional[str] = None) -> DatabaseOutput:
        """Soft delete: mark project as archived in SQLite."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        existing = self.db.get_project_by_id(project_id)
        if not existing:
            msg = f"Project with ID #{project_id} not found."
            logger.warning(msg)
            return DatabaseOutput(
                status="failure",
                record_id=project_id,
                message=msg,
                action="none",
                operation="Project not found",
                table="projects",
                success=False,
                error="Project not found",
                timestamp=now_iso
            )

        try:
            archived = self.db.archive_project(project_id)
            run_id = workflow_run_id or f"wf_arch_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.db.insert_workflow_run(
                workflow_run_id=run_id,
                project_id=project_id,
                project_name=existing["project_name"],
                agent_name="agent2_database",
                action="archived",
                status="success",
                details=json.dumps({"status": "archived"})
            )

            # Sync archive to Airtable
            if self.airtable and self.airtable.is_configured():
                try:
                    self.airtable.archive_project(existing["project_name"])
                except Exception as e:
                    logger.warning(f"Airtable archive skipped/failed: {e}")

            return DatabaseOutput(
                status="success",
                record_id=project_id,
                message=f"Project '{existing['project_name']}' (ID #{project_id}) has been archived.",
                action="archived",
                project_name=existing["project_name"],
                slug=existing["slug"],
                version=existing.get("version", 1),
                operation=f"Archived project record ID #{project_id}",
                table="projects",
                success=True,
                error=None,
                timestamp=now_iso
            )
        except Exception as e:
            logger.error(f"Agent 2 error archiving project #{project_id}: {e}", exc_info=True)
            return DatabaseOutput(
                status="failure",
                record_id=project_id,
                message=f"Database archive failed: {str(e)}",
                action="error",
                project_name=existing["project_name"],
                table="projects",
                success=False,
                error=str(e),
                timestamp=now_iso
            )

    def delete_project(self, project_id: int, permanent: bool = False, workflow_run_id: Optional[str] = None) -> DatabaseOutput:
        """Delete project: soft delete (archive) or hard delete if permanent=True."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        existing = self.db.get_project_by_id(project_id)
        if not existing:
            msg = f"Project with ID #{project_id} not found."
            logger.warning(msg)
            return DatabaseOutput(
                status="failure",
                record_id=project_id,
                message=msg,
                action="none",
                operation="Project not found",
                table="projects",
                success=False,
                error="Project not found",
                timestamp=now_iso
            )

        if not permanent:
            return self.archive_project(project_id, workflow_run_id)

        try:
            self.db.delete_project(project_id, permanent=True)
            logger.info(f"Agent 2: Project #{project_id} ('{existing['project_name']}') permanently deleted.")

            # Sync permanent delete to Airtable
            if self.airtable and self.airtable.is_configured():
                try:
                    self.airtable.delete_project(existing["project_name"])
                except Exception as e:
                    logger.warning(f"Airtable permanent delete skipped/failed: {e}")

            return DatabaseOutput(
                status="success",
                record_id=project_id,
                message=f"Project '{existing['project_name']}' (ID #{project_id}) has been permanently deleted.",
                action="deleted",
                project_name=existing["project_name"],
                slug=existing["slug"],
                version=existing.get("version", 1),
                operation=f"Permanently deleted project record ID #{project_id}",
                table="projects",
                success=True,
                error=None,
                timestamp=now_iso
            )
        except Exception as e:
            logger.error(f"Agent 2 error deleting project #{project_id}: {e}", exc_info=True)
            return DatabaseOutput(
                status="failure",
                record_id=project_id,
                message=f"Database delete failed: {str(e)}",
                action="error",
                project_name=existing["project_name"],
                table="projects",
                success=False,
                error=str(e),
                timestamp=now_iso
            )

    def clear_airtable_data(self) -> Dict[str, Any]:
        """Completely wipe all records from the Airtable base, leaving schema and field labels intact."""
        if not self.airtable or not self.airtable.is_configured():
            return {
                "success": False,
                "deleted_count": 0,
                "message": "Airtable sync is not configured or disabled in .env."
            }
        return self.airtable.clear_all_records()
