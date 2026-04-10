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

from contextlib import asynccontextmanager

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the session polling background task."""
    asyncio.create_task(session_poller.start_polling(interval_seconds=30))
    print("Session Poller started.")
    yield

allowed_origins_env = os.environ.get("ALLOWED_ORIGINS")
if allowed_origins_env:
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
else:
    allowed_origins = [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for completed session changeSet data
# Key: session_id, Value: {source, patch, commit_message, base_commit_id}
completed_session_data: Dict[str, Dict] = {}

# Track seen files per session - persists across reconnections
# Key: session_id, Value: set of file paths already reported
session_seen_files: Dict[str, set] = {}

# Credentials storage
CREDENTIALS_FILE = "credentials.json"
SECRET_KEY_FILE = "secret.key"

def get_encryption_key():
    if os.path.exists(SECRET_KEY_FILE):
        with open(SECRET_KEY_FILE, "rb") as f:
            return f.read()
    else:
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        with open(SECRET_KEY_FILE, "wb") as f:
            f.write(key)
        return key

try:
    from cryptography.fernet import Fernet
    cipher_suite = Fernet(get_encryption_key())
except ImportError:
    print("Warning: 'cryptography' not installed. Password encryption disabled.")
    cipher_suite = None

def encrypt_password(password: str) -> str:
    if not password or not cipher_suite: return password
    return cipher_suite.encrypt(password.encode()).decode()

def decrypt_password(token: str) -> str:
    if not token or not cipher_suite: return token
    try:
        return cipher_suite.decrypt(token.encode()).decode()
    except:
        # If decryption fails, it might be plain text from before encryption was added
        return token

def load_credentials() -> Dict[str, List[Dict]]:
    """Load credentials from JSON file."""
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_credentials(data: Dict[str, List[Dict]]):
    """Save credentials to JSON file."""
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# In-memory cache
credentials_data: Dict[str, List[Dict]] = load_credentials()

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
        await client.delete_session(session_id)
        # Also clean up any stored session data
        full_session_id = session_id if session_id.startswith("sessions/") else f"sessions/{session_id}"
        if full_session_id in completed_session_data:
            del completed_session_data[full_session_id]
        return {"success": True, "message": "Session deleted"}
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

# Helper functions for diff extraction
def extract_diff_from_activities(activities: List[Dict]) -> str:
    """Parse activities to find code diffs."""
    for activity in activities:
        # Look for changeSet, fileChanges, or diff fields
        if "changeSet" in activity:
            change_set = activity["changeSet"]
            if isinstance(change_set, dict):
                return change_set.get("patch", "") or change_set.get("diff", "")
        if "fileChanges" in activity:
            changes = activity["fileChanges"]
            if isinstance(changes, list):
                return "\n".join([f"File: {c.get('path', 'unknown')}\n{c.get('diff', '')}" for c in changes])
        # Check for code artifacts
        if "codeArtifact" in activity:
            artifact = activity["codeArtifact"]
            if isinstance(artifact, dict) and "content" in artifact:
                return artifact["content"]
    return ""

def get_jules_branch(session: Dict) -> Optional[str]:
    """Extract the branch name Jules created."""
    for output in session.get("outputs", []):
        if "branch" in output:
            branch_info = output["branch"]
            if isinstance(branch_info, dict):
                return branch_info.get("name")
            return str(branch_info)
        if "pullRequest" in output:
            pr_info = output["pullRequest"]
            if isinstance(pr_info, dict):
                return pr_info.get("headBranch") or pr_info.get("head", {}).get("ref")
    return None

def get_repo_info(session: Dict) -> tuple:
    """Extract owner/repo from session source context."""
    source = session.get("sourceContext", {}).get("source", "")
    # Format: sources/github/owner/repo
    parts = source.split("/")
    if len(parts) >= 4 and parts[1] == "github":
        return parts[2], parts[3]
    return None, None

@app.post("/sessions/{session_id}/generate-test")
async def generate_test_from_session(session_id: str, pr_url: Optional[str] = Query(None)):
    """Generate test steps from a session's code changes.
    
    Priority order:
    1. Use pr_url directly if provided
    2. Extract diff from Jules activities
    3. Fallback to GitHub compare API (if branch/PR exists)
    4. Return error prompting PR creation
    """
    try:
        # Ensure session_id has proper prefix
        if not session_id.startswith("sessions/"):
            session_id = f"sessions/{session_id}"
        
        # Get session details
        session = await client.get_session(session_id)
        
        diff = ""
        instructions = ""
        file_list = []
        
        # Step 0: Use pr_url directly if provided by client
        if pr_url:
            print(f"🔍 Using provided PR URL: {pr_url}", flush=True)
            try:
                import re
                match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
                if match:
                    pr_owner, pr_repo, pr_number = match.groups()
                    github_client = get_github_client()
                    if github_client:
                        diff = await github_client.get_pr_diff(pr_owner, pr_repo, int(pr_number))
                        if diff:
                            print(f"✅ Found diff from provided PR #{pr_number} ({len(diff)} chars)", flush=True)
            except Exception as e:
                print(f"⚠️ Failed to fetch diff from provided PR: {e}", flush=True)
        
        # Step 1: Try to get diff from activities
        if not diff:
            print(f"🔍 Fetching activities for {session_id}...", flush=True)
            activities = await client.list_activities(session_id, get_all=True)
            diff = extract_diff_from_activities(activities)
        
        if diff:
            print(f"✅ Found diff in activities ({len(diff)} chars)", flush=True)
        
        # Step 2: If no diff from activities, try stored data
        if not diff:
            full_session_id = session_id if session_id.startswith("sessions/") else f"sessions/{session_id}"
            if full_session_id in completed_session_data:
                data = completed_session_data[full_session_id]
                diff = data.get("patch", "")
                if diff:
                    print(f"✅ Found diff in stored data ({len(diff)} chars)", flush=True)
        
        # Step 3: If still no diff, try GitHub compare
        if not diff:
            branch = get_jules_branch(session)
            owner, repo = get_repo_info(session)
            if branch and owner and repo:
                print(f"🔍 Trying GitHub compare: {owner}/{repo} main...{branch}", flush=True)
                try:
                    github_client = get_github_client()
                    if github_client:
                        diff = await github_client.get_branch_diff(owner, repo, "main", branch)
                        if diff:
                            print(f"✅ Found diff from GitHub ({len(diff)} chars)", flush=True)
                except Exception as e:
                    print(f"⚠️ GitHub compare failed: {e}", flush=True)
        
        # Step 4: Try to get diff from PR if URL is available in session outputs
        if not diff:
            pr_url = None
            for output in session.get("outputs", []):
                if "pullRequest" in output:
                    pr_url = output["pullRequest"].get("url")
                    break
            
            if pr_url:
                print(f"🔍 Trying to fetch diff from PR: {pr_url}", flush=True)
                try:
                    # Parse PR URL: https://github.com/{owner}/{repo}/pull/{number}
                    import re
                    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
                    if match:
                        pr_owner, pr_repo, pr_number = match.groups()
                        github_client = get_github_client()
                        if github_client:
                            diff = await github_client.get_pr_diff(pr_owner, pr_repo, int(pr_number))
                            if diff:
                                print(f"✅ Found diff from PR #{pr_number} ({len(diff)} chars)", flush=True)
                except Exception as e:
                    print(f"⚠️ PR diff fetch failed: {e}", flush=True)
        
        # Get instructions from session for context
        if "userRequest" in session:
            instructions = session["userRequest"].get("text", "")
        title = session.get("title", "")
        context = instructions or title or "Verify the application works correctly"
        
        # Get file list from outputs if available
        if "outputs" in session:
            for output in session["outputs"]:
                if "pullRequest" in output:
                    pr_info = output.get("pullRequest", {})
                    if "changedFiles" in pr_info:
                        file_list = pr_info["changedFiles"]
        
        # Step 5: If still no diff, inform user
        if not diff and not instructions:
            raise HTTPException(
                status_code=400,
                detail="Create a PR or branch first to enable testing."
            )
        
        # Generate test using AI
        result = await tester_agent.generate_test_from_diff(
            diff=diff,
            instructions=context,
            file_list=file_list
        )
        
        return {
            "success": True,
            "test": result,
            "session_id": session_id,
            "diff_source": "activities" if diff else "context_only"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Test generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== Credentials Management Endpoints =====

class CredentialCreate(BaseModel):
    name: str
    username: str
    password: str

@app.get("/repos/{owner}/{repo}/credentials")
async def list_credentials(owner: str, repo: str):
    """List all saved credentials for a repository."""
    repo_key = f"{owner}/{repo}"
    creds = credentials_data.get(repo_key, [])
    safe_creds = [
        {
            "id": c["id"],
            "name": c["name"],
            "username": c["username"],
            "created_at": c.get("created_at", "")
        }
        for c in creds
    ]
    return {"credentials": safe_creds}

@app.post("/repos/{owner}/{repo}/credentials")
async def add_credential(owner: str, repo: str, cred: CredentialCreate):
    """Add a new credential for a repository."""
    from datetime import datetime
    
    repo_key = f"{owner}/{repo}"
    if repo_key not in credentials_data:
        credentials_data[repo_key] = []
    
    new_cred = {
        "id": str(uuid.uuid4()),
        "name": cred.name,
        "username": cred.username,
        "password": encrypt_password(cred.password),
        "created_at": datetime.now().isoformat()
    }
    
    credentials_data[repo_key].append(new_cred)
    save_credentials(credentials_data)
    
    return {
        "success": True,
        "credential": {
            "id": new_cred["id"],
            "name": new_cred["name"],
            "username": new_cred["username"]
        }
    }

@app.delete("/credentials/{credential_id}")
async def delete_credential(credential_id: str):
    """Delete a credential by ID."""
    for repo_key, creds in credentials_data.items():
        for i, cred in enumerate(creds):
            if cred["id"] == credential_id:
                del credentials_data[repo_key][i]
                save_credentials(credentials_data)
                return {"success": True}
    
    raise HTTPException(status_code=404, detail="Credential not found")

@app.get("/credentials/{credential_id}")
async def get_credential(credential_id: str):
    """Get a credential by ID (returns username and password for test execution)."""
    for repo_key, creds in credentials_data.items():
        for cred in creds:
            if cred["id"] == credential_id:
                return {
                    "id": cred["id"],
                    "name": cred["name"],
                    "username": cred["username"],
                    "password": decrypt_password(cred["password"])
                }
    
    raise HTTPException(status_code=404, detail="Credential not found")

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
    
    # Get or create seen files set for this session (persists across reconnections)
    def get_session_seen_files():
        if active_session_id:
            if active_session_id not in session_seen_files:
                session_seen_files[active_session_id] = set()
            return session_seen_files[active_session_id]
        return set()
    
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
                        
                        # Parse activity to structured JSON, passing session data and seen files
                        parsed = parse_activity(activity, session_data=cached_session_data, seen_files=get_session_seen_files())
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
                
                # Track seen files to avoid duplicate "Updated" messages
                history_seen_files = set()
                
                # Send activities in order (already chronological - oldest first for display)
                for activity in activities:
                    act_id = activity.get("id") or activity.get("name")
                    if act_id:
                        seen_activity_ids.add(act_id)
                        parsed = parse_activity(activity, session_data=session_data, seen_files=history_seen_files)
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

import re

def extract_files_from_text(text: str, diff_files: List[str] = None) -> List[str]:
    """Extract file paths mentioned in message text.
    
    Matches patterns like:
    - `path/to/file.ext` or `file.ext`
    - 'path/to/file.ext' or 'file.ext'
    - path/to/file.ext (common file extensions)
    
    If diff_files is provided, simple filenames will be matched against
    the full paths to resolve them.
    """
    if not text:
        return []
    
    files = []
    
    # Match backtick-quoted file paths: `path/to/file.ext`
    backtick_pattern = r'`([^`]+\.[a-zA-Z]{1,5})`'
    files.extend(re.findall(backtick_pattern, text))
    
    # Match single-quoted file paths: 'path/to/file.ext'
    quote_pattern = r"'([^']+\.[a-zA-Z]{1,5})'"
    files.extend(re.findall(quote_pattern, text))
    
    # Match common file extensions without quotes: path/to/file.ext
    common_extensions = r'\b(\S+\.(?:py|dart|yaml|yml|json|ts|tsx|js|jsx|md|txt|html|css|scss|java|kt|swift|go|rs|rb|php|c|cpp|h|hpp))\b'
    files.extend(re.findall(common_extensions, text, re.IGNORECASE))
    
    # Deduplicate while preserving order
    seen = set()
    unique_files = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)
    
    # If we have diff_files, resolve simple filenames to full paths
    if diff_files:
        resolved = []
        for f in unique_files:
            if '/' in f:
                # Already a full path
                resolved.append(f)
            else:
                # Simple filename - try to find matching full path in diff
                for diff_path in diff_files:
                    if diff_path.endswith('/' + f) or diff_path == f:
                        resolved.append(diff_path)
                        break
        return resolved
    
    return unique_files

def parse_activity(activity: Dict, session_data: Dict = None, seen_files: set = None) -> Dict:
    """Converts a Jules Activity JSON into a structured dict for the Flutter app.
    
    Args:
        activity: The activity dict from Jules API
        session_data: Optional session dict containing outputs[] with PR info
        seen_files: Optional set to track files already reported (for deduplication)
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
    
    # Session Progress (status updates) - may contain Jules' text messages
    if "sessionProgress" in activity:
        progress = activity["sessionProgress"]
        print(f"DEBUG sessionProgress FOUND: keys = {list(progress.keys())}", flush=True)
        print(f"DEBUG sessionProgress value: {str(progress)[:500]}", flush=True)
        result["type"] = "status"
        result["content"] = progress.get("status") or progress.get("message", "Working...")
        return result
    
    # Check for progressUpdated - another format for status/thinking updates
    if "progressUpdated" in activity:
        progress = activity["progressUpdated"]
        print(f"DEBUG progressUpdated FOUND: keys = {list(progress.keys()) if isinstance(progress, dict) else type(progress)}", flush=True)
        print(f"DEBUG progressUpdated value: {str(progress)[:500]}", flush=True)
        # Check if there's a title or description - title is what Jules web shows as the main message
        if isinstance(progress, dict):
            title = progress.get("title", "")
            description = progress.get("description", "")
            
            # Determine if this is just a status update or a real message
            # Status updates: short progress titles without artifacts or description
            # Real messages: have description (the explanation text) or will have artifacts
            has_artifacts = "artifacts" in activity and len(activity["artifacts"]) > 0
            
            # If we have a description, it's a real explanatory message (e.g., "I have successfully modified...")
            if description:
                # This is a real message - combine title and description for full context
                # Title is often a short action summary, description has the details
                result["type"] = "message"
                result["originator"] = "agent"
                # Combine title + description like on Jules web
                if title and title not in description:
                    result["content"] = f"{title}\n{description}"
                else:
                    result["content"] = description
                print(f"DEBUG progressUpdated: message = '{result['content'][:100]}'", flush=True)
            elif title and has_artifacts:
                # Has title and artifacts but no description
                result["type"] = "message"
                result["originator"] = "agent"
                result["content"] = title
                print(f"DEBUG progressUpdated: message with title+artifacts = '{title[:100]}'", flush=True)
            elif title:
                # Just a status update (no artifacts, no description) - update working indicator
                result["type"] = "progress"
                result["content"] = title
                print(f"DEBUG progressUpdated: status update = '{title[:100]}'", flush=True)
                # Note: progress type won't create a chat bubble, just updates indicator
    
    # Agent Messaged (Jules' text/chat responses)
    if "agentMessaged" in activity:
        agent_msg = activity["agentMessaged"]
        print(f"DEBUG agentMessaged FOUND: keys = {list(agent_msg.keys())}", flush=True)
        print(f"DEBUG agentMessaged value: {str(agent_msg)[:500]}", flush=True)
        message = agent_msg.get("message") or agent_msg.get("text") or agent_msg.get("content", "")
        if message:
            result["type"] = "message"
            result["originator"] = "agent"
            result["content"] = message
            print(f"DEBUG agentMessaged: returning message = '{message[:100]}...'", flush=True)
            return result
        else:
            print(f"DEBUG agentMessaged: message was empty", flush=True)
    
    
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
        
        # If we already have a message from progressUpdated, start with it
        if result.get("content") and result.get("type") == "message":
            content_parts.append(result["content"])
        
        # Debug: Log what artifacts we're getting
        for i, art in enumerate(activity["artifacts"]):
            art_keys = list(art.keys())
            print(f"DEBUG: Artifact {i} keys: {art_keys}", flush=True)
        
        for art in activity["artifacts"]:
            if "changeSet" in art:
                cs = art["changeSet"]
                git_patch = cs.get("gitPatch", {})
                unidiff = git_patch.get("unidiffPatch", "")
                
                # First, parse files from the cumulative diff (for resolving simple filenames)
                diff_files = []
                for line in unidiff.split("\n"):
                    if line.startswith("+++ b/"):
                        path = line[6:].strip()
                        if path and path != "/dev/null" and path not in diff_files:
                            diff_files.append(path)
                    elif line.startswith("+++ ") and not line.startswith("+++\t"):
                        path = line[4:].strip()
                        if path and path != "/dev/null" and path not in diff_files:
                            diff_files.append(path)
                
                # Get the message text to extract mentioned files
                message_text = result.get("content", "")
                
                # Extract files mentioned in the message and resolve to full paths
                # Jules web shows only files explicitly mentioned in the step description
                mentioned_files = extract_files_from_text(message_text, diff_files)
                print(f"DEBUG: Message text: {message_text[:100] if message_text else 'empty'}", flush=True)
                print(f"DEBUG: Diff files: {diff_files}", flush=True)
                print(f"DEBUG: Files mentioned in message: {mentioned_files}", flush=True)
                
                # Show "Updated {filepath}" only for files mentioned in this step
                if mentioned_files:
                    for fp in mentioned_files:
                        content_parts.append(f"Updated {fp}")
                
                # Always store the full patch for viewing/PR creation
                result["artifacts"].append({
                    "type": "file_change",
                    "files": mentioned_files if mentioned_files else [],
                    "patch": unidiff,
                    "commitMsg": git_patch.get("suggestedCommitMessage", "")
                })
            
            # Handle fileUpdated artifacts (single file updates)
            elif "fileUpdated" in art:
                fu = art["fileUpdated"]
                file_path = fu.get("path", "") or fu.get("filePath", "")
                if file_path:
                    content_parts.append(f"Updated {file_path}")  # Show file path like Jules web
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

