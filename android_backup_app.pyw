import tkinter
from tkinter import filedialog
import customtkinter
import subprocess
import os
import threading
import queue
import sys
import re
import time
import configparser

# --- Configuration ---
if getattr(sys, 'frozen', False):
    script_dir = sys._MEIPASS
else:
    script_dir = os.path.dirname(os.path.abspath(__file__))

ADB_PATH = os.path.join(script_dir, "adb.exe")
DEFAULT_BACKUP_DIR = os.path.join(os.path.expanduser("~"), "Documents", "AndroidBackup")
CONFIG_FILE = os.path.join(script_dir, "config.ini")
ASSUMED_MB_PER_SECOND = 15


def check_disclaimer_status():
    """Checks if the disclaimer has been accepted previously."""
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        if 'User' in config and config.getboolean('User', 'DisclaimerAccepted', fallback=False):
            return True
    return False

def save_disclaimer_status():
    """Saves the accepted status of the disclaimer."""
    config = configparser.ConfigParser()
    config['User'] = {'DisclaimerAccepted': 'yes'}
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)

def format_bytes(size):
    """Converts bytes to a human-readable format (KB, MB, GB)."""
    if size is None:
        return "0 B"
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power and n < len(power_labels):
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def format_seconds(seconds):
    """Converts seconds into a human-readable string (minutes, seconds)."""
    if seconds < 60:
        return f"less than a minute"
    minutes = int(seconds / 60)
    if minutes == 1:
        return f"about 1 minute"
    return f"about {minutes} minutes"

