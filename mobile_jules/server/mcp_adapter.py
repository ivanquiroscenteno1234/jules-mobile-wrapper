"""
MCP Browser Adapter - High-level browser interface for Jules Test Agent.

Adapted from Script Builder's mcp_adapter.py.
Provides a simple API for browser automation via MCP.
"""

import asyncio
from typing import Any, Dict, Optional

from mcp_client import PlaywrightMCPClient, get_mcp_client, reset_mcp_client


class MCPBrowserAdapter:
    """
    High-level browser adapter using MCP.
    
    Provides browser-like methods (goto, click, fill, screenshot)
    that abstract away MCP tool calling details.
    """
    
    def __init__(self):
        self.mcp: Optional[PlaywrightMCPClient] = None
        self._launched = False
        self._current_url: Optional[str] = None
    
    async def launch(self, force_reconnect: bool = False) -> bool:
        """Launch/connect to the browser via MCP.
        
        Args:
            force_reconnect: If True, disconnect existing connection and reconnect fresh.
                           Useful to avoid stale SSE connections after idle periods.
        """
        self.mcp = get_mcp_client()
        
        is_running = await self.mcp.is_server_running()
        if not is_running:
            print("⚠️ MCP server not running. Please start with:")
            print("   npx @executeautomation/playwright-mcp-server --port 8931")
            return False
        
        # Force fresh connection if requested or if already launched (subsequent test)
        if force_reconnect or self._launched:
            print("🔄 Reconnecting MCP for fresh session...")
            connected = await self.mcp.reconnect()
        else:
            connected = await self.mcp.connect()
            
        if not connected:
            print("⚠️ Failed to connect to MCP server")
            return False
        
        self._launched = True
        print("✅ MCP Browser connected")
        return True
    
    async def goto(self, url: str) -> str:
        """Navigate to a URL and return page content."""
        if not self._launched:
            await self.launch()
        
        await self.mcp.navigate(url)
        self._current_url = url
        
        await asyncio.sleep(1)  # Wait for page load
        
        return await self.get_visible_text()
    
    async def get_visible_text(self) -> str:
        """Get the visible text content of the page."""
        if not self.mcp:
            return ""
        
        try:
            result = await self.mcp.get_visible_text()
            content = result.get("result", "")
            return str(content) if content else ""
        except Exception as e:
            print(f"⚠️ Failed to get visible text: {e}")
            return ""
    
    async def get_visible_html(self) -> str:
        """Get the visible HTML of the page."""
        if not self.mcp:
            return ""
        
        try:
            result = await self.mcp.get_visible_html()
            content = result.get("result", "")
            return str(content) if content else ""
        except Exception as e:
            print(f"⚠️ Failed to get HTML: {e}")
            return ""
    
    async def click(self, selector: str, description: str = "") -> bool:
        """Click an element using a CSS selector."""
        if not self.mcp:
            return False
        
        try:
            await self.mcp.click(selector, description)
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            print(f"❌ Click failed on {selector}: {e}")
            return False
    
    async def fill(self, selector: str, value: str, description: str = "") -> bool:
        """Fill an input field."""
        if not self.mcp:
            return False
        
        try:
            await self.mcp.fill(selector, value, description)
            return True
        except Exception as e:
            print(f"❌ Fill failed on {selector}: {e}")
            return False
    
    async def press_key(self, key: str) -> bool:
        """Press a keyboard key."""
        if not self.mcp:
            return False
        
        try:
            await self.mcp.press_key(key)
            return True
        except Exception as e:
            print(f"❌ Press key failed: {e}")
            return False
    
    async def screenshot(self) -> Optional[str]:
        """Take a screenshot and return base64 data."""
        if not self.mcp:
            return None
        
        try:
            result = await self.mcp.screenshot()
            return result.get("result")
        except Exception as e:
            print(f"⚠️ Screenshot failed: {e}")
            return None
    
    async def close(self):
        """Close the browser. Note: We don't disconnect the MCP session to avoid task context issues."""
        if self.mcp and self._launched:
            try:
                # Just close the browser page, don't disconnect the SSE session
                # The SSE session will be reused for the next test
                await self.mcp.close()
            except Exception as e:
                print(f"⚠️ Close error (ignored): {e}")
        
        self._launched = False


# Global adapter instance
_mcp_adapter: Optional[MCPBrowserAdapter] = None


def get_mcp_adapter() -> MCPBrowserAdapter:
    """Get or create the MCP adapter singleton."""
    global _mcp_adapter
    if _mcp_adapter is None:
        _mcp_adapter = MCPBrowserAdapter()
    return _mcp_adapter


async def reset_mcp_adapter():
    """Reset the global adapter instance."""
    global _mcp_adapter
    if _mcp_adapter:
        await _mcp_adapter.close()
    _mcp_adapter = None
