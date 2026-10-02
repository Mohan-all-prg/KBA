import uuid
import datetime
from typing import Dict, Any, List, Optional
from config.logging_config import get_logger
from orchestrator.models import SubmissionRequest, ProjectUpdateRequest, WorkflowResponse
from agents.agent1_markdown import MarkdownAgent, MarkdownInput, MarkdownOutput
from agents.agent2_database import DatabaseAgent, DatabaseInput, DatabaseOutput
from agents.agent3_documentation import DocumentationAgent, DocumentationInput, DocumentationOutput

logger = get_logger("orchestrator")

class WorkflowOrchestrator:
    """
    Main Orchestrator Agent.
    Coordinates sequential execution of Agent 1, Agent 2, and Agent 3,
    validates input, and compiles the final unified response.
    """

    def __init__(
        self,
        markdown_agent: Optional[MarkdownAgent] = None,
        database_agent: Optional[DatabaseAgent] = None,
        documentation_agent: Optional[DocumentationAgent] = None
    ):
        self.agent1 = markdown_agent or MarkdownAgent()
        self.agent2 = database_agent or DatabaseAgent()
        self.agent3 = documentation_agent or DocumentationAgent()

    @staticmethod
    def generate_workflow_id() -> str:
        """Generate a distinct workflow run identifier."""
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        rand = uuid.uuid4().hex[:6]
        return f"wf_{ts}_{rand}"

    def run(self, request: SubmissionRequest) -> WorkflowResponse:
        """
        Execute the end-to-end multi-agent workflow.
        """
        workflow_id = self.generate_workflow_id()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        logger.info(f"[{workflow_id}] Starting workflow execution for: '{request.project_name}'")

        errors: List[str] = []

        # Step 1: Input Validation
        if not request.project_name or len(request.project_name.strip()) < 2:
            msg = "Validation Error: 'project_name' must be at least 2 characters."
            logger.error(f"[{workflow_id}] {msg}")
            return self._build_failure_response(workflow_id, msg, now_iso)

        if not request.description or len(request.description.strip()) < 5:
            msg = "Validation Error: 'description' must be at least 5 characters."
            logger.error(f"[{workflow_id}] {msg}")
            return self._build_failure_response(workflow_id, msg, now_iso)

        # Step 2: Agent 1 - Markdown Agent
        logger.info(f"[{workflow_id}] Step 1/3: Invoking Agent 1 (Markdown Agent)...")
        agent1_input = MarkdownInput(
            project_name=request.project_name,
            description=request.description,
            requirements=request.requirements,
            additional_info=request.additional_info,
            workflow_run_id=workflow_id
        )
        agent1_output: MarkdownOutput = self.agent1.process(agent1_input)
        if not agent1_output.success:
            err_msg = f"Agent 1 Error: {agent1_output.error}"
            errors.append(err_msg)
            logger.error(f"[{workflow_id}] Agent 1 failed: {agent1_output.error}. Aborting workflow to protect database integrity.")
            return WorkflowResponse(
                workflow_run_id=workflow_id,
                overall_status="failed",
                markdown_status=agent1_output.action or "error",
                markdown_file_path=agent1_output.file_path or "",
                markdown_summary=f"Agent 1 failed: {agent1_output.error}",
                database_status="not_run",
                database_record_id=None,
                database_operation="Aborted: Agent 1 failed; database operation skipped.",
                documentation_status="not_run",
                documentation_file_path="",
                documentation_summary="Workflow aborted: Documentation generation skipped.",
                agent_details={"agent1": agent1_output.model_dump()},
                errors=errors,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
            )

        # Step 3: Agent 2 - Database Agent
        logger.info(f"[{workflow_id}] Step 2/3: Invoking Agent 2 (Database Agent)...")
        agent2_input = DatabaseInput(
            project_name=request.project_name,
            description=request.description,
            requirements=request.requirements,
            additional_info=request.additional_info,
            markdown_path=agent1_output.file_path if agent1_output.success else "",
            workflow_run_id=workflow_id
        )
        agent2_output: DatabaseOutput = self.agent2.process(agent2_input)
        if not agent2_output.success:
            err_msg = f"Agent 2 Error: {agent2_output.error}"
            errors.append(err_msg)
            logger.error(f"[{workflow_id}] Agent 2 failed: {agent2_output.error}. Aborting workflow.")
            return WorkflowResponse(
                workflow_run_id=workflow_id,
                overall_status="failed",
                markdown_status=agent1_output.action,
                markdown_file_path=agent1_output.file_path,
                markdown_summary=agent1_output.summary,
                database_status=agent2_output.action or "error",
                database_record_id=None,
                database_operation=agent2_output.operation or "Database operation failed",
                documentation_status="not_run",
                documentation_file_path="",
                documentation_summary="Workflow aborted: Documentation generation skipped due to database failure.",
                agent_details={
                    "agent1": agent1_output.model_dump(),
                    "agent2": agent2_output.model_dump()
                },
                errors=errors,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
            )

        # Step 4: Agent 3 - Documentation Agent
        logger.info(f"[{workflow_id}] Step 3/3: Invoking Agent 3 (Documentation Agent)...")
        agent3_input = DocumentationInput(
            project_name=request.project_name,
            description=request.description,
            requirements=request.requirements,
            additional_info=request.additional_info,
            markdown_result=agent1_output.model_dump(),
            database_result=agent2_output.model_dump(),
            workflow_run_id=workflow_id
        )
        agent3_output: DocumentationOutput = self.agent3.process(agent3_input)
        if not agent3_output.success:
            errors.append(f"Agent 3 Error: {agent3_output.error}")
            logger.error(f"[{workflow_id}] Agent 3 failed: {agent3_output.error}")

        # Step 5: Determine overall status
        if not errors:
            overall_status = "success"
        else:
            overall_status = "partial_success"

        logger.info(
            f"[{workflow_id}] Multi-agent workflow completed with status '{overall_status}'. "
            f"Markdown: {agent1_output.status}, Database: {agent2_output.status} (ID #{agent2_output.record_id}), "
            f"Documentation: {agent3_output.status}"
        )

        return WorkflowResponse(
            workflow_run_id=workflow_id,
            overall_status=overall_status,
            markdown_status=agent1_output.action,
            markdown_file_path=agent1_output.file_path,
            markdown_summary=agent1_output.summary,
            database_status=agent2_output.action,
            database_record_id=agent2_output.record_id,
            database_operation=agent2_output.operation,
            documentation_status=agent3_output.action,
            documentation_file_path=agent3_output.doc_file_path,
            documentation_summary=agent3_output.summary,
            agent_details={
                "agent1": agent1_output.model_dump(),
                "agent2": agent2_output.model_dump(),
                "agent3": agent3_output.model_dump()
            },
            errors=errors if errors else None,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )

    def update_project(self, project_id: int, request: ProjectUpdateRequest) -> WorkflowResponse:
        """
        Coordinates full project update workflow:
        1. Verifies project exists in database.
        2. Resolves updated values merged with current values.
        3. Re-runs Agent 1 (Markdown) to regenerate markdown.
        4. Re-runs Agent 2 (Database) to update record and increment version.
        5. Re-runs Agent 3 (Documentation) to synchronize documentation.
        """
        workflow_id = f"wf_upd_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        logger.info(f"[{workflow_id}] Starting update workflow for project ID #{project_id}")

        existing = self.agent2.db.get_project_by_id(project_id)
        if not existing:
            msg = f"Project with ID #{project_id} not found."
            logger.error(f"[{workflow_id}] {msg}")
            return self._build_failure_response(workflow_id, msg, now_iso)

        # Merge fields
        new_name = request.project_name if request.project_name is not None else existing["project_name"]
        new_desc = request.description if request.description is not None else existing["description"]
        new_reqs = request.requirements if request.requirements is not None else existing["requirements"]
        new_info = request.additional_info if request.additional_info is not None else (existing.get("additional_info") or "")

        errors: List[str] = []

        # Step 1: Agent 1 (Markdown Agent)
        logger.info(f"[{workflow_id}] Step 1/3: Updating Markdown via Agent 1...")
        agent1_input = MarkdownInput(
            project_name=new_name,
            description=new_desc,
            requirements=new_reqs,
            additional_info=new_info,
            workflow_run_id=workflow_id
        )
        agent1_output: MarkdownOutput = self.agent1.process(agent1_input)
        if not agent1_output.success:
            err_msg = f"Agent 1 Error: {agent1_output.error}"
            errors.append(err_msg)
            logger.error(f"[{workflow_id}] Agent 1 failed: {agent1_output.error}. Aborting update workflow.")
            return WorkflowResponse(
                workflow_run_id=workflow_id,
                overall_status="failed",
                markdown_status=agent1_output.action or "error",
                markdown_file_path=agent1_output.file_path or "",
                markdown_summary=f"Agent 1 failed: {agent1_output.error}",
                database_status="not_run",
                database_record_id=project_id,
                database_operation="Aborted: Agent 1 failed; database update skipped.",
                documentation_status="not_run",
                documentation_file_path="",
                documentation_summary="Workflow aborted: Documentation generation skipped.",
                agent_details={"agent1": agent1_output.model_dump()},
                errors=errors,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
            )

        # Step 2: Agent 2 (Database Agent)
        logger.info(f"[{workflow_id}] Step 2/3: Updating Database via Agent 2...")
        agent2_output: DatabaseOutput = self.agent2.update_project(
            project_id=project_id,
            project_name=new_name,
            description=new_desc,
            requirements=new_reqs,
            additional_info=new_info,
            markdown_path=agent1_output.file_path if agent1_output.success else existing.get("markdown_path"),
            workflow_run_id=workflow_id,
            status=request.status
        )
        if not agent2_output.success:
            err_msg = f"Agent 2 Error: {agent2_output.error}"
            errors.append(err_msg)
            logger.error(f"[{workflow_id}] Agent 2 failed: {agent2_output.error}. Aborting update workflow.")
            return WorkflowResponse(
                workflow_run_id=workflow_id,
                overall_status="failed",
                markdown_status=agent1_output.action,
                markdown_file_path=agent1_output.file_path,
                markdown_summary=agent1_output.summary,
                database_status=agent2_output.action or "error",
                database_record_id=project_id,
                database_operation=agent2_output.operation or "Database update failed",
                documentation_status="not_run",
                documentation_file_path="",
                documentation_summary="Workflow aborted: Documentation synchronization skipped due to database failure.",
                agent_details={
                    "agent1": agent1_output.model_dump(),
                    "agent2": agent2_output.model_dump()
                },
                errors=errors,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
            )

        # Step 3: Agent 3 (Documentation Agent)
        logger.info(f"[{workflow_id}] Step 3/3: Synchronizing Documentation via Agent 3...")
        agent3_input = DocumentationInput(
            project_name=new_name,
            description=new_desc,
            requirements=new_reqs,
            additional_info=new_info,
            markdown_result=agent1_output.model_dump(),
            database_result=agent2_output.model_dump(),
            workflow_run_id=workflow_id
        )
        agent3_output: DocumentationOutput = self.agent3.process(agent3_input)
        if not agent3_output.success:
            errors.append(f"Agent 3 Error: {agent3_output.error}")
            logger.error(f"[{workflow_id}] Agent 3 failed: {agent3_output.error}")

        # Determine overall status
        if not errors:
            overall_status = "success"
        else:
            overall_status = "partial_success"

        logger.info(f"[{workflow_id}] Project #{project_id} update completed with status '{overall_status}'.")

        return WorkflowResponse(
            workflow_run_id=workflow_id,
            overall_status=overall_status,
            markdown_status=agent1_output.action,
            markdown_file_path=agent1_output.file_path,
            markdown_summary=agent1_output.summary,
            database_status=agent2_output.action,
            database_record_id=agent2_output.record_id,
            database_operation=agent2_output.operation,
            documentation_status=agent3_output.action,
            documentation_file_path=agent3_output.doc_file_path,
            documentation_summary=agent3_output.summary,
            agent_details={
                "agent1": agent1_output.model_dump(),
                "agent2": agent2_output.model_dump(),
                "agent3": agent3_output.model_dump()
            },
            errors=errors if errors else None,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )

    def delete_project(self, project_id: int, permanent: bool = False) -> Dict[str, Any]:
        """Delegate deletion (soft/hard) to Agent 2."""
        workflow_id = f"wf_del_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        out = self.agent2.delete_project(project_id, permanent=permanent, workflow_run_id=workflow_id)
        return out.model_dump()

    def _build_failure_response(self, workflow_id: str, error_msg: str, timestamp: str) -> WorkflowResponse:
        """Helper to construct standard failure response for input validation errors."""
        return WorkflowResponse(
            workflow_run_id=workflow_id,
            overall_status="failed",
            markdown_status="not_run",
            markdown_file_path="",
            markdown_summary="Workflow aborted due to input validation error.",
            database_status="not_run",
            database_record_id=None,
            database_operation="Aborted",
            documentation_status="not_run",
            documentation_file_path="",
            documentation_summary="Workflow aborted.",
            agent_details=None,
            errors=[error_msg],
            timestamp=timestamp
        )

# Global orchestrator instance
orchestrator = WorkflowOrchestrator()
