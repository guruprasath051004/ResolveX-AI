"""ResolveX Standalone MCP Server entry point."""
import uvicorn
from backend.mcp_server.server import app, mcp_server

if __name__ == "__main__":
    uvicorn.run("backend.mcp_server.main:app", host="0.0.0.0", port=8001, log_level="info")
