## 2026-04-09 - [SSRF vulnerability in URL testing endpoint]
**Vulnerability:** The `/test/start` endpoint accepted arbitrary URLs and passed them to the browser testing agent via `tester_agent.run_test`. It was possible to pass `file://` or other internal network schemes, leading to Server-Side Request Forgery (SSRF) and local file access.
**Learning:** Endpoints that spawn headless browsers or make HTTP requests on behalf of the user must always strictly validate the provided URL schemes (allowlisting only `http` and `https`).
**Prevention:** Added `urllib.parse.urlparse` validation to reject URLs with invalid schemes at the API boundary, before the request reaches the browser component.

## 2024-04-10 - [Fix Information Exposure in Error Handling]
**Vulnerability:** The FastAPI endpoints in `mobile_jules/server/main.py` were catching generic `Exception`s and raising 500 `HTTPException`s with the detail set to `str(e)`. This leaked internal stack traces and internal application errors to the client, leading to Information Exposure. Additionally, it intercepted internally raised `HTTPException`s (like 404s and 422s), obscuring the actual HTTP status code logic by wrapping it in a generic 500 error.
**Learning:** This occurred because the endpoints attempted a universal catch-all for exception handling without differentiating between expected HTTP Exceptions and unexpected system exceptions.
**Prevention:** In FastAPI applications, always catch `HTTPException` first and re-raise it to let FastAPI handle structured responses natively. Then catch generic `Exception`, log it securely on the server-side, and return a sanitized, generic error message (e.g., "An internal server error occurred.") to the client. Never expose raw `Exception` details directly via API endpoints.

## 2024-05-24 - [Fix plaintext password leak in unauthenticated API endpoint]
**Vulnerability:** The `/credentials/{credential_id}` GET endpoint in the FastAPI backend (`mobile_jules/server/main.py`) returned decrypted plaintext passwords without requiring authentication. Additionally, the Flutter client retrieved these plaintext credentials over the network to include them in the POST payload to start tests.
**Learning:** Returning plaintext credentials to a client, especially unauthenticated, is a severe security risk. Operations requiring secrets should decrypt them securely on the backend, only when necessary, and avoid transmitting them back to the client.
**Prevention:** Removed the unauthenticated GET endpoint completely. Refactored the test initiation flow to allow the client to pass a `credential_id` securely. The backend now looks up the credential internally, decrypts it in-memory, and injects it directly into the testing process, preventing exposure over the network.
