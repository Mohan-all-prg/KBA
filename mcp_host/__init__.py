"""
MCP Host Module for Multi-Agent Workflow Application.
Enables the application to operate as an interactive MCP Host / Client.
"""

from .host import MCPHostManager, mcp_host_manager

__all__ = ["MCPHostManager", "mcp_host_manager"]
