## 2024-05-18 - [CRITICAL] Prevented SSRF in Tester Agent
**Vulnerability:** The `/test/start` endpoint accepted any URL scheme for Playwright to navigate to, which allowed Server-Side Request Forgery (SSRF) and local file access (e.g., `file:///etc/passwd`).
**Learning:** Tools that control headless browsers or similar services must strictly validate the URL schemes to prevent arbitrary local or internal network requests.
**Prevention:** Always validate URLs using `urllib.parse.urlparse` and ensure the scheme is explicitly allowed (like `http` or `https`) before passing it to internal tools or headless browsers.
