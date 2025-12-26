import os
import asyncio
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Import the Client
from jules_client import JulesClient, MockJulesClient

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
API_KEY = os.environ.get("JULES_API_KEY")

# Choose client based on environment
if API_KEY:
    client = JulesClient(api_key=API_KEY)
else:
    print("WARNING: No JULES_API_KEY found. Using MockJulesClient.")
    client = MockJulesClient(api_key="dummy")

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
    """Lists existing Jules sessions for debugging."""
    try:
        sessions = await client.list_sessions()
        print(f"DEBUG: Found {len(sessions)} sessions")
        for s in sessions:
            print(f"DEBUG session: {s}")
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/chat/{source_id:path}") # :path allows slashes in source_id
async def websocket_endpoint(websocket: WebSocket, source_id: str):
    await websocket.accept()
    
    # Create a new session for this connection
    # Use a prompt that tells Jules to wait for instructions rather than start working immediately
    try:
        initial_prompt = "Hello! I'm connecting from a mobile app. Please wait for my instructions before starting any work. Just acknowledge this connection and let me know you're ready."
        session_data = await client.create_session(source_id=source_id, prompt=initial_prompt)
        print(f"DEBUG: Full session data = {session_data}")  # Debug log
        
        # The session response should have a "name" field with format "sessions/{id}"
        session_id = session_data.get("name")
        if not session_id:
            # Fallback: try to construct from "id" field
            raw_id = session_data.get("id", "")
            session_id = f"sessions/{raw_id}" if raw_id else None
        
        if not session_id:
            await websocket.send_text(f"System: Error - Could not extract session ID from response: {session_data}")
            await websocket.close()
            return
            
        print(f"DEBUG: Using session_id = {session_id}")  # Debug log
        await websocket.send_text(f"System: Connected to Jules Session {session_id}")
        
        # Verify the session exists by fetching it
        try:
            session_check = await client.get_session(session_id)
            print(f"DEBUG: Session check = {session_check}")
        except Exception as check_err:
            print(f"DEBUG: Could not verify session: {check_err}")
    except Exception as e:
        await websocket.send_text(f"System: Error creating session: {str(e)}")
        await websocket.close()
        return

    # Track which activities we've already sent to the client to avoid duplicates
    seen_activity_ids = set()

    async def poll_jules():
        """Background task to poll for new messages/activities from Jules."""
        while True:
            try:
                activities = await client.list_activities(session_id)
                # Sort by time if needed, but assuming API returns logical order or we just check IDs
                for activity in activities:
                    act_id = activity.get("id") or activity.get("name")
                    if act_id not in seen_activity_ids:
                        seen_activity_ids.add(act_id)
                        
                        # Parse the activity to a friendly string
                        message = parse_activity(activity)
                        if message:
                            await websocket.send_text(message)
                
                await asyncio.sleep(2) # Poll every 2 seconds
            except Exception as e:
                print(f"Polling error: {e}")
                # Don't crash the loop, just wait and retry
                await asyncio.sleep(5)

    # Start the polling loop
    poller = asyncio.create_task(poll_jules())

    try:
        while True:
            # Wait for user message from phone
            data = await websocket.receive_text()
            # Send to Jules
            await client.send_message(session_id, data)
            # The poller will pick up the response
    except WebSocketDisconnect:
        print(f"Client disconnected")
    finally:
        poller.cancel()

def parse_activity(activity: Dict) -> str:
    """Converts a Jules Activity JSON into a readable string for the chat."""
    print(f"DEBUG parse_activity: {activity}")  # Debug log
    
    # Get the actor/originator
    actor = activity.get("actor") or activity.get("originator", "unknown")
    
    if actor == "user":
        # We might not want to echo user messages back if the UI already shows them
        return None 
    
    # Look for message content in various possible fields
    # Jules API may use different field names for different activity types
    
    # Check for agentMessaged (agent sending a message)
    if "agentMessaged" in activity:
        msg = activity["agentMessaged"]
        # The actual field name is 'agentMessage' (discovered from debug logs)
        text = msg.get("agentMessage") or msg.get("text") or msg.get("message") or msg.get("content", "")
        if text:
            return f"Jules: {text}"
    
    # Check for sessionProgress (status updates like "Booting VM", "Cloning repo")
    if "sessionProgress" in activity:
        progress = activity["sessionProgress"]
        status = progress.get("status") or progress.get("message", "")
        return f"Jules: [Status] {status}"
    
    # Handle Plan Activities
    if "planGenerated" in activity:
        plan = activity["planGenerated"]
        if isinstance(plan, dict) and "plan" in plan:
            steps = len(plan["plan"].get("steps", []))
            return f"Jules: I have generated a plan with {steps} steps."
        return f"Jules: Plan generated"
    
    if "progressUpdated" in activity:
        progress = activity["progressUpdated"]
        title = progress.get("title", "")
        desc = progress.get("description", "")
        return f"Jules: {title}\n{desc}" if title or desc else None
    
    # Check for generic description field
    if "description" in activity:
        return f"Jules: {activity['description']}"
    
    # Check for text field
    if "text" in activity:
        return f"Jules: {activity['text']}"
    
    # Check for message field
    if "message" in activity:
        return f"Jules: {activity['message']}"
    
    # Default fallback - show activity name/type
    name = activity.get("name", "unknown")
    return f"Jules: [Activity: {name}]"

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
