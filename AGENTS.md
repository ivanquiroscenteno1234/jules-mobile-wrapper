# Instructions for Jules (AI Agent)

## Project Structure
- This is a **Flutter monorepo**.
- The mobile app source code is located in: `mobile_jules/client/`
- We use a custom CI/CD process that creates a `temp_build` directory for APK generation.

## Build & Environment
- **Java Version:** Java 11 (configured in `android/app/build.gradle.kts`)
  - Note: CI workflow uses Zulu 17 for compatibility, but the app itself targets Java 11
- **Flutter Channel:** Stable
- **Install Command:** Run `flutter pub get` inside the `mobile_jules/client/` directory
- **Build Command:** `flutter build apk --release` (executed from `temp_build` path in CI)
- **Build Failure Focus Areas:** If the build fails, investigate:
  - `/mobile_jules/client/pubspec.yaml` (dependency conflicts)
  - `/mobile_jules/client/android/app/build.gradle.kts` (Gradle/Java compatibility)

## Coding Standards & Preferences
- Follow official Flutter/Dart linting rules
- Maintain existing architecture patterns in the `lib/` folder
- Use **Core Library Desugaring** for Android compatibility (already enabled in build.gradle.kts)
- If a build error mentions "Core Library Desugaring," check `android/app/build.gradle.kts`
- Ensure all Google Drive integration scripts remain intact in `/scripts/`

## Task Execution Guidelines
- **Critical:** Apply fixes to source files in `mobile_jules/client/`, NOT just the `temp_build` folder
- Always run `flutter pub get` locally to verify dependency resolutions before proposing a PR
- When creating a PR, reference the specific build failure or issue that triggered your investigation
