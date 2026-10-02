import re
from typing import Optional, Union, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

def _validate_strict_string(
    field_name: str,
    value: Any,
    min_len: int,
    max_len: int,
    required: bool = True,
    require_meaningful: bool = True
) -> str:
    """
    Strictly validates that value is a string, rejecting numbers, booleans,
    nulls, arrays, and objects without silent type coercion.
    Strips whitespace, enforces length boundaries, and rejects meaningless gibberish/spam.
    """
    if value is None:
        if required:
            raise ValueError(f"'{field_name}' is required and cannot be null.")
        return ""

    # In Python, bool is a subclass of int, so check bool explicitly first
    if isinstance(value, bool):
        raise ValueError(f"'{field_name}' must be a string, received boolean.")

    if not isinstance(value, str):
        raise ValueError(f"'{field_name}' must be a string, received {type(value).__name__}.")

    stripped = value.strip()
    if required and len(stripped) == 0:
        raise ValueError(f"'{field_name}' cannot be empty or contain only whitespace.")

    if required and len(stripped) < min_len:
        raise ValueError(f"'{field_name}' must be at least {min_len} characters (currently {len(stripped)}).")

    if len(stripped) > max_len:
        raise ValueError(f"'{field_name}' exceeds maximum allowed length of {max_len} characters (currently {len(stripped)}).")

    if require_meaningful and stripped:
        letters = re.findall(r'[a-zA-Z]', stripped)
        if len(letters) < 2:
            raise ValueError(f"'{field_name}' must contain meaningful text with letters, not purely numbers or symbols.")
        if re.search(r'(.)\1{4,}', stripped):
            raise ValueError(f"'{field_name}' contains excessive repetitive characters and appears invalid.")
        alnum = [c.lower() for c in stripped if c.isalnum()]
        if len(alnum) >= 6 and len(set(alnum)) < 3:
            raise ValueError(f"'{field_name}' lacks sufficient character variety and appears to be meaningless spam.")

    return stripped

class SubmissionRequest(BaseModel):
    """User input payload submitted via Entry Form or API."""
    project_name: str = Field(..., description="Project or task name (2-120 chars)")
    description: str = Field(..., description="Project description (5-5000 chars)")
    requirements: Union[str, List[str]] = Field(..., description="Project requirements (5-5000 chars)")
    additional_info: Optional[str] = Field(default="", description="Additional context or notes (max 3000 chars)")

    @field_validator("project_name", mode="before")
    @classmethod
    def validate_name(cls, v: Any) -> str:
        return _validate_strict_string("project_name", v, min_len=2, max_len=120, required=True, require_meaningful=True)

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, v: Any) -> str:
        return _validate_strict_string("description", v, min_len=5, max_len=5000, required=True, require_meaningful=True)

    @field_validator("requirements", mode="before")
    @classmethod
    def validate_requirements(cls, v: Any) -> str:
        if v is None:
            raise ValueError("'requirements' is required and cannot be null.")
        if isinstance(v, bool):
            raise ValueError("'requirements' must be a string, received boolean.")
        if isinstance(v, (int, float, dict)):
            raise ValueError(f"'requirements' must be a string, received {type(v).__name__}.")
        if isinstance(v, list):
            # If a list is submitted, ensure every item is a valid string
            if len(v) == 0:
                raise ValueError("'requirements' list cannot be empty.")
            cleaned_items = []
            for idx, item in enumerate(v):
                if not isinstance(item, str) or isinstance(item, bool):
                    raise ValueError(f"Requirement item at index {idx} must be a string, received {type(item).__name__}.")
                item_str = item.strip()
                if item_str:
                    _validate_strict_string(f"Requirement item at index {idx}", item_str, min_len=2, max_len=1000, required=True, require_meaningful=True)
                    cleaned_items.append(item_str)
            if not cleaned_items:
                raise ValueError("'requirements' cannot be empty or contain only whitespace.")
            v_str = "\n".join(cleaned_items)
            return _validate_strict_string("requirements", v_str, min_len=5, max_len=5000, required=True, require_meaningful=True)

        return _validate_strict_string("requirements", v, min_len=5, max_len=5000, required=True, require_meaningful=True)

    @field_validator("additional_info", mode="before")
    @classmethod
    def validate_additional_info(cls, v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, bool):
            raise ValueError("'additional_info' must be a string if provided, received boolean.")
        if not isinstance(v, str):
            raise ValueError(f"'additional_info' must be a string if provided, received {type(v).__name__}.")
        stripped = v.strip()
        if len(stripped) > 3000:
            raise ValueError(f"'additional_info' exceeds maximum length of 3000 characters (currently {len(stripped)}).")
        if stripped:
            if re.search(r'(.)\1{4,}', stripped):
                raise ValueError("'additional_info' contains excessive repetitive characters and appears invalid.")
            if len(stripped) >= 5 and len(re.findall(r'[a-zA-Z]', stripped)) < 2:
                raise ValueError("'additional_info' must contain meaningful text if provided.")
        return stripped

