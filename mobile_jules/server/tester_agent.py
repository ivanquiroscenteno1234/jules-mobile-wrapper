"""
Tester Agent - AI-powered web application testing

Uses Gemini for reasoning and Playwright for browser automation.
The agent takes screenshots, analyzes them, and decides what actions to take
to verify that a web application works correctly.

Requires:
- GEMINI_API_KEY or GOOGLE_API_KEY environment variable
- google-genai package (pip install google-genai)
"""

import os
import json
import asyncio
import base64
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# New Google GenAI SDK (supports ThinkingConfig for Gemini 3)
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("⚠️ google-genai not installed. Install with: pip install google-genai")


@dataclass
class TestStep:
    """A single step in the test execution."""
    step_number: int
    action: str
    target: Optional[str] = None
    value: Optional[str] = None
    reasoning: str = ""
    description: str = ""  # Human-readable summary of the action
    page_state: Optional[str] = None
    success: bool = True
    screenshot: Optional[str] = None  # Base64 encoded
    error: Optional[str] = None


@dataclass
class TestResult:
    """Complete test result."""
    test_id: str
    url: str
    objective: str
    status: str  # running, passed, failed
    steps: List[TestStep]
    started_at: str
    completed_at: Optional[str] = None
    final_verdict: Optional[str] = None


