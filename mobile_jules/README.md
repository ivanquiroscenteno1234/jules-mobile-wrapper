# Mobile Jules

A mobile companion app for **Jules** (Google's AI coding agent) that lets you manage coding tasks, approve plans, and review PRs from your phone.

---

## ✨ Features

### 🎯 Core Functionality
- **Chat with Jules** - Send coding tasks and receive real-time responses
- **View Session History** - Browse and reconnect to previous sessions
- **Approve Plans** - Review and approve Jules' execution plans on the go
- **View PRs** - See created pull requests and open them in browser

### 🆕 Repoless Sessions (No Codebase Mode)
- **Start from Scratch** - Create sessions without selecting a repository
- **Rapid Prototyping** - Perfect for generating scripts, utilities, or new projects
- **Prompt-First UX** - Enter your task first, then optionally select a repo

### 🗣️ Speech-to-Text
- **Voice Input** - Tap the microphone to dictate your coding tasks
- **Powered by Gemini 3 Flash** - Uses `thinking_level="medium"` for accurate transcription
- **Works Offline** - Recordings are sent to server for processing

### 🔔 Notifications
- **Session Status Alerts** - Get notified when Jules needs your attention
- **Native Notifications** - Uses `flutter_local_notifications` for Android/iOS
- **Background Updates** - Server polls sessions and sends alerts

### 🔀 Auto-Create PR Mode
- **One-Click Automation** - Enable to automatically create PRs when Jules finishes
- **Per-Session Toggle** - Choose automation level for each task
- **Repo Sessions Only** - Available when working on a connected repository

### 🗑️ Session Management
- **Swipe to Delete** - Remove sessions with a swipe gesture
- **Confirmation Dialog** - Prevents accidental deletions
- **Synced with API** - Deletes from both local list and Jules backend

### ⚙️ Settings
- **Server URL Configuration** - Connect to your local or remote proxy server
- **Dark Mode** - Toggle between light and dark themes
- **Auto Mode** - Global setting for automatic PR creation

---

## 🏗️ Architecture

```
┌─────────────────┐     WebSocket      ┌─────────────────┐     REST API      ┌─────────────────┐
│  Flutter App    │◄──────────────────►│  Python Server  │◄────────────────►│  Jules API      │
│  (Mobile)       │                    │  (Proxy)        │                  │  (googleapis)   │
└─────────────────┘                    └─────────────────┘                  └─────────────────┘
```

- **Server (Python/FastAPI)** - Runs on your laptop. Proxies requests to Jules API and handles WebSocket connections.
- **Client (Flutter)** - Runs on your phone. Connects to the server to interact with Jules.

---

## 📋 Prerequisites

1. **Python 3.10+** installed on your computer
2. **Flutter SDK** installed (for building/running the app)
3. **Jules API Key** - Get from [jules.google.com/settings](https://jules.google.com/settings)
4. **Gemini API Key** (optional) - For speech-to-text functionality

---

## 🚀 Quick Start

### Server Setup

```bash
cd mobile_jules/server

# Install dependencies
pip install -r requirements.txt

# Set your API key (PowerShell)
$env:JULES_API_KEY="your_jules_api_key"
$env:GEMINI_API_KEY="your_gemini_api_key"  # Optional, for STT

# Run the server
.\start_server.bat
# Or: python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

The server will start on `http://0.0.0.0:8000`. If ngrok is configured, it will also create a public tunnel.

### Client Setup

```bash
cd mobile_jules/client

# Install dependencies
flutter pub get

# Run on your device/emulator
flutter run
```

On first launch, tap the **Settings** icon and enter your server URL.

---

## 📱 App Screens

| Screen | Description |
|--------|-------------|
| **Home** | Browse connected GitHub repositories |
| **Sessions** | View and manage recent Jules sessions |
| **Chat** | Real-time conversation with Jules |
| **Settings** | Configure server URL and preferences |

---

## 🔧 Server Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/repos` | GET | List connected GitHub repositories |
| `/sessions` | GET | List all Jules sessions |
| `/sessions/{id}` | GET | Get session details |
| `/sessions/{id}` | DELETE | Delete a session |
| `/chat/{source_id}` | WS | WebSocket for repo-based chat |
| `/chat` | WS | WebSocket for repoless sessions |
| `/stt` | POST | Speech-to-text transcription |

---

## 📚 API Documentation

See [JULES_API_REFERENCE.md](./JULES_API_REFERENCE.md) for complete Jules API documentation.

---

## 🛠️ Tech Stack

**Server:**
- Python 3.10+
- FastAPI + Uvicorn
- httpx (async HTTP client)
- google-generativeai (for STT)
- pyngrok (optional, for tunneling)

**Client:**
- Flutter 3.x
- web_socket_channel
- http
- record (audio recording)
- flutter_local_notifications
- shared_preferences

---

## 📝 License

MIT License

---

*Built with ❤️ for Jules developers on the go*
