# Jules API Reference

> **Official Documentation**: [jules.google/docs/api/reference](https://jules.google/docs/api/reference)
>
> This file is for AI reference when working with the Jules API.

---

## Base URL

```
https://jules.googleapis.com/v1alpha
```

## Authentication

Include API key in the `x-goog-api-key` header:

```bash
curl -H "x-goog-api-key: $JULES_API_KEY" \
  https://jules.googleapis.com/v1alpha/sessions
```

Get your API key from [jules.google.com/settings](https://jules.google.com/settings).

---

## Sessions

### Create Session
`POST /v1alpha/sessions`

**Request Body:**
```json
{
  "prompt": "Task description for Jules",
  "title": "Optional title",
  "sourceContext": {
    "source": "sources/github-owner-repo",
    "githubRepoContext": {
      "startingBranch": "main"
    }
  },
  "requirePlanApproval": true,
  "automationMode": "AUTO_CREATE_PR"  // or "NONE"
}
```

**Repoless Session (No Codebase):**
Omit the `source` field in `sourceContext` to create a session without a repository:
```json
{
  "prompt": "Create a Flask app...",
  "sourceContext": {},
  "automationMode": "NONE"
}
```

**Response:**
```json
{
  "name": "sessions/1234567",
  "id": "abc123",
  "state": "QUEUED",
  "url": "https://jules.google.com/session/abc123",
  "createTime": "2024-01-15T10:30:00Z"
}
```

### List Sessions
`GET /v1alpha/sessions`

### Get Session
`GET /v1alpha/sessions/{session_id}`

### Delete Session
`DELETE /v1alpha/sessions/{session_id}`

### Send Message
`POST /v1alpha/sessions/{session_id}:sendMessage`

```json
{
  "prompt": "User message text"
}
```

### Approve Plan
`POST /v1alpha/sessions/{session_id}:approvePlan`

---

## Session States

| State | Description |
|-------|-------------|
| `QUEUED` | Waiting to start |
| `PLANNING` | Creating a plan |
| `AWAITING_PLAN_APPROVAL` | Plan ready for review |
| `AWAITING_USER_FEEDBACK` | Needs user input |
| `IN_PROGRESS` | Executing plan |
| `PAUSED` | Temporarily paused |
| `COMPLETED` | Successfully finished |
| `FAILED` | Encountered error |

---

## Activities

### List Activities
`GET /v1alpha/sessions/{session_id}/activities`

### Get Activity
`GET /v1alpha/sessions/{session_id}/activities/{activity_id}`

### Activity Types
- `planGenerated` - A plan was created
- `planApproved` - Plan was approved
- `userMessaged` - User sent a message
- `agentMessaged` - Jules responded
- `progressUpdated` - Progress update
- `sessionCompleted` - Session finished
- `sessionFailed` - Session failed

### Artifacts
Activities may include artifacts:
- **ChangeSet** - Code changes (patch format)
- **BashOutput** - Command execution output
- **Media** - Images or files

---

## Sources

### List Sources
`GET /v1alpha/sources`

Returns connected GitHub repositories.

### Get Source
`GET /v1alpha/sources/{source_id}`

**Response:**
```json
{
  "name": "sources/github-owner-repo",
  "id": "github-owner-repo",
  "githubRepo": {
    "owner": "owner",
    "repo": "repo-name"
  }
}
```

---

## Types

### Session
```typescript
{
  name: string;           // Full resource name
  id: string;             // Session ID
  prompt: string;         // Task description
  title?: string;         // Optional title
  state: SessionState;
  url: string;            // Web UI URL
  sourceContext: SourceContext;
  outputs?: SessionOutput[];
  createTime: string;
  updateTime: string;
}
```

### SourceContext
```typescript
{
  source?: string;         // "sources/github-owner-repo" (optional for repoless)
  githubRepoContext?: {
    startingBranch?: string;
  };
}
```

### AutomationMode
- `AUTOMATION_MODE_UNSPECIFIED`
- `AUTO_CREATE_PR` - Automatically create PR when ready
- `NONE` - No automation (required for repoless sessions)

### Activity
```typescript
{
  name: string;           // Full resource name
  id: string;             // Activity ID
  originator: "user" | "agent" | "system";
  description?: string;
  artifacts?: Artifact[];
  createTime: string;
  // One of these event fields:
  planGenerated?: PlanGenerated;
  planApproved?: PlanApproved;
  userMessaged?: UserMessaged;
  agentMessaged?: AgentMessaged;
  progressUpdated?: ProgressUpdated;
  sessionCompleted?: SessionCompleted;
  sessionFailed?: SessionFailed;
}
```

---

## Quick Examples

### Create repo-based session
```python
await client.create_session(
    source_id="sources/github/owner/repo",
    prompt="Add unit tests",
    auto_mode=True  # AUTO_CREATE_PR
)
```

### Create repoless session
```python
await client.create_session(
    source_id=None,  # No repo
    prompt="Create a Python Flask app"
)
```

---

*Last updated: December 2024*
