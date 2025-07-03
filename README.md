# Android Backup & Restore Tool

A simple yet powerful desktop application for Windows that allows users to back up and restore data from their Android devices using the Android Debug Bridge (ADB). It features a clean, tabbed interface to separate backup and restore functions, making the process intuitive and safe.

> ## ⚠️ Disclaimer
>
> This software is provided 'as is' without warranty of any kind. The author is **NOT responsible for any data loss** that may occur from using this tool. It is the user's sole responsibility to verify that all data has been successfully backed up before performing any factory reset or data wipe on their device. By using this application, you acknowledge and accept these terms.

---
## Features

* **Tabbed Interface**: A clean, two-tab layout separates Backup and Restore functions for a simpler workflow.
* **Device Detection**: Automatically detects connected Android devices and their model.
* **Selective Folder Backup**: Scan your device's storage, see the size of each major folder, and choose exactly which folders you want to back up.
* **Comprehensive Restore**: Restore both individual folders and full app backups from the dedicated "Restore" tab.
* **Intelligent Folder Naming**: Backups are automatically named with the date, time, your device's model, and the backup type (`Files` or `Apps`).
* **Real-Time Progress**: The progress bar now updates smoothly during large file transfers, giving you a live view of the download status.
* **Flexible Backup Location**: Choose where you want to save your backups on your computer.
* **Bulk Selection**: A "Select All / Deselect All" checkbox for one-click folder selection.
* **Built-in Instructions**: A "How to Use" tab provides clear, step-by-step instructions right within the app.
* **First-Use Disclaimer**: Ensures users understand the importance of verifying backups before proceeding.

---
## How to Use (EXE Release)

1.  **Download the Release**
    Go to the Releases page of this project's repository and download the latest `Android_Backup_Tool.zip` file.

2.  **Prepare the Application**
    Unzip the downloaded file. This will give you a folder containing `backup_tool.exe` and any necessary ADB files.
    **Important:** Keep all files in the same folder.

3.  **Enable USB Debugging on Your Phone**
    * Open **Settings** on your Android device.
    * Scroll to the bottom and tap on **"About phone"**.
    * Find the **"Build number"** and tap on it 7 times in a row. You will see a message saying "You are now a developer!".
    * Go back to the main Settings screen.
    * Find and open the new **"Developer options"** menu.
    * Inside Developer options, find and turn **ON** the switch for **"USB debugging"**.

4.  **Run the Backup Tool**
    * Double-click `backup_tool.exe` to run the application. On first launch, you must agree to the disclaimer.
    * Connect your phone to your computer with a USB cable.
    * A pop-up will appear on your phone asking to "Allow USB debugging?". Check the box that says **"Always allow from this computer"** and tap **"Allow"**.
    * In the app's **"Device & Backup"** tab, click the **"Refresh Connection"** button. The status should turn green and show your device model.
    * Follow the on-screen instructions to scan, select, and back up your data.

5.  **Restoring Data**
    * To restore your data, click on the **"Restore"** tab.
    * Choose either **"Restore from Folder Backup"** or **"Restore from App Backup"** and select the appropriate backup file or folder.

---
## For Developers: Running from Source

If you want to run or modify the source code, follow these instructions.

#### Prerequisites

* **Python 3.x**: Download and install from python.org. **Important:** During installation, check the box that says "Add Python to PATH".
* **Android SDK Platform-Tools**: This contains `adb.exe`. Download the tools from the official Android developer website and place `adb.exe` (and its DLLs, if any) in the project folder.

#### Prepare and Run the Application
1.  Save the application's Python script (`backup_tool.pyw`) inside your project folder.
2.  Ensure `adb.exe` is in the same folder.
3.  Open a Command Prompt or PowerShell and install the required Python libraries:
    ```bash
    pip install customtkinter
    ```
4.  Run the application from the command line:
    ```bash
    python backup_tool.pyw
    ```
---
## How to Package into an EXE

You can package this application into a single `.exe` file using **PyInstaller**.

1.  **Install PyInstaller**:
    ```bash
    pip install pyinstaller
    ```
2.  **Run the Packaging Command**:
    Open a Command Prompt or PowerShell, navigate to your project folder, and run the command below. To force the app to request admin privileges, you will first need to create the `admin.manifest` file mentioned in previous instructions.

    ```bash
    pyinstaller --onefile --windowed --add-data "adb.exe;." --manifest "admin.manifest" --icon="your_icon.ico" backup_tool.pyw
    ```
3.  **Find Your EXE**: The final `backup_tool.exe` will be located in the `dist` folder.
