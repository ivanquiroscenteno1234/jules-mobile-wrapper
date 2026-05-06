## 2024-05-06 - Dynamic Text for Disabled Buttons in Dialogs
**Learning:** Tooltips on disabled buttons (like `ElevatedButton(onPressed: null)`) provide poor UX on mobile interfaces because they require hover interactions that don't exist on touch devices, and taps are often swallowed.
**Action:** Instead of tooltips, dynamically update the text of the disabled button itself to explain the missing requirement (e.g., changing 'Save' to 'Enter password'). This provides immediate, actionable feedback without relying on hover states.
