from dotenv import load_dotenv
load_dotenv()  # Load .env file if it exists

import os
import json
import asyncio
import uuid
from typing import List, Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, BackgroundTasks
import google.generativeai as genai
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, BackgroundTasks, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Import the Client
from jules_client import JulesClient
from notifications import notification_service, SessionPoller
from tester_agent import tester_agent
from github_client import get_github_client

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
API_KEY = os.environ.get("JULES_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Initialize Gemini for STT
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("WARNING: GEMINI_API_KEY not set. Speech-to-Text will not work.")

# Choose client based on environment
if API_KEY:
    client = JulesClient(api_key=API_KEY)
else:
    print("ERROR: JULES_API_KEY is required. Please set it in your environment.")
    print("Example: $env:JULES_API_KEY = 'your_api_key'")
    import sys
    sys.exit(1)

# Session poller for notifications
session_poller = SessionPoller(client, notification_service)

@app.on_event("startup")
async def startup_event():
    """Start the session polling background task."""
    asyncio.create_task(session_poller.start_polling(interval_seconds=30))
    print("Session Poller started.")

# In-memory storage for completed session changeSet data
# Key: session_id, Value: {source, patch, commit_message, base_commit_id}
completed_session_data: Dict[str, Dict] = {}

# Device registration model
class DeviceRegistration(BaseModel):
    user_id: str
    fcm_token: str

@app.post("/register-device")
async def register_device(reg: DeviceRegistration):
    """Register a device's FCM token for push notifications."""
    notification_service.register_device(reg.user_id, reg.fcm_token)
    return {"success": True}

class Repo(BaseModel):
    name: str
    id: str
    full_name: str

class Session(BaseModel):
    name: str
    id: str
    title: str = ""
    source: str = ""

@app.get("/repos", response_model=List[Repo])
async def list_repos():
    """Lists available GitHub sources from Jules API."""
    try:
        sources = await client.list_sources()
        # Transform Jules Source object to our simple Repo model
        repos = []
        for s in sources:
            # Source name format: "sources/github/owner/repo"
            # We want to extract a friendly name
            friendly_name = s.get("githubRepo", {}).get("repo", "Unknown")
            full_name = f"{s.get('githubRepo', {}).get('owner', '')}/{friendly_name}"
            
            repos.append(Repo(
                name=friendly_name,
                full_name=full_name,
                id=s["name"] # Use the full resource name as ID
            ))
        return repos
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions")
async def list_sessions():
    """Lists existing Jules sessions."""
    try:
        sessions = await client.list_sessions()
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id:path}")
async def get_session(session_id: str):
    """Gets a specific session's details including PR outputs."""
    try:
        session = await client.get_session(session_id)
        
        # Extract PR information from outputs if available
        prs = []
        if "outputs" in session:
            for output in session["outputs"]:
                if "pullRequest" in output:
                    pr = output["pullRequest"]
                    prs.append({
                        "url": pr.get("url"),
                        "title": pr.get("title"),
                        "description": pr.get("description")
                    })
        
        session["pullRequests"] = prs
        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sessions/{session_id:path}/approve")
async def approve_plan(session_id: str):
    """Approves the current plan for a session."""
    try:
        result = await client.approve_plan(session_id)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sessions/{session_id:path}")
async def delete_session(session_id: str):
    """Deletes a session from Jules."""
    try:
        # Ensure session_id has correct format (sessions/ID)
        if not session_id.startswith("sessions/"):
            session_id = f"sessions/{session_id}"
        
        # Call Jules API to delete the session
        url = f"{JULES_API_BASE}/{session_id}"
        print(f"DEBUG delete_session: calling DELETE {url}", flush=True)
        async with httpx.AsyncClient() as http_client:
            response = await http_client.delete(
                url,
                headers={"x-goog-api-key": JULES_API_KEY}
            )
            print(f"DEBUG delete_session: response status={response.status_code}", flush=True)
            if response.status_code == 200 or response.status_code == 204:
                # Also clean up any stored session data
                if session_id in completed_session_data:
                    del completed_session_data[session_id]
                return {"success": True, "message": "Session deleted"}
            else:
                print(f"DEBUG delete_session error: {response.text}", flush=True)
                raise HTTPException(status_code=response.status_code, detail=response.text)
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG delete_session exception: {e}", flush=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sessions/{session_id:path}/publish")
async def publish_branch(session_id: str, create_pr: bool = Query(False)):
    """Publishes the branch (and optionally creates a PR) for a completed session.
    
    Args:
        session_id: The session ID
        create_pr: If True, also creates a pull request
    """
    try:
        result = await client.submit_branch(session_id, create_pr=create_pr)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}/patch")