class TesterAgent:
    """AI-powered web testing agent using Gemini and Playwright MCP Server."""
    
    def __init__(self):
        # Support both GEMINI_API_KEY and GOOGLE_API_KEY
        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            print("WARNING: GEMINI_API_KEY or GOOGLE_API_KEY not set. Tester Agent will not work.")
        
        # Configure GenAI Client (new SDK)
        self.model_name = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
        self.thinking_level = os.environ.get("THINKING_LEVEL", "low").lower()
        
        if GENAI_AVAILABLE and self.api_key:
            # Create client with API key
            self.client = genai.Client(api_key=self.api_key)
            print(f"✅ GenAI Client configured: model={self.model_name}, thinking_level={self.thinking_level}")
        else:
            self.client = None
        
        self.mcp = None  # MCP Browser Adapter
        self.tests: Dict[str, TestResult] = {}
    
    async def _init_browser(self):
        """Initialize browser via MCP."""
        try:
            from mcp_adapter import get_mcp_adapter
            
            self.mcp = get_mcp_adapter()
            success = await self.mcp.launch()
            if not success:
                print("⚠️ MCP server not available. Start with:")
                print("   npx @executeautomation/playwright-mcp-server --port 8931")
                return False
            return True
        except ImportError as e:
            print(f"MCP adapter not found: {e}")
            return False
        except Exception as e:
            print(f"Browser init error: {e}")
            return False
    
    async def _get_page_snapshot(self) -> str:
        """Get a detailed text snapshot of the page via MCP."""
        if not self.mcp:
            return "MCP not initialized"
        
        try:
            # Get visible HTML and text from MCP
            html = await self.mcp.get_visible_html()
            text = await self.mcp.get_visible_text()
            
            return f"PAGE CONTENT:\n{text}\n\nHTML STRUCTURE (partial):\n{html[:2000] if html else 'N/A'}"
        except Exception as e:
            return f"Error getting page snapshot via MCP: {e}"

    async def _close_browser(self):
        """Close the browser via MCP."""
        if self.mcp:
            await self.mcp.close()
    
    async def _take_screenshot(self) -> str:
        """Take a screenshot via MCP and return as base64."""
        if not self.mcp:
            return ""
        
        try:
            result = await self.mcp.screenshot()
            if not result:
                return ""
            
            # MCP returns a path like "Screenshot saved to: C:\...\screenshot.png"
            result_text = str(result)
            if "Screenshot saved to:" in result_text:
                # Extract the file path
                path = result_text.split("Screenshot saved to:")[1].strip()
                # Remove any trailing quotes or extra characters
                path = path.strip('"').strip("'")
                
                # Read the file and encode to base64
                import os
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        return base64.b64encode(f.read()).decode()
                else:
                    print(f"⚠️ Screenshot file not found: {path}")
                    return ""
            else:
                # Maybe it's already base64 or some other format
                return result if isinstance(result, str) else ""
        except Exception as e:
            print(f"⚠️ Screenshot error: {e}")
            return ""
    
    async def _ask_gemini(self, screenshot_b64: str, objective: str, history: List[TestStep], 
                     snapshot: str = "", username: str = None, password: str = None) -> Dict:
        """Ask Gemini what to do next using the new google-genai Client API."""
        
        if not self.client:
            raise Exception("GenAI client not initialized. Check API key and google-genai package.")
        
        # Build history context
        history_text = ""
        for step in history[-8:]:
            history_text += f"Step {step.step_number}: {step.action}"
            if step.target:
                history_text += f" on '{step.target}'"
            history_text += f" - {step.reasoning} (Success: {step.success})\n"
            
        credentials_context = ""
        if username or password:
            credentials_context = f"\nAVAILABLE CREDENTIALS:\n- Username: {username if username else 'N/A'}\n- Password: {password if password else 'N/A'}\n"

        prompt = f"""You are a Senior QA Automation Engineer. Your goal is to verify that a web application functions correctly.

TEST OBJECTIVE: {objective}
{credentials_context}
PREVIOUS ACTIONS:
{history_text if history_text else "None - this is the first step"}

CURRENT PAGE SNAPSHOT:
{snapshot}

Analyze the screenshot and provide your next step as a JSON object with these fields:
- "description": Short sentence for activity log (e.g., 'Clicked the Login button')
- "reasoning": Detailed QA reasoning for this step
- "page_state": "LOGIN_PAGE", "LANDING", "CONTENT_VIEW", "ERROR", or "OTHER"
- "action": "click", "type", "scroll", "wait", or "done"
- "target": CSS selector or visible text for the action
- "value": Text to type (for "type" action) or wait time in ms (for "wait")
- "confidence": 0.0-1.0
- "is_objective_met": true/false

IMPORTANT: Respond with ONLY the JSON object, no markdown code blocks."""

        try:
            import io
            from PIL import Image
            
            # Build content parts
            contents = [prompt]
            
            # Add image if available
            if screenshot_b64:
                image_data = base64.b64decode(screenshot_b64)
                image = Image.open(io.BytesIO(image_data))
                contents.append(image)
            
            # Call generate_content with ThinkingConfig
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=2048,
                    thinking_config=types.ThinkingConfig(thinking_level=self.thinking_level)
                )
            )
            
            # Extract text response
            text = response.text.strip()
            print(f"   Gemini raw response (first 200 chars): {text[:200]}", flush=True)
            
            # Remove markdown code blocks if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            
            return json.loads(text)
            
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parse error: {e}", flush=True)
            print(f"   Raw: {repr(text[:500])}", flush=True)
            # Return wait action to continue
            return {
                "action": "wait",
                "target": None,
                "value": "2000",
                "reasoning": f"JSON parse error: {str(e)[:100]}",
                "description": "Waiting due to response issue",
                "is_objective_met": False
            }
        except Exception as e:
            print(f"❌ Gemini API error: {e}", flush=True)
            raise
    
    async def _execute_action(self, action: str, target: str = None, value: str = None) -> bool:
        """Execute a browser action via MCP with fallbacks."""
        if not self.mcp:
            return False
            
        try:
            if action == "navigate":
                await self.mcp.goto(value)
                return True
                
            elif action == "click":
                # Try CSS selector first
                success = await self.mcp.click(target, f"Clicking {target}")
                if success:
                    return True
                
                # Fallback: try as text selector
                success = await self.mcp.click(f"text='{target}'", f"Clicking text '{target}'")
                if success:
                    return True
                
                # Fallback: try pressing Enter (useful for buttons)
                await self.mcp.press_key("Enter")
                return False
                
            elif action == "type":
                success = await self.mcp.fill(target, value, f"Typing into {target}")
                return success
                
            elif action == "scroll":
                # MCP doesn't have scroll, use press_key as workaround
                await self.mcp.press_key("PageDown")
                return True
                
            elif action == "wait":
                wait_ms = int(value) if value and value.isdigit() else 2000
                await asyncio.sleep(wait_ms / 1000)
                return True
                
            elif action == "assert_text":
                text = await self.mcp.get_visible_text()
                return value.lower() in text.lower() if text else False
                
            elif action == "assert_element":
                html = await self.mcp.get_visible_html()
                return target in html if html else False
                
            elif action == "done":
                return True
                
            return False
        except Exception as e:
            print(f"❌ Action execution error: {e}")
            return False
    
    async def run_test(self, test_id: str, url: str, objective: str, 
                   username: str = None, password: str = None, callback=None) -> TestResult:
        """Run a test against a URL with a natural language objective.
        
        Args:
            test_id: Unique identifier for this test
            url: URL to test
            objective: Natural language description of what to test
            username: Optional login name
            password: Optional login secret
            callback: Optional async function to call after each step
        """
        result = TestResult(
            test_id=test_id,
            url=url,
            objective=objective,
            status="running",
            steps=[],
            started_at=datetime.now().isoformat()
        )
        self.tests[test_id] = result
        
        if not self.api_key:
            result.status = "failed"
            result.final_verdict = "GEMINI_API_KEY not configured"
            return result
        
        # Initialize browser
        if not await self._init_browser():
            result.status = "failed"
            result.final_verdict = "Could not initialize browser"
            return result
        
        try:
            # Navigate to URL via MCP
            await self.mcp.goto(url)
            await asyncio.sleep(1)
            
            max_steps = 15
            for step_num in range(1, max_steps + 1):
                print(f"📍 Step {step_num}: Taking screenshot...", flush=True)
                # Take screenshot and page snapshot
                screenshot = await self._take_screenshot()
                print(f"   Screenshot: {'✅ Got' if screenshot else '❌ Empty'} ({len(screenshot) if screenshot else 0} chars)", flush=True)
                
                snapshot = await self._get_page_snapshot()
                print(f"   Snapshot: {len(snapshot)} chars", flush=True)
                
                # Ask Gemini what to do
                print(f"   Calling Gemini...", flush=True)
                try:
                    gemini_response = await self._ask_gemini(
                        screenshot, objective, result.steps, 
                        snapshot=snapshot, username=username, password=password
                    )
                    print(f"   Gemini response: action={gemini_response.get('action')}, target={gemini_response.get('target')}", flush=True)
                except Exception as e:
                    step = TestStep(
                        step_number=step_num,
                        action="error",
                        reasoning=f"Gemini error: {str(e)}",
                        success=False,
                        screenshot=screenshot[:100] + "..."  # Truncated for storage
                    )
                    result.steps.append(step)
                    break
                
                action = gemini_response.get("action", "unknown")
                target = gemini_response.get("target")
                value = gemini_response.get("value")
                reasoning = gemini_response.get("reasoning", "")
                description = gemini_response.get("description", "")  # Natural language summary
                page_state = gemini_response.get("page_state")
                is_objective_met = gemini_response.get("is_objective_met", False)
                
                # Check if done
                if action == "done":
                    success = True
                    if is_objective_met:
                        result.status = "passed"
                        result.final_verdict = "Test objective achieved"
                    else:
                        result.status = "failed"
                        result.final_verdict = reasoning
                    
                    # Store final step
                    step = TestStep(
                        step_number=step_num,
                        action=action,
                        reasoning=reasoning,
                        description=description or "Test completed",
                        page_state=page_state,
                        success=success,
                        screenshot=screenshot
                    )
                    result.steps.append(step)
                    break
                
                # Execute action
                success = await self._execute_action(action, target, value)
                
                # Store step
                step = TestStep(
                    step_number=step_num,
                    action=action,
                    target=target,
                    value=value,
                    reasoning=reasoning,
                    description=description,
                    page_state=page_state,
                    success=success,
                    screenshot=screenshot
                )
                result.steps.append(step)
                
                if not success:
                    # Optional: wait and retry or just continue to next logic step
                    await asyncio.sleep(1)
                
                # Update status
                if callback:
                    await callback(result)
                
                # Small wait between steps
                await asyncio.sleep(1)
            if result.status == "running":
                result.status = "failed"
                result.final_verdict = f"Did not complete within {max_steps} steps"
                
        except Exception as e:
            result.status = "failed"
            result.final_verdict = f"Test error: {str(e)}"
        finally:
            await self._close_browser()
            result.completed_at = datetime.now().isoformat()
        
        return result
    
    def get_test(self, test_id: str) -> Optional[TestResult]:
        """Get a test result by ID."""
        return self.tests.get(test_id)
    
    def to_json(self, result: TestResult) -> Dict:
        """Convert TestResult to JSON-serializable dict."""
        return asdict(result)


# Global instance
tester_agent = TesterAgent()
