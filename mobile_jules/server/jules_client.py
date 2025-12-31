import os
import httpx
import asyncio
import base64
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
            # Repo-based session - ALWAYS include githubRepoContext with startingBranch
            payload["sourceContext"] = {
                "source": source_id,
                "githubRepoContext": {
                    "startingBranch": starting_branch or "main"
                }
            }
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

    async def send_message(self, session_id: str, message: str, image_filename: Optional[str] = None):
        """Sends a user message to an existing session."""
        url = f"{self.base_url}/{session_id}:sendMessage"
        
        payload = {"prompt": message}

        if image_filename:
            image_path = os.path.join("uploads", image_filename)
            if os.path.exists(image_path):
                try:
                    with open(image_path, "rb") as image_file:
                        encoded_string = base64.b64encode(image_file.read()).decode()
                    
                    payload["visualContexts"] = [
                        {
                            "image": {
                                "data": encoded_string
                            }
                        }
                    ]
                except Exception as e:
                    print(f"Error processing image file: {e}")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=self.headers,
                json=payload
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
                
                page_token = data.get("nextPageToken")
                if not page_token or not get_all:
                    break
                    
            print(f"DEBUG list_activities: fetched {len(all_activities)} activities total")
            
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
        return {
            "status": "web_fallback",
            "message": "Publishing must be done through the Jules Web UI or via AUTO_CREATE_PR mode.",
            "url": f"https://jules.google.com/{session_id}" if not session_id.startswith("http") else session_id
        }
