from typing import Optional, Dict, Any, Union, List
from pydantic import BaseModel, Field

class DocumentationInput(BaseModel):
    """Input payload for Agent 3 (Documentation Agent)."""
    project_name: str = Field(default="", description="Project or task name")
    description: str = Field(default="", description="Description of the project")
    requirements: Any = Field(default="", description="Requirements list or text")
    additional_info: Optional[str] = Field(default="", description="Additional context or constraints")
    markdown_result: Dict[str, Any] = Field(default_factory=dict, description="Output from Agent 1 (Markdown Agent)")
    database_result: Dict[str, Any] = Field(default_factory=dict, description="Output from Agent 2 (Database Agent)")
    workflow_run_id: Optional[str] = Field(default=None, description="Workflow run ID")

class DocumentationOutput(BaseModel):
    """
    Output payload returned by Agent 3 (Documentation Agent).
    Conforms to required specification:
    {
      "status": "success/failure",
      "documentation_path": "...",
      "summary": "..."
    }
    """
    status: str = Field(..., description="'success' or 'failure'")
    documentation_path: str = Field(..., description="Path to generated project documentation file")
    summary: str = Field(..., description="Summary of documentation generated")
    doc_file_path: Optional[str] = Field(default="", description="Alias for documentation_path for compatibility")
    relative_doc_path: Optional[str] = Field(default="", description="Relative path to project doc")
    catalog_path: Optional[str] = Field(default="", description="Path to updated central project catalog")
    action: str = Field(default="created", description="'created', 'updated', or 'none'")
    success: bool = Field(default=True, description="Whether the documentation operation succeeded")
    error: Optional[str] = Field(default=None, description="Error message if failed")

    def __init__(self, **data: Any):
        super().__init__(**data)
        if not self.doc_file_path:
            self.doc_file_path = self.documentation_path

    def to_dict(self) -> Dict[str, Any]:
        """Return the exact primary dictionary requested by user specification."""
        return {
            "status": self.status,
            "documentation_path": self.documentation_path,
            "summary": self.summary
        }
