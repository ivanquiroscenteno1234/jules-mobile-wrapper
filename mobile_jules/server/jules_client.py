import os
import httpx
import asyncio
import base64
import mimetypes
from typing import List, Dict, Optional

from config import UPLOAD_DIR

def _prepare_image_payload(filename: str) -> Optional[Dict]:
    """Reads an image, base64 encodes it, and returns the payload dict."""
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        print(f"Warning: Image file not found: {filepath}")
        return None
    
    try:
        mime_type, _ = mimetypes.guess_type(filepath)
        if not mime_type or not mime_type.startswith("image/"):
            print(f"Warning: Invalid image MIME type: {mime_type}")
            return None
            
        with open(filepath, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        
        return {
            "image": {
                "inlineData": {
                    "data": encoded_string,
                    "mimeType": mime_type,
                }
            }
        }
    except Exception as e:
        print(f"Error preparing image payload: {e}")
        return None

class JulesClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://jules.googleapis.com/v1alpha"
        self.headers = {
            "X-Goog-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    async def list_sources(self) -> List[Dict]:
        """Lists available sources (GitHub repos)."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/sources", 
                headers=self.headers
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("sources", [])

    async def list_sessions(self, page_size: int = 30) -> List[Dict]:
        """Lists existing sessions."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/sessions",
                headers=self.headers,
                params={"pageSize": page_size}
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("sessions", [])

    async def create_session(
        self, 
        source_id: str = None,
        prompt: str = "Start session",
        image_filename: Optional[str] = None,
        auto_mode: bool = False,
        starting_branch: str = None,
        title: str = None
    ) -> Dict:
        """Creates a new chat session, optionally with an image."""
        payload = {
            "prompt": prompt,
            "requirePlanApproval": True
        }

        if image_filename:
            image_payload = _prepare_image_payload(image_filename)
            if image_payload:
                payload["visualContexts"] = [image_payload]
        
        if title:
            payload["title"] = title
        
        if source_id:
            payload["sourceContext"] = {
                "source": source_id,
                "githubRepoContext": {"startingBranch": starting_branch or "main"}
            }
            if auto_mode:
                payload["automationMode"] = "AUTO_CREATE_PR"
                payload["requirePlanApproval"] = False
            
        print(f"DEBUG create_session payload: {payload}", flush=True)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/sessions",
                headers=self.headers,
                json=payload,
                timeout=60.0 # Increase timeout for uploads
            )
            if not resp.is_success:
                print(f"DEBUG create_session error {resp.status_code}: {resp.text}", flush=True)
            resp.raise_for_status()
            return resp.json()

    async def send_message(self, session_id: str, message: str, image_filename: Optional[str] = None):
        """Sends a user message to an existing session, optionally with an image."""
        url = f"{self.base_url}/{session_id}:sendMessage"
        
        payload = {"prompt": message}
        if image_filename:
            image_payload = _prepare_image_payload(image_filename)
            if image_payload:
                payload["visualContexts"] = [image_payload]

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=60.0 # Increase timeout for uploads
            )
            resp.raise_for_status()
            return resp.json()

    async def get_session(self, session_id: str) -> Dict:
        """Gets a session's current state."""
        url = f"{self.base_url}/{session_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers)
            if not resp.is_success:
                print(f"DEBUG get_session error: {resp.status_code} - {resp.text}")
            resp.raise_for_status()
            return resp.json()

    async def delete_session(self, session_id: str) -> bool:
        """Deletes a session.
        
        Args:
            session_id: The session ID (can be just the ID or full path 'sessions/123...')
        Returns:
            True if deletion was successful
        """
        # Ensure session_id has correct format (sessions/ID)
        if not session_id.startswith("sessions/"):
            session_id = f"sessions/{session_id}"
        
        url = f"{self.base_url}/{session_id}"
        print(f"DEBUG delete_session: calling DELETE {url}", flush=True)
        async with httpx.AsyncClient() as client:
            resp = await client.delete(url, headers=self.headers)
            print(f"DEBUG delete_session: response status={resp.status_code}", flush=True)
            if not resp.is_success:
                print(f"DEBUG delete_session error: {resp.text}", flush=True)
            resp.raise_for_status()
            return True

    async def list_activities(self, session_id: str, page_size: int = 100, get_all: bool = False) -> List[Dict]:
        """Fetches the history of the session (user messages, agent plans/responses).
        
        Args:
            session_id: The session ID
            page_size: Number of activities per request (max 100)
            get_all: If True, fetches ALL pages and returns all activities
        """
        url = f"{self.base_url}/{session_id}/activities"
        all_activities = []
        page_token = None
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params = {"pageSize": min(page_size, 100)}
                if page_token:
                    params["pageToken"] = page_token
                    
                resp = await client.get(
                    url,
                    headers=self.headers,
                    params=params
                )
                if not resp.is_success:
                    print(f"DEBUG list_activities error: {resp.status_code}")
                resp.raise_for_status()
                data = resp.json()
                activities = data.get("activities", [])
                all_activities.extend(activities)
                
                # Check for more pages
                page_token = data.get("nextPageToken")
                if not page_token or not get_all:
                    # If not getting all, just return first page
                    break
                    
            print(f"DEBUG list_activities: fetched {len(all_activities)} activities total")
            
            # Return ALL activities in chronological order
            return all_activities

    async def approve_plan(self, session_id: str) -> Dict:
        """Approves the current plan for a session."""
        url = f"{self.base_url}/{session_id}:approvePlan"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self.headers, json={})
            if not resp.is_success:
                print(f"DEBUG approve_plan error: {resp.status_code} - {resp.text}")
            resp.raise_for_status()
            return resp.json()

    async def submit_branch(self, session_id: str, create_pr: bool = False) -> Dict:
        """The Jules API doesn't support direct publishing via API.
        This method returns info for the client to open Jules Web.
        """
        # We don't perform an API call here because research shows it doesn't exist.
        # Instead we return information for the UI to guide the user.
        return {
            "status": "web_fallback",
            "message": "Publishing must be done through the Jules Web UI or via AUTO_CREATE_PR mode.",
            "url": f"https://jules.google.com/{session_id}" if not session_id.startswith("http") else session_id
        }

