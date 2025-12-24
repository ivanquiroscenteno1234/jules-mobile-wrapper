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

    async def create_session(self, source_id: str, prompt: str = "Start session") -> Dict:
        """Creates a new chat session."""
        payload = {
            "prompt": prompt,
            "sourceContext": {
                "source": source_id,
                "githubRepoContext": {
                    # Omit startingBranch to let Jules use the repo's default branch
                }
            },
            # Optional: "automationMode": "AUTO_CREATE_PR"
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/sessions",
                headers=self.headers,
                json=payload
            )
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

    async def list_activities(self, session_id: str, page_size: int = 30) -> List[Dict]:
        """Fetches the history of the session (user messages, agent plans/responses)."""
        url = f"{self.base_url}/{session_id}/activities"
        params = {"pageSize": page_size}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers=self.headers,
                params=params
            )
            if not resp.is_success:
                print(f"DEBUG list_activities error: {resp.status_code} - {resp.text}")
            resp.raise_for_status()
            data = resp.json()
            print(f"DEBUG list_activities response: {data}")  # Debug log
            return data.get("activities", [])

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