# ===== MCP Server Management =====
import socket
import subprocess
import signal

MCP_PORT = 8931
mcp_process = None

def is_mcp_port_in_use(port: int = MCP_PORT) -> bool:
    """Check if MCP server port is already in use."""
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            if s.connect_ex(('::1', port)) == 0:
                return True
    except:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            return s.connect_ex(('localhost', port)) == 0
    except:
        return False

def start_mcp_server(port: int = MCP_PORT):
    """Start the ExecuteAutomation Playwright MCP server."""
    global mcp_process
    
    if is_mcp_port_in_use(port):
        print(f"✅ MCP server already running on port {port}")
        return True
    
    print(f"🚀 Starting MCP server on port {port}...")
    
    try:
        if os.name == 'nt':
            mcp_process = subprocess.Popen(
                f'npx @executeautomation/playwright-mcp-server --port {port}',
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                shell=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            mcp_process = subprocess.Popen(
                ["npx", "@executeautomation/playwright-mcp-server", "--port", str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
        
        # Wait for server to be ready (max 30 seconds)
        import time
        for i in range(60):
            if is_mcp_port_in_use(port):
                print(f"✅ MCP server ready on port {port}")
                return True
            time.sleep(0.5)
        
        print("⚠️ MCP server may not be fully ready")
        return True
        
    except Exception as e:
        print(f"❌ Failed to start MCP server: {e}")
        return False

def stop_mcp_server():
    """Stop the MCP server process."""
    global mcp_process
    if mcp_process:
        print("🛑 Stopping MCP server...")
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(mcp_process.pid)], capture_output=True)
            else:
                os.killpg(os.getpgid(mcp_process.pid), signal.SIGTERM)
            mcp_process.wait(timeout=5)
        except Exception as e:
            print(f"⚠️ Error stopping MCP server: {e}")
            mcp_process.kill()
        mcp_process = None
        print("✅ MCP server stopped")

# ===== Tester Agent Endpoints =====

class TestRequest(BaseModel):
    url: str
    objective: str
    username: Optional[str] = None
    password: Optional[str] = None
    deeper_analysis: bool = False

URL_HISTORY_FILE = "test_urls.json"

def save_url_to_history(url: str):
    """Save unique URL to history file."""
    urls = []
    if os.path.exists(URL_HISTORY_FILE):
        try:
            with open(URL_HISTORY_FILE, "r") as f:
                urls = json.load(f)
        except:
            urls = []
            
    if url not in urls:
        urls.append(url)
        with open(URL_HISTORY_FILE, "w") as f:
            json.dump(urls, f)

@app.post("/test/start")
async def start_test(request: TestRequest):
    """Start a new test with the Tester Agent."""
    # Prevent SSRF/local file access
    import urllib.parse
    parsed_url = urllib.parse.urlparse(request.url)
    if parsed_url.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Invalid URL scheme. Only http and https are allowed.")

    # Start MCP server if not running
    start_mcp_server()
    
    test_id = str(uuid.uuid4())[:8]
    save_url_to_history(request.url)
    
    # Start the test as a background async task in the current event loop
    task = asyncio.create_task(
        tester_agent.run_test(
            test_id, 
            request.url, 
            request.objective,
            username=request.username,
            password=request.password,
            deeper_analysis=request.deeper_analysis
        )
    )
    # Register the task so it can be canceled
    tester_agent.active_tasks[test_id] = task
    
    # Small delay to ensure test is registered
    await asyncio.sleep(0.1)
    
    return {
        "test_id": test_id,
        "status": "started",
        "url": request.url,
        "objective": request.objective,
        "thinking": "Initializing agent..."
    }

@app.get("/test/status/{test_id}")
async def get_test_status(test_id: str):
    """Get the status and results of a test."""
    result = tester_agent.get_test(test_id)
    if not result:
        raise HTTPException(status_code=404, detail="Test not found")
    return result

@app.post("/test/cancel/{test_id}")
async def cancel_test(test_id: str):
    """Cancel a running test."""
    success = await tester_agent.cancel_test(test_id)
    if not success:
        return {"status": "error", "message": "Test not found or not running"}
    return {"status": "canceled", "test_id": test_id}

@app.post("/test/retry/{test_id}")
async def retry_test(test_id: str):
    """Retry a previous test."""
    result = tester_agent.get_test(test_id)
    if not result:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # Start MCP server if not running
    start_mcp_server()
    
    new_test_id = str(uuid.uuid4())[:8]
    
    # Start the test as a background async task
    task = asyncio.create_task(
        tester_agent.run_test(
            new_test_id, 
            result.url, 
            result.objective,
            deeper_analysis=False
        )
    )
    tester_agent.active_tasks[new_test_id] = task
    
    return {
        "test_id": new_test_id,
        "status": "started",
        "url": result.url,
        "objective": result.objective,
        "is_retry": True,
        "original_test_id": test_id,
        "thinking": "Retrying test..."
    }

@app.post("/test/retry-deeper/{test_id}")
async def retry_test_deeper(test_id: str):
    """Retry a previous test with deeper analysis."""
    result = tester_agent.get_test(test_id)
    if not result:
        raise HTTPException(status_code=404, detail="Test not found")
    
    start_mcp_server()
    new_test_id = str(uuid.uuid4())[:8]
    
    task = asyncio.create_task(
        tester_agent.run_test(
            new_test_id, 
            result.url, 
            result.objective,
            deeper_analysis=True
        )
    )
    tester_agent.active_tasks[new_test_id] = task
    
    return {
        "test_id": new_test_id,
        "status": "started",
        "url": result.url,
        "objective": result.objective,
        "is_retry": True,
        "deeper_analysis": True,
        "original_test_id": test_id,
        "thinking": "Retrying with Deeper Analysis..."
    }

@app.get("/test/urls")
async def get_test_urls():
    """Get list of previously used test URLs."""
    if os.path.exists(URL_HISTORY_FILE):
        try:
            with open(URL_HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

@app.get("/tests")
async def list_tests():
    """List all tests."""
    return [tester_agent.to_json(t) for t in tester_agent.tests.values()]

# ===== Test Presets API =====

PRESETS_FILE = os.path.join(os.path.dirname(__file__), "test_presets.json")

class TestPreset(BaseModel):
    id: Optional[str] = None
    title: str
    url: str
    objective: str
    username: Optional[str] = None
    password: Optional[str] = None
    repository_full_name: str

def _load_presets() -> Dict:
    """Load presets from JSON file."""
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r") as f:
                return json.load(f)
        except:
            return {"presets": []}
    return {"presets": []}

def _save_presets(data: Dict):
    """Save presets to JSON file."""
    with open(PRESETS_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.get("/repos/{owner}/{repo}/presets")
async def get_repo_presets(owner: str, repo: str):
    """Get test presets for a specific repository."""
    full_name = f"{owner}/{repo}"
    data = _load_presets()
    repo_presets = [p for p in data.get("presets", []) if p.get("repository_full_name") == full_name]
    return {"presets": repo_presets}

@app.post("/repos/{owner}/{repo}/presets")
async def create_preset(owner: str, repo: str, preset: TestPreset):
    """Create a new test preset for a repository."""
    full_name = f"{owner}/{repo}"
    data = _load_presets()
    
    new_preset = {
        "id": str(uuid.uuid4())[:8],
        "title": preset.title,
        "url": preset.url,
        "objective": preset.objective,
        "username": preset.username,
        "password": preset.password,
        "repository_full_name": full_name
    }
    
    data["presets"].append(new_preset)
    _save_presets(data)
    
    return {"status": "created", "preset": new_preset}

@app.delete("/presets/{preset_id}")
async def delete_preset(preset_id: str):
    """Delete a test preset by ID."""
    data = _load_presets()
    original_count = len(data.get("presets", []))
    data["presets"] = [p for p in data.get("presets", []) if p.get("id") != preset_id]
    
    if len(data["presets"]) == original_count:
        raise HTTPException(status_code=404, detail="Preset not found")
    
    _save_presets(data)
    return {"status": "deleted", "preset_id": preset_id}

@app.get("/presets")
async def list_all_presets():
    """List all test presets."""
    data = _load_presets()
    return data

@app.post("/test/{test_id}/save-as-preset")
async def save_test_as_preset(test_id: str, title: str = Query(...), repo_full_name: str = Query(...)):
    """Save a completed test as a new preset."""
    result = tester_agent.get_test(test_id)
    if not result:
        raise HTTPException(status_code=404, detail="Test not found")
    
    data = _load_presets()
    new_preset = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "url": result.url,
        "objective": result.objective,
        "username": None,  # Don't save credentials for security
        "password": None,
        "repository_full_name": repo_full_name
    }
    
    data["presets"].append(new_preset)
    _save_presets(data)
    
    return {"status": "created", "preset": new_preset}

# ===== Speech to Text Endpoints =====

@app.post("/stt")
async def speech_to_text(file: UploadFile = File(...)):
    """Transcribe an audio file using Gemini 3 Flash with thinking."""
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured on server")
    
    try:
        # Save temporary file safely
        ext = file.filename.split('.')[-1] if file.filename and '.' in file.filename else 'raw'
        safe_ext = ''.join(c for c in ext if c.isalnum())
        if not safe_ext:
            safe_ext = "audio"
        temp_filename = f"temp_{uuid.uuid4()}.{safe_ext}"

        content = await file.read()
        def write_file():
            with open(temp_filename, "wb") as buffer:
                buffer.write(content)
        await asyncio.to_thread(write_file)
        
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
        def remove_file():
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
        await asyncio.to_thread(remove_file)
        
        return {"text": response.text.strip()}
    
    except Exception as e:
        print(f"STT Error: {e}")
        if 'temp_filename' in locals():
            def safe_remove():
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
            await asyncio.to_thread(safe_remove)
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