# --- MOCK CLIENT FOR TESTING WITHOUT API KEY ---

class MockJulesClient(JulesClient):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.mock_session_id = "sessions/mock-123"
        self.messages = [] # Store chat history

    async def list_sources(self) -> List[Dict]:
        return [
            {
                "name": "sources/github/user/repo-a",
                "id": "github/user/repo-a",
                "githubRepo": {"owner": "user", "repo": "repo-a"}
            },
            {
                "name": "sources/github/user/repo-b",
                "id": "github/user/repo-b",
                "githubRepo": {"owner": "user", "repo": "repo-b"}
            }
        ]

    async def create_session(self, source_id: str, prompt: str = "Start session") -> Dict:
        return {
            "name": self.mock_session_id,
            "id": "mock-123",
            "title": "Mock Session",
            "sourceContext": {"source": source_id}
        }

    async def send_message(self, session_id: str, message: str):
        # Simulate user message
        self.messages.append({
            "name": f"{session_id}/activities/user-{len(self.messages)}",
            "originator": "user",
            "createTime": "2025-01-01T12:00:00Z",
            "text": message # Simplifying structure for mock
        })
        # Simulate agent response
        self.messages.append({
            "name": f"{session_id}/activities/agent-{len(self.messages)}",
            "originator": "agent",
            "createTime": "2025-01-01T12:00:01Z",
            "progressUpdated": {
                "title": "Thinking...",
                "description": f"I received your message: '{message}'. Here is a mock response."
            }
        })
        return {}

    async def list_activities(self, session_id: str, page_size: int = 30) -> List[Dict]:
        return self.messages
