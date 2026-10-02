import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Dict, Any, List
from config.settings import AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, AIRTABLE_ENABLED
from config.logging_config import get_logger

logger = get_logger("agent.database.airtable")

class AirtableSyncManager:
    """
    Manages real-time cloud synchronization between Agent 2 (Database Agent)
    and an external Airtable Base.

    Operates in dual-storage mode:
    - Non-blocking and fault-tolerant: failure to reach Airtable never breaks the primary workflow.
    - Automatic typecasting for select/number/text fields.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_id: Optional[str] = None,
        table_name: Optional[str] = None,
        enabled: Optional[bool] = None
    ):
        self.api_key = api_key if api_key is not None else AIRTABLE_API_KEY
        self.base_id = base_id if base_id is not None else AIRTABLE_BASE_ID
        self.table_name = table_name if table_name is not None else AIRTABLE_TABLE_NAME
        self.enabled = enabled if enabled is not None else AIRTABLE_ENABLED

    def is_configured(self) -> bool:
        """Check if valid Airtable credentials are present and sync is enabled."""
        return bool(self.enabled and self.api_key and self.base_id and self.table_name)

    @property
    def base_url(self) -> str:
        safe_table = urllib.parse.quote(self.table_name, safe="")
        return f"https://api.airtable.com/v0/{self.base_id}/{safe_table}"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def find_record_by_name(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Find an existing Airtable record by Project Name."""
        if not self.is_configured():
            return None

        # Clean project name for formula
        escaped_name = project_name.replace("'", "\\'")
        formula = f"{{Project Name}}='{escaped_name}'"
        params = urllib.parse.urlencode({"filterByFormula": formula, "maxRecords": 1})
        url = f"{self.base_url}?{params}"

        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                records = data.get("records", [])
                return records[0] if records else None
        except Exception as e:
            logger.warning(f"Error querying Airtable for '{project_name}': {e}")
            return None

    def upsert_project(
        self,
        project_name: str,
        description: str,
        requirements: Any,
        additional_info: Optional[str] = "",
        markdown_path: Optional[str] = "",
        version: int = 1,
        status: str = "active",
        workflow_run_id: Optional[str] = ""
    ) -> Dict[str, Any]:
        """
        Create or update a project record in Airtable.
        """
        if not self.is_configured():
            return {"success": False, "reason": "Airtable sync not configured or disabled."}

        # Format requirements as clean multi-line string if list
        if isinstance(requirements, list):
            reqs_str = "\n".join(str(r) for r in requirements)
        else:
            reqs_str = str(requirements)

        fields = {
            "Project Name": project_name,
            "Description": description,
            "Requirements": reqs_str,
            "Additional Info": additional_info or "",
            "Status": status or "active",
            "Version": int(version or 1),
            "Markdown Path": markdown_path or "",
            "Workflow Run ID": workflow_run_id or ""
        }

        existing = self.find_record_by_name(project_name)

        if existing:
            # Update existing record
            record_id = existing["id"]
            url = f"{self.base_url}/{record_id}"
            payload = json.dumps({"fields": fields, "typecast": True}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers=self._headers(), method="PATCH")
            action = "updated"
        else:
            # Create new record
            url = self.base_url
            payload = json.dumps({
                "records": [{"fields": fields}],
                "typecast": True
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers=self._headers(), method="POST")
            action = "created"

        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                if action == "created":
                    rec_id = res_data.get("records", [{}])[0].get("id")
                else:
                    rec_id = res_data.get("id")

                logger.info(f"Airtable sync success: Project '{project_name}' {action} (Airtable ID: {rec_id})")
                return {
                    "success": True,
                    "action": action,
                    "airtable_record_id": rec_id,
                    "project_name": project_name
                }
        except Exception as e:
            logger.warning(f"Failed to sync project '{project_name}' to Airtable: {e}")
            return {"success": False, "error": str(e)}

    def archive_project(self, project_name: str) -> Dict[str, Any]:
        """Update an Airtable project's status to 'archived'."""
        if not self.is_configured():
            return {"success": False, "reason": "Airtable sync not configured."}

        existing = self.find_record_by_name(project_name)
        if not existing:
            return {"success": False, "reason": "Record not found in Airtable."}

        record_id = existing["id"]
        url = f"{self.base_url}/{record_id}"
        payload = json.dumps({"fields": {"Status": "archived"}, "typecast": True}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=self._headers(), method="PATCH")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"Airtable record '{record_id}' archived successfully.")
                return {"success": True, "action": "archived", "airtable_record_id": record_id}
        except Exception as e:
            logger.warning(f"Failed to archive Airtable project '{project_name}': {e}")
            return {"success": False, "error": str(e)}

    def delete_project(self, project_name: str) -> Dict[str, Any]:
        """Permanently delete an Airtable record by project name."""
        if not self.is_configured():
            return {"success": False, "reason": "Airtable sync not configured."}

        existing = self.find_record_by_name(project_name)
        if not existing:
            return {"success": False, "reason": "Record not found in Airtable."}

        record_id = existing["id"]
        url = f"{self.base_url}/{record_id}"
        req = urllib.request.Request(url, headers=self._headers(), method="DELETE")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"Airtable record '{record_id}' deleted successfully.")
                return {"success": True, "action": "deleted", "airtable_record_id": record_id}
        except Exception as e:
            logger.warning(f"Failed to delete Airtable project '{project_name}': {e}")
            return {"success": False, "error": str(e)}

    def list_projects(self, max_records: int = 100) -> List[Dict[str, Any]]:
        """Fetch all project records from Airtable."""
        if not self.is_configured():
            return []

        params = urllib.parse.urlencode({"maxRecords": max_records})
        url = f"{self.base_url}?{params}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                records = []
                for r in data.get("records", []):
                    fields = r.get("fields", {})
                    fields["airtable_id"] = r.get("id")
                    fields["created_time"] = r.get("createdTime")
                    records.append(fields)
                return records
        except Exception as e:
            logger.warning(f"Failed to list Airtable projects: {e}")
            return []

    def clear_all_records(self) -> Dict[str, Any]:
        """
        Delete all records from the Airtable base completely, clearing all data rows
        while leaving the table structure, column headers, and field labels completely intact.
        """
        if not self.is_configured():
            return {"success": False, "deleted_count": 0, "reason": "Airtable sync not configured or disabled."}

        # Step 1: Fetch all records using pagination
        record_ids = []
        offset = None
        while True:
            query_dict = {"pageSize": 100}
            if offset:
                query_dict["offset"] = offset
            params = urllib.parse.urlencode(query_dict)
            url = f"{self.base_url}?{params}"
            req = urllib.request.Request(url, headers=self._headers(), method="GET")
            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    records = data.get("records", [])
                    for r in records:
                        if "id" in r:
                            record_ids.append(r["id"])
                    offset = data.get("offset")
                    if not offset:
                        break
            except Exception as e:
                logger.error(f"Error fetching record IDs to clear Airtable: {e}")
                return {"success": False, "deleted_count": len(record_ids), "error": str(e)}

        if not record_ids:
            return {
                "success": True,
                "deleted_count": 0,
                "message": "Airtable table is already completely empty. All field labels and column definitions remain intact."
            }

        # Step 2: Delete in batches of up to 10 records (Airtable batch limit)
        deleted_count = 0
        batch_size = 10
        for i in range(0, len(record_ids), batch_size):
            chunk = record_ids[i:i + batch_size]
            query = [("records[]", rid) for rid in chunk]
            del_url = f"{self.base_url}?{urllib.parse.urlencode(query)}"
            del_req = urllib.request.Request(del_url, headers=self._headers(), method="DELETE")
            try:
                with urllib.request.urlopen(del_req, timeout=12) as resp:
                    del_data = json.loads(resp.read().decode("utf-8"))
                    deleted_count += len(del_data.get("records", chunk))
            except Exception as e:
                logger.warning(f"Batch delete failed on chunk {chunk}, attempting single record deletes: {e}")
                for rid in chunk:
                    single_url = f"{self.base_url}/{rid}"
                    s_req = urllib.request.Request(single_url, headers=self._headers(), method="DELETE")
                    try:
                        with urllib.request.urlopen(s_req, timeout=10) as s_resp:
                            deleted_count += 1
                    except Exception as se:
                        logger.error(f"Failed to delete record {rid}: {se}")

        logger.info(f"Airtable table cleared completely. Deleted {deleted_count} records. All field labels preserved.")
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Successfully deleted {deleted_count} records from Airtable. Table structure and column field labels remain intact."
        }

# Singleton instance
airtable_sync = AirtableSyncManager()