class ProjectUpdateRequest(BaseModel):
    """Payload for editing/updating an existing project."""
    project_name: Optional[str] = Field(default=None, description="Updated project name")
    description: Optional[str] = Field(default=None, description="Updated description")
    requirements: Optional[Union[str, List[str]]] = Field(default=None, description="Updated requirements")
    additional_info: Optional[str] = Field(default=None, description="Updated additional info")
    status: Optional[str] = Field(default=None, description="Updated status ('active', 'archived')")

    @field_validator("project_name", mode="before")
    @classmethod
    def validate_name(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return _validate_strict_string("project_name", v, min_len=2, max_len=120, required=True, require_meaningful=True)

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return _validate_strict_string("description", v, min_len=5, max_len=5000, required=True, require_meaningful=True)

    @field_validator("requirements", mode="before")
    @classmethod
    def validate_requirements(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, bool):
            raise ValueError("'requirements' must be a string, received boolean.")
        if isinstance(v, (int, float, dict)):
            raise ValueError(f"'requirements' must be a string, received {type(v).__name__}.")
        if isinstance(v, list):
            if len(v) == 0:
                raise ValueError("'requirements' list cannot be empty.")
            cleaned_items = []
            for idx, item in enumerate(v):
                if not isinstance(item, str) or isinstance(item, bool):
                    raise ValueError(f"Requirement item at index {idx} must be a string, received {type(item).__name__}.")
                item_str = item.strip()
                if item_str:
                    _validate_strict_string(f"Requirement item at index {idx}", item_str, min_len=2, max_len=1000, required=True, require_meaningful=True)
                    cleaned_items.append(item_str)
            if not cleaned_items:
                raise ValueError("'requirements' cannot be empty or contain only whitespace.")
            v_str = "\n".join(cleaned_items)
            return _validate_strict_string("requirements", v_str, min_len=5, max_len=5000, required=True, require_meaningful=True)

        return _validate_strict_string("requirements", v, min_len=5, max_len=5000, required=True, require_meaningful=True)

    @field_validator("additional_info", mode="before")
    @classmethod
    def validate_additional_info(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, bool):
            raise ValueError("'additional_info' must be a string if provided, received boolean.")
        if not isinstance(v, str):
            raise ValueError(f"'additional_info' must be a string if provided, received {type(v).__name__}.")
        stripped = v.strip()
        if len(stripped) > 3000:
            raise ValueError(f"'additional_info' exceeds maximum length of 3000 characters (currently {len(stripped)}).")
        if stripped:
            if re.search(r'(.)\1{4,}', stripped):
                raise ValueError("'additional_info' contains excessive repetitive characters and appears invalid.")
            if len(stripped) >= 5 and len(re.findall(r'[a-zA-Z]', stripped)) < 2:
                raise ValueError("'additional_info' must contain meaningful text if provided.")
        return stripped

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, bool):
            raise ValueError("'status' must be a string, received boolean.")
        if not isinstance(v, str):
            raise ValueError(f"'status' must be a string, received {type(v).__name__}.")
        s = v.strip().lower()
        if s not in ("active", "archived", "completed"):
            raise ValueError(f"Invalid status '{v}'. Allowed values: 'active', 'archived', 'completed'.")
        return s

class WorkflowResponse(BaseModel):
    """Final unified response returned after all 3 agents have completed processing."""
    workflow_run_id: str = Field(..., description="Unique tracking identifier for this workflow run")
    overall_status: str = Field(..., description="'success', 'partial_success', or 'failed'")
    
    # Agent 1 (Markdown) results
    markdown_status: str = Field(..., description="Status of markdown operation ('created', 'updated', 'error')")
    markdown_file_path: str = Field(..., description="File path of the created/updated Markdown file")
    markdown_summary: str = Field(..., description="Summary from Agent 1")
    
    # Agent 2 (Database) results
    database_status: str = Field(..., description="Status of database operation ('inserted', 'updated', 'error')")
    database_record_id: Optional[int] = Field(default=None, description="Database record ID")
    database_operation: str = Field(default="", description="Description of database action")
    
    # Agent 3 (Documentation) results
    documentation_status: str = Field(..., description="Status of documentation operation ('created', 'updated', 'error')")
    documentation_file_path: str = Field(..., description="File path of generated documentation")
    documentation_summary: str = Field(..., description="Summary from Agent 3")

    # Detailed agent metadata for inspection/debugging
    agent_details: Optional[Dict[str, Any]] = Field(default=None, description="Detailed payloads from all agents")
    errors: Optional[List[str]] = Field(default=None, description="List of any errors encountered")
    timestamp: str = Field(..., description="Completion timestamp")