async def get_session_patch(session_id: str):
    """Returns the patch content for a session (for copying to clipboard).
    
    Args:
        session_id: The session ID
    """
    # Check if we have stored patch data for this session
    if session_id in completed_session_data:
        data = completed_session_data[session_id]
        patch = data.get("patch", "")
        commit_message = data.get("commit_message", "Changes from Jules")
        return {
            "success": True,
            "patch": patch,
            "commitMessage": commit_message,
            "instructions": f"# Apply this patch locally:\n# Save the patch to a file and run:\n# git apply patch.diff\n\n{patch}"
        }
    else:
        raise HTTPException(
            status_code=404, 
            detail="Patch data not found. Session may not have completed or page was refreshed."
        )

@app.get("/repos/{owner}/{repo}/branches")
async def list_repo_branches(owner: str, repo: str):
    """List all branches in a GitHub repository."""
    github_client = get_github_client()
    if not github_client:
        raise HTTPException(
            status_code=500, 
            detail="GITHUB_TOKEN not configured."
        )
    
    try:
        branches = await github_client.list_branches(owner, repo)
        return {"branches": branches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== GitHub Repo Management Endpoints =====

class CreateRepoRequest(BaseModel):
    name: str
    description: str = ""
    private: bool = False

@app.post("/github/repos")
async def create_github_repo(request: CreateRepoRequest):
    """Create a new GitHub repository for the authenticated user."""
    github_client = get_github_client()
    if not github_client:
        raise HTTPException(
            status_code=500, 
            detail="GITHUB_TOKEN not configured. Cannot create repositories."
        )
    
    try:
        repo = await github_client.create_repository(
            name=request.name,
            description=request.description,
            private=request.private,
            auto_init=True  # Always create with README
        )
        return {
            "success": True,
            "name": repo["name"],
            "full_name": repo["full_name"],
            "html_url": repo["html_url"],
            "clone_url": repo["clone_url"],
            "private": repo["private"]
        }
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 422:
            raise HTTPException(status_code=422, detail="Repository name already exists or is invalid")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/github/repos")
async def list_github_repos():
    """List GitHub repositories for the authenticated user."""
    github_client = get_github_client()
    if not github_client:
        raise HTTPException(
            status_code=500, 
            detail="GITHUB_TOKEN not configured."
        )
    
    try:
        repos = await github_client.list_user_repos(per_page=50)
        return {"repos": repos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/github/repos/{owner}/{repo}")
async def delete_github_repo(owner: str, repo: str):
    """Delete a GitHub repository. Requires delete_repo scope on token."""
    github_client = get_github_client()
    if not github_client:
        raise HTTPException(
            status_code=500, 
            detail="GITHUB_TOKEN not configured."
        )
    
    try:
        success = await github_client.delete_repository(owner, repo)
        if success:
            return {"success": True, "message": f"Repository {owner}/{repo} deleted"}
        else:
            raise HTTPException(status_code=404, detail="Repository not found or permission denied")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sessions/{session_id:path}/github-pr")
async def create_github_pr(
    session_id: str,
    base_branch: str = Query("main"),
    branch_only: bool = Query(False)
):
    """Creates a GitHub branch/PR directly using the stored changeSet data.
    
    Args:
        session_id: The session ID
        base_branch: The target branch to base the PR on (default: main)
        branch_only: If True, only create branch without PR
    """
    # Check if we have GitHub client
    github_client = get_github_client()
    if not github_client:
        raise HTTPException(
            status_code=500, 
            detail="GITHUB_TOKEN not configured. Please set the GITHUB_TOKEN environment variable."
        )
    
    # Get the stored changeSet data
    if session_id not in completed_session_data:
        # Try to fetch from session
        try:
            session_data = await client.get_session(session_id)
            activities = await client.list_activities(session_id)
            
            # Find sessionCompleted activity with changeSet
            for activity in reversed(activities):
                if "sessionCompleted" in activity or "artifacts" in activity:
                    for artifact in activity.get("artifacts", []):
                        if "changeSet" in artifact:
                            cs = artifact["changeSet"]
                            completed_session_data[session_id] = {
                                "source": cs.get("source", ""),
                                "patch": cs.get("gitPatch", {}).get("unidiffPatch", ""),
                                "commit_message": cs.get("gitPatch", {}).get("suggestedCommitMessage", "Changes by Jules"),
                                "base_commit_id": cs.get("gitPatch", {}).get("baseCommitId"),
                            }
                            break
                if session_id in completed_session_data:
                    break
        except Exception as e:
            print(f"Error fetching session data: {e}")
    
    if session_id not in completed_session_data:
        raise HTTPException(
            status_code=404, 
            detail="No changeSet data found for this session. The session may not be completed."
        )
    
    data = completed_session_data[session_id]
    
    if not data.get("patch"):
        raise HTTPException(status_code=400, detail="No patch data available for this session.")
    
    # Parse source to get owner/repo
    # Format: sources/github/owner/repo
    source = data["source"]
    parts = source.replace("sources/github/", "").split("/")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail=f"Invalid source format: {source}")
    
    owner = parts[0]
    repo = parts[1]
    
    try:
        result = await github_client.create_pr_from_patch(
            owner=owner,
            repo=repo,
            patch=data["patch"],
            commit_message=data["commit_message"],
            base_branch=base_branch,
            base_commit_id=data.get("base_commit_id"),
            branch_only=branch_only,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Repoless WebSocket endpoint - no source_id required
@app.websocket("/chat")
async def websocket_repoless_endpoint(
    websocket: WebSocket, 
    session_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None)
):
    """WebSocket endpoint for repoless sessions (No Codebase mode)."""
    await _handle_websocket(
        websocket=websocket,
        source_id=None,  # Repoless
        session_id=session_id,
        auto_mode=False,  # Repoless sessions don't support auto-PR
        user_id=user_id
    )

# Repo-based WebSocket endpoint
@app.websocket("/chat/{source_id:path}")
async def websocket_endpoint(
    websocket: WebSocket, 
    source_id: str, 
    session_id: Optional[str] = Query(None),
    auto_mode: bool = Query(False),
    user_id: Optional[str] = Query(None)
):
    """WebSocket endpoint for repo-based sessions."""
    await _handle_websocket(
        websocket=websocket,
        source_id=source_id,
        session_id=session_id,
        auto_mode=auto_mode,
        user_id=user_id
    )

async def _handle_websocket(
    websocket: WebSocket, 
    source_id: Optional[str],  # None for repoless
    session_id: Optional[str] = None,
    auto_mode: bool = False,
    user_id: Optional[str] = None
):
    await websocket.accept()
    
    # Track which activities we've already sent to the client
    seen_activity_ids = set()
    poller_task = None
    active_session_id = session_id  # Will be set when session is created/reconnected
    
    async def poll_jules():
        """Background task to poll for new messages/activities from Jules."""
        cached_session_data = None
        while active_session_id:
            try:
                activities = await client.list_activities(active_session_id)
                for activity in activities:
                    act_id = activity.get("id") or activity.get("name")
                    if act_id not in seen_activity_ids:
                        seen_activity_ids.add(act_id)
                        
                        # For sessionCompleted, fetch fresh session data for PR info
                        if "sessionCompleted" in activity:
                            try:
                                cached_session_data = await client.get_session(active_session_id)
                            except Exception as e:
                                print(f"Error fetching session data: {e}")
                        
                        # Parse activity to structured JSON, passing session data
                        parsed = parse_activity(activity, session_data=cached_session_data)
                        if parsed:
                            await websocket.send_json(parsed)
                
                await asyncio.sleep(2)  # Poll every 2 seconds
            except Exception as e:
                print(f"Polling error: {e}")
                await asyncio.sleep(5)
    
    try:
        if session_id:
            # Reconnecting to existing session
            print(f"DEBUG: Reconnecting to session {session_id}", flush=True)
            session_data = await client.get_session(session_id)
            active_session_id = session_id
            
            # Link session with user for notifications
            if user_id:
                session_poller.track_session(user_id, session_id)
                print(f"Tracking reconnecting session {session_id} for user {user_id}")
            
            # Debug: Check what's in session_data
            print(f"DEBUG: session_data keys: {list(session_data.keys()) if session_data else 'None'}", flush=True)
            if session_data and "outputs" in session_data:
                print(f"DEBUG: session_data.outputs: {session_data['outputs']}", flush=True)
            else:
                print(f"DEBUG: session_data has NO outputs field", flush=True)
            
            # Send connection confirmation
            await websocket.send_json({
                "type": "system",
                "content": "Reconnected to session",
                "sessionId": session_id
            })
            
            # IMPORTANT: Immediately fetch and send latest activities (history)
            print(f"DEBUG: Loading session history...", flush=True)
            try:
                # Fetch ALL activities for the session
                activities = await client.list_activities(session_id, page_size=100, get_all=True)
                print(f"DEBUG: Found {len(activities)} historical activities", flush=True)
                
                # Send activities in order (already chronological - oldest first for display)
                for activity in activities:
                    act_id = activity.get("id") or activity.get("name")
                    if act_id:
                        seen_activity_ids.add(act_id)
                        parsed = parse_activity(activity, session_data=session_data)
                        if parsed:
                            await websocket.send_json(parsed)
                
                await websocket.send_json({
                    "type": "system",
                    "content": f"Loaded {len(activities)} recent activities"
                })
            except Exception as e:
                print(f"Error loading history: {e}")
                await websocket.send_json({
                    "type": "system", 
                    "content": f"Warning: Could not load full history"
                })
            
            # Now start polling for NEW activities
            poller_task = asyncio.create_task(poll_jules())
        else:
            # NEW: Don't create session yet - wait for user's first message
            # Send a ready message to the client
            await websocket.send_json({
                "type": "system",
                "content": "Ready! Send your task to start working.",
                "status": "waiting_for_task"
            })
            print(f"DEBUG: Waiting for user's first message to create session for source {source_id}")
        
    except Exception as e:
        await websocket.send_json({"type": "error", "content": str(e)})
        await websocket.close()
        return

    try:
        while True:
            # Wait for user message from phone
            data = await websocket.receive_text()
            
            # If no session yet, create one with this message as the task
            if not active_session_id:
                try:
                    await websocket.send_json({
                        "type": "status",
                        "content": "Creating session and sending task to Jules..."
                    })
                    
                    # Create session with user's message as the actual task
                    session_data = await client.create_session(
                        source_id=source_id, 
                        prompt=data,  # User's first message becomes the task
                        auto_mode=auto_mode
                    )
                    print(f"DEBUG: Created session with task: {data[:50]}...")
                    
                    # Extract session_id from response
                    active_session_id = session_data.get("name")
                    if not active_session_id:
                        raw_id = session_data.get("id", "")
                        active_session_id = f"sessions/{raw_id}" if raw_id else None
                    
                    if not active_session_id:
                        await websocket.send_json({"type": "error", "content": "Could not create session"})
                        continue
                    
                    # Track new session for notifications
                    if user_id:
                        session_poller.track_session(user_id, active_session_id)
                        print(f"Tracking new session {active_session_id} for user {user_id}")
                    
                    # Send confirmation
                    await websocket.send_json({
                        "type": "system",
                        "content": "Session created! Jules is working on your task.",
                        "sessionId": active_session_id
                    })
                    
                    # Start polling for this session
                    poller_task = asyncio.create_task(poll_jules())
                    
                except Exception as e:
                    await websocket.send_json({"type": "error", "content": f"Failed to create session: {e}"})
                    
            else:
                # Session already exists, handle commands or send messages
                if data.startswith("/approve"):
                    await client.approve_plan(active_session_id)
                    await websocket.send_json({"type": "system", "content": "Plan approved!"})
                else:
                    # Send regular message to Jules
                    await client.send_message(active_session_id, data)
            # The poller will pick up the response
    except WebSocketDisconnect:
        print(f"Client disconnected")
    finally:
        if 'poller_task' in dir() and poller_task:
            poller_task.cancel()

def parse_activity(activity: Dict, session_data: Dict = None) -> Dict:
    """Converts a Jules Activity JSON into a structured dict for the Flutter app.
    
    Args:
        activity: The activity dict from Jules API
        session_data: Optional session dict containing outputs[] with PR info
    """
    # Debug: Log all activity keys to understand structure
    act_keys = [k for k in activity.keys() if k not in {"name", "id", "createTime", "originator"}]
    if act_keys:
        print(f"DEBUG parse_activity: keys={act_keys}, has_artifacts={'artifacts' in activity}", flush=True)
    
    result = {
        "id": activity.get("id") or activity.get("name"),
        "type": "message",
        "originator": activity.get("originator", "agent"),
        "timestamp": activity.get("createTime"),
    }
    
    # Skip user activities UNLESS it's a userMessaged activity (we want to show those)
    if result["originator"] == "user" and "userMessaged" not in activity:
        return None
    
    # Plan Generated - show expandable steps
    if "planGenerated" in activity:
        plan_data = activity["planGenerated"].get("plan", {})
        result["type"] = "plan"
        result["planId"] = plan_data.get("id")
        result["steps"] = [
            {"id": s.get("id"), "title": s.get("title"), "index": s.get("index", i)}
            for i, s in enumerate(plan_data.get("steps", []))
        ]
        result["content"] = f"Plan with {len(result['steps'])} steps"
        return result
    
    # Plan Approved
    if "planApproved" in activity:
        result["type"] = "plan_approved"
        result["content"] = "Plan approved"
        return result
    
    # Agent Message
    if "agentMessaged" in activity:
        msg = activity["agentMessaged"]
        result["type"] = "message"
        result["content"] = msg.get("agentMessage") or msg.get("text") or msg.get("message", "")
        return result
    
    # User Message (user's chat messages)
    if "userMessaged" in activity:
        # Log the full activity to find the correct field
        print(f"DEBUG userMessaged FOUND: full activity keys = {list(activity.keys())}", flush=True)
        print(f"DEBUG userMessaged value: {activity['userMessaged']}", flush=True)
        msg = activity["userMessaged"]
        message_content = msg.get("userMessage") or msg.get("text") or msg.get("message") or msg.get("content", "")
        if message_content:
            result["type"] = "user"
            result["originator"] = "user"
            result["content"] = message_content
            print(f"DEBUG userMessaged: returning user message = '{message_content[:50]}...'", flush=True)
            return result
        else:
            print(f"DEBUG userMessaged: message_content was empty, msg={msg}", flush=True)
    
    # Text output / thought / summary from agent
    if "textGenerated" in activity:
        tg = activity["textGenerated"]
        result["type"] = "message"
        result["content"] = tg.get("text") or tg.get("content", "")
        return result
    
    # Generic text field (some activities have this)
    if "text" in activity and isinstance(activity["text"], str):
        result["type"] = "message"
        result["content"] = activity["text"]
        return result
    
    # Thought or summary messages
    if "thought" in activity:
        result["type"] = "message"
        result["content"] = activity["thought"].get("text") or activity["thought"].get("content", "")
        return result
    
    # Summary message
    if "summary" in activity and isinstance(activity["summary"], str):
        result["type"] = "message"
        result["content"] = activity["summary"]
        return result
    
    # Progress Update - DON'T return early if artifacts exist
    if "progressUpdated" in activity:
        progress = activity["progressUpdated"]
        result["type"] = "progress"
        result["title"] = progress.get("title", "")
        result["description"] = progress.get("description", "")
        result["content"] = result["title"]
        # Only return early if there are NO artifacts
        if "artifacts" not in activity:
            return result
    
    # Session Completed
    if "sessionCompleted" in activity:
        # Extract Jules session web URL
        jules_url = session_data.get("url") if session_data else None
        session_id = session_data.get("id") if session_data else activity.get("name", "").split("/activities/")[0]
        if not jules_url and session_id:
            jules_url = f"https://jules.google.com/{session_id}"
            
        # Try to find changeSet in artifacts
        artifacts = activity.get("artifacts", [])
        print(f"DEBUG sessionCompleted: session_id={session_id}, num_artifacts={len(artifacts)}")
        for i, art in enumerate(artifacts):
            print(f"DEBUG sessionCompleted artifact {i}: keys={list(art.keys())}")
        
        change_set = {}
        for artifact in artifacts:
            if "changeSet" in artifact:
                change_set = artifact["changeSet"]
                break
        
        # Store changeSet data for GitHub PR creation
        if change_set and session_id:
            git_patch = change_set.get("gitPatch", {})
            completed_session_data[session_id] = {
                "source": change_set.get("source", ""),
                "patch": git_patch.get("unidiffPatch", ""),
                "commit_message": git_patch.get("suggestedCommitMessage", "Changes by Jules"),
                "base_commit_id": git_patch.get("baseCommitId"),
            }
            print(f"DEBUG Stored changeSet for session {session_id}")
        
        # Extract info from changeSet (available during live sessions)
        commit_message = change_set.get("gitPatch", {}).get("suggestedCommitMessage", "Changes by Jules")
        
        # Try to extract the branch from outputs or changeSet
        outputs = session_data.get("outputs", []) if session_data else []
        pr_url = None
        for output in outputs:
            if "pullRequest" in output:
                pr_url = output["pullRequest"].get("url")
                break
        
        repo_name = ""
        source = ""
        if session_data:
            source = session_data.get("sourceContext", {}).get("source", "")
            repo_name = source.split("/")[-1]
        
        # Check if we have patch data (for the "Create PR" button)
        has_patch = bool(change_set.get("gitPatch", {}).get("unidiffPatch"))
        
        response = {
            "id": result["id"],
            "timestamp": result["timestamp"],
            "originator": "agent",
            "type": "completed",
            "message": "Task completed! Check the details below.",
            "title": "PR Review Card",
            "description": commit_message,
            "pullRequestUrl": pr_url,
            "julesUrl": jules_url,
            "repoName": repo_name,
            "hasPatch": has_patch,
            "sessionId": session_id,
        }
        print(f"DEBUG sessionCompleted response: hasPatch={has_patch}, sessionId={session_id}, pr_url={pr_url}")
        return response
    
    # Session Progress (status updates)
    if "sessionProgress" in activity:
        progress = activity["sessionProgress"]
        result["type"] = "status"
        result["content"] = progress.get("status") or progress.get("message", "Working...")
        return result
    
    # Agent Messaged (Jules' text/chat responses)
    if "agentMessaged" in activity:
        agent_msg = activity["agentMessaged"]
        message = agent_msg.get("message") or agent_msg.get("text") or agent_msg.get("content", "")
        if message:
            result["type"] = "message"
            result["originator"] = "agent"
            result["content"] = message
            return result
    
    
    # Tool Called (commands executed)
    if "toolCalled" in activity:
        tool = activity["toolCalled"]
        tool_name = tool.get("name", "")
        tool_input = tool.get("input", {})
        
        # Extract command if it's a bash/shell tool
        command = tool_input.get("command") or tool_input.get("cmd") or ""
        if command:
            result["type"] = "artifact"
            result["content"] = f"Ran: {command}"
            return result
        elif tool_name:
            result["type"] = "artifact"
            result["content"] = f"Tool: {tool_name}"
            return result
    
    # Step Updated (plan step progress)
    if "stepUpdated" in activity:
        step = activity["stepUpdated"]
        title = step.get("title") or step.get("description") or ""
        status = step.get("status", "")
        if title:
            result["type"] = "progress"
            result["title"] = title
            result["content"] = f"{status}: {title}" if status else title
            return result
    
    # Task Started/Completed
    if "taskStarted" in activity:
        task = activity["taskStarted"]
        result["type"] = "status"
        result["content"] = task.get("description") or task.get("title") or "Task started"
        return result
    
    # Command Executed (another potential format)
    if "commandExecuted" in activity:
        cmd = activity["commandExecuted"]
        command = cmd.get("command") or cmd.get("cmd", "")
        if command:
            result["type"] = "artifact"
            result["content"] = f"Ran: {command}"
            return result
    
    # Handle artifacts (file changes, bash output)
    if "artifacts" in activity:
        result["artifacts"] = []
        content_parts = []
        
        # Debug: Log what artifacts we're getting
        for i, art in enumerate(activity["artifacts"]):
            art_keys = list(art.keys())
            print(f"DEBUG: Artifact {i} keys: {art_keys}", flush=True)
        
        for art in activity["artifacts"]:
            if "changeSet" in art:
                cs = art["changeSet"]
                git_patch = cs.get("gitPatch", {})
                unidiff = git_patch.get("unidiffPatch", "")
                
                # Extract file paths from the unidiff patch (lines starting with +++ b/ or --- a/)
                file_paths = []
                for line in unidiff.split("\n"):
                    # Handle "+++ b/path/file.tsx" format
                    if line.startswith("+++ b/"):
                        path = line[6:].strip()  # Skip "+++ b/" prefix
                        if path and path != "/dev/null" and path not in file_paths:
                            file_paths.append(path)
                    # Handle "--- a/path/file.tsx" format  
                    elif line.startswith("--- a/"):
                        path = line[6:].strip()  # Skip "--- a/" prefix
                        if path and path != "/dev/null" and path not in file_paths:
                            file_paths.append(path)
                    # Handle "+++ path/file.tsx" format (no a/b prefix)
                    elif line.startswith("+++ ") and not line.startswith("+++\t"):
                        path = line[4:].strip()
                        if path and path != "/dev/null" and path not in file_paths:
                            file_paths.append(path)
                    elif line.startswith("--- ") and not line.startswith("---\t"):
                        path = line[4:].strip()
                        if path and path != "/dev/null" and path not in file_paths:
                            file_paths.append(path)
                
                # Use extracted file paths or fall back to commit message
                if file_paths:
                    for fp in file_paths:
                        content_parts.append(f"Updated: {fp}")
                    result["artifacts"].append({
                        "type": "file_change",
                        "files": file_paths,
                        "patch": unidiff,
                        "commitMsg": git_patch.get("suggestedCommitMessage", "")
                    })
                else:
                    commit_msg = git_patch.get("suggestedCommitMessage", "File updated")
                    result["artifacts"].append({
                        "type": "file_change",
                        "patch": unidiff,
                        "commitMsg": commit_msg
                    })
                    content_parts.append(f"Updated: {commit_msg}")
            
            # Handle fileUpdated artifacts (single file updates)
            elif "fileUpdated" in art:
                fu = art["fileUpdated"]
                file_path = fu.get("path", "") or fu.get("filePath", "")
                if file_path:
                    content_parts.append(f"Updated: {file_path}")
                    result["artifacts"].append({
                        "type": "file_change",
                        "files": [file_path],
                        "patch": fu.get("content", "")
                    })
                    
            elif "bashOutput" in art:
                command = art["bashOutput"].get("command", "")
                output = art["bashOutput"].get("output", "")
                print(f"DEBUG: BashOutput found - command: {command[:50] if command else 'EMPTY'}")
                result["artifacts"].append({
                    "type": "bash",
                    "command": command,
                    "output": output
                })
                if command:
                    content_parts.append(f"Ran: {command}")
                    
            elif "media" in art:
                result["artifacts"].append({
                    "type": "media",
                    "mimeType": art["media"].get("mimeType", "")
                })
                content_parts.append("Generated media")
            else:
                # Unknown artifact type - log it
                print(f"DEBUG: Unknown artifact type with keys: {list(art.keys())}")
        
        # Set content from artifacts if we found any
        if content_parts:
            result["type"] = "artifact"
            result["content"] = "\n".join(content_parts)
            return result
        elif result["artifacts"]:
            # We have artifacts but no content - something went wrong
            print(f"DEBUG: Artifacts parsed but no content generated. Count: {len(result['artifacts'])}")
    
    # Default fallback
    if "content" not in result:
        # Try to extract any text from the activity
        result["content"] = (
            activity.get("description") or 
            activity.get("text") or 
            activity.get("message") or
            ""
        )
    
    # Skip completely empty activities
    if not result.get("content") and not result.get("artifacts"):
        # Log unhandled activity types for debugging
        known_keys = {"id", "name", "createTime", "originator"}
        unknown_keys = [k for k in activity.keys() if k not in known_keys]
        if unknown_keys:
            print(f"DEBUG: Unhandled activity keys: {unknown_keys}")
        return None
    

    return result

# ===== Tester Agent Endpoints =====

class TestRequest(BaseModel):
    url: str
    objective: str

@app.post("/test/start")
async def start_test(request: TestRequest, background_tasks: BackgroundTasks):
    """Start a new test with the Tester Agent."""
    test_id = str(uuid.uuid4())[:8]
    
    async def run_test():
        await tester_agent.run_test(test_id, request.url, request.objective)
    
    background_tasks.add_task(asyncio.create_task, run_test())
    
    return {
        "test_id": test_id,
        "status": "started",
        "url": request.url,
        "objective": request.objective
    }

@app.get("/test/status/{test_id}")
async def get_test_status(test_id: str):
    """Get the status and results of a test."""
    result = tester_agent.get_test(test_id)
    if not result:
        raise HTTPException(status_code=404, detail="Test not found")
    return tester_agent.to_json(result)

@app.get("/tests")
async def list_tests():
    """List all tests."""
    return [tester_agent.to_json(t) for t in tester_agent.tests.values()]

# ===== Speech to Text Endpoints =====

@app.post("/stt")
async def speech_to_text(file: UploadFile = File(...)):
    """Transcribe an audio file using Gemini 3 Flash with thinking."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured on server")
    
    try:
        # Save temporary file
        temp_filename = f"temp_{uuid.uuid4()}.{file.filename.split('.')[-1]}"
        with open(temp_filename, "wb") as buffer:
            buffer.write(await file.read())
        
        # Using Gemini 3 Flash with thinking_level="medium"
        # Requires google-genai >= 1.51.0
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Upload file to Gemini
        myfile = client.files.upload(file=temp_filename)
        
        # Generate transcription with medium thinking level
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                "Transcribe this audio accurately. Only return the transcribed text, nothing else.",
                myfile
            ],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="medium")
            )
        )
        
        # Cleanup
        os.remove(temp_filename)
        
        return {"text": response.text.strip()}
    
    except Exception as e:
        print(f"STT Error: {e}")
        if 'temp_filename' in locals() and os.path.exists(temp_filename):
            os.remove(temp_filename)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

if __name__ == "__main__":
    # Attempt to start ngrok for easier mobile testing
    try:
        from pyngrok import ngrok

        # Open a HTTP tunnel on the default port 8000
        # <NgrokTunnel: "http://<public_sub>.ngrok.io" -> "http://localhost:8000">
        http_tunnel = ngrok.connect(8000)
        public_url = http_tunnel.public_url
        print("\n" + "="*60)
        print(f"NGROK TUNNEL STARTED: {public_url}")
        print("Use this URL in your Mobile App Settings!")
        print("="*60 + "\n")
    except ImportError:
        print("Warning: 'pyngrok' not installed. Skipping auto-tunnel.")
    except Exception as e:
        print(f"Warning: Could not start ngrok: {e}")

    uvicorn.run(app, host="0.0.0.0", port=8000)
