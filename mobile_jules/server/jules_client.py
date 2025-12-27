import os
import httpx
import asyncio
from typing import List, Dict, Optional

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
        source_id: str = None,  # Now optional for repoless sessions
        prompt: str = "Start session",
        auto_mode: bool = False,
        starting_branch: str = None,
        title: str = None
    ) -> Dict:
        """Creates a new chat session.
        
        Args:
            source_id: The source (repo) to work with. If None, creates a repoless session.
            prompt: Initial task description
            auto_mode: If True, auto-approve plans and auto-create PRs (only for repo sessions)
            starting_branch: Optional branch to start from (only for repo sessions)
            title: Optional title for the session
        """
        payload = {
            "prompt": prompt,
            "requirePlanApproval": True
        }
        
        if title:
            payload["title"] = title
        
        if source_id:
            # Repo-based session
            payload["sourceContext"] = {"source": source_id}
            if starting_branch:
                payload["sourceContext"]["githubRepoContext"] = {"startingBranch": starting_branch}
            if auto_mode:
                payload["automationMode"] = "AUTO_CREATE_PR"
                payload["requirePlanApproval"] = False
        # For repoless sessions, omit sourceContext entirely
            
        print(f"DEBUG create_session payload: {payload}", flush=True)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/sessions",
                headers=self.headers,
                json=payload
            )
            if not resp.is_success:
                print(f"DEBUG create_session error {resp.status_code}: {resp.text}", flush=True)
            resp.raise_for_status()
            return resp.json()

    async def send_message(self, session_id: str, message: str):
        """Sends a user message to an existing session."""
        # Note: session_id usually comes in full form "sessions/123..."
        # If the API expects just the ID, we might need to parse it, 
        # but the docs show using the full resource name in the URL.
        url = f"{self.base_url}/{session_id}:sendMessage"
        
        payload = {"prompt": message}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=self.headers,
                json=payload
            )
            resp.raise_for_status()
            # The response is usually empty or the updated session object; 
            # we rely on list_activities to get the actual answer.
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

    async def list_activities(self, session_id: str, page_size: int = 30, get_latest: bool = False) -> List[Dict]:
        """Fetches the history of the session (user messages, agent plans/responses).
        
        Args:
            session_id: The session ID
            page_size: Number of activities per request (max 100)
            get_latest: If True, fetches all pages and returns the most recent activities
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
                if not page_token or not get_latest:
                    # If not getting latest, just return first page
                    break
                    
            print(f"DEBUG list_activities: fetched {len(all_activities)} activities total")
            
            if get_latest and len(all_activities) > page_size:
                # Return only the most recent activities
                return all_activities[-page_size:]
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
