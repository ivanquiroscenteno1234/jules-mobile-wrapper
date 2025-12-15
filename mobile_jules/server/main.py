import os
import asyncio
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Import the Client
from mobile_jules.server.jules_client import JulesClient, MockJulesClient

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
API_KEY = os.environ.get("GOOGLE_API_KEY")

# Choose client based on environment
if API_KEY:
    client = JulesClient(api_key=API_KEY)
else:
    print("WARNING: No GOOGLE_API_KEY found. Using MockJulesClient.")
    client = MockJulesClient(api_key="dummy")

class Repo(BaseModel):
    name: str
    id: str
    full_name: str

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

@app.websocket("/chat/{source_id:path}") # :path allows slashes in source_id
async def websocket_endpoint(websocket: WebSocket, source_id: str):
    await websocket.accept()
    
    # Create a new session for this connection
    try:
        session_data = await client.create_session(source_id=source_id, prompt="Mobile app connected")
        session_id = session_data["name"] # "sessions/..."
        await websocket.send_text(f"System: Connected to Jules Session {session_id}")
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
    originator = activity.get("originator", "unknown")
    
    if originator == "user":
        # We might not want to echo user messages back if the UI already shows them
        return None 
    
    # Handle Agent Activities
    if "planGenerated" in activity:
        steps = len(activity["planGenerated"]["plan"].get("steps", []))
        return f"Jules: I have generated a plan with {steps} steps."
    
    if "progressUpdated" in activity:
        title = activity["progressUpdated"].get("title", "")
        desc = activity["progressUpdated"].get("description", "")
        return f"Jules: {title}\n{desc}"
    
    if "text" in activity: # In case of simple text response (mock or future API)
        return f"Jules: {activity['text']}"

    # Default fallback
    return f"Jules: [Activity: {activity.get('name')}]"

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
