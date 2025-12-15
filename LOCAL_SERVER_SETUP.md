# Local Server Setup Guide (Permanent Service)

This guide explains how to set up the Mobile Jules server to run automatically in the background on your laptop, starting automatically when you turn on your computer. This ensures the server is always available for your phone to connect to.

## Windows

The best way to run a Python script as a service on Windows is using **Task Scheduler**.

### Step 1: Create a Startup Script

1.  Navigate to the `mobile_jules/server` folder.
2.  Create a new file named `start_server.bat`.
3.  Edit it with Notepad and paste the following (adjust paths to match your actual setup):

    ```batch
    @echo off
    :: Navigate to the directory
    cd /d "C:\Users\YOUR_USERNAME\path\to\jules-mobile-wrapper\mobile_jules\server"

    :: Set the API Key (Replace with your actual key)
    set GOOGLE_API_KEY=your_actual_jules_api_key

    :: Add parent directory to PYTHONPATH
    set PYTHONPATH=%PYTHONPATH%;..

    :: Run the server
    :: If you use a virtual environment, point to the python.exe in venv\Scripts\python.exe
    python -m uvicorn main:app --host 0.0.0.0 --port 8000
    ```
4.  Save the file. **Test it** by double-clicking it to make sure the server starts.

### Step 2: Schedule the Task

1.  Press `Win + R`, type `taskschd.msc`, and press Enter.
2.  In the right pane, click **"Create Basic Task..."**.
3.  **Name**: "Mobile Jules Server". Click Next.
4.  **Trigger**: Select **"When the computer starts"** (or "When I log on" if you prefer). Click Next.
5.  **Action**: Select **"Start a program"**. Click Next.
6.  **Program/script**: Browse and select the `start_server.bat` file you created.
    *   **Start in**: Copy the folder path where the bat file is (e.g., `C:\Users\YOUR_USERNAME\path\to\jules-mobile-wrapper\mobile_jules\server`). **This is important.**
7.  Click **Next**, then **Finish**.

Now the server will start automatically!

---

## macOS

On macOS, we use `launchd` to create a background service.

### Step 1: Create a Property List (.plist) file

1.  Open a text editor.
2.  Paste the following content, modifying the paths:

    ```xml
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>Label</key>
        <string>com.jules.mobileserver</string>
        <key>ProgramArguments</key>
        <array>
            <string>/usr/bin/python3</string> <!-- Path to your python executable -->
            <string>-m</string>
            <string>uvicorn</string>
            <string>main:app</string>
            <string>--host</string>
            <string>0.0.0.0</string>
            <string>--port</string>
            <string>8000</string>
        </array>
        <key>WorkingDirectory</key>
        <string>/Users/YOUR_USERNAME/path/to/jules-mobile-wrapper/mobile_jules/server</string>
        <key>EnvironmentVariables</key>
        <dict>
            <key>GOOGLE_API_KEY</key>
            <string>your_actual_jules_api_key</string>
            <key>PYTHONPATH</key>
            <string>..</string>
        </dict>
        <key>RunAtLoad</key>
        <true/>
        <key>KeepAlive</key>
        <true/>
        <key>StandardOutPath</key>
        <string>/tmp/jules_server.out</string>
        <key>StandardErrorPath</key>
        <string>/tmp/jules_server.err</string>
    </dict>
    </plist>
    ```

3.  Save the file as `com.jules.mobileserver.plist` in `~/Library/LaunchAgents/`.
    *   You can do this via terminal: `mv com.jules.mobileserver.plist ~/Library/LaunchAgents/`

### Step 2: Load the Service

Run this command in Terminal:

```bash
launchctl load ~/Library/LaunchAgents/com.jules.mobileserver.plist
```

The server will now start automatically when you log in.

---

## Linux

On Linux, we use `systemd`.

### Step 1: Create a Service File

1.  Create a file named `jules-server.service`:

    ```ini
    [Unit]
    Description=Mobile Jules Server
    After=network.target

    [Service]
    User=YOUR_USERNAME
    WorkingDirectory=/home/YOUR_USERNAME/path/to/jules-mobile-wrapper/mobile_jules/server
    Environment="GOOGLE_API_KEY=your_actual_jules_api_key"
    Environment="PYTHONPATH=.."
    ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```

2.  Move it to the system folder (requires sudo):
    ```bash
    sudo mv jules-server.service /etc/systemd/system/
    ```

### Step 2: Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable jules-server
sudo systemctl start jules-server
```

Check status with `sudo systemctl status jules-server`.
