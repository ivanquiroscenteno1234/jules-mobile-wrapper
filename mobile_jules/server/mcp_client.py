"""
Playwright MCP Client - For Jules Test Agent.

Adapted from Script Builder's mcp_client.py.
Uses the ExecuteAutomation Playwright MCP server for browser automation.

MCP Server: @executeautomation/playwright-mcp-server
Start with: npx @executeautomation/playwright-mcp-server --port 8931
"""

import asyncio
import socket
from typing import Any, Dict, List, Optional

# Official MCP SDK imports
from mcp import ClientSession
from mcp.client.sse import sse_client


class PlaywrightMCPClient:
    """
    Client for ExecuteAutomation Playwright MCP server.
    
    Provides browser automation tools for the Test Agent.
    """
    
    def __init__(self, port: int = 8931):
        """
        Initialize MCP client.
        
        Args:
            port: MCP server port (default 8931)
        """
        self.port = port
        self.base_url = f"http://localhost:{port}/sse"
        self._session: Optional[ClientSession] = None
        self._read_stream = None
        self._write_stream = None
        self._context_manager = None
        self._session_context = None
    
    async def is_server_running(self) -> bool:
        """Check if the MCP server is running by testing the port."""
        # Try IPv6 first (some servers bind to ::1 on Windows)
        try:
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                result = s.connect_ex(('::1', self.port))
                if result == 0:
                    return True
        except Exception:
            pass
        
        # Fallback to IPv4
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                result = s.connect_ex(('127.0.0.1', self.port))
                return result == 0
        except Exception:
            return False
    
    async def connect(self) -> bool:
        """Connect to the MCP server using SSE transport."""
        if self._session is not None:
            return True
        
        try:
            self._context_manager = sse_client(self.base_url)
            streams = await self._context_manager.__aenter__()
            self._read_stream, self._write_stream = streams
            
            self._session_context = ClientSession(self._read_stream, self._write_stream)
            self._session = await self._session_context.__aenter__()
            
            await self._session.initialize()
            
            print("✅ Connected to Playwright MCP server")
            return True
            
        except Exception as e:
            print(f"⚠️ Failed to connect to MCP server: {e}")
            # Don't call disconnect here - just clear references
            self._session = None
            self._session_context = None
            self._context_manager = None
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server. Note: We don't close async contexts to avoid task issues."""
        # Just clear the references - don't try to close the async context managers
        # The SSE connection will be cleaned up when the server shuts down
        self._session = None
        self._session_context = None
        self._context_manager = None
        self._read_stream = None
        self._write_stream = None
    
    async def call_tool(self, tool_name: str, params: Dict[str, Any] = None) -> Any:
        """Call an MCP tool."""
        if self._session is None:
            if not await self.connect():
                raise Exception("Not connected to MCP server")
        
        if params is None:
            params = {}
        
        try:
            result = await self._session.call_tool(tool_name, arguments=params)
            
            if result and result.content:
                for content in result.content:
                    if hasattr(content, 'text'):
                        return {"result": content.text}
                return {"result": str(result.content)}
            return {"result": None}
            
        except Exception as e:
            raise Exception(f"MCP tool '{tool_name}' failed: {e}")
    
    async def list_tools(self) -> List[str]:
        """List available MCP tools."""
        if self._session is None:
            if not await self.connect():
                return []
        
        try:
            tools = await self._session.list_tools()
            return [tool.name for tool in tools.tools]
        except Exception as e:
            print(f"⚠️ Failed to list tools: {e}")
            return []
    
    # ============ Browser Automation Tools ============
    
    async def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL."""
        print(f"🌐 Navigating to: {url}")
        return await self.call_tool("playwright_navigate", {"url": url})
    
    async def click(self, selector: str, description: str = "") -> Dict[str, Any]:
        """Click an element by selector."""
        print(f"🖱️ Clicking: {description or selector}")
        return await self.call_tool("playwright_click", {"selector": selector})
    
    async def fill(self, selector: str, value: str, description: str = "") -> Dict[str, Any]:
        """Fill a text field."""
        print(f"⌨️ Filling: {description or selector}")
        return await self.call_tool("playwright_fill", {"selector": selector, "value": value})
    
    async def get_visible_text(self) -> Dict[str, Any]:
        """Get visible text of the page."""
        return await self.call_tool("playwright_get_visible_text", {})
    
    async def get_visible_html(self) -> Dict[str, Any]:
        """Get visible HTML of the page."""
        return await self.call_tool("playwright_get_visible_html", {})
    
    async def screenshot(self, name: str = "screenshot", full_page: bool = False) -> Dict[str, Any]:
        """Take a screenshot of the page."""
        return await self.call_tool("playwright_screenshot", {"name": name, "fullPage": full_page})
    
    async def press_key(self, key: str) -> Dict[str, Any]:
        """Press a keyboard key."""
        return await self.call_tool("playwright_press_key", {"key": key})
    
    async def close(self) -> Dict[str, Any]:
        """Close the browser."""
        return await self.call_tool("playwright_close", {})


# Singleton instance
_mcp_client: Optional[PlaywrightMCPClient] = None


def get_mcp_client(port: int = 8931) -> PlaywrightMCPClient:
    """Get or create the singleton MCP client."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = PlaywrightMCPClient(port)
    return _mcp_client


async def reset_mcp_client():
    """Reset the MCP client (disconnect and clear singleton)."""
    global _mcp_client
    if _mcp_client:
        await _mcp_client.disconnect()
        _mcp_client = None


async def is_mcp_available() -> bool:
    """Check if MCP server is available."""
    client = get_mcp_client()
    return await client.is_server_running()
