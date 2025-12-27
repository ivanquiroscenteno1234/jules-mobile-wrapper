"""
Tester Agent - AI-powered web application testing

Uses Gemini for reasoning and Playwright for browser automation.
The agent takes screenshots, analyzes them, and decides what actions to take
to verify that a web application works correctly.

Requires:
- GEMINI_API_KEY environment variable
- playwright package (pip install playwright && playwright install)
"""

import os
import json
import asyncio
import base64
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import httpx


@dataclass
class TestStep:
    """A single step in the test execution."""
    step_number: int
    action: str  # screenshot, click, type, scroll, assert, navigate
    target: Optional[str] = None  # CSS selector or text
    value: Optional[str] = None  # Value to type or assertion
    reasoning: str = ""
    success: bool = True
    screenshot_b64: Optional[str] = None
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
    """AI-powered web testing agent using Gemini and Playwright."""
    
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            print("WARNING: GEMINI_API_KEY not set. Tester Agent will not work.")
        
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        self.browser = None
        self.page = None
        self.tests: Dict[str, TestResult] = {}
    
    async def _init_browser(self):
        """Initialize Playwright browser."""
        try:
            from playwright.async_api import async_playwright
            
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
            await self.page.set_viewport_size({"width": 1280, "height": 720})
            return True
        except ImportError:
            print("Playwright not installed. Run: pip install playwright && playwright install")
            return False
        except Exception as e:
            print(f"Browser init error: {e}")
            return False
    
    async def _close_browser(self):
        """Close the browser."""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    async def _take_screenshot(self) -> str:
        """Take a screenshot and return as base64."""
        screenshot_bytes = await self.page.screenshot(type="png")
        return base64.b64encode(screenshot_bytes).decode()
    
    async def _ask_gemini(self, screenshot_b64: str, objective: str, history: List[TestStep]) -> Dict:
        """Ask Gemini what to do next based on screenshot and objective."""
        
        # Build history context
        history_text = ""
        for step in history[-5:]:  # Last 5 steps for context
            history_text += f"Step {step.step_number}: {step.action}"
            if step.target:
                history_text += f" on '{step.target}'"
            history_text += f" - {step.reasoning}\n"
        
        prompt = f"""You are a web application tester. Analyze this screenshot and determine the next action to achieve the test objective.

TEST OBJECTIVE: {objective}

PREVIOUS ACTIONS:
{history_text if history_text else "None - this is the first step"}

Based on the screenshot, respond with a JSON object containing:
{{
    "reasoning": "Brief explanation of what you see and why you're taking this action",
    "action": "One of: click, type, scroll, assert_text, assert_element, navigate, wait, done",
    "target": "CSS selector or visible text to click/type into (null if not applicable)",
    "value": "Text to type, URL to navigate to, or text to assert (null if not applicable)",
    "confidence": 0.0-1.0 confidence this will help achieve the objective,
    "is_objective_met": true/false whether the test objective appears to be met
}}

IMPORTANT RULES:
- Use clear CSS selectors like "button.submit", "#login-form input[type=email]", etc.
- For clicking text links, use the visible text as target
- If the objective is met, set action to "done" and is_objective_met to true
- If stuck after 10+ steps, set action to "done" with is_objective_met to false
- Be specific with selectors to avoid clicking wrong elements

Respond ONLY with the JSON object, no markdown or explanation."""

        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": screenshot_b64
                        }
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1000
            }
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.gemini_url}?key={self.api_key}",
                headers=headers,
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
        
        # Extract text from response
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        
        # Parse JSON from response (might be wrapped in ```json blocks)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        
        return json.loads(text)
    
    async def _execute_action(self, action: str, target: Optional[str], value: Optional[str]) -> bool:
        """Execute a browser action. Returns True if successful."""
        try:
            if action == "click":
                if target:
                    # Try CSS selector first, then text
                    try:
                        await self.page.click(target, timeout=5000)
                    except:
                        await self.page.get_by_text(target).click(timeout=5000)
                        
            elif action == "type":
                if target and value:
                    try:
                        await self.page.fill(target, value)
                    except:
                        await self.page.get_by_placeholder(target).fill(value)
                        
            elif action == "scroll":
                await self.page.evaluate("window.scrollBy(0, 300)")
                
            elif action == "navigate":
                if value:
                    await self.page.goto(value, timeout=30000)
                    
            elif action == "wait":
                await asyncio.sleep(2)
                
            elif action == "assert_text":
                if value:
                    await self.page.wait_for_selector(f"text={value}", timeout=5000)
                    
            elif action == "assert_element":
                if target:
                    await self.page.wait_for_selector(target, timeout=5000)
            
            await asyncio.sleep(0.5)  # Small delay after action
            return True
            
        except Exception as e:
            print(f"Action error: {e}")
            return False
    
    async def run_test(self, test_id: str, url: str, objective: str, callback=None) -> TestResult:
        """Run a test against a URL with a natural language objective.
        
        Args:
            test_id: Unique identifier for this test
            url: URL to test
            objective: Natural language description of what to test
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
            # Navigate to URL
            await self.page.goto(url, timeout=30000)
            await asyncio.sleep(1)
            
            max_steps = 15
            for step_num in range(1, max_steps + 1):
                # Take screenshot
                screenshot = await self._take_screenshot()
                
                # Ask Gemini what to do
                try:
                    gemini_response = await self._ask_gemini(screenshot, objective, result.steps)
                except Exception as e:
                    step = TestStep(
                        step_number=step_num,
                        action="error",
                        reasoning=f"Gemini error: {str(e)}",
                        success=False,
                        screenshot_b64=screenshot[:100] + "..."  # Truncated for storage
                    )
                    result.steps.append(step)
                    break
                
                # Create step record
                step = TestStep(
                    step_number=step_num,
                    action=gemini_response.get("action", "unknown"),
                    target=gemini_response.get("target"),
                    value=gemini_response.get("value"),
                    reasoning=gemini_response.get("reasoning", ""),
                    screenshot_b64=screenshot[:100] + "..."  # Truncated
                )
                
                # Check if done
                if gemini_response.get("action") == "done":
                    step.success = True
                    result.steps.append(step)
                    
                    if gemini_response.get("is_objective_met"):
                        result.status = "passed"
                        result.final_verdict = "Test objective achieved"
                    else:
                        result.status = "failed"
                        result.final_verdict = gemini_response.get("reasoning", "Objective not met")
                    break
                
                # Execute action
                success = await self._execute_action(
                    gemini_response.get("action"),
                    gemini_response.get("target"),
                    gemini_response.get("value")
                )
                step.success = success
                if not success:
                    step.error = "Action failed to execute"
                
                result.steps.append(step)
                
                # Callback for real-time updates
                if callback:
                    await callback(step)
            
            # If we hit max steps without completing
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
