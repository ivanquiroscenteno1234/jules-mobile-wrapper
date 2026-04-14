## 2026-04-09 - [SSRF vulnerability in URL testing endpoint]
**Vulnerability:** The `/test/start` endpoint accepted arbitrary URLs and passed them to the browser testing agent via `tester_agent.run_test`. It was possible to pass `file://` or other internal network schemes, leading to Server-Side Request Forgery (SSRF) and local file access.
**Learning:** Endpoints that spawn headless browsers or make HTTP requests on behalf of the user must always strictly validate the provided URL schemes (allowlisting only `http` and `https`).
**Prevention:** Added `urllib.parse.urlparse` validation to reject URLs with invalid schemes at the API boundary, before the request reaches the browser component.

## 2024-04-10 - [Fix Information Exposure in Error Handling]
**Vulnerability:** The FastAPI endpoints in `mobile_jules/server/main.py` were catching generic `Exception`s and raising 500 `HTTPException`s with the detail set to `str(e)`. This leaked internal stack traces and internal application errors to the client, leading to Information Exposure. Additionally, it intercepted internally raised `HTTPException`s (like 404s and 422s), obscuring the actual HTTP status code logic by wrapping it in a generic 500 error.
**Learning:** This occurred because the endpoints attempted a universal catch-all for exception handling without differentiating between expected HTTP Exceptions and unexpected system exceptions.
**Prevention:** In FastAPI applications, always catch `HTTPException` first and re-raise it to let FastAPI handle structured responses natively. Then catch generic `Exception`, log it securely on the server-side, and return a sanitized, generic error message (e.g., "An internal server error occurred.") to the client. Never expose raw `Exception` details directly via API endpoints.

## 2026-04-14 - [Memory Exhaustion / DoS in File Upload endpoint]
**Vulnerability:** The FastAPI `/stt` endpoint was using `await file.read()` which reads the entire uploaded file into memory at once, and lacked any file size limits. This allowed an attacker to send an infinitely large file, causing the server to exhaust memory (OOM crash) or disk space, leading to Denial of Service (DoS).
**Learning:** By default, FastAPI's `UploadFile` parses files into memory up to a point (spooled), but explicitly calling `.read()` with no arguments loads the entire contents into RAM regardless of size.
**Prevention:** Always read uploaded files in fixed-size chunks (e.g. `await file.read(8192)`) and enforce a strict hard-limit `MAX_FILE_SIZE`. If the limit is exceeded, cleanly delete the temporary artifact and raise a `413 Payload Too Large` error.
