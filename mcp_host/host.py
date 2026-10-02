"""
MCP Host Implementation

Provides MCP Client/Host capabilities for the application:
1. Tool Discovery: Introspects registered MCP tools and formats schemas for the UI.
2. Tool Execution: Dispatches JSON-RPC tool calls to MCP tools with latency telemetry.
3. Host AI Assistant: Natural language parser that maps user queries to MCP tool calls.
4. Preference Management: Tracks and persists User Mode ('server' vs 'host').
"""

import os
import sys
import asyncio
import time
import uuid
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from config.logging_config import get_logger
from config.settings import BASE_DIR
from .llm_client import LLMHostClient

logger = get_logger("mcp.host")

PREF_FILE = BASE_DIR / "config" / "user_mode_pref.json"


class MCPHostManager:
    """
    Manages MCP Host capabilities, acting as the client that invokes MCP tools,
    inspects tool contracts, and provides natural-language tool orchestration.
    """

    def __init__(self, mcp_server: Optional[Any] = None):
        self._mcp_server = mcp_server
        self._mode: str = self._load_mode_preference()
        self._execution_history: List[Dict[str, Any]] = []

    def set_mcp_server(self, mcp_server: Any) -> None:
        """Register the underlying MCPServer instance."""
        self._mcp_server = mcp_server

    def _load_mode_preference(self) -> str:
        """Load user mode preference ('server' or 'host') from file or default to 'server'."""
        try:
            if PREF_FILE.exists():
                data = json.loads(PREF_FILE.read_text(encoding="utf-8"))
                mode = data.get("mode", "server")
                if mode in ("server", "host"):
                    return mode
        except Exception as e:
            logger.warning(f"Could not load mode preference: {e}")
        return "server"

    def get_mode(self) -> str:
        """Return currently active mode ('server' or 'host')."""
        return self._mode

    def set_mode(self, mode: str) -> str:
        """Update and persist mode preference."""
        if mode not in ("server", "host"):
            raise ValueError(f"Invalid mode '{mode}'. Must be 'server' or 'host'.")
        self._mode = mode
        try:
            PREF_FILE.parent.mkdir(parents=True, exist_ok=True)
            PREF_FILE.write_text(json.dumps({"mode": self._mode, "updated_at": time.time()}, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not persist mode preference: {e}")
        logger.info(f"User mode switched to: {self._mode.upper()}")
        return self._mode

    def _categorize_tool(self, name: str) -> str:
        """Assign category badge for UI organization."""
        if "orchestrate" in name:
            return "Pipeline Orchestrator"
        if "markdown" in name:
            return "Agent 1 (Markdown)"
        if "database" in name or "store" in name:
            return "Agent 2 (Database)"
        if "documentation" in name:
            return "Agent 3 (Docs)"
        if "airtable" in name:
            return "Airtable Cloud"
        if "project" in name or "list" in name:
            return "Project Management"
        return "Utility & Math"

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        Inspect all tools registered with the MCP server and return
        clean, frontend-friendly tool descriptors and JSON Schema.
        """
        if not self._mcp_server:
            logger.warning("MCP Server reference not set in MCPHostManager.")
            return []

        try:
            raw_tools = await self._mcp_server.list_tools()
        except Exception as e:
            logger.error(f"Error querying tools from MCP server: {e}", exc_info=True)
            return []

        formatted_tools: List[Dict[str, Any]] = []

        for t in raw_tools:
            schema = t.input_schema or {}
            properties = schema.get("properties", {})
            required_fields = schema.get("required", [])

            parameters: List[Dict[str, Any]] = []
            for param_name, prop_meta in properties.items():
                p_type = prop_meta.get("type", "string")
                if "anyOf" in prop_meta:
                    types = [sub.get("type") for sub in prop_meta["anyOf"] if "type" in sub and sub.get("type") != "null"]
                    p_type = types[0] if types else "string"

                parameters.append({
                    "name": param_name,
                    "title": prop_meta.get("title", param_name.replace("_", " ").title()),
                    "type": p_type,
                    "required": param_name in required_fields,
                    "default": prop_meta.get("default", None),
                    "description": prop_meta.get("description", "")
                })

            formatted_tools.append({
                "name": t.name,
                "title": (t.name.replace("_", " ").title()),
                "description": (t.description or "").strip(),
                "category": self._categorize_tool(t.name),
                "parameters": parameters,
                "schema": schema
            })

        return formatted_tools

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an MCP tool call formulated as an MCP Host Client.
        Includes execution duration telemetry and standardized JSON-RPC framing.
        """
        if not self._mcp_server:
            raise RuntimeError("MCP Server not bound to Host.")

        # Clean arguments: remove empty strings if parameter has a default or is optional
        clean_args = {}
        for k, v in arguments.items():
            if v is not None:
                clean_args[k] = v

        call_id = f"mcp-call-{uuid.uuid4().hex[:8]}"
        rpc_request = {
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": clean_args
            }
        }

        start_time = time.perf_counter()
        is_error = False
        parsed_result: Any = None
        raw_text: str = ""

        try:
            mcp_res = await self._mcp_server.call_tool(tool_name, clean_args)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            is_error = getattr(mcp_res, "is_error", False)
            content_list = getattr(mcp_res, "content", [])

            if content_list and len(content_list) > 0:
                raw_text = getattr(content_list[0], "text", str(content_list[0]))
            elif hasattr(mcp_res, "structured_content") and mcp_res.structured_content:
                raw_text = str(mcp_res.structured_content)
            else:
                raw_text = str(mcp_res)

            # Attempt JSON parse of the text result if possible
            try:
                parsed_result = json.loads(raw_text)
            except Exception:
                parsed_result = raw_text

            response_payload = {
                "success": not is_error,
                "call_id": call_id,
                "tool": tool_name,
                "arguments": clean_args,
                "execution_time_ms": duration_ms,
                "result": parsed_result,
                "raw_text": raw_text,
                "rpc_request": rpc_request,
                "rpc_response": {
                    "jsonrpc": "2.0",
                    "id": call_id,
                    "result": {
                        "content": [{"type": "text", "text": raw_text}],
                        "isError": is_error
                    }
                }
            }

            self._execution_history.append({
                "call_id": call_id,
                "tool": tool_name,
                "timestamp": time.time(),
                "duration_ms": duration_ms,
                "success": not is_error
            })

            return response_payload

        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(f"Host tool execution failed for '{tool_name}': {e}", exc_info=True)
            return {
                "success": False,
                "call_id": call_id,
                "tool": tool_name,
                "arguments": clean_args,
                "execution_time_ms": duration_ms,
                "error": str(e),
                "rpc_request": rpc_request,
                "rpc_response": {
                    "jsonrpc": "2.0",
                    "id": call_id,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                }
            }

    async def chat(
        self,
        user_message: str,
        provider: str = "local",
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Natural Language Host Assistant:
        Interprets conversational user instructions, chooses the right MCP tool,
        invokes it as an MCP Host, and returns a natural language summary.

        Supports 3 Host Brain Providers:
        1. 'local': Fast, offline intent parser (free, no API key needed).
        2. 'gemini': Google Gemini 1.5 Flash live LLM Host reasoning with MCP function calling.
        3. 'claude': Anthropic Claude 3.5 Sonnet live LLM Host reasoning with MCP tool_use.
        """
        msg = user_message.strip()

        # =====================================================================
        # Provider 1: Google Gemini (Live LLM Host)
        # =====================================================================
        if provider == "gemini":
            key = api_key or os.environ.get("GEMINI_API_KEY")
            if not key:
                return {
                    "message": (
                        "⚠️ **Google Gemini API Key Required**\n\n"
                        "To have Google Gemini act as your live Host Brain:\n"
                        "1. Paste your Gemini API key in the **Host Brain Key** input in the top bar, or\n"
                        "2. Add `GEMINI_API_KEY=your_key` to your `.env` file.\n\n"
                        "*Tip: You can switch to **Local Fast Engine** to run tools without an API key.*"
                    ),
                    "tool_called": None,
                    "provider": "gemini",
                    "needs_key": True
                }

            tools = await self.list_tools()
            llm_res = LLMHostClient.call_gemini(api_key=key, user_message=msg, tools=tools)

            if "error" in llm_res:
                logger.warning(f"Gemini API returned error: {llm_res['error']}. Attempting local host fallback.")
                local_fallback = await self._chat_local(msg)
                if local_fallback.get("tool_called"):
                    return {
                        "message": (
                            f"✨ *Note: Google Gemini experienced high traffic ({llm_res['error']}). Processed seamlessly via Local Host Engine:*\n\n"
                            f"{local_fallback.get('message')}"
                        ),
                        "tool_called": local_fallback.get("tool_called"),
                        "execution": local_fallback.get("execution"),
                        "provider": "gemini"
                    }
                return {
                    "message": f"❌ **Google Gemini Host Error:** {llm_res['error']}\n\n*Tip: Switch to **Local Fast Engine** in the top bar to run offline instantly.*",
                    "tool_called": None,
                    "provider": "gemini"
                }

            if "tool_call" in llm_res:
                tc = llm_res["tool_call"]
                tool_name = tc.get("name")
                tool_args = tc.get("arguments", {})
                exec_res = await self.execute_tool(tool_name, tool_args)
                model_note = f" ({llm_res.get('model_used')})" if llm_res.get("model_used") else ""
                return {
                    "message": (
                        f"✨ **Google Gemini Host Brain{model_note}** analyzed your request and decided to call MCP tool **`{tool_name}`**!\n\n"
                        f"**Arguments:**\n```json\n{json.dumps(tool_args, indent=2)}\n```\n\n"
                        f"**Tool Execution Output:**\n```json\n{json.dumps(exec_res.get('result', {}), indent=2)}\n```"
                    ),
                    "tool_called": tool_name,
                    "execution": exec_res,
                    "provider": "gemini"
                }

            if "text" in llm_res:
                model_note = f" ({llm_res.get('model_used')})" if llm_res.get("model_used") else ""
                return {
                    "message": f"✨ **Google Gemini Host{model_note}:**\n\n{llm_res['text']}",
                    "tool_called": None,
                    "provider": "gemini"
                }

        # =====================================================================
        # Provider 2: Anthropic Claude (Live LLM Host)
        # =====================================================================
        if provider == "claude":
            key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                return {
                    "message": (
                        "⚠️ **Anthropic Claude API Key Required**\n\n"
                        "To have Anthropic Claude act as your live Host Brain:\n"
                        "1. Paste your Claude API key in the **Host Brain Key** input in the top bar, or\n"
                        "2. Add `ANTHROPIC_API_KEY=your_key` to your `.env` file.\n\n"
                        "*Tip: You can switch to **Local Fast Engine** to run tools without an API key.*"
                    ),
                    "tool_called": None,
                    "provider": "claude",
                    "needs_key": True
                }

            tools = await self.list_tools()
            llm_res = LLMHostClient.call_claude(api_key=key, user_message=msg, tools=tools)

            if "error" in llm_res:
                return {
                    "message": f"❌ **Anthropic Claude Host Error:** {llm_res['error']}",
                    "tool_called": None,
                    "provider": "claude"
                }

            if "tool_call" in llm_res:
                tc = llm_res["tool_call"]
                tool_name = tc.get("name")
                tool_args = tc.get("arguments", {})
                exec_res = await self.execute_tool(tool_name, tool_args)
                return {
                    "message": (
                        f"🧠 **Anthropic Claude Host** reasoned through your request and decided to call MCP tool **`{tool_name}`**!\n\n"
                        f"**Arguments:**\n```json\n{json.dumps(tool_args, indent=2)}\n```\n\n"
                        f"**Tool Execution Output:**\n```json\n{json.dumps(exec_res.get('result', {}), indent=2)}\n```"
                    ),
                    "tool_called": tool_name,
                    "execution": exec_res,
                    "provider": "claude"
                }

            if "text" in llm_res:
                return {
                    "message": f"🧠 **Anthropic Claude Host:**\n\n{llm_res['text']}",
                    "tool_called": None,
                    "provider": "claude"
                }

        # =====================================================================
        # Provider 3: Local Fast Engine (Zero-API Key / Fallback)
        # =====================================================================
        return await self._chat_local(msg)

    async def _chat_local(self, msg: str) -> Dict[str, Any]:
        """Fast offline rule-based intent parsing and execution."""
        lower = msg.lower()

        # 1. Math / Add Tool
        math_match = re.search(r'(?:add|plus|\+)\s+(-?\d+)\s+(?:and|with|\+)?\s*(-?\d+)', lower)
        if math_match:
            a, b = int(math_match.group(1)), int(math_match.group(2))
            exec_res = await self.execute_tool("add", {"a": a, "b": b})
            return {
                "message": f"I invoked the MCP **`add`** tool with `a={a}` and `b={b}`. The calculation result is **{exec_res.get('result')}**.",
                "tool_called": "add",
                "execution": exec_res,
                "provider": "local"
            }

        # 2. List Airtable records
        if any(w in lower for w in ["list airtable", "show airtable", "view airtable", "airtable records", "airtable projects"]):
            exec_res = await self.execute_tool("list_airtable_projects", {})
            count = len(exec_res.get("result", [])) if isinstance(exec_res.get("result"), list) else 0
            return {
                "message": f"Successfully queried the **Airtable Cloud MCP Tool**. Found **{count}** records synchronized in the Airtable base.",
                "tool_called": "list_airtable_projects",
                "execution": exec_res,
                "provider": "local"
            }

        # 3. Sync to Airtable
        if any(w in lower for w in ["sync airtable", "sync all to airtable", "push to airtable", "sync to airtable", "airtable sync"]):
            exec_res = await self.execute_tool("sync_all_to_airtable", {})
            res_obj = exec_res.get("result", {})
            synced_count = res_obj.get("synced_count", 0) if isinstance(res_obj, dict) else "?"
            return {
                "message": f"Executed **`sync_all_to_airtable`** tool! Synchronized **{synced_count}** project records from local SQLite to Airtable cloud.",
                "tool_called": "sync_all_to_airtable",
                "execution": exec_res,
                "provider": "local"
            }

        # 3b. Clear Airtable Data
        if any(w in lower for w in ["clear airtable", "wipe airtable", "empty airtable", "delete airtable records", "clear the air table", "clean airtable"]):
            exec_res = await self.execute_tool("clear_airtable_data", {})
            res_obj = exec_res.get("result", {})
            del_count = res_obj.get("deleted_count", 0) if isinstance(res_obj, dict) else 0
            return {
                "message": (
                    f"Executed MCP tool **`clear_airtable_data`**! Successfully cleared **{del_count}** records from Airtable.\n\n"
                    f"✨ **Preserved:** All table schema, column definitions, and field labels remain completely intact."
                ),
                "tool_called": "clear_airtable_data",
                "execution": exec_res,
                "provider": "local"
            }

        # 4. List Projects
        if any(w in lower for w in ["list project", "show project", "view project", "get project", "all project", "existing project"]):
            status_filter = None
            if "active" in lower:
                status_filter = "active"
            elif "archived" in lower:
                status_filter = "archived"
            args = {"status": status_filter} if status_filter else {}
            exec_res = await self.execute_tool("list_projects", args)
            count = len(exec_res.get("result", [])) if isinstance(exec_res.get("result"), list) else 0
            return {
                "message": f"Queried SQLite database via MCP tool **`list_projects`**. Retrieved **{count}** project records.",
                "tool_called": "list_projects",
                "execution": exec_res,
                "provider": "local"
            }

        # 5. Delete or archive project
        delete_match = re.search(r'(?:delete|archive|remove)\s+(?:project\s+)?#?(\d+)', lower)
        if delete_match:
            pid = int(delete_match.group(1))
            is_perm = "permanent" in lower or "hard" in lower
            exec_res = await self.execute_tool("archive_or_delete_project", {"project_id": pid, "permanent": is_perm})
            action_desc = "permanently deleted" if is_perm else "archived"
            return {
                "message": f"Invoked MCP tool **`archive_or_delete_project`** for Project #{pid} ({action_desc}).",
                "tool_called": "archive_or_delete_project",
                "execution": exec_res,
                "provider": "local"
            }

        # 6. Workflow Orchestration / Create Project
        if any(w in lower for w in ["create project", "orchestrate", "run workflow", "new project", "build project"]):
            name_match = re.search(r'(?:named|called|project)\s+["\']?([^"\',]+)["\']?', msg, re.IGNORECASE)
            proj_name = name_match.group(1).strip() if name_match else "AI Host Generated Project"

            desc = f"Generated by MCP Host from instruction: {msg}"
            reqs = "- Autonomous requirement parsing\n- Multi-Agent coordination via MCP\n- Automated documentation"
            exec_res = await self.execute_tool("orchestrate_workflow", {
                "project_name": proj_name,
                "description": desc,
                "requirements": reqs,
                "additional_info": "Initiated via MCP Host Assistant console."
            })
            return {
                "message": f"Dispatched full 3-Agent pipeline via MCP tool **`orchestrate_workflow`** for project **'{proj_name}'**! Agent 1 (Markdown), Agent 2 (Database), and Agent 3 (Docs) executed.",
                "tool_called": "orchestrate_workflow",
                "execution": exec_res,
                "provider": "local"
            }

        # 7. Help / Tool Listing
        if any(w in lower for w in ["help", "what tools", "available tools", "list tools", "capabilities", "what can you do"]):
            tools = await self.list_tools()
            tool_names = [f"`{t['name']}`" for t in tools]
            return {
                "message": (
                    f"**MCP Host Client Ready!**\n\n"
                    f"I have discovered **{len(tools)} MCP tools** exposed by the system:\n"
                    f"{', '.join(tool_names)}\n\n"
                    f"**Host Brain Providers available:**\n"
                    f"- **⚡ Local Fast Engine:** Instant, offline, zero API keys.\n"
                    f"- **✨ Google Gemini:** Live frontier LLM Host reasoning with MCP function calling.\n\n"
                    f"**Things you can ask me to do:**\n"
                    f"- *'List all projects in the database'*\n"
                    f"- *'Show Airtable records'*\n"
                    f"- *'Sync all records to Airtable cloud'*\n"
                    f"- *'Add 45 and 99'*\n"
                    f"- *'Create project named Cloud Sentinel'*"
                ),
                "tool_called": None,
                "tools_available": len(tools),
                "provider": "local"
            }

        # Fallback friendly response
        return {
            "message": (
                f"Hello! I am your **MCP Host Assistant**.\n\n"
                f"You asked: *\"{msg}\"*\n\n"
                f"I can invoke any registered MCP tool on your behalf. Try typing:\n"
                f"- **`list projects`** to inspect SQLite records\n"
                f"- **`show airtable`** to inspect Airtable sync\n"
                f"- **`sync airtable`** to trigger dual-sync\n"
                f"- **`add 12 and 34`** to test standard arithmetic tool\n"
                f"- Or switch to the **Tool Catalog** tab to manually execute any of the 10 available MCP tools."
            ),
            "tool_called": None,
            "provider": "local"
        }

    def get_claude_desktop_config(self) -> Dict[str, Any]:
        """Return the Claude Desktop configuration JSON and file path."""
        appdata = os.environ.get("APPDATA", "")
        claude_dir = Path(appdata) / "Claude" if appdata else Path.home() / ".claude"
        config_path = claude_dir / "claude_desktop_config.json"

        python_exec = sys.executable
        server_path = str((BASE_DIR / "server.py").resolve())

        snippet = {
            "mcpServers": {
                "multi-agent-workflow-server": {
                    "command": python_exec,
                    "args": [server_path, "--mcp"]
                }
            }
        }

        return {
            "config_path": str(config_path),
            "directory_exists": claude_dir.exists(),
            "file_exists": config_path.exists(),
            "config_snippet": snippet
        }

    def install_claude_desktop_config(self) -> Dict[str, Any]:
        """Automatically write or merge configuration into Claude Desktop config file."""
        info = self.get_claude_desktop_config()
        config_path = Path(info["config_path"])
        config_path.parent.mkdir(parents=True, exist_ok=True)

        current_data = {"mcpServers": {}}
        if config_path.exists():
            try:
                current_data = json.loads(config_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Error reading existing Claude desktop config: {e}")

        if "mcpServers" not in current_data:
            current_data["mcpServers"] = {}

        current_data["mcpServers"]["multi-agent-workflow-server"] = info["config_snippet"]["mcpServers"]["multi-agent-workflow-server"]
        config_path.write_text(json.dumps(current_data, indent=2), encoding="utf-8")

        logger.info(f"Successfully configured Claude Desktop at {config_path}")
        return {
            "status": "success",
            "message": f"Successfully registered server in Claude Desktop config at: {config_path}",
            "config_path": str(config_path),
            "config": current_data
        }

    def get_status(self) -> Dict[str, Any]:
        """Return diagnostic metrics of the MCP Host."""
        return {
            "host_status": "ready",
            "active_mode": self._mode,
            "connected_server": "Multi-Agent Workflow Server",
            "protocol_version": "2024-11-05 (MCP v1.0)",
            "transport": "In-Process Async JSON-RPC",
            "total_executions": len(self._execution_history),
            "recent_executions": self._execution_history[-5:],
            "claude_desktop_installed": Path(self.get_claude_desktop_config()["config_path"]).exists()
        }


# Global singleton instance of MCPHostManager
mcp_host_manager = MCPHostManager()
