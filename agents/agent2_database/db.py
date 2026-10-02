import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
from config.settings import DATABASE_PATH, BASE_DIR
from config.logging_config import get_logger

logger = get_logger("agent.database.db")

class DatabaseManager:
    """Manages SQLite connection, schema lifecycle, and queries."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or DATABASE_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Create and return a configured SQLite connection with foreign keys and Row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def init_db(self) -> None:
        """Ensure database schema is created from schema.sql."""
        schema_file = BASE_DIR / "database" / "schema.sql"
        try:
            with self.get_connection() as conn:
                if schema_file.exists():
                    schema_sql = schema_file.read_text(encoding="utf-8")
                    conn.executescript(schema_sql)
                    conn.commit()
                    logger.info(f"Database schema initialized successfully at {self.db_path}")
                else:
                    logger.warning(f"Schema file not found at {schema_file}. Creating fallback schema.")
                    conn.executescript("""
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
                        CREATE TABLE IF NOT EXISTS workflow_runs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            workflow_run_id TEXT NOT NULL,
                            project_id INTEGER,
                            project_name TEXT NOT NULL,
                            agent_name TEXT NOT NULL,
                            action TEXT NOT NULL,
                            status TEXT NOT NULL,
                            details TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                        );
                    """)
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            raise

    def get_project_by_id(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Look up project by its primary key ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ? LIMIT 1", (project_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_project_by_name_or_slug(self, project_name: str, slug: str) -> Optional[Dict[str, Any]]:
        """Look up project by name or slug."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM projects WHERE LOWER(project_name) = LOWER(?) OR slug = ? LIMIT 1",
                (project_name.strip(), slug)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_all_projects(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all stored projects sorted by updated_at descending, optionally filtered by status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status and status != "all":
                cursor.execute(
                    "SELECT * FROM projects WHERE status = ? ORDER BY updated_at DESC",
                    (status,)
                )
            else:
                cursor.execute("SELECT * FROM projects ORDER BY updated_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def update_project(
        self,
        project_id: int,
        project_name: str,
        slug: str,
        description: str,
        requirements: str,
        additional_info: Optional[str] = "",
        markdown_path: Optional[str] = None,
        status: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Atomically update an existing project record and increment its revision version.
        Checks for uniqueness collision against other project IDs.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Verify existence
            cursor.execute("SELECT * FROM projects WHERE id = ? LIMIT 1", (project_id,))
            existing = cursor.fetchone()
            if not existing:
                return None

            # 2. Check collision on name or slug with other records
            cursor.execute(
                "SELECT id FROM projects WHERE (LOWER(project_name) = LOWER(?) OR slug = ?) AND id != ? LIMIT 1",
                (project_name.strip(), slug, project_id)
            )
            collision = cursor.fetchone()
            if collision:
                raise ValueError(f"Another project already exists with name '{project_name}'.")

            # 3. Parameterized atomic update
            cursor.execute("""
                UPDATE projects
                SET project_name = ?,
                    slug = ?,
                    description = ?,
                    requirements = ?,
                    additional_info = ?,
                    markdown_path = COALESCE(?, markdown_path),
                    status = COALESCE(?, status),
                    version = version + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                project_name.strip(),
                slug,
                description.strip(),
                requirements,
                additional_info or "",
                markdown_path,
                status,
                project_id
            ))
            conn.commit()

            # Return updated row
            cursor.execute("SELECT * FROM projects WHERE id = ? LIMIT 1", (project_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def archive_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Soft delete: set project status to 'archived'."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ? LIMIT 1", (project_id,))
            existing = cursor.fetchone()
            if not existing:
                return None

            cursor.execute("""
                UPDATE projects
                SET status = 'archived',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (project_id,))
            conn.commit()

            cursor.execute("SELECT * FROM projects WHERE id = ? LIMIT 1", (project_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def restore_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Restore an archived project to 'active'."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ? LIMIT 1", (project_id,))
            existing = cursor.fetchone()
            if not existing:
                return None

            cursor.execute("""
                UPDATE projects
                SET status = 'active',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (project_id,))
            conn.commit()

            cursor.execute("SELECT * FROM projects WHERE id = ? LIMIT 1", (project_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_project(self, project_id: int, permanent: bool = False) -> bool:
        """
        Delete project. If permanent is False, soft delete (archive).
        If permanent is True, remove record completely (foreign keys cascade audit entries).
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM projects WHERE id = ? LIMIT 1", (project_id,))
            if not cursor.fetchone():
                return False

            if not permanent:
                cursor.execute("""
                    UPDATE projects
                    SET status = 'archived',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (project_id,))
                conn.commit()
                return True
            else:
                cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                conn.commit()
                return True

    def insert_workflow_run(
        self,
        workflow_run_id: str,
        project_id: Optional[int],
        project_name: str,
        agent_name: str,
        action: str,
        status: str,
        details: str
    ) -> int:
        """Record execution audit entry into workflow_runs table."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO workflow_runs (
                    workflow_run_id, project_id, project_name,
                    agent_name, action, status, details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                workflow_run_id,
                project_id,
                project_name,
                agent_name,
                action,
                status,
                details
            ))
            conn.commit()
            return cursor.lastrowid
