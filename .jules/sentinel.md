## 2026-04-09 - [SSRF vulnerability in URL testing endpoint]
**Vulnerability:** The `/test/start` endpoint accepted arbitrary URLs and passed them to the browser testing agent via `tester_agent.run_test`. It was possible to pass `file://` or other internal network schemes, leading to Server-Side Request Forgery (SSRF) and local file access.
**Learning:** Endpoints that spawn headless browsers or make HTTP requests on behalf of the user must always strictly validate the provided URL schemes (allowlisting only `http` and `https`).
**Prevention:** Added `urllib.parse.urlparse` validation to reject URLs with invalid schemes at the API boundary, before the request reaches the browser component.
