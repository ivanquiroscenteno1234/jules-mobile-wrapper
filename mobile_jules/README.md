# Mobile Jules

This project allows you to "remote control" your coding environment from your mobile phone using the official **Jules API**.

## Architecture

*   **Server (Python)**: Runs on your laptop/desktop. It acts as a secure proxy between your phone and the Jules API (`jules.googleapis.com`).
*   **Client (Flutter)**: Runs on your Android phone. It connects to your Python server to list GitHub repos and chat with Jules.

## Prerequisites

1.  **Python 3.10+** installed on your computer.
2.  **Flutter SDK** installed (for building the app).
3.  A **Google/Jules API Key**. You can generate this in your [Jules Settings](https://jules.google.com/settings).

## Setup Instructions (Server)

1.  Navigate to the `server` directory:
    ```bash
    cd mobile_jules/server
    ```

2.  Install dependencies:
    ```bash
    pip install fastapi uvicorn websockets httpx pydantic
    ```

3.  **Configuration**:
    Set your API Key as an environment variable.

    **Windows (PowerShell):**
    ```powershell
    $env:GOOGLE_API_KEY="your_actual_jules_api_key"
    ```

    **Windows (CMD):**
    ```cmd
    set GOOGLE_API_KEY=your_actual_jules_api_key
    ```

4.  **Run the Server**:
    ```bash
    # Ensure the parent directory is in python path
    set PYTHONPATH=%PYTHONPATH%;..
    python -m uvicorn main:app --host 0.0.0.0 --port 8000
    ```

## Setup Instructions (Client App)

1.  **Create the Flutter Project**:
    Since I only provided the source files, you need to create the project skeleton first:
    ```bash
    flutter create mobile_jules_client
    ```

2.  **Copy Files**:
    Copy the contents of the `mobile_jules/client/lib` folder (provided by me) into your new `mobile_jules_client/lib` folder, overwriting `main.dart`.
    Also copy `mobile_jules/client/pubspec.yaml` to your project root.

3.  **Configure IP**:
    Open `lib/main.dart` and update `SERVER_URL` to your computer's local IP address (e.g., `http://192.168.1.5:8000`).

4.  **Run the App**:
    ```bash
    flutter run
    ```
