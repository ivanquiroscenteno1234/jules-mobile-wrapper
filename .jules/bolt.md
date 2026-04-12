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
## 2025-02-24 - [Flutter Long List Rendering Performance]
**Learning:** In Flutter apps, rendering potentially large data sets (like full git diffs or long chat histories) using standard `ListView` with a pre-mapped list of widget children causes immediate instantiation of all items. This completely bypasses virtualization, leading to significant memory spikes and UI thread jank, especially in bottom sheets (`DraggableScrollableSheet`).
**Action:** Always use `ListView.builder` for lists of unbounded or potentially large size to ensure lazy instantiation. Pre-compute derived invariants (like `patch.split('\n')`) outside the builder to prevent redundant O(N) operations during scrolling.
