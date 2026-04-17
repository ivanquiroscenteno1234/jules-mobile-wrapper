## 2024-03-24 - Accessibility Enhancements
**Learning:** Added tooltips to icon-only buttons (IconButton) across chat_screen.dart, dashboard_screen.dart, and sessions_screen.dart to improve screen reader accessibility.
**Action:** Always include tooltip property for any icon-only button.

## 2024-04-12 - Accessibility Enhancements
**Learning:** ActionChips and FloatingActionButtons lacking text or with confusing labels need tooltips for better accessibility, just like IconButtons. The 'tooltip' property natively provides this functionality for both widgets.
**Action:** Always include tooltip property for ActionChips and FloatingActionButtons.
## 2026-04-16 - [Dialog Validation Pattern]
**Learning:** Silent failures in dialogs occur when submit buttons allow empty inputs. Users get confused when a dialog closes without saving.
**Action:** Always disable submit buttons and provide visual cues when required fields are empty in Flutter dialogs.
