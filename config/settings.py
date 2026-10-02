import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if present
load_dotenv(BASE_DIR / ".env")

# Server settings
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

# Database settings
_db_env = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PATH") or str(BASE_DIR / "database" / "projects.db")
if _db_env.startswith("sqlite:///"):
    _db_env = _db_env.replace("sqlite:///", "")
DATABASE_PATH = Path(_db_env)
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = BASE_DIR / DATABASE_PATH

# Storage directories
MARKDOWN_OUTPUT_DIR = Path(os.getenv("MARKDOWN_OUTPUT_DIR", str(BASE_DIR / "output" / "markdown")))
DOCS_DIR = Path(os.getenv("DOCS_DIR", str(BASE_DIR / "docs")))
DOCS_PROJECTS_DIR = DOCS_DIR / "projects"
FRONTEND_DIR = BASE_DIR / "frontend" / "entry-form"

# MCP settings
MCP_SERVER_NAME = os.getenv("MCP_SERVER_NAME", "multi-agent-workflow-server")
MCP_ENABLED = os.getenv("MCP_ENABLED", "True").lower() in ("true", "1", "yes")

# Airtable Cloud Sync Settings
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "tblf6e5PZVACQy2ZC")
AIRTABLE_ENABLED = os.getenv("AIRTABLE_ENABLED", "True").lower() in ("true", "1", "yes")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Ensure required directories exist
MARKDOWN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)
DOCS_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
