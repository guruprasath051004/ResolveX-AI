"""ResolveX MCP Server and Client module."""
from backend.mcp_server.server import mcp_server, app
from backend.mcp_server.client import MCPClient

__all__ = ["mcp_server", "app", "MCPClient"]

