# Android Backup & Restore Tool
A simple yet powerful desktop application for Windows that allows users to back up and restore data from their Android devices using the Android Debug Bridge (ADB). This tool is provided as a standalone .exe file, so no installation of Python is required to use it.

# Features
User-Friendly GUI: A clean and modern interface makes the backup process easy for all users.

Device Detection: Automatically detects connected Android devices and their authorization status.

Selective Folder Backup: Scan your device's storage, see the size of each major folder, and choose exactly which folders you want to back up.

Full Application Backup: A one-click solution to back up your installed applications and their data (for apps that allow it).

Timestamped Backups: Each backup is saved in a neatly organized, timestamped folder to prevent overwrites and keep your backups organized.

Progress and Time Estimation: A progress bar and an estimated time remaining give you a clear idea of how long backups will take.

Built-in Instructions: A "How to Use" tab provides clear, step-by-step instructions right within the app.

# How to Use (EXE Release)
1. Download the Release
Go to the Releases page of this project's repository and download the latest Android_Backup_Tool.zip file.

2. Prepare the Application
Unzip the downloaded file. This will give you a folder containing android_backup_app.exe and the necessary ADB files.

Important: Keep all files (.exe and the Adb...dll files) in the same folder.

3. Enable USB Debugging on Your Phone
This is the most important step. The tool cannot see your phone without it.

Open Settings on your Android device.

Scroll to the bottom and tap on "About phone".

Find the "Build number" and tap on it 7 times in a row. You will see a message saying "You are now a developer!".

Go back to the main Settings screen.

Find and open the new "Developer options" menu (it might be under a "System" or "Advanced" submenu).

Inside Developer options, find and turn ON the switch for "USB debugging".

4. Run the Backup
Double-click android_backup_app.exe to run the application.

Connect your phone to your computer with a USB cable.

A pop-up will appear on your phone asking to "Allow USB debugging?". Check the box that says "Always allow from this computer" and tap "Allow".

Click the "Refresh Connection" button in the app. The status should turn green and show "Connected".

Follow the instructions in the app to scan, select, and back up your data.

All backups will be saved in a new, timestamped folder inside Documents\AndroidBackup.

For Developers: Running from Source
If you want to run or modify the source code, follow these instructions.

# Prerequisites
Python 3.x: If you don't have it, download and install Python from python.org. Important: During installation, make sure to check the box that says "Add Python to PATH".

Android SDK Platform-Tools: This contains the Android Debug Bridge (adb.exe).

Download the "SDK Platform-Tools for Windows" from the official Android developer website.

Unzip the downloaded file.

Prepare and Run the Application
Create a new folder for the application (e.g., C:\AndroidBackupTool).

Save the application's Python script (android_backup_app.pyw) inside this folder.

From the unzipped "platform-tools" folder, copy the following three files into your new application folder:

adb.exe

AdbWinApi.dll

AdbWinUsbApi.dll

Open a Command Prompt or PowerShell and install the required Python library:

pip install customtkinter

Double-click the android_backup_app.pyw file to run the application.

# How to Package into an EXE
You can package this application into a single .exe file using PyInstaller.

Install PyInstaller:

pip install pyinstaller

Run the Packaging Command: Open a Command Prompt or PowerShell, navigate to your project folder, and run:

python -m PyInstaller --onefile --windowed --add-data "adb.exe;." --add-data "AdbWinApi.dll;." --add-data "AdbWinUsbApi.dll;." android_backup_app.pyw

Find Your EXE: The final android_backup_app.exe will be located in the dist folder.
