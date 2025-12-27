"""
Push Notification Service for Mobile Jules

This module provides server-side polling and notification sending.
Requires Firebase Admin SDK to be configured with a service account.

Setup:
1. Create a Firebase project at https://console.firebase.google.com
2. Download the service account JSON file
3. Set FIREBASE_CREDENTIALS env var to the path of that file
4. Add the client's FCM token via the /register-device endpoint
"""

import os
import json
import asyncio
from typing import Dict, List, Optional
from datetime import datetime


class NotificationService:
    """Handles push notification logic for Mobile Jules."""
    
    def __init__(self):
        self.device_tokens: Dict[str, str] = {}  # user_id -> fcm_token
        self.firebase_app = None
        self._setup_firebase()
    
    def _setup_firebase(self):
        """Initialize Firebase Admin SDK if credentials are available."""
        creds_path = os.environ.get("FIREBASE_CREDENTIALS")
        if not creds_path:
            print("INFO: FIREBASE_CREDENTIALS not set. Push notifications disabled.")
            return
        
        try:
            import firebase_admin
            from firebase_admin import credentials
            
            cred = credentials.Certificate(creds_path)
            self.firebase_app = firebase_admin.initialize_app(cred)
            print("Firebase Admin SDK initialized successfully.")
        except ImportError:
            print("WARNING: firebase-admin not installed. Run: pip install firebase-admin")
        except Exception as e:
            print(f"WARNING: Failed to initialize Firebase: {e}")
    
    def register_device(self, user_id: str, fcm_token: str):
        """Register a device's FCM token for receiving notifications."""
        self.device_tokens[user_id] = fcm_token
        print(f"Registered device for user {user_id}")
    
    def unregister_device(self, user_id: str):
        """Remove a device's FCM token."""
        if user_id in self.device_tokens:
            del self.device_tokens[user_id]
    
    async def send_notification(
        self, 
        user_id: str, 
        title: str, 
        body: str,
        data: Optional[Dict] = None
    ) -> bool:
        """Send a push notification to a user's device.
        
        Args:
            user_id: The user to notify
            title: Notification title
            body: Notification body text
            data: Optional data payload for the app
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.firebase_app:
            print(f"Notification (not sent - Firebase not configured): {title}")
            return False
        
        token = self.device_tokens.get(user_id)
        if not token:
            print(f"No device token for user {user_id}")
            return False
        
        try:
            from firebase_admin import messaging
            
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=token,
            )
            
            response = messaging.send(message)
            print(f"Notification sent: {response}")
            return True
        except Exception as e:
            print(f"Failed to send notification: {e}")
            return False
    
    async def notify_plan_ready(self, user_id: str, session_id: str, step_count: int):
        """Notify user that a plan is ready for approval."""
        await self.send_notification(
            user_id=user_id,
            title="📋 Plan Ready",
            body=f"Jules generated a plan with {step_count} steps. Tap to review.",
            data={"session_id": session_id, "type": "plan_ready"}
        )
    
    async def notify_task_complete(self, user_id: str, session_id: str, has_pr: bool):
        """Notify user that a task is complete."""
        if has_pr:
            title = "✅ PR Created"
            body = "Jules finished the task and created a pull request."
        else:
            title = "✅ Task Complete"
            body = "Jules has finished working on your task."
        
        await self.send_notification(
            user_id=user_id,
            title=title,
            body=body,
            data={"session_id": session_id, "type": "task_complete", "has_pr": str(has_pr)}
        )
    
    async def notify_needs_input(self, user_id: str, session_id: str, message: str):
        """Notify user that Jules needs input."""
        await self.send_notification(
            user_id=user_id,
            title="💬 Jules Needs Input",
            body=message[:100] + ("..." if len(message) > 100 else ""),
            data={"session_id": session_id, "type": "needs_input"}
        )


# Global instance
notification_service = NotificationService()


class SessionPoller:
    """Polls Jules sessions for changes and triggers notifications."""
    
    def __init__(self, jules_client, notification_service: NotificationService):
        self.jules_client = jules_client
        self.notifications = notification_service
        self.active_sessions: Dict[str, Dict] = {}  # session_id -> last_known_state
        self.user_sessions: Dict[str, List[str]] = {}  # user_id -> [session_ids]
        self._running = False
    
    def track_session(self, user_id: str, session_id: str):
        """Start tracking a session for a user."""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = []
        if session_id not in self.user_sessions[user_id]:
            self.user_sessions[user_id].append(session_id)
            self.active_sessions[session_id] = {"user_id": user_id, "state": None}
    
    async def poll_once(self):
        """Check all tracked sessions for state changes."""
        for session_id, session_info in list(self.active_sessions.items()):
            try:
                user_id = session_info["user_id"]
                last_state = session_info.get("state")
                
                # Get current session state
                session = await self.jules_client.get_session(session_id)
                current_state = session.get("state")
                
                # Check for state changes that warrant notifications
                if current_state != last_state:
                    await self._handle_state_change(
                        user_id, session_id, session, last_state, current_state
                    )
                    self.active_sessions[session_id]["state"] = current_state
                
                # Check if session is done
                if current_state in ["DONE", "FAILED"]:
                    # Stop tracking completed sessions after notifying
                    del self.active_sessions[session_id]
                    if user_id in self.user_sessions:
                        self.user_sessions[user_id].remove(session_id)
                        
            except Exception as e:
                print(f"Error polling session {session_id}: {e}")
    
    async def _handle_state_change(
        self, 
        user_id: str, 
        session_id: str, 
        session: Dict,
        old_state: Optional[str], 
        new_state: str
    ):
        """Handle session state changes and send notifications."""
        if new_state == "WAITING_FOR_USER":
            # Check if it's waiting for plan approval
            activities = await self.jules_client.list_activities(session_id)
            for activity in reversed(activities):
                if "planGenerated" in activity:
                    plan = activity["planGenerated"].get("plan", {})
                    step_count = len(plan.get("steps", []))
                    await self.notifications.notify_plan_ready(user_id, session_id, step_count)
                    return
            
            # Generic needs input
            await self.notifications.notify_needs_input(
                user_id, session_id, "Jules is waiting for your response."
            )
        
        elif new_state == "DONE":
            # Check for PR
            outputs = session.get("outputs", [])
            has_pr = any("pullRequest" in o for o in outputs)
            await self.notifications.notify_task_complete(user_id, session_id, has_pr)
    
    async def start_polling(self, interval_seconds: int = 30):
        """Start the background polling loop."""
        self._running = True
        print(f"Starting session poller (interval: {interval_seconds}s)")
        
        while self._running:
            await self.poll_once()
            await asyncio.sleep(interval_seconds)
    
    def stop_polling(self):
        """Stop the background polling loop."""
        self._running = False