class DisclaimerWindow(customtkinter.CTkToplevel):
    """A modal pop-up window for the disclaimer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geometry("500x300")
        self.title("Disclaimer")
        self.lift()
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.grab_set() 
        self.accepted = False

        disclaimer_text = (
            "This software is provided 'as is' without warranty of any kind.\n\n"
            "The author is NOT responsible for any data loss that may occur from using this tool. "
            "It is the user's sole responsibility to verify that all data has been successfully "
            "backed up before performing any factory reset or data wipe on their device.\n\n"
            "By clicking 'I Agree', you acknowledge and accept these terms."
        )

        label = customtkinter.CTkLabel(self, text=disclaimer_text, wraplength=450, justify="left")
        label.pack(padx=20, pady=20, expand=True, fill="both")
        
        button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=10)

        agree_button = customtkinter.CTkButton(button_frame, text="I Agree", command=self.on_agree)
        agree_button.pack(side="left", padx=10)

        disagree_button = customtkinter.CTkButton(button_frame, text="Disagree & Exit", command=self.on_closing, fg_color="#D32F2F", hover_color="#C62828")
        disagree_button.pack(side="left", padx=10)
    
    def on_agree(self):
        self.accepted = True
        self.grab_release()
        self.destroy()

    def on_closing(self):
        self.accepted = False
        self.grab_release()
        self.destroy()

    def get_status(self):
        self.master.wait_window(self)
        return self.accepted

# --- Main Application Class ---
class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        if not check_disclaimer_status():
            self.withdraw()
            disclaimer = DisclaimerWindow(self)
            if disclaimer.get_status():
                save_disclaimer_status()
                self.deiconify()
            else:
                self.quit()
                sys.exit()
        
        # --- Window Setup ---
        self.title("Android Backup & Restore Tool")
        self.geometry("950x850") 
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- App State Variables ---
        self.device_id = None
        self.device_model = "UnknownDevice"
        self.is_operation_running = False
        self.folder_stats = {}
        self.folder_checkboxes = {}
        self.backup_dir = DEFAULT_BACKUP_DIR
        self.last_backup_path = None
        self.select_all_var = tkinter.IntVar(value=0)
        
        # --- Queues for thread communication ---
        self.log_queue = queue.Queue()
        self.scan_results_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        self.ui_queue = queue.Queue()

        # --- UI Elements ---
        self.create_widgets()
        
        # --- Initial Device Check ---
        self.log_message("Welcome! Checking for connected devices...")
        self.log_message(f"Default backup location: {self.backup_dir}")
        self.check_device_thread()
        
        # --- Start the queue checkers ---
        self.after(100, self.process_log_queue)
        self.after(100, self.process_scan_results_queue)
        self.after(100, self.process_progress_queue)
        self.after(100, self.process_ui_queue)

    def create_widgets(self):
        """Creates and arranges all the UI elements in the window."""
        
        self.tab_view = customtkinter.CTkTabview(self, corner_radius=10)
        self.tab_view.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.tab_view.add("Device & Backup")
        self.tab_view.add("Restore")
        self.tab_view.add("How to Use")

        self.create_backup_tab()
        self.create_restore_tab()
        self.create_instructions_tab()
    
    def create_backup_tab(self):
        """Creates the content for the main 'Device & Backup' tab."""
        backup_tab = self.tab_view.tab("Device & Backup")
        backup_tab.grid_columnconfigure(0, weight=1)
        backup_tab.grid_rowconfigure(2, weight=2) 
        backup_tab.grid_rowconfigure(5, weight=1)

        top_frame = customtkinter.CTkFrame(backup_tab)
        top_frame.grid(row=0, column=0, padx=0, pady=10, sticky="ew")
        top_frame.grid_columnconfigure((0, 1), weight=1)

        connection_frame = customtkinter.CTkFrame(top_frame, fg_color="transparent")
        connection_frame.grid(row=0, column=0, padx=10, pady=0, sticky="w")
        
        self.status_label = customtkinter.CTkLabel(connection_frame, text="Status: No Device", font=customtkinter.CTkFont(size=14, weight="bold"))
        self.status_label.pack(side="top", anchor="w", pady=(5,10))
        self.refresh_button = customtkinter.CTkButton(connection_frame, text="Refresh Connection", command=self.check_device_thread)
        self.refresh_button.pack(side="left", anchor="w", padx=(0,5))
        self.scan_button = customtkinter.CTkButton(connection_frame, text="Scan Device Folders", command=lambda: self.start_operation(self.scan_device_for_files))
        self.scan_button.pack(side="left", anchor="w")
        
        backup_actions_frame = customtkinter.CTkFrame(top_frame, fg_color="transparent")
        backup_actions_frame.grid(row=0, column=1, padx=10, pady=0, sticky="se")
        self.backup_selected_button = customtkinter.CTkButton(backup_actions_frame, text="Backup Selected Folders", height=35, command=lambda: self.start_operation(self.backup_selected_folders))
        self.backup_selected_button.pack(side="left", padx=(0, 5))
        self.backup_apps_button = customtkinter.CTkButton(backup_actions_frame, text="Full App Backup", height=35, command=lambda: self.start_operation(self.backup_all_apps))
        self.backup_apps_button.pack(side="left", padx=(5, 0))
        
        selection_options_frame = customtkinter.CTkFrame(backup_tab, fg_color="transparent")
        selection_options_frame.grid(row=1, column=0, padx=0, pady=(5,0), sticky="ew")
        self.select_all_checkbox = customtkinter.CTkCheckBox(selection_options_frame, text="Select All / Deselect All", variable=self.select_all_var, onvalue=1, offvalue=0, command=self.toggle_all_folders)
        self.select_all_checkbox.pack(side="left", padx=5)
        self.change_dir_button = customtkinter.CTkButton(selection_options_frame, text="Change Backup Location...", command=self.change_backup_directory)
        self.change_dir_button.pack(side="right", padx=5)

        self.selection_frame = customtkinter.CTkScrollableFrame(backup_tab, label_text="Scan Results")
        self.selection_frame.grid(row=2, column=0, padx=0, pady=0, sticky="nsew")

        self.progress_frame = customtkinter.CTkFrame(backup_tab, fg_color="transparent")
        self.progress_frame.grid(row=3, column=0, padx=0, pady=5, sticky="ew")
        self.progress_frame.grid_columnconfigure(1, weight=1)
        self.progress_label = customtkinter.CTkLabel(self.progress_frame, text="Progress:")
        self.progress_bar = customtkinter.CTkProgressBar(self.progress_frame)
        self.time_label = customtkinter.CTkLabel(self.progress_frame, text="")
        
        log_actions_frame = customtkinter.CTkFrame(backup_tab, fg_color="transparent")
        log_actions_frame.grid(row=4, column=0, padx=0, pady=0, sticky="ew")
        self.clear_log_button = customtkinter.CTkButton(log_actions_frame, text="Clear Log", width=100, command=self.clear_log)
        self.clear_log_button.pack(side="left", padx=5)
        self.open_folder_button = customtkinter.CTkButton(log_actions_frame, text="Open Backup Folder", command=self.open_last_backup_folder)

        self.log_textbox = customtkinter.CTkTextbox(backup_tab, state="disabled", corner_radius=10, font=("Consolas", 12))
        self.log_textbox.grid(row=5, column=0, padx=0, pady=(5, 0), sticky="nsew")

    def create_restore_tab(self):
        """Creates the content for the 'Restore' tab."""
        restore_tab = self.tab_view.tab("Restore")
        restore_tab.grid_columnconfigure(0, weight=1)
        
        restore_main_frame = customtkinter.CTkFrame(restore_tab)
        restore_main_frame.pack(padx=20, pady=20, fill="x")

        restore_folders_label = customtkinter.CTkLabel(restore_main_frame, text="Restore Files & Folders", font=customtkinter.CTkFont(size=16, weight="bold"))
        restore_folders_label.pack(pady=(5,5))
        restore_folders_desc = customtkinter.CTkLabel(restore_main_frame, text="This will push backed up folders (like DCIM, Documents, etc.) back to your device.\nSelect the timestamped folder (e.g., '..._Files') that you want to restore from.", justify="left")
        restore_folders_desc.pack(pady=(0,10), padx=10)
        self.restore_folders_button = customtkinter.CTkButton(restore_main_frame, text="Restore from Folder Backup", height=40, command=self.handle_restore_folders_click)
        self.restore_folders_button.pack(pady=(0,20))

        restore_apps_label = customtkinter.CTkLabel(restore_main_frame, text="Restore Applications", font=customtkinter.CTkFont(size=16, weight="bold"))
        restore_apps_label.pack(pady=(10,5))
        restore_apps_desc = customtkinter.CTkLabel(restore_main_frame, text="This will restore all apps and their data from a full app backup.\nSelect the 'full_backup.ab' file from within a '..._Apps' backup folder.", justify="left")
        restore_apps_desc.pack(pady=(0,10), padx=10)
        self.restore_apps_button = customtkinter.CTkButton(restore_main_frame, text="Restore from App Backup (.ab)", height=40, command=self.handle_restore_app_backup_click)
        self.restore_apps_button.pack(pady=(0,20))

    def create_instructions_tab(self):
        """Creates the content for the 'How to Use' tab."""
        instructions_tab = self.tab_view.tab("How to Use")
        instructions_tab.grid_columnconfigure(0, weight=1)
        instructions_tab.grid_rowconfigure(0, weight=1)

        instructions_frame = customtkinter.CTkScrollableFrame(instructions_tab)
        instructions_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        instructions_frame.grid_columnconfigure(0, weight=1)

        def create_text_block(parent, text, font_size=14, is_bold=False, wrap=True):
            font_weight = "bold" if is_bold else "normal"
            label = customtkinter.CTkLabel(parent, text=text, font=customtkinter.CTkFont(size=font_size, weight=font_weight), justify="left", anchor="w")
            if wrap:
                label.bind('<Configure>', lambda e: label.configure(wraplength=label.winfo_width() - 20))
            return label

        welcome_label = create_text_block(instructions_frame, "Welcome to the Android Backup Tool!", 18, True, False)
        welcome_label.pack(anchor="w", padx=10, pady=(10, 5))

        step1_title = create_text_block(instructions_frame, "Step 1: Enable USB Debugging", 16, True, False)
        step1_title.pack(anchor="w", padx=10, pady=(10, 5))
        step1_instructions = [
            "1. On your phone, go to Settings -> About phone and tap 'Build number' 7 times.",
            "2. Go back to Settings, find 'Developer options', and enable 'USB debugging'."
        ]
        for instruction in step1_instructions: create_text_block(instructions_frame, instruction).pack(anchor="w", fill="x", padx=20, pady=2)

        step2_title = create_text_block(instructions_frame, "Step 2: Connect and Scan", 16, True, False)
        step2_title.pack(anchor="w", padx=10, pady=(20, 5))
        step2_instructions = [
            "1. Connect your phone via USB. A pop-up asking to 'Allow USB debugging?' will appear.",
            "2. Check 'Always allow' and tap 'Allow'.",
            "3. In the app's 'Device & Backup' tab, click 'Refresh Connection'. The status should turn green.",
            "4. Click 'Scan Device Folders' to see a list of your phone's main folders."
        ]
        for instruction in step2_instructions: create_text_block(instructions_frame, instruction).pack(anchor="w", fill="x", padx=20, pady=2)
            
        step3_title = create_text_block(instructions_frame, "Step 3: Backing Up Data", 16, True, False)
        step3_title.pack(anchor="w", padx=10, pady=(20, 5))
        step3_instructions = [
            "1. File Backup: Select the folders you want to save and click 'Backup Selected Folders'.",
            "2. App Backup: Click 'Full App Backup' for app data and settings (phone approval required)."
        ]
        for instruction in step3_instructions: create_text_block(instructions_frame, instruction).pack(anchor="w", fill="x", padx=20, pady=2)

        step4_title = create_text_block(instructions_frame, "Step 4: Restoring Data", 16, True, False)
        step4_title.pack(anchor="w", padx=10, pady=(20, 5))
        step4_instructions = [
            "1. Navigate to the 'Restore' tab.",
            "2. To restore folders, click 'Restore from Folder Backup' and choose a folder like '..._Files'.",
            "3. To restore apps, click 'Restore from App Backup' and choose a 'full_backup.ab' file.",
            "4. You must approve the restore operation on your phone's screen."
        ]
        for instruction in step4_instructions: create_text_block(instructions_frame, instruction).pack(anchor="w", fill="x", padx=20, pady=2)

    def process_log_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                if isinstance(message, tuple) and message[0] == 'status':
                    _, text, color = message
                    self.status_label.configure(text=text, text_color=color)
                else:
                    self.log_textbox.configure(state="normal")
                    self.log_textbox.insert("end", str(message) + "\n")
                    self.log_textbox.configure(state="disabled")
                    self.log_textbox.see("end")
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_log_queue)

    def process_scan_results_queue(self):
        try:
            self.folder_stats = self.scan_results_queue.get_nowait()
            for widget in self.selection_frame.winfo_children(): widget.destroy()
            self.folder_checkboxes.clear()
            self.select_all_var.set(0)
            
            if not self.folder_stats: return

            sorted_results = sorted(self.folder_stats.items(), key=lambda item: item[1]['size'], reverse=True)

            for i, (folder, data) in enumerate(sorted_results):
                label_text = f"{folder:<25} | Files: {data['count']:<8} | Size: {format_bytes(data['size'])}"
                checkbox = customtkinter.CTkCheckBox(self.selection_frame, text=label_text, font=("Consolas", 12))
                checkbox.grid(row=i, column=0, sticky="ew", padx=5, pady=2)
                self.folder_checkboxes[folder] = checkbox
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_scan_results_queue)

    def process_progress_queue(self):
        try:
            while True:
                message = self.progress_queue.get_nowait()
                if isinstance(message, str):
                    if message.startswith("Time:"):
                        self.time_label.configure(text=message)
                    elif message == "start_determinate":
                        self.progress_label.grid(row=0, column=0, padx=5, sticky="w")
                        self.progress_bar.grid(row=0, column=1, padx=5, sticky="ew")
                        self.time_label.grid(row=0, column=2, padx=10, sticky="e")
                        self.progress_bar.configure(mode="determinate")
                        self.progress_bar.set(0)
                    elif message == "start_indeterminate":
                        self.progress_label.grid(row=0, column=0, padx=5, sticky="w")
                        self.progress_bar.grid(row=0, column=1, columnspan=2, padx=5, sticky="ew")
                        self.time_label.grid_remove()
                        self.progress_bar.configure(mode="indeterminate")
                        self.progress_bar.start()
                    elif message == "stop":
                        self.progress_bar.stop()
                        self.progress_label.grid_remove()
                        self.progress_bar.grid_remove()
                        self.time_label.grid_remove()
                    else:
                        self.progress_label.configure(text=message)
                elif isinstance(message, float):
                    self.progress_bar.set(message)
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_progress_queue)
            
    def process_ui_queue(self):
        try:
            while True:
                message = self.ui_queue.get_nowait()
                if message == 'enable':
                    self.set_ui_state(True)
                elif message == 'disable':
                    self.set_ui_state(False)
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_ui_queue)

    def log_message(self, message):
        self.log_queue.put(message)

    def set_ui_state(self, enabled):
        state = "normal" if enabled else "disabled"
        self.refresh_button.configure(state=state)
        self.scan_button.configure(state=state)
        self.backup_selected_button.configure(state=state)
        self.backup_apps_button.configure(state=state)
        self.restore_apps_button.configure(state=state)
        self.restore_folders_button.configure(state=state)
        self.change_dir_button.configure(state=state)
        self.is_operation_running = not enabled

    def start_operation(self, target_function, args=()):
        if self.is_operation_running:
            self.log_message("Error: An operation is already in progress.")
            return
        if not self.device_id and target_function not in [self.check_device, self.change_backup_directory]:
            self.log_message("Error: No device connected. Please refresh.")
            return
        self.ui_queue.put('disable')
        self.open_folder_button.pack_forget()
        thread = threading.Thread(target=target_function, args=args)
        thread.daemon = True
        thread.start()

    def check_device_thread(self):
        if self.is_operation_running: return
        self.start_operation(self.check_device)

    def get_device_model(self):
        """Gets the model name of the connected device."""
        if not self.device_id:
            return "UnknownDevice"
        model = self.run_adb_command([ADB_PATH, "shell", "getprop", "ro.product.model"], return_output=True)
        if model:
            sanitized_model = model.strip().replace(' ', '-')
            sanitized_model = re.sub(r'[^a-zA-Z0-9_-]', '', sanitized_model)
            return sanitized_model
        return "UnknownDevice"

    def check_device(self):
        try:
            if not os.path.exists(ADB_PATH):
                self.log_queue.put(('status', "Status: ADB not found!", "red"))
                return
            result = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1 and "device" in lines[1]:
                self.device_id = lines[1].split()[0]
                self.device_model = self.get_device_model()
                self.log_queue.put(('status', f"Status: Connected ({self.device_model})", "green"))
                self.log_message(f"Success: Device '{self.device_model}' connected.")
            else:
                self.device_id = None
                self.device_model = "UnknownDevice"
                self.log_queue.put(('status', "Status: No Device", "orange"))
                self.log_message("No authorized device found. Please enable USB Debugging.")
        except Exception as e:
            self.device_id = None
            self.device_model = "UnknownDevice"
            self.log_queue.put(('status', "Status: Error", "red"))
            self.log_message(f"An error occurred during device check: {e}")
        finally:
            self.ui_queue.put('enable')

    def run_adb_command(self, command_list, return_output=False):
        try:
            process = subprocess.Popen(command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            stdout_output, stderr_output = process.communicate()
            
            if "no devices/emulators found" in stderr_output:
                self.log_message("CRITICAL: Device disconnected.")
                self.log_queue.put(('status', "Status: Disconnected", "red"))
                self.device_id = None
                return None if return_output else False
            
            # Log non-error info from stderr (like pull/push progress)
            if stderr_output:
                for line in stderr_output.strip().split('\n'):
                     # Only log actual errors as ADB_ERROR
                    if "adb: error:" in line.lower():
                        self.log_message(f"ADB_ERROR: {line}")
                    else: # Log progress info differently
                        self.log_message(f"ADB_INFO: {line}")

            if return_output:
                return stdout_output if process.returncode == 0 else None
            else:
                if stdout_output: self.log_message(f"ADB: {stdout_output.strip()}")
                return process.returncode == 0
        except Exception as e:
            self.log_message(f"An unexpected error occurred while running ADB: {e}")
            return None if return_output else False

    def scan_device_for_files(self):
        try:
            self.log_message("--- Starting Device Scan ---")
            self.progress_queue.put("start_indeterminate")
            self.progress_queue.put("Scanning device... this may take a while.")
            self.scan_results_queue.put({}) 
            command = [ADB_PATH, "shell", "ls", "-lR", "/sdcard/"]
            output = self.run_adb_command(command, return_output=True)
            if output is not None:
                self.log_message("Scan complete. Parsing results...")
                parsed_stats = self.parse_ls_output(output)
                self.scan_results_queue.put(parsed_stats)
                self.log_message("--- Scan Analysis Finished ---")
            else:
                self.log_message("--- Scan Failed: No data received from device. ---")
        except Exception as e:
            self.log_message(f"An error occurred during scan: {e}")
        finally:
            self.progress_queue.put("stop")
            self.ui_queue.put('enable')

    def parse_ls_output(self, output):
        stats = {}
        current_dir = ""
        file_regex = re.compile(r"^-.*?\s+\d+\s+\w+\s+\w+\s+(\d+)\s+[\d-]+\s+[\d:]+\s+(.+?)\r?$")
        for line in output.splitlines():
            line = line.strip()
            if not line: continue
            if line.startswith('/sdcard/') and line.endswith(':'):
                current_dir = line[:-1]
                continue
            match = file_regex.match(line)
            if match and current_dir:
                try:
                    size = int(match.group(1))
                    relative_path = os.path.relpath(current_dir, "/sdcard")
                    top_folder = relative_path.split(os.path.sep)[0]
                    if top_folder == ".": top_folder = "Internal Storage (Root)"
                    if top_folder not in stats:
                        stats[top_folder] = {'size': 0, 'count': 0}
                    stats[top_folder]['size'] += size
                    stats[top_folder]['count'] += 1
                except (ValueError, IndexError): pass
        return stats

    def get_folder_size(self, path):
        """Calculates the total size of a local folder."""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
        except FileNotFoundError:
            return 0
        return total_size

    def monitor_pull_progress(self, dest_path, initial_backed_up_size, total_backup_size, stop_event):
        """Monitors the size of the destination folder and updates the progress bar."""
        while not stop_event.is_set():
            time.sleep(0.5)
            if not os.path.exists(dest_path):
                continue
            
            current_local_size = self.get_folder_size(dest_path)
            progress = (initial_backed_up_size + current_local_size) / total_backup_size
            self.progress_queue.put(min(progress, 1.0))

    def get_long_path_prefix(self, path):
        """Returns a path with the Windows long path prefix if on Windows."""
        if sys.platform == "win32":
            return "\\\\?\\" + os.path.abspath(path)
        return os.path.abspath(path)
        
    def backup_selected_folders(self):
        try:
            self.log_message("--- Starting Selected Folder Backup ---")
            selected_folders = [folder for folder, checkbox in self.folder_checkboxes.items() if checkbox.get() == 1]
            if not selected_folders:
                self.log_message("No folders selected. Nothing to back up.")
                return

            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            folder_name = f"{timestamp}_{self.device_model}_Files"
            self.last_backup_path = os.path.join(self.backup_dir, folder_name)
            self.log_message(f"Creating new backup in: {self.last_backup_path}")
            os.makedirs(self.get_long_path_prefix(self.last_backup_path), exist_ok=True)
            
            self.progress_queue.put("start_determinate")
            total_size = sum(self.folder_stats.get(f, {}).get('size', 0) for f in selected_folders)
            if total_size == 0:
                self.log_message("Selected folders are empty. Nothing to back up.")
                return

            backed_up_size = 0
            for folder in selected_folders:
                self.progress_queue.put(f"Backing up {folder}...")
                dest_path_raw = os.path.join(self.last_backup_path, folder)
                os.makedirs(self.get_long_path_prefix(dest_path_raw), exist_ok=True)
                
                stop_event = threading.Event()
                monitor_thread = threading.Thread(
                    target=self.monitor_pull_progress,
                    args=(dest_path_raw, backed_up_size, total_size, stop_event)
                )
                monitor_thread.start()

                source_path = f"/sdcard/{folder}" if folder != "Internal Storage (Root)" else "/sdcard/"
                success = self.run_adb_command([ADB_PATH, "pull", source_path, self.get_long_path_prefix(dest_path_raw)])
                
                stop_event.set()
                monitor_thread.join()

                if not success:
                    self.log_message("\nCRITICAL ERROR: Backup failed during transfer.")
                    return
                
                backed_up_size += self.folder_stats.get(folder, {}).get('size', 0)
                self.progress_queue.put(backed_up_size / total_size)

            self.progress_queue.put(1.0)
            self.log_message(f"--- Selected Folder Backup Finished ---")
            self.log_message(f"✅ Success! {format_bytes(total_size)} backed up.")
            self.open_folder_button.pack(side="left", padx=5)
        except Exception as e:
            self.log_message(f"An error occurred during folder backup: {e}")
        finally:
            self.progress_queue.put("stop")
            self.ui_queue.put('enable')

    def backup_all_apps(self):
        try:
            self.log_message("--- Starting Full App Backup ---")
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            folder_name = f"{timestamp}_{self.device_model}_Apps"
            self.last_backup_path = os.path.join(self.backup_dir, folder_name)
            self.log_message(f"Creating new app backup in: {self.last_backup_path}")
            os.makedirs(self.get_long_path_prefix(self.last_backup_path), exist_ok=True)

            self.progress_queue.put("start_indeterminate")
            self.progress_queue.put("Performing full app backup... Please check your phone to confirm.")
            backup_file = os.path.join(self.last_backup_path, "full_backup.ab")

            if self.run_adb_command([ADB_PATH, "backup", "-apk", "-shared", "-all", "-f", self.get_long_path_prefix(backup_file)]):
                self.log_message(f"--- Full backup process complete. File at '{backup_file}' ---")
                self.open_folder_button.pack(side="left", padx=5)
            else:
                 self.log_message(f"--- Full backup failed. Check ADB logs above. ---")
        except Exception as e:
            self.log_message(f"An error occurred during app backup: {e}")
        finally:
            self.progress_queue.put("stop")
            self.ui_queue.put('enable')

    def handle_restore_app_backup_click(self):
        if self.is_operation_running: return
        backup_file = filedialog.askopenfilename(title="Select Android Backup File (.ab)", initialdir=self.backup_dir, filetypes=(("Android Backup Files", "*.ab"), ("All files", "*.*")))
        if backup_file: self.start_operation(self.restore_app_backup, args=(backup_file,))

    def restore_app_backup(self, backup_file):
        try:
            self.log_message("--- Starting Full App Restore ---")
            self.progress_queue.put("start_indeterminate")
            self.progress_queue.put("Restoring... Please check your phone to confirm.")
            self.run_adb_command([ADB_PATH, "restore", self.get_long_path_prefix(backup_file)])
            self.log_message("--- Full Restore Command Sent. ---")
        except Exception as e:
            self.log_message(f"An error occurred during restore: {e}")
        finally:
            self.progress_queue.put("stop")
            self.ui_queue.put('enable')

    def handle_restore_folders_click(self):
        if self.is_operation_running: return
        self.log_message("Select the timestamped backup folder you want to restore from.")
        restore_path = filedialog.askdirectory(title="Select Backup Folder to Restore", initialdir=self.backup_dir)
        if restore_path: self.start_operation(self.restore_selected_folders, args=(restore_path,))

    def restore_selected_folders(self, restore_path):
        try:
            self.log_message(f"--- Starting Folder Restore from {os.path.basename(restore_path)} ---")
            folders_to_restore = [f for f in os.listdir(restore_path) if os.path.isdir(os.path.join(restore_path, f))]
            if not folders_to_restore:
                self.log_message("No folders found in the selected backup directory.")
                return

            self.progress_queue.put("start_indeterminate")
            for folder in folders_to_restore:
                self.progress_queue.put(f"Restoring {folder}...")
                source_path = os.path.join(restore_path, folder)
                dest_path = f"/sdcard/"
                if not self.run_adb_command([ADB_PATH, "push", self.get_long_path_prefix(source_path), dest_path]):
                    self.log_message(f"\nCRITICAL ERROR: Failed to restore {folder}.")
                    return
            
            self.log_message(f"--- Folder Restore Finished ---")
            self.log_message(f"✅ Success! Restored {len(folders_to_restore)} folder(s).")
        except Exception as e:
            self.log_message(f"An error occurred during folder restore: {e}")
        finally:
            self.progress_queue.put("stop")
            self.ui_queue.put('enable')

    def toggle_all_folders(self):
        """Selects or deselects all folder checkboxes."""
        if self.select_all_var.get() == 1:
            for checkbox in self.folder_checkboxes.values(): checkbox.select()
        else:
            for checkbox in self.folder_checkboxes.values(): checkbox.deselect()
    
    def change_backup_directory(self):
        """Opens a dialog to change the main backup directory."""
        if self.is_operation_running: return
        new_dir = filedialog.askdirectory(initialdir=self.backup_dir)
        if new_dir:
            self.backup_dir = new_dir
            self.log_message(f"Backup location changed to: {self.backup_dir}")

    def clear_log(self):
        """Clears the log textbox."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

    def open_last_backup_folder(self):
        """Opens the most recent backup folder in the file explorer."""
        if self.last_backup_path and os.path.exists(self.last_backup_path):
            os.startfile(self.last_backup_path)
        else:
            self.log_message("Error: Could not find the last backup folder.")

if __name__ == "__main__":
    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")
    
    if check_disclaimer_status():
        app = App()
        if app.winfo_exists():
            app.mainloop()
    else:
        root = customtkinter.CTk()
        root.withdraw()
        disclaimer = DisclaimerWindow(root)
        if disclaimer.get_status():
            save_disclaimer_status()
            root.destroy()
            app = App()
            if app.winfo_exists():
                app.mainloop()
        else:
            root.destroy()
            sys.exit()