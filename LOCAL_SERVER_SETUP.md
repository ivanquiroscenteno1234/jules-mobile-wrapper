# Local Server Setup Guide (Permanent Service)

This guide explains how to set up the Mobile Jules server to run automatically in the background on your laptop, starting automatically when you turn on your computer. This ensures the server is always available for your phone to connect to.

## Windows

The best way to run a Python script as a service on Windows is using **Task Scheduler**.

### Step 1: Configure the Startup Script

 1.  Open Command Prompt / Terminal.
 2.  Navigate to the `mobile_jules/server` folder.
 3.  Install dependencies:
     ```bash
     pip install -r requirements.txt
     ```
 4.  (Optional) If you have an Ngrok account, run: `ngrok config add-authtoken YOUR_TOKEN`. This prevents the tunnel from expiring quickly.

### Step 2: Configure the Startup Script

1.  Navigate to the `mobile_jules/server` folder.
2.  Find the file **`start_server.bat`**.
3.  Right-click it and select **Edit** (using Notepad or any text editor).
4.  Update the lines under `:: CONFIGURATION SECTION`:
    *   `set JULES_API_KEY=...`: Paste your actual key.
    *   `cd /d ...`: Paste the full path to the `mobile_jules/server` folder on your computer.
5.  Save the file.
6.  **Test it** by double-clicking it to make sure the server starts.

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

### Step 1: Configure the Property List (.plist) file

1.  Navigate to `mobile_jules/server` and find **`com.jules.mobileserver.plist`**.
2.  Open it with a text editor.
3.  Edit the values inside `<string>...</string>` tags:
    *   **WorkingDirectory**: Set the full path to `mobile_jules/server`.
    *   **JULES_API_KEY**: Set your actual key.
    *   **ProgramArguments** (Optional): If you installed Python via Homebrew/Conda, update `/usr/bin/python3` to your specific python path (run `which python3` in terminal to find it).
4.  Copy the file to your LaunchAgents folder:
    ```bash
    cp mobile_jules/server/com.jules.mobileserver.plist ~/Library/LaunchAgents/
    ```

### Step 2: Load the Service

Run this command in Terminal:

```bash
launchctl load ~/Library/LaunchAgents/com.jules.mobileserver.plist
```

The server will now start automatically when you log in.

---

## Linux

On Linux, we use `systemd`.

### Step 1: Configure the Service File

1.  Navigate to `mobile_jules/server` and find **`jules-server.service`**.
2.  Open it with a text editor.
3.  Edit the `CONFIGURATION SECTION`:
    *   **User**: Set to your Linux username.
    *   **WorkingDirectory**: Set the full path to `mobile_jules/server`.
    *   **JULES_API_KEY**: Set your actual key.
4.  Copy it to the system folder:
    ```bash
    sudo cp mobile_jules/server/jules-server.service /etc/systemd/system/
    ```

### Step 2: Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable jules-server
sudo systemctl start jules-server
```

Check status with `sudo systemctl status jules-server`.
