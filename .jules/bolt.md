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

## 2025-04-13 - [Flutter List Rendering Performance]
**Learning:** In Flutter, rendering large datasets like Git patch diffs using a standard `ListView` with a `map().toList()` pattern instantiates all child widgets at once. This causes massive memory spikes and UI thread jank, especially when nested inside a `DraggableScrollableSheet`.
**Action:** Always use `ListView.builder` for large lists to ensure lazy widget instantiation, improving rendering performance and avoiding memory limits.
## 2025-05-18 - [Python Regex Performance]
**Learning:** In Python, calling `re.findall(pattern, text)` repeatedly inside a frequently called function (like one parsing diffs or logs) forces Python to parse and evaluate the string regex pattern on every invocation, causing unnecessary overhead.
**Action:** Always extract static regular expressions into module-level variables and pre-compile them using `re.compile(pattern)`. Then, use `.findall(text)` directly on the compiled object to prevent redundant memory allocations and parsing.
