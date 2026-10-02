"""
LLM Host Client Provider

Connects the MCP Host to real frontier LLMs (Google Gemini & Anthropic Claude)
so they can act as the Host Brain, reasoning about user requests and deciding
which MCP tools to invoke.
"""

import os
import json
import urllib.request
import urllib.error
import ssl
from typing import Dict, Any, List, Optional, Tuple
from config.logging_config import get_logger

logger = get_logger("mcp.host.llm")


class LLMHostClient:
    """Dispatches reasoning requests to Google Gemini and Anthropic Claude APIs."""

    @staticmethod
    def _create_ssl_context():
        try:
            return ssl.create_default_context()
        except Exception:
            return None

    DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
    GEMINI_MODELS_CASCADE = [
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.8-flash",
        "gemini-flash-latest",
    ]

    @classmethod
    def call_gemini(
        cls,
        api_key: str,
        user_message: str,
        tools: List[Dict[str, Any]],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send prompt and MCP tool definitions to Google Gemini.
        Supports multi-model fallback cascade to prevent 503 high-demand or rate-limit errors.
        Returns either a decided tool call or direct conversational text.
        """
        if not api_key:
            return {"error": "Missing Gemini API key."}

        # Convert MCP tools to Gemini function declarations
        function_declarations = []
        for t in tools:
            schema = t.get("schema", {})
            props = schema.get("properties", {})
            gemini_props = {}
            for pk, pv in props.items():
                ptype = pv.get("type", "string").upper()
                if "anyOf" in pv:
                    ptype = "STRING"
                gemini_props[pk] = {
                    "type": ptype,
                    "description": pv.get("description", pv.get("title", pk))
                }

            decl = {
                "name": t["name"],
                "description": (t.get("description") or t["name"])[:1000],
                "parameters": {
                    "type": "OBJECT",
                    "properties": gemini_props,
                    "required": schema.get("required", [])
                }
            }
            function_declarations.append(decl)

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_message}]
                }
            ],
            "tools": [{"functionDeclarations": function_declarations}],
            "generationConfig": {
                "temperature": 0.2
            }
        }

        # Build candidate models list: start with requested model if any, followed by cascade
        if model:
            models_to_try = [model] + [m for m in cls.GEMINI_MODELS_CASCADE if m != model]
        else:
            models_to_try = list(cls.GEMINI_MODELS_CASCADE)

        last_error = None
        for current_model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url=url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            try:
                ctx = cls._create_ssl_context()
                with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                candidates = data.get("candidates", [])
                if not candidates:
                    return {"text": "Gemini returned no response candidates."}

                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "functionCall" in part:
                        fc = part["functionCall"]
                        return {
                            "tool_call": {
                                "name": fc.get("name"),
                                "arguments": fc.get("args", {})
                            },
                            "model_used": current_model
                        }
                    elif "text" in part:
                        return {"text": part["text"], "model_used": current_model}

                return {"text": "Gemini did not return text or tool call."}

            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                logger.warning(f"Gemini API HTTP Error {e.code} on model '{current_model}': {err_body[:200]}")
                try:
                    err_json = json.loads(err_body)
                    msg = err_json.get("error", {}).get("message", err_body)
                except Exception:
                    msg = err_body
                last_error = f"Gemini API Error ({e.code}): {msg}"
                # If high demand (503), not found (404), or rate limited (429), try next model in cascade
                if e.code in (503, 404, 429):
                    continue
                return {"error": last_error}
            except Exception as e:
                logger.warning(f"Connection error to Gemini on model '{current_model}': {e}")
                last_error = f"Failed to connect to Google Gemini: {str(e)}"
                continue

        return {"error": last_error or "All Google Gemini models temporarily unavailable."}

    @classmethod
    def call_claude(
        cls,
        api_key: str,
        user_message: str,
        tools: List[Dict[str, Any]],
        model: str = "claude-3-5-sonnet-20241022"
    ) -> Dict[str, Any]:
        """
        Send prompt and MCP tool definitions to Anthropic Claude Messages API.
        Returns either a decided tool call or direct conversational text.
        """
        if not api_key:
            return {"error": "Missing Anthropic Claude API key."}

        # Convert MCP tools to Claude tool format
        claude_tools = []
        for t in tools:
            schema = t.get("schema", {})
            claude_tools.append({
                "name": t["name"],
                "description": (t.get("description") or t["name"])[:1024],
                "input_schema": schema or {"type": "object", "properties": {}}
            })

        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": user_message}],
            "tools": claude_tools
        }

        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            method="POST"
        )

        try:
            ctx = cls._create_ssl_context()
            with urllib.request.urlopen(req, context=ctx, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            content_blocks = data.get("content", [])
            for block in content_blocks:
                if block.get("type") == "tool_use":
                    return {
                        "tool_call": {
                            "name": block.get("name"),
                            "arguments": block.get("input", {})
                        }
                    }
                elif block.get("type") == "text":
                    return {"text": block.get("text", "")}

            return {"text": "Claude processed request without text or tool calls."}

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            logger.error(f"Claude API HTTP Error {e.code}: {err_body}")
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("error", {}).get("message", err_body)
            except Exception:
                msg = err_body
            return {"error": f"Anthropic Claude API Error ({e.code}): {msg}"}
        except Exception as e:
            logger.error(f"Failed to call Claude API: {e}", exc_info=True)
            return {"error": f"Failed to connect to Anthropic Claude: {str(e)}"}
