"""
StudyMind AI — MCP Client & Tool Calling Bridge
Provides an in-process MCP client interface to inspect, invoke, and bridge
MCP tools with the Python runtime and Gemini's function-calling engine.
"""
import inspect
import json
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("StudyMind.MCPClient")


class MCPClient:
    """
    Client interface for StudyMind AI's Model Context Protocol (MCP) Server.
    Provides tool discovery, validation, dispatching, and Gemini function declaration bridging.
    """

    def __init__(self, mcp_server=None):
        if mcp_server is None:
            from mcp_server import server as default_server
            self.server = default_server
        else:
            self.server = mcp_server

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        Lists all registered MCP tools with their metadata and JSON parameter schemas.
        """
        tools_list = []
        try:
            registered_tools = self.server._tool_manager.list_tools()
            for t in registered_tools:
                tools_list.append({
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.parameters or {},
                })
        except Exception as e:
            logger.error(f"Error listing MCP tools: {e}")
        return tools_list

    def get_tool_names(self) -> List[str]:
        """Returns the names of all registered MCP tools."""
        return [t["name"] for t in self.list_tools()]

    def get_tool(self, name: str):
        """Retrieves the underlying MCP tool object by name."""
        return self.server._tool_manager.get_tool(name)

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """
        Invokes an MCP tool by name with arguments.
        Performs synchronous or asynchronous execution and returns the result.
        """
        if arguments is None:
            arguments = {}

        tool_obj = self.get_tool(name)
        if not tool_obj:
            raise ValueError(f"Unknown MCP Tool: '{name}'. Available tools: {self.get_tool_names()}")

        fn = tool_obj.fn
        if inspect.iscoroutinefunction(fn):
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Running in existing event loop
                    import nest_asyncio
                    nest_asyncio.apply()
                    return loop.run_until_complete(fn(**arguments))
                else:
                    return loop.run_until_complete(fn(**arguments))
            except Exception:
                return asyncio.run(fn(**arguments))
        else:
            return fn(**arguments)

    def get_tool_callables(self, tool_names: Optional[List[str]] = None) -> List[Callable]:
        """
        Returns a list of Python callables for the specified MCP tools
        (or all tools if None) ready to be passed directly to Gemini GenerativeModel(tools=[...]).
        """
        callables = []
        all_registered = self.server._tool_manager.list_tools()
        for t in all_registered:
            if tool_names is None or t.name in tool_names:
                tool_obj = self.get_tool(t.name)
                if tool_obj and hasattr(tool_obj, "fn"):
                    callables.append(tool_obj.fn)
        return callables


# Singleton MCP Client instance for application-wide use
mcp_client = MCPClient()

