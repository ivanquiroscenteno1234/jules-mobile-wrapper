## 2025-02-24 - [Flutter List Filtering Performance]
**Learning:** In Flutter apps rendering lists, un-debounced search inputs combined with multiple string computations (`toLowerCase()`) inside `.where()` iteration loops cause noticeable UI jank and frame drops due to repeated, synchronous execution blocking the main thread during rapid user input.
**Action:** Always wrap text-based search filters in a debounce timer (e.g., 300ms using `Timer` from `dart:async`), and pre-compute invariants (like `query.toLowerCase()`) outside the iteration loop before updating state.## 2026-04-10 - Async I/O for Screen Shots
**Bottleneck:** Synchronous I/O in async context block event loops.
**Learning:** For async context, using  is optimal for I/O bounds, but CPU bounds like base64 encode should still be executed in a thread pool via  to ensure event loop isn't blocked.
**Prevention:** Profile performance-critical code carefully.

## 2024-05-18 - Async I/O for Screen Shots
**Bottleneck:** Synchronous I/O in async context blocks event loops.
**Learning:** For async context, using `aiofiles` is optimal for I/O bound operations. However, CPU bound operations like base64 encoding should still be executed in a thread pool via `asyncio.to_thread` to ensure the event loop isn't blocked.
**Prevention:** Profile performance-critical code carefully.
