"""ResolveX MCP Client wrapper used by backend agents."""
import json
import time
from typing import Any, Dict, List, Optional
from backend.database import SessionLocal
from backend.models import MCPToolCall
from backend.mcp_server.server import mcp_server

class MCPClient:
    """Client wrapper for interacting with the ResolveX MCP server."""

    def __init__(self, server=None):
        self.server = server or mcp_server

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List registered tools from the MCP server using official protocol."""
        tools_list = await self.server.list_tools()
        result = []
        for t in tools_list:
            result.append({
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            })
        return result

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_role: str = "employee",
        calling_agent: str = "system",
        incident_id: Optional[int] = None,
        run_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Call an MCP tool with full logging, timing, and error handling."""
        start_time = time.perf_counter()
        args = dict(arguments)
        args["user_role"] = user_role
        incident_id = incident_id or self._as_int(args.get("incident_id")) or self._as_int(args.get("ticket_id"))

        call_status = "success"
        permission_status = "granted"
        output_data = None
        error_msg = None

        try:
            raw_result = await self.server.call_tool(tool_name, args)
            # The MCP server returns CallToolResult with content
            if hasattr(raw_result, "content") and raw_result.content:
                first_item = raw_result.content[0]
                if hasattr(first_item, "text"):
                    try:
                        output_data = json.loads(first_item.text)
                    except Exception:
                        output_data = {"raw": first_item.text}
                else:
                    output_data = str(first_item)
            elif isinstance(raw_result, dict):
                output_data = raw_result
            else:
                output_data = {"result": str(raw_result)}
            return output_data

        except PermissionError as pe:
            call_status = "error"
            permission_status = "denied"
            error_msg = str(pe)
            output_data = {"error": error_msg, "permission_denied": True}
            raise pe

        except Exception as exc:
            actual_exc = getattr(exc, "__cause__", None) or exc
            exc_str = str(actual_exc)
            call_status = "error"
            if isinstance(actual_exc, PermissionError) or "permission denied" in exc_str.lower():
                permission_status = "denied"
            error_msg = f"{type(actual_exc).__name__}: {exc_str}"
            output_data = {"error": error_msg}
            raise actual_exc

        finally:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logged_incident_id = incident_id
            if logged_incident_id is None and isinstance(output_data, dict):
                logged_incident_id = self._as_int(
                    output_data.get("ticket_id") or output_data.get("incident_id")
                )
            self._log_tool_call(
                tool_name=tool_name,
                input_args=arguments,
                output_data=output_data if output_data is not None else {"error": error_msg},
                duration_ms=duration_ms,
                status=call_status,
                permission_status=permission_status,
                calling_agent=calling_agent,
                incident_id=logged_incident_id,
                run_id=run_id,
                user_id=user_id,
            )

    @staticmethod
    def _as_int(value: Any) -> Optional[int]:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _log_tool_call(
        self,
        tool_name: str,
        input_args: Dict[str, Any],
        output_data: Any,
        duration_ms: int,
        status: str,
        permission_status: str,
        calling_agent: str,
        incident_id: Optional[int],
        run_id: Optional[int],
        user_id: Optional[int],
    ):
        """Record the tool execution in mcp_tool_calls table."""
        db = SessionLocal()
        try:
            call_record = MCPToolCall(
                tool_name=tool_name,
                input_summary=json.dumps(input_args),
                output_summary=json.dumps(output_data) if isinstance(output_data, (dict, list)) else str(output_data),
                duration_ms=duration_ms,
                status=status,
                permission_status=permission_status,
                calling_agent=calling_agent,
                incident_id=incident_id,
                run_id=run_id,
                user_id=user_id,
            )
            db.add(call_record)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
