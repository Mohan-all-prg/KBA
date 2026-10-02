from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field

class MarkdownInput(BaseModel):
    """Input payload for Agent 1 (Markdown Agent)."""
    project_name: str = Field(default="", description="Name of the project or task")
    description: str = Field(default="", description="Detailed description of the project")
    requirements: Union[List[str], str] = Field(default="", description="Requirements list or string")
    additional_info: Optional[str] = Field(default="", description="Additional notes or constraints")
    workflow_run_id: Optional[str] = Field(default=None, description="Optional workflow tracking ID")

class MarkdownOutput(BaseModel):
    """
    Output payload returned by Agent 1 (Markdown Agent).
    Conforms to required specification:
    {
      "status": "success/failure",
      "file_path": "...",
      "summary": "..."
    }
    """
    status: str = Field(..., description="'success' or 'failure'")
    file_path: str = Field(..., description="Path to the created or updated markdown file")
    summary: str = Field(..., description="Human-readable summary of the action performed")
    action: str = Field(default="created", description="'created' or 'updated' or 'none'")
    relative_path: Optional[str] = Field(default="", description="Workspace-relative path to markdown file")
    file_name: Optional[str] = Field(default="", description="File name of the markdown file")
    version: int = Field(default=1, description="Revision version counter")
    char_count: int = Field(default=0, description="Total characters written")
    success: bool = Field(default=True, description="Boolean success flag")
    error: Optional[str] = Field(default=None, description="Error message if operation failed")

    def to_dict(self) -> Dict[str, Any]:
        """Return the exact primary dictionary requested by user specification."""
        return {
            "status": self.status,
            "file_path": self.file_path,
            "summary": self.summary
        }
